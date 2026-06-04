# -*- coding: utf-8 -*-
"""Authentication endpoints for Web admin login."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from src.auth import (
    ADMIN_COOKIE_NAME,
    AUTH_CLIENT_ADMIN,
    AUTH_CLIENT_HEADER,
    AUTH_CLIENT_WEB,
    SESSION_MAX_AGE_HOURS_DEFAULT,
    SESSION_SUBJECT_ADMIN_USER,
    WEB_COOKIE_NAME,
    authenticate_admin_user,
    authenticate_user,
    change_password,
    check_rate_limit,
    clear_rate_limit,
    create_session,
    get_session_user,
    get_client_ip,
    has_stored_password,
    is_password_changeable,
    is_password_set,
    record_login_failure,
    register_user,
    set_initial_password,
    verify_stored_password,
    verify_session,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _auth_client(request: Request) -> str:
    """Return the frontend auth client that owns this auth request."""
    client = (request.headers.get(AUTH_CLIENT_HEADER) or "").strip().lower()
    if client == AUTH_CLIENT_ADMIN:
        return AUTH_CLIENT_ADMIN
    if client == AUTH_CLIENT_WEB:
        return AUTH_CLIENT_WEB

    referer = (request.headers.get("referer") or "").lower()
    if "/admin" in referer:
        return AUTH_CLIENT_ADMIN
    return AUTH_CLIENT_WEB


def _cookie_name_for_request(request: Request) -> str:
    return ADMIN_COOKIE_NAME if _auth_client(request) == AUTH_CLIENT_ADMIN else WEB_COOKIE_NAME


def _get_session_cookie(request: Request) -> str | None:
    return request.cookies.get(_cookie_name_for_request(request))


def _delete_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(key=_cookie_name_for_request(request), path="/")


class LoginRequest(BaseModel):
    """Login request body. For first-time setup use password + password_confirm."""

    model_config = {"populate_by_name": True}

    username: str = Field(default="admin", description="Username")
    password: str = Field(default="", description="Password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm", description="Confirm (first-time)")


class RegisterRequest(BaseModel):
    """Open user registration request."""

    model_config = {"populate_by_name": True}

    username: str = Field(default="", description="Username")
    password: str = Field(default="", description="Password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm")


class ChangePasswordRequest(BaseModel):
    """Change password request body."""

    model_config = {"populate_by_name": True}

    current_password: str = Field(default="", alias="currentPassword")
    new_password: str = Field(default="", alias="newPassword")
    new_password_confirm: str = Field(default="", alias="newPasswordConfirm")


class AuthSettingsRequest(BaseModel):
    """Set or confirm mandatory password login settings."""

    model_config = {"populate_by_name": True}

    auth_enabled: bool = Field(alias="authEnabled")
    password: str = Field(default="")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm")
    current_password: str = Field(default="", alias="currentPassword")


def _cookie_params(request: Request) -> dict:
    """Build cookie params including Secure based on request."""
    secure = False
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        proto = request.headers.get("X-Forwarded-Proto", "").lower()
        secure = proto == "https"
    else:
        # Check URL scheme when not behind proxy
        secure = request.url.scheme == "https"

    try:
        max_age_hours = int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", str(SESSION_MAX_AGE_HOURS_DEFAULT)))
    except ValueError:
        max_age_hours = SESSION_MAX_AGE_HOURS_DEFAULT
    max_age = max_age_hours * 3600

    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
        "max_age": max_age,
    }


def _password_set_for_response(auth_enabled: bool) -> bool:
    """Return whether the mandatory login password is initialized."""
    return is_password_set()


def _set_session_cookie(response: Response, session_value: str, request: Request) -> None:
    """Attach the admin session cookie to a response."""
    params = _cookie_params(request)
    response.set_cookie(
        key=_cookie_name_for_request(request),
        value=session_value,
        httponly=params["httponly"],
        samesite=params["samesite"],
        secure=params["secure"],
        path=params["path"],
        max_age=params["max_age"],
    )


def _get_auth_status_dict(request: Request | None = None) -> dict:
    """Helper to build consistent auth status response body."""
    auth_enabled = True
    logged_in = False
    session_user = None
    if request:
        cookie_val = _get_session_cookie(request)
        logged_in = verify_session(cookie_val) if cookie_val else False
        session_user = get_session_user(cookie_val) if cookie_val else None
        logged_in = bool(session_user)

    setup_state = "enabled" if has_stored_password() else "no_password"

    return {
        "authEnabled": auth_enabled,
        "loggedIn": logged_in,
        "passwordSet": _password_set_for_response(auth_enabled),
        "passwordChangeable": is_password_changeable(),
        "setupState": setup_state,
        "currentUser": (
            {
                "id": session_user["id"],
                "username": session_user["username"],
                "isAdmin": bool(session_user.get("isAdmin") or session_user.get("is_admin")),
                "accountType": session_user.get("accountType") or "web",
                "role": session_user.get("role"),
                "roleKey": session_user.get("roleKey"),
                "roleName": session_user.get("roleName"),
                "menuPermissions": session_user.get("menuPermissions") or [],
                "settingPermissions": session_user.get("settingPermissions") or [],
            }
            if session_user
            else None
        ),
    }


@router.get(
    "/status",
    summary="Get auth status",
    description="Returns whether auth is enabled and if the current request is logged in.",
)
async def auth_status(request: Request):
    """Return authEnabled, loggedIn, passwordSet, passwordChangeable, setupState without requiring auth."""
    return _get_auth_status_dict(request)


@router.post(
    "/settings",
    summary="Update auth settings",
    description="Configure the mandatory password login. Disabling authentication is not allowed.",
)
async def auth_update_settings(request: Request, body: AuthSettingsRequest):
    """Set or confirm the mandatory admin password; auth cannot be disabled."""
    stored_password_exists = has_stored_password()

    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    current_password = (body.current_password or "").strip()

    if password or confirm:
        if stored_password_exists:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "password_already_set",
                    "message": "管理员密码已存在，请通过修改密码功能更新",
                },
            )
        if not password:
            return JSONResponse(
                status_code=400,
                content={"error": "password_required", "message": "请输入要设置的管理员密码"},
            )
        if password != confirm:
            return JSONResponse(
                status_code=400,
                content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
            )
        if has_stored_password():
            return JSONResponse(
                status_code=400,
                content={
                    "error": "password_already_set",
                    "message": "管理员密码已存在，请通过修改密码功能更新",
                },
            )
        err = set_initial_password(password)
        if err:
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
    elif not stored_password_exists:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "设置管理员密码后才能登录"},
        )
    else:
        cookie_val = _get_session_cookie(request)
        is_valid_session = bool(cookie_val and verify_session(cookie_val))

        if not is_valid_session:
            if not current_password:
                return JSONResponse(
                    status_code=400,
                    content={"error": "current_required", "message": "请输入当前密码"},
                )
            ip = get_client_ip(request)
            if not check_rate_limit(ip):
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "rate_limited",
                        "message": "Too many failed attempts. Please try again later.",
                    },
                )
            if not verify_stored_password(current_password):
                record_login_failure(ip)
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid_password", "message": "当前密码错误"},
                )
            clear_rate_limit(ip)

    session_val = create_session()
    if not session_val:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create session"},
        )

    content = _get_auth_status_dict(request)
    content["loggedIn"] = True
    resp = JSONResponse(content=content)
    _set_session_cookie(resp, session_val, request)
    return resp


@router.post(
    "/login",
    summary="Login or set initial password",
    description="Verify password and set session cookie. If password not set yet, accepts password+passwordConfirm.",
)
async def auth_login(request: Request, body: LoginRequest):
    """Verify password or set initial password, set cookie on success. Returns 401 or 429 on failure."""
    password = (body.password or "").strip()
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入密码"},
        )

    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Too many failed attempts. Please try again later.",
            },
        )

    username = (body.username or "admin").strip()
    auth_client = _auth_client(request)
    if auth_client == AUTH_CLIENT_ADMIN:
        if username.lower() != "admin":
            record_login_failure(ip)
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_credentials", "message": "账号或密码错误"},
            )
        password_set = is_password_set()
        if not password_set:
            confirm = (body.password_confirm or "").strip()
            if password != confirm:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "Passwords do not match"},
                )
            err = set_initial_password(password)
            if err:
                record_login_failure(ip)
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": err},
                )
        user = authenticate_admin_user("admin", password)
        if not user:
            record_login_failure(ip)
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_password", "message": "账号或密码错误"},
            )
        clear_rate_limit(ip)
        session_val = create_session(user, subject_type=SESSION_SUBJECT_ADMIN_USER)
        if not session_val:
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to create session"},
            )
        resp = JSONResponse(content={"ok": True})
        _set_session_cookie(resp, session_val, request)
        return resp

    if username.lower() == "admin" and not is_password_set():
        confirm = (body.password_confirm or "").strip()
        if password != confirm:
            record_login_failure(ip)
            return JSONResponse(
                status_code=400,
                content={"error": "password_mismatch", "message": "Passwords do not match"},
            )
        err = set_initial_password(password)
        if err:
            record_login_failure(ip)
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
        user = authenticate_admin_user("admin", password)
        if not user:
            record_login_failure(ip)
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_password", "message": "账号或密码错误"},
            )
        clear_rate_limit(ip)
        session_val = create_session(user, subject_type=SESSION_SUBJECT_ADMIN_USER)
        if not session_val:
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to create session"},
            )
        resp = JSONResponse(content={"ok": True})
        _set_session_cookie(resp, session_val, request)
        return resp

    if username.lower() == "admin":
        record_login_failure(ip)
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_credentials", "message": "账号或密码错误"},
        )

    user = authenticate_user(username, password)
    if not user:
        record_login_failure(ip)
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_credentials", "message": "用户名或密码错误"},
        )
    clear_rate_limit(ip)
    session_val = create_session(user)
    if not session_val:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create session"},
        )

    resp = JSONResponse(content={"ok": True})
    _set_session_cookie(resp, session_val, request)
    return resp


@router.post(
    "/register",
    summary="Register user",
    description="Create a user account with username and password.",
)
async def auth_register(request: Request, body: RegisterRequest):
    """Open registration endpoint."""
    if _auth_client(request) == AUTH_CLIENT_ADMIN:
        return JSONResponse(
            status_code=403,
            content={"error": "admin_registration_disabled", "message": "Admin accounts cannot be registered"},
        )

    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    if password != confirm:
        return JSONResponse(
            status_code=400,
            content={"error": "password_mismatch", "message": "Passwords do not match"},
        )

    user, err = register_user(body.username, password)
    if err:
        return JSONResponse(status_code=400, content={"error": "invalid_registration", "message": err})

    session_val = create_session(user)
    if not session_val:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create session"},
        )
    resp = JSONResponse(content={"ok": True})
    _set_session_cookie(resp, session_val, request)
    return resp


@router.post(
    "/change-password",
    summary="Change password",
    description="Change password. Requires valid session.",
)
async def auth_change_password(body: ChangePasswordRequest):
    """Change password. Requires login."""
    if not is_password_changeable():
        return JSONResponse(
            status_code=400,
            content={"error": "not_changeable", "message": "Password cannot be changed via web"},
        )

    current = (body.current_password or "").strip()
    new_pwd = (body.new_password or "").strip()
    new_confirm = (body.new_password_confirm or "").strip()

    if not current:
        return JSONResponse(
            status_code=400,
            content={"error": "current_required", "message": "请输入当前密码"},
        )
    if new_pwd != new_confirm:
        return JSONResponse(
            status_code=400,
            content={"error": "password_mismatch", "message": "两次输入的新密码不一致"},
        )

    err = change_password(current, new_pwd)
    if err:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_password", "message": err},
        )
    return Response(status_code=204)


@router.post(
    "/logout",
    summary="Logout",
    description="Clear session cookie.",
)
async def auth_logout(request: Request):
    """Clear session cookie."""
    resp = Response(status_code=204)
    _delete_session_cookie(resp, request)
    return resp
