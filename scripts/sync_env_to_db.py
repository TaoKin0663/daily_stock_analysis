#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
.env → PostgreSQL system_configs 表 同步脚本

将 .env 中 DB 尚不存在的 key 同步到 system_configs 表。
已有 key 以 DB 为准，不会被覆盖。基础设施 key 会被自动排除。

使用方法：
    python scripts/sync_env_to_db.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保 import 正常
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from dotenv import dotenv_values

# 基础设施 key：与 SystemConfigService._INFRASTRUCTURE_KEYS 保持一致
_INFRASTRUCTURE_KEYS = {
    "DATABASE_URL", "DATA_DIR",
    "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_PORT",
    "POSTGRES_INTERNAL_PORT", "POSTGRES_HOST",
    "ENV_FILE", "DSA_DESKTOP_MODE",
}


def _find_env_path() -> Path:
    """定位 .env 文件路径。"""
    env_file = os.getenv("ENV_FILE")
    if env_file:
        return Path(env_file)
    return _PROJECT_ROOT / ".env"


def _read_env_map(env_path: Path) -> dict[str, str]:
    """读取 .env 文件中的 key-value 映射。"""
    if not env_path.exists():
        print(f"⚠ .env 文件不存在: {env_path}")
        return {}

    values = dotenv_values(env_path)
    return {
        str(key): "" if value is None else str(value)
        for key, value in values.items()
        if key is not None
    }


def main() -> None:
    """主流程：将 .env 中新 key 同步到 PostgreSQL system_configs 表。"""
    env_path = _find_env_path()
    print(f"📄 读取 .env 文件: {env_path}")

    # 1. 读取 .env 配置
    env_map = _read_env_map(env_path)
    if not env_map:
        print("⚠ .env 没有有效配置项，无需同步")
        return

    print(f"   .env 中共 {len(env_map)} 个配置项")

    # 2. 加载数据库（初始化 DatabaseManager 与 session）
    from src.config import setup_env
    setup_env(override=False)

    from src.storage import DatabaseManager
    try:
        db = DatabaseManager.get_instance()
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("   请确认 DATABASE_URL 配置正确且 PostgreSQL 服务已启动")
        sys.exit(1)

    # 3. 读取 DB 中已有配置
    try:
        db_map = db.get_system_config_map()
    except Exception as e:
        print(f"❌ 读取 system_configs 表失败: {e}")
        sys.exit(1)

    # 4. 比对，找出 DB 中不存在的 key
    new_keys: dict[str, str] = {}
    skipped_infra: list[str] = []
    for key, value in env_map.items():
        key_upper = key.upper()
        if key_upper in _INFRASTRUCTURE_KEYS:
            skipped_infra.append(key_upper)
            continue
        if key_upper not in db_map:
            new_keys[key_upper] = value

    # 5. 输出结果
    if skipped_infra:
        print(f"\n⏭ 跳过基础设施 key ({len(skipped_infra)} 个): {', '.join(sorted(skipped_infra))}")

    print(f"\n📊 DB 中已有 {len(db_map)} 个配置项")
    print(f"📊 .env 中新增 {len(new_keys)} 个配置项")

    if not new_keys:
        print("\n✅ 无需同步，.env 中的 key 已全部存在于 DB")
        return

    # 6. 写入 DB
    print("\n🔄 正在同步以下配置项到 DB:")
    for key in sorted(new_keys.keys()):
        # 敏感信息脱敏显示
        value = new_keys[key]
        if any(hint in key.upper() for hint in ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "KEY")):
            display_value = value[:4] + "****" if len(value) > 4 else "****"
        else:
            display_value = value
        print(f"   + {key} = {display_value}")

    try:
        changed = db.upsert_system_config_map(new_keys)
        print(f"\n✅ 同步完成，成功写入 {len(changed)} 个配置项")
    except Exception as e:
        print(f"\n❌ 写入 DB 失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
