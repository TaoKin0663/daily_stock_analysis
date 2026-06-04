# -*- coding: utf-8 -*-
"""Web authentication module.

Login is mandatory. Runtime authentication cannot be disabled through
environment configuration.
"""

from __future__ import annotations

import json
import base64
import getpass
import hashlib
import hmac
import logging
import os
import secrets
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

COOKIE_NAME = "dsa_session"
WEB_COOKIE_NAME = "dsa_web_session"
ADMIN_COOKIE_NAME = "dsa_admin_session"
AUTH_CLIENT_HEADER = "x-dsa-auth-client"
AUTH_CLIENT_WEB = "web"
AUTH_CLIENT_ADMIN = "admin"
SESSION_SUBJECT_WEB_USER = "web_user"
SESSION_SUBJECT_ADMIN_USER = "admin_user"
PBKDF2_ITERATIONS = 100_000
RATE_LIMIT_WINDOW_SEC = 300
RATE_LIMIT_MAX_FAILURES = 5
SESSION_MAX_AGE_HOURS_DEFAULT = 24
MIN_PASSWORD_LEN = 6
MIN_USERNAME_LEN = 3

_session_secret: Optional[bytes] = None
_rate_limit: dict[str, Tuple[int, float]] = {}
_rate_limit_lock = None


def _get_lock():
    """Lazy init threading lock for rate limit dict."""
    global _rate_limit_lock
    if _rate_limit_lock is None:
        import threading
        _rate_limit_lock = threading.Lock()
    return _rate_limit_lock


def _ensure_env_loaded() -> None:
    """Ensure .env is loaded before reading config."""
    from src.config import setup_env
    setup_env()


def _get_data_dir() -> Path:
    """Return DATA_DIR as parent of DATABASE_PATH."""
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return Path(db_path).resolve().parent


def rotate_session_secret() -> bool:
    """Rotate the session signing secret to invalidate all active sessions."""
    global _session_secret
    data_dir = _get_data_dir()
    secret_path = data_dir / ".session_secret"
    data_dir.mkdir(parents=True, exist_ok=True)
    new_secret = secrets.token_bytes(32)
    try:
        tmp_path = secret_path.with_suffix(".tmp")
        tmp_path.write_bytes(new_secret)
        tmp_path.chmod(0o600)
        tmp_path.replace(secret_path)
        _session_secret = new_secret
        logger.info("Session secret rotated successfully")
        return True
    except OSError as e:
        logger.error("Failed to rotate .session_secret: %s", e)
        return False


def _load_session_secret() -> Optional[bytes]:
    """Load or create session secret."""
    global _session_secret
    if _session_secret is not None:
        return _session_secret

    data_dir = _get_data_dir()
    secret_path = data_dir / ".session_secret"

    try:
        if secret_path.exists():
            _session_secret = secret_path.read_bytes()
            if len(_session_secret) != 32:
                logger.warning("Invalid .session_secret length, regenerating")
                _session_secret = None
                if rotate_session_secret():
                    return _session_secret
                return None
            return _session_secret

        data_dir.mkdir(parents=True, exist_ok=True)
        new_secret = secrets.token_bytes(32)
        try:
            with open(secret_path, "xb") as f:
                f.write(new_secret)
            secret_path.chmod(0o600)
        except FileExistsError:
            _session_secret = secret_path.read_bytes()
        else:
            _session_secret = new_secret
        return _session_secret
    except OSError as e:
        logger.error("Failed to create or read .session_secret: %s", e)
        return None


def _verify_password_hash(submitted: str, salt: bytes, stored_hash: bytes) -> bool:
    """Verify submitted password against stored pbkdf2 hash."""
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        submitted.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(computed, stored_hash)

def refresh_auth_state() -> None:
    """Reload auth-related state from disk."""
    global _session_secret
    _session_secret = None


def is_auth_enabled() -> bool:
    """Return whether authentication is enabled."""
    return True


def has_stored_password() -> bool:
    """Return whether the database admin password has been initialized."""
    try:
        from src.storage import DatabaseManager

        return DatabaseManager.get_instance().is_admin_password_initialized()
    except Exception:
        logger.warning("Failed to read admin password state from database", exc_info=True)
        return False


