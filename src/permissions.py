# -*- coding: utf-8 -*-
"""Permission definitions shared by API and clients."""

from __future__ import annotations

from typing import Any, Dict, List

from src.core.config_registry import (
    get_category_definitions,
    get_field_definition,
    get_registered_field_keys,
)

SUPER_ADMIN_ROLE_KEY = "super_admin"
DEFAULT_USER_ROLE_KEY = "user"

# These are C-end dsa-web menu permissions. dsa-admin is restricted by admin
# identity and is intentionally not part of role menu authorization.
MENU_ITEMS: List[Dict[str, str]] = [
    {"key": "home", "label": "首页", "path": "/"},
    {"key": "chat", "label": "问股", "path": "/chat"},
    {"key": "portfolio", "label": "持仓", "path": "/portfolio"},
    {"key": "backtest", "label": "回测", "path": "/backtest"},
    {"key": "payment", "label": "积分", "path": "/payment"},
    {"key": "settings", "label": "设置", "path": "/settings"},
]

ALL_MENU_KEYS = [item["key"] for item in MENU_ITEMS]
DEFAULT_USER_MENU_KEYS = ["home", "chat", "portfolio", "backtest", "payment", "settings"]
ADMIN_MENU_KEYS = ALL_MENU_KEYS

def _build_setting_items() -> List[Dict[str, Any]]:
    categories = {
        item["category"]: item
        for item in get_category_definitions()
    }
    items: List[Dict[str, Any]] = []
    for key in get_registered_field_keys():
        field = get_field_definition(key)
        category_key = str(field.get("category") or "uncategorized")
        category = categories.get(category_key, {})
        items.append({
            "key": str(field["key"]),
            "label": str(field.get("title") or field["key"]),
            "category": category_key,
            "categoryLabel": str(category.get("title") or category_key),
            "categoryOrder": int(category.get("display_order") or 999),
            "displayOrder": int(field.get("display_order") or 9999),
        })
    return sorted(items, key=lambda item: (item["categoryOrder"], item["displayOrder"], item["key"]))


SETTING_ITEMS = _build_setting_items()
ALL_SETTING_KEYS = [item["key"] for item in SETTING_ITEMS]
DEFAULT_USER_SETTING_KEYS = [
    key
    for key in get_registered_field_keys()
    if get_field_definition(key).get("access_level") == "user"
]
PLATFORM_SETTING_KEYS = [
    key
    for key in get_registered_field_keys()
    if get_field_definition(key).get("access_level") == "admin"
]
ADMIN_SETTING_KEYS = ALL_SETTING_KEYS


def get_menu_items() -> List[Dict[str, str]]:
    """Return a copy of the fixed C-end menu catalog."""
    return [dict(item) for item in MENU_ITEMS]


def get_setting_items() -> List[Dict[str, Any]]:
    """Return a copy of the configurable C-end settings catalog."""
    allowed = set(DEFAULT_USER_SETTING_KEYS)
    return [dict(item) for item in SETTING_ITEMS if item["key"] in allowed]


def get_platform_setting_items() -> List[Dict[str, Any]]:
    """Return a copy of the full setting catalog managed in dsa-admin (管理员可查看全部设置)."""
    allowed = set(ALL_SETTING_KEYS)
    return [dict(item) for item in SETTING_ITEMS if item["key"] in allowed]


def normalize_menu_keys(menu_keys: List[str] | None) -> List[str]:
    """Keep only known C-end menu keys while preserving catalog order."""
    allowed = set(menu_keys or [])
    return [key for key in ALL_MENU_KEYS if key in allowed]


def normalize_setting_keys(setting_keys: List[str] | None) -> List[str]:
    """Keep only known system setting keys while preserving catalog order."""
    allowed = {str(key).upper() for key in (setting_keys or [])}
    return [key for key in ALL_SETTING_KEYS if key in allowed]
