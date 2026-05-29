"""Request-scoped user and configuration context."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    is_admin: bool = False
    account_type: str = "web"
    role_key: str = ""
    role_name: str = ""
    menu_permissions: Tuple[str, ...] = ()
    setting_permissions: Tuple[str, ...] = ()


_current_user: ContextVar[Optional[CurrentUser]] = ContextVar("dsa_current_user", default=None)


def get_current_user() -> Optional[CurrentUser]:
    return _current_user.get()


def get_current_user_id() -> Optional[int]:
    user = get_current_user()
    return user.id if user else None


@contextmanager
def use_current_user(user: Optional[CurrentUser]) -> Iterator[None]:
    token = _current_user.set(user)
    try:
        yield
    finally:
        _current_user.reset(token)
