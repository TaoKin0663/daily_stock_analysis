# -*- coding: utf-8 -*-
"""
Auth middleware: protect /api/v1/* with mandatory login.
"""

from __future__ import annotations

from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.auth import (
    ADMIN_COOKIE_NAME,
    AUTH_CLIENT_ADMIN,
    AUTH_CLIENT_HEADER,
    WEB_COOKIE_NAME,
    get_session_user,
    verify_session,
)
from src.user_context import CurrentUser, use_current_user

EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/status",
    "/api/health",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})


def _cookie_name_for_request(request: Request) -> str:
    path = request.url.path
    client = (request.headers.get(AUTH_CLIENT_HEADER) or "").strip().lower()
    if path.startswith("/api/v1/admin") or client == AUTH_CLIENT_ADMIN:
        return ADMIN_COOKIE_NAME
    return WEB_COOKIE_NAME


def _path_exempt(path: str) -> bool:
    """Check if path is exempt from auth."""
    normalized = path.rstrip("/") or "/"
    return normalized in EXEMPT_PATHS


class AuthMiddleware(BaseHTTPMiddleware):
    """Require valid session for /api/v1/* when auth is enabled."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):
        path = request.url.path
        if _path_exempt(path):
            return await call_next(request)

        if not path.startswith("/api/v1/"):
            return await call_next(request)

        cookie_val = request.cookies.get(_cookie_name_for_request(request))
        user = get_session_user(cookie_val) if cookie_val else None
        if not cookie_val or not verify_session(cookie_val) or not user:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "message": "Login required",
                },
            )

        current_user = CurrentUser(
            id=int(user["id"]),
            username=str(user["username"]),
            is_admin=bool(user.get("is_admin") or user.get("isAdmin")),
            account_type=str(user.get("accountType") or "web"),
            role_key=str(user.get("roleKey") or ""),
            role_name=str(user.get("roleName") or ""),
            menu_permissions=tuple(user.get("menuPermissions") or ()),
            setting_permissions=tuple(user.get("settingPermissions") or ()),
        )
        request.state.current_user = current_user
        with use_current_user(current_user):
            return await call_next(request)


def add_auth_middleware(app):
    """Add auth middleware to protect API routes with mandatory login."""
    app.add_middleware(AuthMiddleware)
