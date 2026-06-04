# -*- coding: utf-8 -*-
"""Integration tests for auth API endpoints (login, logout, change-password, API protection)."""

import asyncio
import os
import sys
import tempfile
import uuid
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.responses import Response
from starlette.requests import Request

# Keep this test runnable when optional LLM runtime deps are not installed.
try:
    import litellm  # noqa: F401
except ModuleNotFoundError:
    sys.modules["litellm"] = MagicMock()

import src.auth as auth
from api.middlewares.auth import AuthMiddleware
from api.v1.endpoints import auth as auth_endpoint
from src.config import Config
from src.auth import ADMIN_COOKIE_NAME, WEB_COOKIE_NAME
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._session_secret = None
    auth._rate_limit = {}


class AuthApiTestCase(unittest.TestCase):
    """Integration tests for /api/v1/auth/* and API protection."""

    def setUp(self) -> None:
        _reset_auth_globals()
        os.environ.pop("ADMIN_INITIAL_PASSWORD", None)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self._original_env_file = os.environ.get("ENV_FILE")
        self._original_database_path = os.environ.get("DATABASE_PATH")
        self._original_database_url = os.environ.get("DATABASE_URL")
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        os.environ.pop("DATABASE_URL", None)
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.data_dir_patcher.start()

    def tearDown(self) -> None:
        self.data_dir_patcher.stop()
        Config.reset_instance()
        DatabaseManager.reset_instance()
        if self._original_env_file is None:
            os.environ.pop("ENV_FILE", None)
        else:
            os.environ["ENV_FILE"] = self._original_env_file
        if self._original_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self._original_database_path
        os.environ.pop("ADMIN_INITIAL_PASSWORD", None)
        if self._original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self._original_database_url
        self.temp_dir.cleanup()

    @staticmethod
    def _build_request(cookies=None, headers=None):
        return SimpleNamespace(
            headers=headers or {},
            url=SimpleNamespace(scheme="http"),
            cookies=cookies or {},
            client=SimpleNamespace(host="127.0.0.1"),
        )

    @staticmethod
    def _extract_cookie_value(response, cookie_name: str) -> str:
        return response.headers["set-cookie"].split(f"{cookie_name}=", 1)[1].split(";", 1)[0]

    def test_auth_status_when_password_not_set(self) -> None:
        data = asyncio.run(auth_endpoint.auth_status(self._build_request()))
        self.assertTrue(data["authEnabled"])
        self.assertFalse(data["passwordSet"])
        self.assertFalse(data["loggedIn"])

    def test_admin_initial_password_seeds_database_password(self) -> None:
        os.environ["ADMIN_INITIAL_PASSWORD"] = "seedpass123"
        Config.reset_instance()
        DatabaseManager.reset_instance()

        data = asyncio.run(auth_endpoint.auth_status(self._build_request()))

        self.assertEqual(data["setupState"], "enabled")
        self.assertTrue(data["passwordSet"])
        self.assertTrue(auth.verify_stored_password("seedpass123"))

    def test_admin_initial_password_does_not_overwrite_existing_password(self) -> None:
        os.environ["ADMIN_INITIAL_PASSWORD"] = "seedpass123"
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.assertTrue(auth.verify_stored_password("seedpass123"))

        auth.change_password("seedpass123", "changedpass123")
        os.environ["ADMIN_INITIAL_PASSWORD"] = "otherpass123"
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.assertTrue(auth.verify_stored_password("changedpass123"))
        self.assertFalse(auth.verify_stored_password("otherpass123"))

    def test_login_first_time_set_initial_password(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="newpass123", passwordConfirm="newpass123"),
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(f"{ADMIN_COOKIE_NAME}=", response.headers["set-cookie"])
        self.assertIn(b'"ok":true', response.body)

    def test_web_client_can_set_first_time_admin_password(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "web"}),
                auth_endpoint.LoginRequest(password="newpass123", passwordConfirm="newpass123"),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"{WEB_COOKIE_NAME}=", response.headers["set-cookie"])
        self.assertTrue(auth.verify_stored_password("newpass123"))

    def test_admin_login_sets_admin_cookie(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="newpass123", passwordConfirm="newpass123"),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(f"{ADMIN_COOKIE_NAME}=", response.headers["set-cookie"])

    def test_login_first_time_mismatch_rejected(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="pass1", passwordConfirm="pass2"),
            )
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_mismatch"', response.body)

    def test_login_after_set_normal_login(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="mypass456", passwordConfirm="mypass456"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="mypass456"),
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"ok":true', response.body)

    def test_login_wrong_password_returns_401(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="correct", passwordConfirm="correct"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="wrong"),
            )
        )
        self.assertEqual(response.status_code, 401)

    def test_admin_client_rejects_registered_web_user(self) -> None:
        username = f"web{uuid.uuid4().hex[:10]}"
        register_response = asyncio.run(
            auth_endpoint.auth_register(
                self._build_request(),
                auth_endpoint.RegisterRequest(username=username, password="passwd6", passwordConfirm="passwd6"),
            )
        )
        self.assertEqual(register_response.status_code, 200, register_response.body)

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(username=username, password="passwd6"),
            )
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn(b'"error":"invalid_credentials"', response.body)

    def test_web_client_rejects_admin_login(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="adminpass", passwordConfirm="adminpass"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(),
                auth_endpoint.LoginRequest(username="admin", password="adminpass"),
            )
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn(b'"error":"invalid_credentials"', response.body)

    def test_admin_client_cannot_register_accounts(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_register(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.RegisterRequest(username="staff", password="passwd6", passwordConfirm="passwd6"),
            )
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'"error":"admin_registration_disabled"', response.body)

    def test_web_registration_rejects_reserved_admin_username(self) -> None:
        response = asyncio.run(
            auth_endpoint.auth_register(
                self._build_request(),
                auth_endpoint.RegisterRequest(username="admin", password="passwd6", passwordConfirm="passwd6"),
            )
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"invalid_registration"', response.body)

    def test_logout_clears_cookie(self) -> None:
        response = asyncio.run(auth_endpoint.auth_logout(self._build_request()))
        self.assertEqual(response.status_code, 204)
        self.assertIn(f"{WEB_COOKIE_NAME}=", response.headers["set-cookie"])

    def test_web_logout_does_not_invalidate_admin_session(self) -> None:
        username = f"web{uuid.uuid4().hex[:10]}"
        web_login_response = asyncio.run(
            auth_endpoint.auth_register(
                self._build_request(),
                auth_endpoint.RegisterRequest(username=username, password="webpass6", passwordConfirm="webpass6"),
            )
        )
        self.assertEqual(web_login_response.status_code, 200)
        admin_login_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="passwd6", passwordConfirm="passwd6"),
            )
        )
        self.assertEqual(admin_login_response.status_code, 200)
        admin_cookie = self._extract_cookie_value(admin_login_response, ADMIN_COOKIE_NAME)

        logout_response = asyncio.run(auth_endpoint.auth_logout(self._build_request()))

        self.assertEqual(logout_response.status_code, 204)
        self.assertTrue(auth.verify_session(admin_cookie))

    def test_change_password_requires_session(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="oldpass6", passwordConfirm="oldpass6"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_change_password(
                auth_endpoint.ChangePasswordRequest(
                    currentPassword="oldpass6",
                    newPassword="newpass6",
                    newPasswordConfirm="newpass6",
                )
            )
        )
        self.assertIn(response.status_code, (200, 204))

    def test_change_password_wrong_current_rejected(self) -> None:
        first_response = asyncio.run(
            auth_endpoint.auth_login(
                self._build_request(headers={"x-dsa-auth-client": "admin"}),
                auth_endpoint.LoginRequest(password="actual6", passwordConfirm="actual6"),
            )
        )
        self.assertEqual(first_response.status_code, 200)

        response = asyncio.run(
            auth_endpoint.auth_change_password(
                auth_endpoint.ChangePasswordRequest(
                    currentPassword="wrong",
                    newPassword="new123",
                    newPasswordConfirm="new123",
                )
            )
        )
        self.assertEqual(response.status_code, 400)

    def test_protected_api_returns_401_without_session(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/system/config",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())

        if True:
            response = asyncio.run(middleware.dispatch(request, AsyncMock(return_value=Response(status_code=200))))

        self.assertEqual(response.status_code, 401)

    def test_logout_requires_session_when_auth_enabled(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/logout",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=Response(status_code=204))

        if True:
            response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 401)
        call_next.assert_not_awaited()

    def test_admin_logout_accepts_admin_session_cookie(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/logout",
            "headers": [
                (b"x-dsa-auth-client", b"admin"),
                (b"cookie", f"{ADMIN_COOKIE_NAME}=admin-session".encode("utf-8")),
            ],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        call_next = AsyncMock(return_value=Response(status_code=204))
        user = {
            "id": 1,
            "username": "admin",
            "isAdmin": True,
            "roleKey": "super_admin",
            "roleName": "超级管理员",
            "menuPermissions": [],
            "settingPermissions": [],
        }

        if True:
            with patch("api.middlewares.auth.get_session_user", return_value=user):
                with patch("api.middlewares.auth.verify_session", return_value=True):
                    response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 204)
        call_next.assert_awaited_once()

    def test_protected_api_accessible_with_session(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/system/config",
            "headers": [(b"cookie", f"{WEB_COOKIE_NAME}=test-session".encode("utf-8"))],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        next_response = Response(status_code=200)
        call_next = AsyncMock(return_value=next_response)

        if True:
            with patch("api.middlewares.auth.get_session_user", return_value={
                "id": 1,
                "username": "admin",
                "isAdmin": True,
                "roleKey": "super_admin",
                "roleName": "超级管理员",
                "menuPermissions": [],
                "settingPermissions": [],
            }):
                with patch("api.middlewares.auth.verify_session", return_value=True):
                    response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 200)
        call_next.assert_awaited_once()

    def test_admin_api_uses_admin_session_cookie(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/admin/users",
            "headers": [
                (
                    b"cookie",
                    f"{WEB_COOKIE_NAME}=web-session; {ADMIN_COOKIE_NAME}=admin-session".encode("utf-8"),
                )
            ],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())
        next_response = Response(status_code=200)
        call_next = AsyncMock(return_value=next_response)

        user = {
            "id": 1,
            "username": "admin",
            "isAdmin": True,
            "roleKey": "super_admin",
            "roleName": "超级管理员",
            "menuPermissions": [],
            "settingPermissions": [],
        }
        if True:
            with patch("api.middlewares.auth.get_session_user", side_effect=lambda value: user if value == "admin-session" else None):
                with patch("api.middlewares.auth.verify_session", side_effect=lambda value: value == "admin-session"):
                    response = asyncio.run(middleware.dispatch(request, call_next))

        self.assertEqual(response.status_code, 200)
        call_next.assert_awaited_once()

    def test_auth_settings_requires_session_when_auth_enabled(self) -> None:
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/settings",
            "headers": [],
            "query_string": b"",
            "scheme": "http",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "root_path": "",
        }
        request = Request(scope)
        middleware = AuthMiddleware(app=MagicMock())

        if True:
            response = asyncio.run(middleware.dispatch(request, AsyncMock(return_value=Response(status_code=200))))

        self.assertEqual(response.status_code, 401)

    def test_auth_settings_enable_sets_initial_password_and_logs_in(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\n",
            encoding="utf-8",
        )
        auth.refresh_auth_state()

        response = asyncio.run(
            auth_endpoint.auth_update_settings(
                self._build_request(),
                auth_endpoint.AuthSettingsRequest(
                    authEnabled=True,
                    password="initpass123",
                    passwordConfirm="initpass123",
                ),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"authEnabled":true', response.body)
        self.assertIn(b'"loggedIn":true', response.body)
        self.assertIn(b'"passwordSet":true', response.body)
        self.assertIn(f"{WEB_COOKIE_NAME}=", response.headers["set-cookie"])

    def test_auth_settings_enable_requires_password_when_missing(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\n",
            encoding="utf-8",
        )
        auth.refresh_auth_state()

        response = asyncio.run(
            auth_endpoint.auth_update_settings(
                self._build_request(),
                auth_endpoint.AuthSettingsRequest(authEnabled=True),
            )
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_required"', response.body)

    def test_auth_settings_rechecks_password_before_initial_write(self) -> None:
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\n",
            encoding="utf-8",
        )
        auth.refresh_auth_state()

        with patch.object(
            auth_endpoint,
            "has_stored_password",
            side_effect=[False, True],
        ) as has_password_mock:
            with patch.object(auth_endpoint, "set_initial_password") as set_password_mock:
                response = asyncio.run(
                    auth_endpoint.auth_update_settings(
                        self._build_request(),
                        auth_endpoint.AuthSettingsRequest(
                            authEnabled=True,
                            password="initpass123",
                            passwordConfirm="initpass123",
                        ),
                    )
                )

        self.assertEqual(has_password_mock.call_count, 2)
        set_password_mock.assert_not_called()
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"password_already_set"', response.body)

    def test_auth_settings_ignores_disabled_flag_and_logs_in_with_current_password(self) -> None:
        auth.set_initial_password("passwd6")
        response = asyncio.run(
            auth_endpoint.auth_update_settings(
                self._build_request(),
                auth_endpoint.AuthSettingsRequest(authEnabled=False, currentPassword="passwd6"),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"authEnabled":true', response.body)
        self.assertIn(b'"loggedIn":true', response.body)

    def test_auth_settings_enable_requires_valid_session_cookie_against_toctou(self) -> None:
        """Verify fix for P1 vulnerability: passing authEnabled=True without currentPassword
        must be rejected if the caller lacks a cryptographically valid session, even if
        is_auth_enabled() evaluates to True during handler execution (TOCTOU race condition).
        """
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\n",
            encoding="utf-8",
        )
        auth.set_initial_password("passwd6")

        response = asyncio.run(
            auth_endpoint.auth_update_settings(
                self._build_request(cookies={WEB_COOKIE_NAME: "invalid"}),
                auth_endpoint.AuthSettingsRequest(authEnabled=True),
            )
        )

        # Must be rejected because they lack a valid session + NO current_password.
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'"error":"current_required"', response.body)


if __name__ == "__main__":
    unittest.main()

