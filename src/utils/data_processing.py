# -*- coding: utf-8 -*-
"""
Shared data parsing and normalization helpers.
"""

import json
from typing import Any, Dict, List, Optional


_MODEL_PLACEHOLDER_VALUES = {"unknown", "error", "none", "null", "n/a"}


def normalize_model_used(value: Any) -> Optional[str]:
    """Normalize placeholder/empty model values to None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in _MODEL_PLACEHOLDER_VALUES:
        return None
    return text


def parse_json_field(value: Any) -> Any:
    """Best-effort JSON parse for string values; passthrough for others."""
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return value
    return value


def _non_empty_dict(value: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(value, dict):
        return None
    return value if value else None


def _normalize_belong_boards(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is None:
            continue
        name_text = str(name).strip()
        if not name_text:
            continue
        board = {"name": name_text}
        if item.get("code") is not None:
            code_text = str(item.get("code")).strip()
            if code_text:
                board["code"] = code_text
        if item.get("type") is not None:
            type_text = str(item.get("type")).strip()
            if type_text:
                board["type"] = type_text
        normalized.append(board)
    return normalized


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.endswith("%"):
                text = text[:-1].strip()
            return float(text)
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if not text:
                return None
            return int(float(text))
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"none", "null", "nan", "n/a", "--"}:
        return None
    return text


def _first_text(*values: Any) -> Optional[str]:
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return None


def _normalize_sector_ranking_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name is None:
            continue
        name_text = str(name).strip()
        if not name_text:
            continue
        ranking_item: Dict[str, Any] = {"name": name_text}
        change_pct = _safe_float(item.get("change_pct"))
        if change_pct is not None:
            ranking_item["change_pct"] = change_pct
        normalized.append(ranking_item)
    return normalized


def _normalize_sector_rankings(value: Any) -> Optional[Dict[str, List[Dict[str, Any]]]]:
    if not isinstance(value, dict):
        return None

    return {
        "top": _normalize_sector_ranking_items(value.get("top")),
        "bottom": _normalize_sector_ranking_items(value.get("bottom")),
    }


def extract_fundamental_context(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Optional[Dict[str, Any]]:
    """
    Resolve fundamental_context from context snapshot, with optional fallback payload.
    """
    snapshot_obj = parse_json_field(context_snapshot)
    if isinstance(snapshot_obj, dict):
        enhanced = snapshot_obj.get("enhanced_context")
        if isinstance(enhanced, dict):
            fundamental = enhanced.get("fundamental_context")
            if isinstance(fundamental, dict):
                return fundamental
        direct_fundamental = snapshot_obj.get("fundamental_context")
        if isinstance(direct_fundamental, dict):
            return direct_fundamental
        if any(key in snapshot_obj for key in ("earnings", "growth", "valuation", "company_profile")):
            return snapshot_obj

    fallback_obj = parse_json_field(fallback_fundamental_payload)
    if isinstance(fallback_obj, dict):
        return fallback_obj
    return None


def extract_fundamental_detail_fields(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Extract stable API-facing financial and dividend blocks from fundamental_context.
    """
    fundamental_ctx = extract_fundamental_context(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    if not isinstance(fundamental_ctx, dict):
        return {"financial_report": None, "dividend_metrics": None}

    earnings_block = fundamental_ctx.get("earnings")
    earnings_data = earnings_block.get("data") if isinstance(earnings_block, dict) else None
    if not isinstance(earnings_data, dict):
        return {"financial_report": None, "dividend_metrics": None}

    financial_report = _non_empty_dict(earnings_data.get("financial_report"))
    dividend_metrics = _non_empty_dict(earnings_data.get("dividend"))
    return {
        "financial_report": financial_report,
        "dividend_metrics": dividend_metrics,
    }


def extract_board_detail_fields(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Dict[str, Any]:
    """
    Extract stable board detail fields from fundamental_context.
    """
    fundamental_ctx = extract_fundamental_context(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    if not isinstance(fundamental_ctx, dict):
        return {"belong_boards": [], "sector_rankings": None}

    boards_block = fundamental_ctx.get("boards")
    sector_rankings = None
    if isinstance(boards_block, dict):
        boards_status = boards_block.get("status")
        if boards_status in {"ok", "partial"} or boards_status is None:
            sector_rankings = boards_block.get("data")
    return {
        "belong_boards": _normalize_belong_boards(fundamental_ctx.get("belong_boards")),
        "sector_rankings": _normalize_sector_rankings(sector_rankings),
    }


def extract_company_profile_detail_field(
    context_snapshot: Any,
    fallback_fundamental_payload: Any = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract stable company profile fields from fundamental_context.
    """
    fundamental_ctx = extract_fundamental_context(
        context_snapshot=context_snapshot,
        fallback_fundamental_payload=fallback_fundamental_payload,
    )
    if not isinstance(fundamental_ctx, dict):
        return None

    profile_block = fundamental_ctx.get("company_profile")
    profile_data = profile_block.get("data") if isinstance(profile_block, dict) else profile_block
    if not isinstance(profile_data, dict):
        return None

    normalized: Dict[str, Any] = {}
    text_fields = {
        "full_name": ("full_name", "company_name", "long_name", "name"),
        "industry": ("industry", "sector", "sw_industry", "gics_industry"),
        "legal_representative": ("legal_representative", "legal_person", "representative"),
        "listing_date": ("listing_date", "ipo_date", "list_date"),
        "website": ("website", "homepage", "official_website"),
        "main_business": ("main_business", "business", "principal_business"),
        "business_scope": ("business_scope", "scope_of_business"),
        "company_intro": ("company_intro", "company_profile", "description", "summary"),
        "actual_controller": ("actual_controller", "controlling_person"),
        "direct_controller": ("direct_controller", "direct_controlling_person"),
        "control_type": ("control_type",),
    }
    for output_key, source_keys in text_fields.items():
        value = _first_text(*(profile_data.get(key) for key in source_keys))
        if value is not None:
            normalized[output_key] = value

    numeric_fields = {
        "total_share_capital": ("total_share_capital", "total_shares", "shares_outstanding"),
        "float_share_capital": ("float_share_capital", "float_shares", "circulating_shares"),
        "employee_count": ("employee_count", "employees", "full_time_employees"),
    }
    for output_key, source_keys in numeric_fields.items():
        value = None
        for source_key in source_keys:
            value = _safe_int(profile_data.get(source_key))
            if value is not None:
                break
        if value is not None:
            normalized[output_key] = value

    ratio_value = None
    for source_key in ("actual_controller_hold_ratio", "controller_hold_ratio", "control_ratio"):
        try:
            raw_value = profile_data.get(source_key)
            if raw_value is None:
                continue
            ratio_value = float(str(raw_value).strip().replace(",", "").rstrip("%"))
            break
        except (TypeError, ValueError):
            continue
    if ratio_value is not None:
        normalized["actual_controller_hold_ratio"] = ratio_value

    return normalized or None
