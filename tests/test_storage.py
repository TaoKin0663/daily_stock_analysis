# -*- coding: utf-8 -*-
import unittest
import sys
import os
import tempfile
import threading
import sqlite3
from datetime import date
from unittest.mock import patch

import pandas as pd
from sqlalchemy import and_, delete, select
from sqlalchemy.sql import func

# Ensure src module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.auth import register_user
from src.config import Config
from src.storage import DatabaseManager, Role, RoleSettingPermission, StockDaily

class TestStorage(unittest.TestCase):
    
    def test_parse_sniper_value(self):
        """测试解析狙击点位数值"""
        
        # 1. 正常数值
        self.assertEqual(DatabaseManager._parse_sniper_value(100), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value(100.5), 100.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("100"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("100.5"), 100.5)
        
        # 2. 包含中文描述和"元"
        self.assertEqual(DatabaseManager._parse_sniper_value("建议在 100 元附近买入"), 100.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("价格：100.5元"), 100.5)
        
        # 3. 包含干扰数字（修复的Bug场景）
        # 之前 "MA5" 会被错误提取为 5.0，现在应该提取 "元" 前面的 100
        text_bug = "无法给出。需等待MA5数据恢复，在股价回踩MA5且乖离率<2%时考虑100元"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_bug), 100.0)
        
        # 4. 更多干扰场景
        text_complex = "MA10为20.5，建议在30元买入"
        self.assertEqual(DatabaseManager._parse_sniper_value(text_complex), 30.0)
        
        text_multiple = "支撑位10元，阻力位20元" # 应该提取最后一个"元"前面的数字，即20，或者更复杂的逻辑？
        # 当前逻辑是找最后一个冒号，然后找之后的第一个"元"，提取中间的数字。
        # 测试没有冒号的情况
        self.assertEqual(DatabaseManager._parse_sniper_value("30元"), 30.0)
        
        # 测试多个数字在"元"之前
        self.assertEqual(DatabaseManager._parse_sniper_value("MA5 10 20元"), 20.0)
        
        # 5. Fallback: no "元" character — extracts last non-MA number
        self.assertEqual(DatabaseManager._parse_sniper_value("102.10-103.00（MA5附近）"), 103.0)
        self.assertEqual(DatabaseManager._parse_sniper_value("97.62-98.50（MA10附近）"), 98.5)
        self.assertEqual(DatabaseManager._parse_sniper_value("93.40下方（MA20支撑）"), 93.4)
        self.assertEqual(DatabaseManager._parse_sniper_value("108.00-110.00（前期高点阻力）"), 110.0)

        # 6. 无效输入
        self.assertIsNone(DatabaseManager._parse_sniper_value(None))
        self.assertIsNone(DatabaseManager._parse_sniper_value(""))
        self.assertIsNone(DatabaseManager._parse_sniper_value("没有数字"))
        self.assertIsNone(DatabaseManager._parse_sniper_value("MA5但没有元"))

        # 7. 回归：括号内技术指标数字不应被提取
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.52-1.53 (回踩MA5/10附近)"), 10.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20支撑)"), 20.0)
        self.assertNotEqual(DatabaseManager._parse_sniper_value("1.49-1.50(MA60附近企稳)"), 60.0)
        # 验证正确值在区间内
        self.assertIn(DatabaseManager._parse_sniper_value("1.52-1.53 (回踩MA5/10附近)"), [1.52, 1.53])
        self.assertIn(DatabaseManager._parse_sniper_value("1.55-1.56(MA5/M20支撑)"), [1.55, 1.56])
        self.assertIn(DatabaseManager._parse_sniper_value("1.49-1.50(MA60附近企稳)"), [1.49, 1.50])

    def test_get_chat_sessions_prefix_is_scoped_by_colon_boundary(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("telegram_12345:chat", "user", "first user")
        db.save_conversation_message("telegram_123456:chat", "user", "second user")

        sessions = db.get_chat_sessions(session_prefix="telegram_12345")

        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], "telegram_12345:chat")

        DatabaseManager.reset_instance()

    def test_get_chat_sessions_can_include_legacy_exact_session_id(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        db.save_conversation_message("feishu_u1", "user", "legacy chat")
        db.save_conversation_message("feishu_u1:ask_600519", "user", "ask session")

        sessions = db.get_chat_sessions(
            session_prefix="feishu_u1:",
            extra_session_ids=["feishu_u1"],
        )

        self.assertEqual({item["session_id"] for item in sessions}, {"feishu_u1", "feishu_u1:ask_600519"})

        DatabaseManager.reset_instance()

    def test_list_user_accounts_includes_credit_balances(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        funded = db.create_user(username="funded", password_salt=b"salt", password_hash=b"hash")
        empty = db.create_user(username="empty", password_salt=b"salt", password_hash=b"hash")
        db.add_credit_transaction(user_id=int(funded.id), credit_amount=250, reason="test top-up")

        users = {item["username"]: item for item in db.list_user_accounts()}

        self.assertEqual(users["funded"]["creditBalance"], 250)
        self.assertEqual(users["funded"]["lifetimeCredits"], 250)
        self.assertEqual(users["empty"]["creditBalance"], 0)
        self.assertEqual(users["empty"]["lifetimeCredits"], 0)
        self.assertNotIn("admin", users)

        DatabaseManager.reset_instance()

    def test_default_user_role_does_not_reseed_removed_setting_permissions(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")

        with db.session_scope() as session:
            role = session.execute(select(Role).where(Role.key == "user")).scalar_one()
            session.execute(
                delete(RoleSettingPermission).where(
                    RoleSettingPermission.role_id == int(role.id),
                    RoleSettingPermission.setting_key == "AGENT_ARCH",
                )
            )

        db.ensure_default_roles()
        role_payload = db.get_role_by_key("user")

        self.assertNotIn("AGENT_ARCH", role_payload["settingKeys"])
        self.assertNotIn("AGENT_SKILL_DIR", role_payload["settingKeys"])

        DatabaseManager.reset_instance()

    def test_role_update_persists_removed_notification_setting_permission(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        role = db.get_role_by_key("user")
        self.assertIsNotNone(role)
        self.assertIn("EMAIL_SENDER", role["settingKeys"])

        next_setting_keys = [key for key in role["settingKeys"] if key != "EMAIL_SENDER"]
        updated = db.update_role_record(int(role["id"]), setting_keys=next_setting_keys)
        self.assertIsNotNone(updated)
        self.assertNotIn("EMAIL_SENDER", updated["settingKeys"])

        db.ensure_default_roles()
        reloaded = db.get_role_by_key("user")
        self.assertNotIn("EMAIL_SENDER", reloaded["settingKeys"])

        DatabaseManager.reset_instance()

    def test_file_sqlite_enables_wal_and_busy_timeout(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_pragmas.db")
        original_env = {
            "DATABASE_PATH": os.environ.get("DATABASE_PATH"),
            "SQLITE_BUSY_TIMEOUT_MS": os.environ.get("SQLITE_BUSY_TIMEOUT_MS"),
            "SQLITE_WAL_ENABLED": os.environ.get("SQLITE_WAL_ENABLED"),
        }

        try:
            os.environ["DATABASE_PATH"] = db_path
            os.environ["SQLITE_BUSY_TIMEOUT_MS"] = "1234"
            os.environ["SQLITE_WAL_ENABLED"] = "true"
            Config.reset_instance()
            DatabaseManager.reset_instance()

            db = DatabaseManager.get_instance()
            with db.get_session() as session:
                journal_mode = session.connection().exec_driver_sql("PRAGMA journal_mode").scalar()
                busy_timeout = session.connection().exec_driver_sql("PRAGMA busy_timeout").scalar()

            self.assertEqual(str(journal_mode).lower(), "wal")
            self.assertEqual(int(busy_timeout), 1234)
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            temp_dir.cleanup()

    def test_get_instance_reinitializes_stale_uninitialized_singleton(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_reinit.db")
        original_database_path = os.environ.get("DATABASE_PATH")

        try:
            os.environ["DATABASE_PATH"] = db_path
            Config.reset_instance()
            DatabaseManager.reset_instance()

            stale = object.__new__(DatabaseManager)
            stale._initialized = False
            DatabaseManager._instance = stale

            db = DatabaseManager.get_instance()

            self.assertIs(db, stale)
            self.assertTrue(db._initialized)
            with db.get_session() as session:
                self.assertIsNotNone(session)
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            if original_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = original_database_path
            temp_dir.cleanup()

    def test_legacy_users_table_is_migrated_for_registration(self):
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "legacy_users.db")
        original_database_path = os.environ.get("DATABASE_PATH")

        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE
                )
                """
            )
            conn.execute("INSERT INTO users (username) VALUES (?)", ("admin",))
            conn.commit()
        finally:
            conn.close()

        try:
            os.environ["DATABASE_PATH"] = db_path
            Config.reset_instance()
            DatabaseManager.reset_instance()

            db = DatabaseManager.get_instance()
            row = db.get_user_by_username("admin")
            self.assertIsNotNone(row)
            self.assertIsNotNone(row.password_salt)
            self.assertIsNotNone(row.password_hash)

            user, err = register_user("legacy_user", "legacyPass123")
            self.assertIsNone(err)
            self.assertIsNotNone(user)
        finally:
            DatabaseManager.reset_instance()
            Config.reset_instance()
            if original_database_path is None:
                os.environ.pop("DATABASE_PATH", None)
            else:
                os.environ["DATABASE_PATH"] = original_database_path
            temp_dir.cleanup()

    def test_sqlite_write_transactions_begin_immediate(self):
        DatabaseManager.reset_instance()
        db = DatabaseManager(db_url="sqlite:///:memory:")
        session = db.get_session()
        connection = session.connection()

        try:
            with patch.object(db, "get_session", return_value=session):
                with patch.object(connection, "exec_driver_sql", wraps=connection.exec_driver_sql) as mock_exec:
                    result = db._run_write_transaction("unit-test", lambda current_session: 7)

            self.assertEqual(result, 7)
            self.assertTrue(
                any(call.args == ("BEGIN IMMEDIATE",) for call in mock_exec.call_args_list)
            )
        finally:
            DatabaseManager.reset_instance()

    def test_save_daily_data_sqlite_concurrent_same_code_date_counts_only_new_rows(self):
        DatabaseManager.reset_instance()
        temp_dir = tempfile.TemporaryDirectory()
        db_path = os.path.join(temp_dir.name, "sqlite_daily_concurrency.db")
        db = DatabaseManager(db_url=f"sqlite:///{db_path}")

        results = []
        results_lock = threading.Lock()
        start_barrier = threading.Barrier(2)

        def worker() -> None:
            start_barrier.wait()
            count = db.save_daily_data(
                pd.DataFrame(
                    [
                        {
                            'date': date(2026, 4, 1),
                            'open': 10,
                            'high': 11,
                            'low': 9,
                            'close': 10.5,
                            'volume': 100,
                            'amount': 1050,
                            'pct_chg': 1.2,
                            'ma5': 10.1,
                            'ma10': 10.2,
                            'ma20': 10.3,
                            'volume_ratio': 1.0,
                        }
                    ]
                ),
                code='600519',
                data_source='test',
            )
            with results_lock:
                results.append(count)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        try:
            self.assertCountEqual(results, [1, 0])

            with db.get_session() as session:
                total = session.execute(
                    select(func.count()).select_from(StockDaily).where(
                        and_(
                            StockDaily.code == '600519',
                            StockDaily.date == date(2026, 4, 1),
                        )
                    )
                ).scalar()

            self.assertEqual(total, 1)
        finally:
            DatabaseManager.reset_instance()
            temp_dir.cleanup()

if __name__ == '__main__':
    unittest.main()