def verify_stored_password(password: str) -> bool:
    """Verify password against the initialized database admin credential."""
    try:
        from src.storage import DatabaseManager

        db = DatabaseManager.get_instance()
        row = db.get_admin_user_by_username("admin")
    except Exception:
        logger.warning("Failed to load admin credential from database", exc_info=True)
        return False

    if row is None or not row.is_active or not row.password_initialized:
        return False
    return _verify_password_hash(password, row.password_salt, row.password_hash)


def is_password_set() -> bool:
    """Return whether initial password has been set."""
    return has_stored_password()


def is_password_changeable() -> bool:
    """Return whether password can be changed via web/CLI (always True when auth enabled)."""
    return is_auth_enabled()


def _get_session_secret() -> Optional[bytes]:
    """Return session signing secret."""
    return _load_session_secret()


def _validate_password(pwd: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not pwd or not pwd.strip():
        return "密码不能为空"
    if len(pwd) < MIN_PASSWORD_LEN:
        return f"密码至少 {MIN_PASSWORD_LEN} 位"
    return None


def _normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def _validate_username(username: str) -> Optional[str]:
    normalized = _normalize_username(username)
    if len(normalized) < MIN_USERNAME_LEN:
        return f"用户名至少 {MIN_USERNAME_LEN} 位"
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
    if any(ch not in allowed for ch in normalized):
        return "用户名只能包含字母、数字、下划线和短横线"
    return None


def _hash_password(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    salt = salt or secrets.token_bytes(32)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return salt, derived


def register_user(username: str, password: str) -> tuple[Optional[dict], Optional[str]]:
    """Create a user account for open registration."""
    username_norm = _normalize_username(username)
    if username_norm == "admin":
        return None, "admin username is reserved"
    err = _validate_username(username_norm) or _validate_password(password)
    if err:
        return None, err

    from sqlalchemy.exc import IntegrityError
    from src.storage import DatabaseManager

    db = DatabaseManager.get_instance()
    if db.get_user_by_username(username_norm):
        return None, "用户名已存在"

    salt, stored = _hash_password(password)
    try:
        row = db.create_user(
            username=username_norm,
            password_salt=salt,
            password_hash=stored,
            is_admin=False,
        )
    except IntegrityError:
        return None, "用户名已存在"
    return _user_to_dict(row), None


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return user payload when username/password are valid."""
    from src.storage import DatabaseManager

    username_norm = _normalize_username(username)
    if username_norm == "admin":
        return None
    row = DatabaseManager.get_instance().get_user_by_username(username_norm)
    if row is None or not row.is_active:
        return None
    if not _verify_password_hash(password, row.password_salt, row.password_hash):
        return None
    return _user_to_dict(row)


def get_user_by_id(user_id: int) -> Optional[dict]:
    from src.storage import DatabaseManager

    row = DatabaseManager.get_instance().get_user_by_id(int(user_id))
    if row is None or not row.is_active:
        return None
    return _user_to_dict(row)


def authenticate_admin_user(username: str, password: str) -> Optional[dict]:
    """Return isolated admin account payload when credentials are valid."""
    from src.storage import DatabaseManager

    username_norm = _normalize_username(username)
    if username_norm != "admin":
        return None
    db = DatabaseManager.get_instance()
    db.ensure_default_admin_account()
    row = db.get_admin_user_by_username(username_norm)
    if row is None or not row.is_active or not row.password_initialized:
        return None
    if not _verify_password_hash(password, row.password_salt, row.password_hash):
        return None
    return _admin_user_to_dict(row)


def get_admin_user_by_id(admin_user_id: int) -> Optional[dict]:
    from src.storage import DatabaseManager

    row = DatabaseManager.get_instance().get_admin_user_by_id(int(admin_user_id))
    if row is None or not row.is_active or not row.password_initialized:
        return None
    return _admin_user_to_dict(row)


def _user_to_dict(row) -> dict:
    role_payload = {}
    try:
        from src.storage import DatabaseManager

        role_payload = DatabaseManager.get_instance().get_user_role_payload(
            int(row.id),
            is_admin=bool(row.is_admin),
        )
    except Exception:
        role_payload = {}
    menu_permissions = tuple(role_payload.get("menuKeys") or ())
    setting_permissions = tuple(role_payload.get("settingKeys") or ())
    return {
        "id": int(row.id),
        "username": str(row.username),
        "isAdmin": bool(row.is_admin),
        "is_admin": bool(row.is_admin),
        "accountType": "web",
        "role": role_payload or None,
        "roleKey": role_payload.get("key") if role_payload else None,
        "roleName": role_payload.get("name") if role_payload else None,
        "menuPermissions": list(menu_permissions),
        "settingPermissions": list(setting_permissions),
        "subjectType": SESSION_SUBJECT_WEB_USER,
    }


def _admin_user_to_dict(row) -> dict:
    from src.storage import DatabaseManager
    from src.permissions import ADMIN_MENU_KEYS, ADMIN_SETTING_KEYS, SUPER_ADMIN_ROLE_KEY

    owner_id = DatabaseManager.get_instance().ensure_default_admin_user()
    return {
        "id": int(owner_id),
        "adminUserId": int(row.id),
        "username": str(row.username),
        "isAdmin": True,
        "is_admin": True,
        "accountType": "admin",
        "role": {"key": SUPER_ADMIN_ROLE_KEY, "name": "Super Admin"},
        "roleKey": SUPER_ADMIN_ROLE_KEY,
        "roleName": "Super Admin",
        "menuPermissions": list(ADMIN_MENU_KEYS),
        "settingPermissions": list(ADMIN_SETTING_KEYS),
        "subjectType": SESSION_SUBJECT_ADMIN_USER,
    }


def _store_admin_password(password: str) -> Optional[str]:
    try:
        from src.storage import DatabaseManager

        salt, stored = _hash_password(password)
        DatabaseManager.get_instance().set_admin_account_password(salt, stored)
        return None
    except Exception:
        logger.error("Failed to write admin password to database", exc_info=True)
        return "密码保存失败"


def set_initial_password(password: str) -> Optional[str]:
    """
    Set initial password (first-time setup). Returns error message or None on success.
    """
    err = _validate_password(password)
    if err:
        return err

    return _store_admin_password(password)


def verify_password(password: str) -> bool:
    """Verify password against stored credential. Constant-time where applicable."""
    return verify_stored_password(password)


def change_password(current: str, new: str) -> Optional[str]:
    """
    Change password. Verifies current, writes new hash. Returns error message or None on success.
    """
    if not is_password_set():
        return "尚未设置密码"

    if not current or not current.strip():
        return "请输入当前密码"
    if not verify_stored_password(current):
        return "当前密码错误"

    err = _validate_password(new)
    if err:
        return err

    return _store_admin_password(new)


def create_session(user: Optional[dict] = None, subject_type: Optional[str] = None) -> str:
    """Create a signed session payload. Format: payload.signature."""
    secret = _get_session_secret()
    if not secret:
        return ""
    if user is None:
        try:
            from src.storage import DatabaseManager
            admin_user_id = DatabaseManager.get_instance().ensure_default_admin_account()
            user = get_admin_user_by_id(admin_user_id)
        except Exception:
            user = None
    subject_type = subject_type or (user.get("subjectType") if user else None) or SESSION_SUBJECT_WEB_USER
    body = {
        "nonce": secrets.token_urlsafe(32),
        "ts": int(time.time()),
        "subject_type": subject_type,
    }
    if user:
        subject_id = user.get("adminUserId") if subject_type == SESSION_SUBJECT_ADMIN_USER else user.get("id")
        body.update({
            "user_id": int(subject_id),
            "username": user["username"],
            "is_admin": bool(user.get("is_admin") or user.get("isAdmin")),
        })
    payload = base64.urlsafe_b64encode(
        json.dumps(body, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    sig = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def get_session_payload(value: str) -> Optional[dict]:
    """Verify session cookie, check expiry, and return payload."""
    secret = _get_session_secret()
    if not secret or not value:
        return None
    parts = value.split(".")
    if len(parts) == 3:
        # Legacy nonce.ts.sig token has no user identity.
        nonce, ts_str, sig = parts[0], parts[1], parts[2]
        payload = f"{nonce}.{ts_str}"
        expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            ts = int(ts_str)
        except ValueError:
            return None
        body = {"ts": ts}
    elif len(parts) == 2:
        payload, sig = parts[0], parts[1]
        expected = hmac.new(secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        try:
            padded = payload + ("=" * (-len(payload) % 4))
            body = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        except Exception:
            return None
        ts = int(body.get("ts") or 0)
    else:
        return None
    try:
        max_age_hours = int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", str(SESSION_MAX_AGE_HOURS_DEFAULT)))
    except ValueError:
        max_age_hours = SESSION_MAX_AGE_HOURS_DEFAULT
    if time.time() - ts > max_age_hours * 3600:
        return None
    return body


def verify_session(value: str) -> bool:
    """Verify session cookie and check expiry."""
    return get_session_payload(value) is not None


def get_session_user(value: str) -> Optional[dict]:
    payload = get_session_payload(value)
    if not payload or not payload.get("user_id"):
        return None
    subject_type = payload.get("subject_type") or SESSION_SUBJECT_WEB_USER
    if subject_type == SESSION_SUBJECT_ADMIN_USER:
        return get_admin_user_by_id(int(payload["user_id"]))
    return get_user_by_id(int(payload["user_id"]))


def get_client_ip(request) -> str:
    """Get client IP, respecting TRUST_X_FORWARDED_FOR.

    When behind a single trusted reverse proxy, the proxy appends the real
    client IP as the rightmost entry in X-Forwarded-For.  We use [-1] instead
    of [0] so that an attacker cannot spoof an arbitrary leftmost value to
    rotate rate-limit buckets and bypass brute-force protection.
    """
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    if request.client:
        return request.client.host or "127.0.0.1"
    return "127.0.0.1"


def check_rate_limit(ip: str) -> bool:
    """Return True if under limit, False if rate limited."""
    lock = _get_lock()
    now = time.time()
    with lock:
        expired_keys = [k for k, (_, ts) in _rate_limit.items() if now - ts > RATE_LIMIT_WINDOW_SEC]
        for k in expired_keys:
            del _rate_limit[k]
        if ip in _rate_limit:
            count, first_ts = _rate_limit[ip]
            if count >= RATE_LIMIT_MAX_FAILURES:
                return False
        return True


def record_login_failure(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    lock = _get_lock()
    now = time.time()
    with lock:
        if ip in _rate_limit:
            count, first_ts = _rate_limit[ip]
            if now - first_ts > RATE_LIMIT_WINDOW_SEC:
                _rate_limit[ip] = (1, now)
            else:
                _rate_limit[ip] = (count + 1, first_ts)
        else:
            _rate_limit[ip] = (1, now)


def clear_rate_limit(ip: str) -> None:
    """Clear rate limit for IP after successful login."""
    lock = _get_lock()
    with lock:
        _rate_limit.pop(ip, None)


def overwrite_password(new_password: str) -> Optional[str]:
    """
    Overwrite stored password without verifying current. For CLI reset only.
    Returns error message or None on success.
    """
    err = _validate_password(new_password)
    if err:
        return err

    return _store_admin_password(new_password)


def reset_password_cli() -> int:
    """Interactive CLI to reset password. Returns exit code."""
    _ensure_env_loaded()

    print("Enter new admin password (will not echo):", end=" ")
    pwd = getpass.getpass("")
    err = _validate_password(pwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("Confirm new password:", end=" ")
    pwd2 = getpass.getpass("")
    if pwd != pwd2:
        print("Error: Passwords do not match", file=sys.stderr)
        return 1

    err = overwrite_password(pwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("Password has been reset successfully.")
    return 0


def _main() -> int:
    """CLI entry: reset_password subcommand."""
    if len(sys.argv) > 1 and sys.argv[1] == "reset_password":
        return reset_password_cli()
    print("Usage: python -m src.auth reset_password", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_main())
