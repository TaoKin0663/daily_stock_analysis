# -*- coding: utf-8 -*-
"""Unit tests for mandatory auth setupState contract."""

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from starlette.requests import Request

import src.auth as auth
from api.v1.endpoints.auth import AuthSettingsRequest, auth_status, auth_update_settings
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._session_secret = None
    auth._rate_limit = {}


def _make_request(*, cookies: dict[str, str] | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/auth/status",
        "raw_path": b"/api/v1/auth/status",
        "query_string": b"",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


class AuthStatusSetupStateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self._original_database_path = os.environ.get("DATABASE_PATH")
        self._original_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_PATH"] = str(self.data_dir / "auth_status.db")
        os.environ.pop("DATABASE_URL", None)
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self._data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self._data_dir_patcher.start()

        self.env_path = self.data_dir / ".env"
        self.env_path.write_text("", encoding="utf-8")
        self._env_patcher = patch.dict(os.environ, {"ENV_FILE": str(self.env_path)})
        self._env_patcher.start()

    def tearDown(self) -> None:
        self._env_patcher.stop()
        self._data_dir_patcher.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if self._original_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = self._original_database_path
        if self._original_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = self._original_database_url
        Config.reset_instance()
        DatabaseManager.reset_instance()
        _reset_auth_globals()
        self.temp_dir.cleanup()

    def test_status_no_password_still_reports_auth_enabled(self) -> None:
        request = _make_request()

        data = asyncio.run(auth_status(request))

        self.assertEqual(data["setupState"], "no_password")
        self.assertTrue(data["authEnabled"])
        self.assertFalse(data["passwordSet"])

    def test_status_existing_password_reports_enabled(self) -> None:
        auth.set_initial_password("password123")
        request = _make_request()

        data = asyncio.run(auth_status(request))

        self.assertEqual(data["setupState"], "enabled")
        self.assertTrue(data["authEnabled"])
        self.assertTrue(data["passwordSet"])

    def test_settings_update_returns_setup_state(self) -> None:
        request = _make_request()
        body = AuthSettingsRequest(
            authEnabled=True,
            password="newpassword123",
            passwordConfirm="newpassword123",
        )

        with patch("api.v1.endpoints.auth.create_session", return_value="mock.session.sig"):
            with patch("api.v1.endpoints.auth._get_auth_status_dict") as mock_status_dict:
                mock_status_dict.return_value = {
                    "authEnabled": True,
                    "loggedIn": True,
                    "passwordSet": True,
                    "passwordChangeable": True,
                    "setupState": "enabled",
                    "currentUser": None,
                }

                response = asyncio.run(auth_update_settings(request, body))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["setupState"], "enabled")
        self.assertTrue(data["authEnabled"])

if __name__ == "__main__":
    unittest.main()
