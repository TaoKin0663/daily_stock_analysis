# -*- coding: utf-8 -*-
"""Tests for backward-compatible config env aliases and TickFlow loading."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.config import Config, clear_user_config_cache, get_config, setup_env
from src.user_context import CurrentUser, use_current_user


class ConfigEnvCompatibilityTestCase(unittest.TestCase):
    def tearDown(self):
        clear_user_config_cache()
        Config.reset_instance()

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_load_from_env_reads_tickflow_api_key(
        self, _mock_parse_litellm_yaml, _mock_setup_env
    ):
        with patch.dict(
            os.environ,
            {
                "STOCK_LIST": "600519",
                "TICKFLOW_API_KEY": "tf-secret",
            },
            clear=True,
        ):
            config = Config._load_from_env()

        self.assertEqual(config.tickflow_api_key, "tf-secret")

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_load_from_env_keeps_default_behavior_without_tickflow_api_key(
        self, _mock_parse_litellm_yaml, _mock_setup_env
    ):
        with patch.dict(
            os.environ,
            {
                "STOCK_LIST": "600519",
            },
            clear=True,
        ):
            config = Config._load_from_env()

        self.assertIsNone(config.tickflow_api_key)
        self.assertEqual(
            config.realtime_source_priority,
            "tencent,akshare_sina,efinance,akshare_em",
        )

    def test_database_url_takes_precedence_when_configured(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+psycopg://dsa:dsa_password@localhost:5435/daily_stock_analysis",
                "DATABASE_PATH": "./data/stock_analysis.db",
            },
            clear=True,
        ):
            database_url = Config._resolve_database_url(
                preexisting_database_url=os.environ.get("DATABASE_URL"),
                preexisting_database_path=os.environ.get("DATABASE_PATH"),
            )

        self.assertEqual(
            database_url,
            "postgresql+psycopg://dsa:dsa_password@localhost:5435/daily_stock_analysis",
        )

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_authorized_empty_user_webhook_does_not_fallback_to_platform(
        self, _mock_parse_litellm_yaml, _mock_setup_env
    ):
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("WECHAT_WEBHOOK_URL",),
        )
        db = MagicMock()
        db.get_system_config_map.return_value = {
            "STOCK_LIST": "600519",
            "WECHAT_WEBHOOK_URL": "https://platform.example/webhook",
        }
        db.get_user_config_map.return_value = {"WECHAT_WEBHOOK_URL": ""}

        with patch.dict(os.environ, {"STOCK_LIST": "600519"}, clear=True):
            with patch("src.storage.DatabaseManager") as db_manager:
                db_manager._instance = MagicMock(_initialized=True)
                db_manager.get_instance.return_value = db
                with use_current_user(current_user):
                    clear_user_config_cache(123)
                    config = get_config()

        self.assertEqual(config.wechat_webhook_url, "")

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_unauthorized_user_webhook_uses_platform_fallback(
        self, _mock_parse_litellm_yaml, _mock_setup_env
    ):
        current_user = CurrentUser(
            id=123,
            username="alice",
            account_type="web",
            setting_permissions=("STOCK_LIST",),
        )
        db = MagicMock()
        db.get_system_config_map.return_value = {
            "STOCK_LIST": "600519",
            "WECHAT_WEBHOOK_URL": "https://platform.example/webhook",
        }
        db.get_user_config_map.return_value = {"WECHAT_WEBHOOK_URL": ""}

        with patch.dict(os.environ, {"STOCK_LIST": "600519"}, clear=True):
            with patch("src.storage.DatabaseManager") as db_manager:
                db_manager._instance = MagicMock(_initialized=True)
                db_manager.get_instance.return_value = db
                with use_current_user(current_user):
                    clear_user_config_cache(123)
                    config = get_config()

        self.assertEqual(config.wechat_webhook_url, "https://platform.example/webhook")

    def test_explicit_database_path_can_override_dotenv_database_url(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+psycopg://dsa:dsa_password@localhost:5435/daily_stock_analysis",
                "DATABASE_PATH": "./data/test.db",
            },
            clear=True,
        ):
            database_url = Config._resolve_database_url(
                preexisting_database_url=None,
                preexisting_database_path="./data/test.db",
            )

        self.assertEqual(database_url, "")

    def test_env_file_database_path_can_override_stale_database_url(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            db_path = Path(temp_dir) / "test.db"
            env_path.write_text(f"DATABASE_PATH={db_path}\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                    "DATABASE_URL": "postgresql+psycopg://dsa:dsa_password@localhost:5435/daily_stock_analysis",
                    "DATABASE_PATH": str(db_path),
                },
                clear=True,
            ):
                database_url = Config._resolve_database_url(
                    preexisting_database_url=os.environ.get("DATABASE_URL"),
                    preexisting_database_path=os.environ.get("DATABASE_PATH"),
                )

        self.assertEqual(database_url, "")

    def test_postgres_host_builds_database_url_when_explicit_url_is_empty(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "",
                "POSTGRES_HOST": "postgres",
                "POSTGRES_INTERNAL_PORT": "5432",
                "POSTGRES_DB": "daily_stock_analysis",
                "POSTGRES_USER": "dsa",
                "POSTGRES_PASSWORD": "dsa_password",
            },
            clear=True,
        ):
            database_url = Config._resolve_database_url(
                preexisting_database_url="",
                preexisting_database_path=None,
            )

        self.assertEqual(
            database_url,
            "postgresql+psycopg://dsa:dsa_password@postgres:5432/daily_stock_analysis",
        )

    def test_postgres_host_rewrites_localhost_database_url_for_container(self):
        with patch.dict(
            os.environ,
            {
                "DATABASE_URL": "postgresql+psycopg://dsa:dsa_password@localhost:5435/daily_stock_analysis",
                "POSTGRES_HOST": "postgres",
                "POSTGRES_INTERNAL_PORT": "5432",
            },
            clear=True,
        ):
            database_url = Config._resolve_database_url(
                preexisting_database_url=os.environ.get("DATABASE_URL"),
                preexisting_database_path=None,
            )

        self.assertEqual(
            database_url,
            "postgresql+psycopg://dsa:dsa_password@postgres:5432/daily_stock_analysis",
        )

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_schedule_run_immediately_falls_back_to_legacy_run_immediately(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "false",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertFalse(config.schedule_run_immediately)
        self.assertFalse(config.run_immediately)

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_schedule_run_immediately_prefers_schedule_specific_setting(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "false",
            "SCHEDULE_RUN_IMMEDIATELY": "true",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertTrue(config.schedule_run_immediately)
        self.assertFalse(config.run_immediately)

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_empty_legacy_run_immediately_stays_false_when_schedule_alias_is_unset(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertFalse(config.schedule_run_immediately)
        self.assertFalse(config.run_immediately)

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_empty_schedule_run_immediately_stays_false_without_falling_back(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "RUN_IMMEDIATELY": "true",
            "SCHEDULE_RUN_IMMEDIATELY": "",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertFalse(config.schedule_run_immediately)
        self.assertTrue(config.run_immediately)

    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_blank_schedule_time_falls_back_to_default(
        self,
        _mock_parse_yaml,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "STOCK_LIST=600519",
                        "SCHEDULE_TIME=",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                },
                clear=True,
            ):
                config = Config._load_from_env()

        self.assertEqual(config.schedule_time, "18:00")

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_report_language_prefers_preexisting_process_env_over_env_file(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("REPORT_LANGUAGE=zh\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                    "REPORT_LANGUAGE": "en",
                },
                clear=True,
            ):
                config = Config._load_from_env()

        self.assertEqual(config.report_language, "en")

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_report_language_uses_env_file_when_process_env_is_absent(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("REPORT_LANGUAGE=en\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                },
                clear=True,
            ):
                config = Config._load_from_env()

        self.assertEqual(config.report_language, "en")

    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_runtime_mutable_keys_reload_from_updated_env_file_after_runtime_refresh(
        self,
        _mock_parse_yaml,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "STOCK_LIST=600519",
                        "SCHEDULE_ENABLED=false",
                        "SCHEDULE_TIME=18:00",
                        "RUN_IMMEDIATELY=true",
                        "SCHEDULE_RUN_IMMEDIATELY=false",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                    "STOCK_LIST": "600519",
                    "SCHEDULE_ENABLED": "false",
                    "SCHEDULE_TIME": "18:00",
                    "RUN_IMMEDIATELY": "true",
                    "SCHEDULE_RUN_IMMEDIATELY": "false",
                },
                clear=True,
            ):
                Config._load_from_env()
                env_path.write_text(
                    "\n".join(
                        [
                            "STOCK_LIST=300750,TSLA",
                            "SCHEDULE_ENABLED=true",
                            "SCHEDULE_TIME=09:30",
                            "RUN_IMMEDIATELY=false",
                            "SCHEDULE_RUN_IMMEDIATELY=true",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
                Config.reset_instance()
                setup_env(override=True)
                config = Config._load_from_env()

        self.assertEqual(config.stock_list, ["300750", "TSLA"])
        self.assertTrue(config.schedule_enabled)
        self.assertEqual(config.schedule_time, "09:30")
        self.assertFalse(config.run_immediately)
        self.assertTrue(config.schedule_run_immediately)

    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_runtime_mutable_keys_prefer_process_env_when_values_differ(
        self,
        _mock_parse_yaml,
    ) -> None:
        """When process env explicitly sets a WEBUI-mutable key to a value
        that differs from .env (e.g. via docker-compose ``environment:``),
        the process env must win because ``_capture_bootstrap_runtime_env_overrides``
        runs before dotenv loads and the mismatch proves an intentional override.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "STOCK_LIST=300750,TSLA",
                        "SCHEDULE_ENABLED=true",
                        "SCHEDULE_TIME=09:30",
                        "RUN_IMMEDIATELY=false",
                        "SCHEDULE_RUN_IMMEDIATELY=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                    "STOCK_LIST": "600519,000001",
                    "SCHEDULE_ENABLED": "false",
                    "SCHEDULE_TIME": "18:00",
                    "RUN_IMMEDIATELY": "true",
                    "SCHEDULE_RUN_IMMEDIATELY": "false",
                },
                clear=True,
            ):
                config = Config._load_from_env()

        # Explicit process env overrides win when values differ from .env
        self.assertEqual(config.stock_list, ["600519", "000001"])
        self.assertFalse(config.schedule_enabled)
        self.assertEqual(config.schedule_time, "18:00")
        self.assertTrue(config.run_immediately)
        self.assertFalse(config.schedule_run_immediately)

    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_runtime_mutable_keys_use_process_env_when_absent_from_file(
        self,
        _mock_parse_yaml,
    ) -> None:
        """When a WEBUI-mutable key exists only in process env (not in .env),
        it IS a genuine explicit override and must be honoured.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            # .env has no STOCK_LIST or SCHEDULE_* keys at all
            env_path.write_text("LOG_LEVEL=INFO\n", encoding="utf-8")

            with patch.dict(
                os.environ,
                {
                    "ENV_FILE": str(env_path),
                    "STOCK_LIST": "600519,000001",
                },
                clear=True,
            ):
                config = Config._load_from_env()

        self.assertEqual(config.stock_list, ["600519", "000001"])

    def test_parse_report_language_accepts_known_alias_without_warning(self) -> None:
        with self.assertNoLogs("src.config", level="WARNING"):
            parsed = Config._parse_report_language("zh-cn")

        self.assertEqual(parsed, "zh")

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_invalid_numeric_env_values_fall_back_to_defaults(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "AGENT_ORCHESTRATOR_TIMEOUT_S": "oops",
            "NEWS_MAX_AGE_DAYS": "bad",
            "MAX_WORKERS": "",
            "WEBUI_PORT": "invalid",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertEqual(config.agent_orchestrator_timeout_s, 600)
        self.assertEqual(config.news_max_age_days, 3)
        self.assertEqual(config.max_workers, 3)
        self.assertEqual(config.webui_port, 8000)

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_stock_email_groups_support_case_insensitive_env_names(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        env = {
            "STOCK_LIST": "600519,300750",
            "Stock_Group_1": "600519",
            "Email_Group_1": "user1@example.com",
            "stock_group_2": "300750",
            "email_group_2": "user2@example.com",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        self.assertEqual(
            config.stock_email_groups,
            [
                (["600519"], ["user1@example.com"]),
                (["300750"], ["user2@example.com"]),
            ],
        )

    @patch("src.config.setup_env")
    @patch.object(Config, "_parse_litellm_yaml", return_value=[])
    def test_stock_email_groups_normalize_codes_at_parse_time(
        self,
        _mock_parse_yaml,
        _mock_setup_env,
    ) -> None:
        """STOCK_GROUP codes are canonicalized at parse time so that
        runtime email routing matches the same equivalence used in
        validate_structured()."""
        env = {
            "STOCK_LIST": "600519,HK00700",
            "STOCK_GROUP_1": "SH600519,1810.HK",
            "EMAIL_GROUP_1": "user@example.com",
        }

        with patch.dict(os.environ, env, clear=True):
            config = Config._load_from_env()

        stocks, emails = config.stock_email_groups[0]
        self.assertEqual(stocks, ["600519", "HK01810"])
        self.assertEqual(emails, ["user@example.com"])


if __name__ == "__main__":
    unittest.main()
