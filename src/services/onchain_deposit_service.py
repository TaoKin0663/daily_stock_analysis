# -*- coding: utf-8 -*-
"""On-chain ERC20 deposit verification and credit settlement."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, getcontext
import json
import logging
import os
import time
from typing import Any
from urllib import request as urlrequest
from urllib.error import URLError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.services.credit_service import CreditService
from src.storage import CreditTransaction, DatabaseManager, OnchainDeposit, User, UserConfig, UserCreditBalance

logger = logging.getLogger(__name__)

SEPOLIA_CHAIN_ID = 11155111
TOKEN_DECIMALS = 18
CONFIRMATION_TIMEOUT_SECONDS = 180
CONFIRMATION_POLL_SECONDS = 6
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


class DepositConfigError(ValueError):
    pass


class DepositVerificationError(ValueError):
    pass


def _normalize_address(value: str) -> str:
    value = value.strip().lower()
    if not value.startswith("0x") or len(value) != 42:
        raise DepositConfigError(f"Invalid address: {value}")
    int(value[2:], 16)
    return value


def _normalize_hash(value: str) -> str:
    value = value.strip().lower()
    if not value.startswith("0x") or len(value) != 66:
        raise DepositVerificationError("Invalid transaction hash")
    int(value[2:], 16)
    return value


def _address_topic(address: str) -> str:
    return "0x" + address[2:].rjust(64, "0")


def _hex_to_int(value: str | None) -> int:
    if not value or value == "0x":
        return 0
    return int(value, 16)


class OnchainDepositService:
    """Verify Sepolia ERC20 transfers and settle credits once."""

    def __init__(self) -> None:
        self.db = DatabaseManager.get_instance()
        self.credit_service = CreditService.get_instance()

    def _get_setting(self, key: str) -> str:
        key = key.upper()
        with self.db.get_session() as session:
            row = session.execute(
                select(UserConfig)
                .join(User, User.id == UserConfig.user_id)
                .where(User.is_admin == True, UserConfig.key == key)  # noqa: E712
                .order_by(UserConfig.updated_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None and row.value:
                return row.value.strip()
        return os.getenv(key, "").strip()

    def get_receiver_address(self) -> str:
        return _normalize_address(self._get_setting("DEPOSIT_RECEIVER_ADDRESS"))

    def get_token_address(self) -> str:
        return _normalize_address(self._get_setting("DEPOSIT_TOKEN_ADDRESS"))

    def get_rpc_url(self) -> str:
        rpc_url = self._get_setting("DEPOSIT_RPC_URL")
        if not rpc_url:
            raise DepositConfigError("DEPOSIT_RPC_URL is not configured")
        return rpc_url

    def get_public_config(self) -> dict[str, str]:
        return {
            "chain_id": str(SEPOLIA_CHAIN_ID),
            "receiver_address": self.get_receiver_address(),
            "token_address": self.get_token_address(),
        }

    def submit_deposit(self, user_id: int, wallet_address: str, tx_hash: str) -> dict[str, Any]:
        wallet = _normalize_address(wallet_address)
        tx = _normalize_hash(tx_hash)
        token_address = self.get_token_address()
        receiver_address = self.get_receiver_address()

        deposit = self._get_or_create_pending_deposit(
            user_id=user_id,
            wallet_address=wallet,
            tx_hash=tx,
            token_address=token_address,
            receiver_address=receiver_address,
        )
        if deposit.status == "succeeded":
            return self._response(deposit)

        receipt = self._rpc("eth_getTransactionReceipt", [tx])
        if receipt is None:
            return self._response(deposit)

        return self._settle_receipt(
            deposit_id=deposit.id,
            user_id=user_id,
            wallet_address=wallet,
            token_address=token_address,
            receiver_address=receiver_address,
            tx_hash=tx,
            receipt=receipt,
        )

    def wait_for_deposit(self, tx_hash: str) -> None:
        tx = _normalize_hash(tx_hash)
        deadline = time.monotonic() + CONFIRMATION_TIMEOUT_SECONDS

        while time.monotonic() <= deadline:
            with self.db.get_session() as session:
                deposit = session.execute(
                    select(OnchainDeposit).where(OnchainDeposit.tx_hash == tx)
                ).scalar_one_or_none()
                if deposit is None or deposit.status == "succeeded":
                    return
                user_id = deposit.user_id
                wallet_address = deposit.wallet_address
                token_address = deposit.token_address
                receiver_address = deposit.receiver_address

            receipt = self._rpc("eth_getTransactionReceipt", [tx])
            if receipt is not None:
                try:
                    self._settle_receipt(
                        deposit_id=deposit.id,
                        user_id=user_id,
                        wallet_address=wallet_address,
                        token_address=token_address,
                        receiver_address=receiver_address,
                        tx_hash=tx,
                        receipt=receipt,
                    )
                except Exception as exc:
                    logger.warning("Failed to settle on-chain deposit %s: %s", tx, exc)
                    self._mark_deposit_failed(tx, str(exc))
                return
            time.sleep(CONFIRMATION_POLL_SECONDS)

    def _settle_receipt(
        self,
        deposit_id: int,
        user_id: int,
        wallet_address: str,
        token_address: str,
        receiver_address: str,
        tx_hash: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        amount_raw = self._extract_transfer_amount(
            receipt=receipt,
            token_address=token_address,
            from_address=wallet_address,
            receiver_address=receiver_address,
        )
        credit_amount = self._amount_to_credits(amount_raw)
        if credit_amount <= 0:
            raise DepositVerificationError("Deposit amount is too small")

        return self._settle_deposit(
            deposit_id=deposit_id,
            user_id=user_id,
            wallet_address=wallet_address,
            token_address=token_address,
            receiver_address=receiver_address,
            amount_raw=amount_raw,
            credit_amount=credit_amount,
            tx_hash=tx_hash,
        )

    def _mark_deposit_failed(self, tx_hash: str, message: str) -> None:
        with self.db.session_scope() as session:
            deposit = session.execute(
                select(OnchainDeposit).where(OnchainDeposit.tx_hash == tx_hash)
            ).scalar_one_or_none()
            if deposit is not None and deposit.status != "succeeded":
                deposit.status = "failed"
                deposit.error = message[:256]

    def _get_or_create_pending_deposit(
        self,
        user_id: int,
        wallet_address: str,
        tx_hash: str,
        token_address: str,
        receiver_address: str,
    ) -> OnchainDeposit:
        with self.db.session_scope() as session:
            existing = session.execute(
                select(OnchainDeposit).where(OnchainDeposit.tx_hash == tx_hash)
            ).scalar_one_or_none()
            if existing is not None:
                if existing.user_id != user_id:
                    raise DepositVerificationError("Transaction hash has already been submitted")
                session.expunge(existing)
                return existing

            deposit = OnchainDeposit(
                user_id=user_id,
                wallet_address=wallet_address,
                tx_hash=tx_hash,
                chain_id=SEPOLIA_CHAIN_ID,
                token_address=token_address,
                receiver_address=receiver_address,
                status="pending",
            )
            session.add(deposit)
            try:
                session.flush()
            except IntegrityError as exc:
                raise DepositVerificationError("Transaction hash has already been submitted") from exc
            session.expunge(deposit)
            return deposit

    def _rpc(self, method: str, params: list[Any]) -> Any:
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
        req = urlrequest.Request(
            self.get_rpc_url(),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=20) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except URLError as exc:
            raise DepositVerificationError("Failed to query chain RPC") from exc

        if body.get("error"):
            raise DepositVerificationError(str(body["error"]))
        return body.get("result")

    def _extract_transfer_amount(
        self,
        receipt: dict[str, Any],
        token_address: str,
        from_address: str,
        receiver_address: str,
    ) -> int:
        if _hex_to_int(receipt.get("status")) != 1:
            raise DepositVerificationError("Transaction failed on chain")

        from_topic = _address_topic(from_address)
        receiver_topic = _address_topic(receiver_address)
        total = 0
        for log in receipt.get("logs") or []:
            topics = [str(topic).lower() for topic in (log.get("topics") or [])]
            if len(topics) < 3:
                continue
            if str(log.get("address", "")).lower() != token_address:
                continue
            if topics[0] != TRANSFER_TOPIC or topics[1] != from_topic or topics[2] != receiver_topic:
                continue
            total += _hex_to_int(log.get("data"))

        if total <= 0:
            raise DepositVerificationError("Matching ERC20 transfer was not found")
        return total

    def _amount_to_credits(self, amount_raw: int) -> int:
        getcontext().prec = 60
        oct_amount = Decimal(amount_raw) / (Decimal(10) ** TOKEN_DECIMALS)
        credits = (oct_amount / Decimal("1.5")) * Decimal(self.credit_service._get_credits_per_dollar())
        return int(credits.to_integral_value(rounding=ROUND_FLOOR))

    def _settle_deposit(
        self,
        deposit_id: int,
        user_id: int,
        wallet_address: str,
        token_address: str,
        receiver_address: str,
        amount_raw: int,
        credit_amount: int,
        tx_hash: str,
    ) -> dict[str, Any]:
        with self.db.session_scope() as session:
            deposit = session.execute(
                select(OnchainDeposit)
                .where(OnchainDeposit.id == deposit_id)
                .with_for_update()
            ).scalar_one()
            if deposit.status == "succeeded":
                session.expunge(deposit)
                return self._response(deposit)

            credit_tx = CreditTransaction(
                user_id=user_id,
                credit_amount=credit_amount,
                operator_user_id=None,
                reason=f"On-chain deposit {tx_hash}",
            )
            session.add(credit_tx)
            session.flush()

            balance_row = session.execute(
                select(UserCreditBalance)
                .where(UserCreditBalance.user_id == user_id)
                .with_for_update()
            ).scalar_one_or_none()
            if balance_row is None:
                balance_row = UserCreditBalance(
                    user_id=user_id,
                    balance=credit_amount,
                    lifetime_credits=credit_amount,
                )
                session.add(balance_row)
            else:
                balance_row.balance += credit_amount
                balance_row.lifetime_credits += credit_amount
                balance_row.version += 1

            deposit.wallet_address = wallet_address
            deposit.token_address = token_address
            deposit.receiver_address = receiver_address
            deposit.token_amount_raw = str(amount_raw)
            deposit.credit_amount = credit_amount
            deposit.credit_transaction_id = credit_tx.id
            deposit.status = "succeeded"
            deposit.error = None
            deposit.confirmed_at = datetime.now()
            session.flush()
            session.expunge(deposit)

        logger.info(
            "On-chain deposit settled: user=%d wallet=%s tx=%s credits=%d",
            user_id,
            wallet_address,
            tx_hash,
            credit_amount,
        )
        return self._response(deposit)

    def _response(self, deposit: OnchainDeposit) -> dict[str, Any]:
        return {
            "success": deposit.status == "succeeded",
            "deposit_id": deposit.id,
            "transaction_id": deposit.credit_transaction_id,
            "credit_amount": deposit.credit_amount or 0,
            "balance": self.credit_service.get_balance(deposit.user_id),
            "status": deposit.status,
        }
