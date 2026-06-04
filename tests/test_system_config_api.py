# -*- coding: utf-8 -*-
"""Integration tests for system configuration API endpoints."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from tests.litellm_stub import ensure_litellm_stub

ensure_litellm_stub()

from api.v1.endpoints import system_config
from api.v1.schemas.system_config import (
    DiscoverLLMChannelModelsRequest,
    ImportSystemConfigRequest,
    TestLLMChannelRequest,
    UpdateSystemConfigRequest,
)
from src.config import Config
from src.core.config_manager import ConfigManager
from src.permissions import get_platform_setting_items, get_setting_items
from src.services.system_config_service import SystemConfigService
from src.user_context import CurrentUser, use_current_user


class SystemConfigApiTestCase(unittest.TestCase):
    """System config API tests in isolation without loading the full app."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_path = Path(self.temp_dir.name) / ".env"
        self.env_path.write_text(
            "\n".join(
                [
                    "STOCK_LIST=600519,000001",
                    "GEMINI_API_KEY=secret-key-value",
                    "SCHEDULE_TIME=18:00",
                    "LOG_LEVEL=INFO",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DSA_DESKTOP_MODE"] = "true"
        Config.reset_instance()

        self.manager = ConfigManager(env_path=self.env_path)
        self.service = SystemConfigService(manager=self.manager)

    def tearDown(self) -> None:
        Config.reset_instance()
        os.environ.pop("DSA_DESKTOP_MODE", None)
        os.environ.pop("ENV_FILE", None)
        self.temp_dir.cleanup()

    def test_get_config_returns_raw_secret_value(self) -> None:
        payload = system_config.get_system_config(include_schema=True, service=self.service).model_dump(by_alias=True)
        item_map = {item["key"]: item for item in payload["items"]}
        self.assertEqual(item_map["GEMINI_API_KEY"]["value"], "secret-key-value")
        self.assertFalse(item_map["GEMINI_API_KEY"]["is_masked"])

    def test_web_user_config_filters_platform_fields(self) -> None:
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("STOCK_LIST",),
        )
        with use_current_user(current_user):
            payload = system_config.get_system_config(
                include_schema=True,
                service=self.service,
                current_user=current_user,
            ).model_dump(by_alias=True)

        keys = {item["key"] for item in payload["items"]}
        self.assertIn("STOCK_LIST", keys)
        self.assertNotIn("GEMINI_API_KEY", keys)
        self.assertNotIn("SCHEDULE_TIME", keys)

    def test_authorized_user_setting_without_override_does_not_show_platform_value(self) -> None:
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("WECHAT_WEBHOOK_URL",),
        )
        db = MagicMock()
        db.get_system_config_map.return_value = {"WECHAT_WEBHOOK_URL": "https://platform.example/webhook"}
        db.get_user_config_map.return_value = {}
        db.get_system_config_version.return_value = "db:test"

        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            with use_current_user(current_user):
                payload = system_config.get_system_config(
                    include_schema=True,
                    service=self.service,
                    current_user=current_user,
                ).model_dump(by_alias=True)

        item_map = {item["key"]: item for item in payload["items"]}
        self.assertIn("WECHAT_WEBHOOK_URL", item_map)
        self.assertEqual(item_map["WECHAT_WEBHOOK_URL"]["value"], "")

    def test_authorized_empty_user_setting_overrides_platform_value(self) -> None:
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("WECHAT_WEBHOOK_URL",),
        )
        db = MagicMock()
        db.get_system_config_map.return_value = {"WECHAT_WEBHOOK_URL": "https://platform.example/webhook"}
        db.get_user_config_map.return_value = {"WECHAT_WEBHOOK_URL": ""}
        db.get_system_config_version.return_value = "db:test"

        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            with use_current_user(current_user):
                payload = system_config.get_system_config(
                    include_schema=True,
                    service=self.service,
                    current_user=current_user,
                ).model_dump(by_alias=True)

        item_map = {item["key"]: item for item in payload["items"]}
        self.assertIn("WECHAT_WEBHOOK_URL", item_map)
        self.assertEqual(item_map["WECHAT_WEBHOOK_URL"]["value"], "")

    def test_web_user_can_read_and_write_authorized_agent_runtime_config(self) -> None:
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("AGENT_ARCH", "AGENT_MAX_STEPS"),
        )
        db = MagicMock()
        db.get_user_config_map.return_value = {"AGENT_ARCH": "single"}
        db.upsert_user_config_map.return_value = ["AGENT_ARCH"]
        db.get_system_config_version.return_value = "db:test"

        with patch("src.storage.DatabaseManager.get_instance", return_value=db):
            with use_current_user(current_user):
                current = system_config.get_system_config(
                    include_schema=True,
                    service=self.service,
                    current_user=current_user,
                ).model_dump(by_alias=True)
                item_map = {item["key"]: item for item in current["items"]}

                self.assertIn("AGENT_ARCH", item_map)
                self.assertEqual(item_map["AGENT_ARCH"]["schema"]["access_level"], "user")
                self.assertNotIn("AGENT_SKILL_DIR", item_map)

                payload = system_config.update_system_config(
                    request=UpdateSystemConfigRequest(
                        config_version=current["config_version"],
                        mask_token="******",
                        reload_now=False,
                        items=[{"key": "AGENT_ARCH", "value": "multi"}],
                    ),
                    service=self.service,
                    current_user=current_user,
                ).model_dump()

        self.assertEqual(payload["applied_count"], 1)
        db.upsert_user_config_map.assert_called_once_with(123, {"AGENT_ARCH": "multi"})
        self.assertNotIn("AGENT_ARCH=multi", self.env_path.read_text(encoding="utf-8"))

    def test_admin_config_shows_all_fields_and_writes_global_env(self) -> None:
        current_user = CurrentUser(
            id=1,
            username="admin",
            is_admin=True,
            account_type="admin",
        )
        with use_current_user(current_user):
            current = system_config.get_system_config(
                include_schema=True,
                service=self.service,
                current_user=current_user,
            ).model_dump(by_alias=True)
            keys = {item["key"] for item in current["items"]}
            self.assertIn("GEMINI_API_KEY", keys)
            self.assertIn("STOCK_LIST", keys)
            self.assertIn("AGENT_ARCH", keys)
            self.assertIn("AGENT_SKILL_DIR", keys)

            payload = system_config.update_system_config(
                request=UpdateSystemConfigRequest(
                    config_version=current["config_version"],
                    mask_token="******",
                    reload_now=False,
                    items=[{"key": "GEMINI_API_KEY", "value": "admin-secret-value"}],
                ),
                service=self.service,
                current_user=current_user,
            ).model_dump()

        self.assertEqual(payload["applied_count"], 1)
        self.assertIn("GEMINI_API_KEY=admin-secret-value", self.env_path.read_text(encoding="utf-8"))

    def test_admin_can_write_user_level_settings_as_platform_defaults(self) -> None:
        current_user = CurrentUser(
            id=1,
            username="admin",
            is_admin=True,
            account_type="admin",
        )
        with use_current_user(current_user):
            current = system_config.get_system_config(
                include_schema=True,
                service=self.service,
                current_user=current_user,
            ).model_dump(by_alias=True)

            payload = system_config.update_system_config(
                request=UpdateSystemConfigRequest(
                    config_version=current["config_version"],
                    mask_token="******",
                    reload_now=False,
                    items=[{"key": "STOCK_LIST", "value": "600519,300750"}],
                ),
                service=self.service,
                current_user=current_user,
            ).model_dump()

        self.assertEqual(payload["applied_count"], 1)
        self.assertIn("STOCK_LIST=600519,300750", self.env_path.read_text(encoding="utf-8"))

    def test_web_user_cannot_write_platform_config(self) -> None:
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("STOCK_LIST",),
        )
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()
        with self.assertRaises(HTTPException) as context:
            system_config.update_system_config(
                request=UpdateSystemConfigRequest(
                    config_version=current["config_version"],
                    items=[{"key": "GEMINI_API_KEY", "value": "blocked"}],
                ),
                service=self.service,
                current_user=current_user,
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["error"], "setting_permission_denied")

    def test_web_user_cannot_write_agent_config_without_setting_permission(self) -> None:
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("STOCK_LIST",),
        )
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()
        with self.assertRaises(HTTPException) as context:
            system_config.update_system_config(
                request=UpdateSystemConfigRequest(
                    config_version=current["config_version"],
                    items=[{"key": "AGENT_ARCH", "value": "multi"}],
                ),
                service=self.service,
                current_user=current_user,
            )

        self.assertEqual(context.exception.status_code, 403)
        self.assertEqual(context.exception.detail["error"], "setting_permission_denied")

    def test_agent_runtime_fields_are_in_all_setting_catalogs(self) -> None:
        user_setting_keys = {item["key"] for item in get_setting_items()}
        platform_setting_keys = {item["key"] for item in get_platform_setting_items()}

        for key in {
            "AGENT_MODE",
            "AGENT_MAX_STEPS",
            "AGENT_ARCH",
            "AGENT_ORCHESTRATOR_MODE",
            "AGENT_ORCHESTRATOR_TIMEOUT_S",
            "AGENT_DEEP_RESEARCH_BUDGET",
            "AGENT_DEEP_RESEARCH_TIMEOUT",
            "AGENT_MEMORY_ENABLED",
            "AGENT_SKILL_AUTOWEIGHT",
        }:
            self.assertIn(key, user_setting_keys)
            self.assertIn(key, platform_setting_keys)

        self.assertNotIn("AGENT_SKILL_DIR", user_setting_keys)
        self.assertIn("AGENT_SKILL_DIR", platform_setting_keys)

    def test_put_config_updates_secret_and_plain_field(self) -> None:
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()
        payload = system_config.update_system_config(
            request=UpdateSystemConfigRequest(
                config_version=current["config_version"],
                mask_token="******",
                reload_now=False,
                items=[
                    {"key": "GEMINI_API_KEY", "value": "new-secret-value"},
                    {"key": "STOCK_LIST", "value": "600519,300750"},
                ],
            ),
            service=self.service,
        ).model_dump()

        self.assertEqual(payload["applied_count"], 2)
        self.assertEqual(payload["skipped_masked_count"], 0)

        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("STOCK_LIST=600519,300750", env_content)
        self.assertIn("GEMINI_API_KEY=new-secret-value", env_content)

    def test_put_config_returns_conflict_when_version_is_stale(self) -> None:
        with self.assertRaises(HTTPException) as context:
            system_config.update_system_config(
                request=UpdateSystemConfigRequest(
                    config_version="stale-version",
                    items=[{"key": "STOCK_LIST", "value": "600519"}],
                ),
                service=self.service,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail["error"], "config_version_conflict")

    def test_put_config_preserves_comments_and_blank_lines(self) -> None:
        self.env_path.write_text(
            "\n".join(
                [
                    "# Base settings",
                    "STOCK_LIST=600519,000001",
                    "",
                    "# Secrets",
                    "GEMINI_API_KEY=secret-key-value",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()
        payload = system_config.update_system_config(
            request=UpdateSystemConfigRequest(
                config_version=current["config_version"],
                mask_token="******",
                reload_now=False,
                items=[{"key": "STOCK_LIST", "value": "600519,300750"}],
            ),
            service=self.service,
        ).model_dump()

        self.assertTrue(payload["success"])
        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("# Base settings\n", env_content)
        self.assertIn("\n\n# Secrets\n", env_content)
        self.assertIn("STOCK_LIST=600519,300750\n", env_content)

    def test_put_config_returns_startup_only_schedule_warning(self) -> None:
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()
        payload = system_config.update_system_config(
            request=UpdateSystemConfigRequest(
                config_version=current["config_version"],
                reload_now=True,
                items=[
                    {"key": "RUN_IMMEDIATELY", "value": "false"},
                    {"key": "SCHEDULE_RUN_IMMEDIATELY", "value": "true"},
                ],
            ),
            service=self.service,
        ).model_dump()

        self.assertTrue(payload["success"])
        run_warning = next(
            warning
            for warning in payload["warnings"]
            if "RUN_IMMEDIATELY 已写入 .env" in warning
        )
        schedule_warning = next(
            warning
            for warning in payload["warnings"]
            if "SCHEDULE_RUN_IMMEDIATELY" in warning
        )

        self.assertIn("非 schedule 模式", run_warning)
        self.assertNotIn("以 schedule 模式", run_warning)
        self.assertIn("不会自动重建 scheduler", schedule_warning)
        self.assertIn("以 schedule 模式重新启动后生效", schedule_warning)
        self.assertNotIn("它属于启动期单次运行配置", schedule_warning)

    def test_export_desktop_system_config_returns_raw_env_content(self) -> None:
        self.env_path.write_text(
            "# Desktop config\nSTOCK_LIST=600519,000001\nGEMINI_API_KEY=secret-key-value\n",
            encoding="utf-8",
        )

        payload = system_config.export_desktop_system_config(service=self.service).model_dump()

        self.assertEqual(
            payload["content"],
            "# Desktop config\nSTOCK_LIST=600519,000001\nGEMINI_API_KEY=secret-key-value\n",
        )
        self.assertEqual(payload["config_version"], self.manager.get_config_version())

    def test_import_desktop_system_config_merges_updates(self) -> None:
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()

        payload = system_config.import_desktop_system_config(
            request=ImportSystemConfigRequest(
                config_version=current["config_version"],
                content="STOCK_LIST=300750\nCUSTOM_NOTE=desktop backup\n",
                reload_now=False,
            ),
            service=self.service,
        ).model_dump()

        self.assertTrue(payload["success"])
        env_content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("STOCK_LIST=300750\n", env_content)
        self.assertIn("CUSTOM_NOTE=desktop backup\n", env_content)
        self.assertIn("GEMINI_API_KEY=secret-key-value\n", env_content)

    def test_import_desktop_system_config_returns_conflict_when_version_is_stale(self) -> None:
        with self.assertRaises(HTTPException) as context:
            system_config.import_desktop_system_config(
                request=ImportSystemConfigRequest(
                    config_version="stale-version",
                    content="STOCK_LIST=300750\n",
                    reload_now=False,
                ),
                service=self.service,
            )

        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(context.exception.detail["error"], "config_version_conflict")

    def test_import_desktop_system_config_returns_bad_request_for_invalid_content(self) -> None:
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()

        with self.assertRaises(HTTPException) as context:
            system_config.import_desktop_system_config(
                request=ImportSystemConfigRequest(
                    config_version=current["config_version"],
                    content="# comments only\n\n",
                    reload_now=False,
                ),
                service=self.service,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"], "invalid_import_file")

    def test_import_desktop_system_config_returns_bad_request_for_empty_content(self) -> None:
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()

        with self.assertRaises(HTTPException) as context:
            system_config.import_desktop_system_config(
                request=ImportSystemConfigRequest(
                    config_version=current["config_version"],
                    content="",
                    reload_now=False,
                ),
                service=self.service,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["error"], "invalid_import_file")

    def test_desktop_env_endpoints_return_forbidden_outside_desktop_mode(self) -> None:
        os.environ["DSA_DESKTOP_MODE"] = "false"
        current = system_config.get_system_config(include_schema=False, service=self.service).model_dump()

        with self.assertRaises(HTTPException) as export_context:
            system_config.export_desktop_system_config(service=self.service)
        with self.assertRaises(HTTPException) as import_context:
            system_config.import_desktop_system_config(
                request=ImportSystemConfigRequest(
                    config_version=current["config_version"],
                    content="STOCK_LIST=300750\n",
                    reload_now=False,
                ),
                service=self.service,
            )

        self.assertEqual(export_context.exception.status_code, 403)
        self.assertEqual(export_context.exception.detail["error"], "desktop_only_feature")
        self.assertEqual(import_context.exception.status_code, 403)
        self.assertEqual(import_context.exception.detail["error"], "desktop_only_feature")

    def test_test_llm_channel_endpoint_returns_service_payload(self) -> None:
        with patch.object(
            self.service,
            "test_llm_channel",
            return_value={
                "success": True,
                "message": "LLM channel test succeeded",
                "error": None,
                "resolved_protocol": "openai",
                "resolved_model": "openai/gpt-4o-mini",
                "latency_ms": 123,
            },
        ) as mock_test:
            payload = system_config.test_llm_channel(
                request=TestLLMChannelRequest(
                    name="primary",
                    protocol="openai",
                    base_url="https://api.example.com/v1",
                    api_key="sk-test",
                    models=["gpt-4o-mini"],
                ),
                service=self.service,
            ).model_dump()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["resolved_model"], "openai/gpt-4o-mini")
        mock_test.assert_called_once()

    def test_validate_returns_user_facing_model_message_without_internal_env_key_name(self) -> None:
        validation = self.service.validate(
            items=[
                {"key": "LLM_CHANNELS", "value": "primary"},
                {"key": "LLM_PRIMARY_PROTOCOL", "value": "openai"},
                {"key": "LLM_PRIMARY_API_KEY", "value": "sk-test-value"},
                {"key": "LLM_PRIMARY_MODELS", "value": "gpt-4o-mini"},
                {"key": "LITELLM_MODEL", "value": "openai/gpt-4o"},
            ]
        )

        self.assertFalse(validation["valid"])
        issue = next(issue for issue in validation["issues"] if issue["key"] == "LITELLM_MODEL")
        self.assertEqual(issue["code"], "unknown_model")
        self.assertNotIn("LITELLM_MODEL", issue["message"])
        self.assertIn("primary model", issue["message"].lower())

    def test_discover_llm_channel_models_endpoint_returns_service_payload(self) -> None:
        with patch.object(
            self.service,
            "discover_llm_channel_models",
            return_value={
                "success": True,
                "message": "LLM channel model discovery succeeded",
                "error": None,
                "resolved_protocol": "openai",
                "models": ["qwen-plus", "qwen-turbo"],
                "latency_ms": 88,
            },
        ) as mock_discover:
            payload = system_config.discover_llm_channel_models(
                request=DiscoverLLMChannelModelsRequest(
                    name="dashscope",
                    protocol="openai",
                    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                    api_key="sk-test",
                ),
                service=self.service,
            ).model_dump()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["models"], ["qwen-plus", "qwen-turbo"])
        mock_discover.assert_called_once()


if __name__ == "__main__":
    unittest.main()
