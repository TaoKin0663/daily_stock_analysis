# -*- coding: utf-8 -*-
"""
AkShare fundamental adapter (fail-open).

This adapter intentionally uses capability probing against multiple AkShare
endpoint candidates. It should never raise to caller; partial data is allowed.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

_DIVIDEND_KEYWORD_MAP: Dict[str, List[str]] = {
    "per_share": [
        "每股派息",
        "每股现金红利",
        "每股分红",
        "每股派现",
        "派现(元/股)",
        "派息(元/股)",
        "税前派息(元/股)",
        "现金分红(税前)",
    ],
    "plan_text": [
        "分配方案",
        "分红方案",
        "实施方案",
        "派息方案",
        "方案",
        "预案",
        "方案说明",
    ],
    "ex_dividend_date": ["除权除息日", "除息日", "除权日", "除权除息", "除息日期"],
    "record_date": ["股权登记日", "登记日"],
    "announce_date": ["公告日期", "公告日", "实施公告日", "预案公告日"],
    "report_date": ["报告期", "报告日期", "截止日期", "统计截止日期"],
}


def _safe_float(value: Any) -> Optional[float]:
    """Best-effort float conversion."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    s = str(value).strip().replace(",", "").replace("%", "")
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    try:
        parsed = pd.to_datetime(value)
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    try:
        return parsed.to_pydatetime()
    except Exception:
        return None


def _normalize_code(raw: Any) -> str:
    s = _safe_str(raw).upper()
    if "." in s:
        s = s.split(".", 1)[0]
    s = re.sub(r"^(SH|SZ|BJ)", "", s)
    return s


def _a_share_secu_code_candidates(raw: Any) -> List[str]:
    text = _safe_str(raw).upper()
    normalized = _normalize_code(text)
    candidates: List[str] = []

    if re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", text):
        candidates.append(text)
    elif re.fullmatch(r"(SH|SZ|BJ)\d{6}", text):
        candidates.append(f"{text[2:]}.{text[:2]}")

    if re.fullmatch(r"\d{6}", normalized):
        if normalized.startswith(("6", "9")):
            candidates.append(f"{normalized}.SH")
        elif normalized.startswith(("0", "2", "3")):
            candidates.append(f"{normalized}.SZ")
        elif normalized.startswith(("4", "8")):
            candidates.append(f"{normalized}.BJ")
        candidates.append(normalized)

    unique_candidates: List[str] = []
    for candidate in candidates:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates or [text]


def _pick_by_keywords(row: pd.Series, keywords: List[str]) -> Optional[Any]:
    """
    Return first non-empty row value whose column name contains any keyword.
    """
    for col in row.index:
        col_s = str(col)
        col_upper = col_s.upper()
        if any(k in col_s or str(k).upper() in col_upper for k in keywords):
            val = row.get(col)
            if val is not None and str(val).strip() not in ("", "-", "nan", "None"):
                return val
    return None


def _parse_dividend_plan_to_per_share(plan_text: str) -> Optional[float]:
    """Parse per-share cash dividend from Chinese plan text."""
    text = _safe_str(plan_text)
    if not text:
        return None

    for pattern in (
        r"(?:每)?\s*10\s*股?\s*派(?:发)?\s*([0-9]+(?:\.[0-9]+)?)\s*元",
        r"10\s*派\s*([0-9]+(?:\.[0-9]+)?)\s*元",
    ):
        match = re.search(pattern, text)
        if match:
            parsed = _safe_float(match.group(1))
            if parsed is not None and parsed > 0:
                return parsed / 10.0

    match_per_share = re.search(r"每\s*股\s*派(?:发)?\s*([0-9]+(?:\.[0-9]+)?)\s*元", text)
    if match_per_share:
        parsed = _safe_float(match_per_share.group(1))
        if parsed is not None and parsed > 0:
            return parsed
    return None


def _extract_cash_dividend_per_share(row: pd.Series) -> Optional[float]:
    """Extract pre-tax cash dividend per share from a row."""
    plan_text = _safe_str(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["plan_text"]))
    # Keep pre-tax semantics; skip explicit after-tax plans unless pre-tax marker exists.
    if "税后" in plan_text and "税前" not in plan_text and "含税" not in plan_text:
        return None

    direct = _safe_float(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["per_share"]))
    if direct is not None and direct > 0:
        return direct
    return _parse_dividend_plan_to_per_share(plan_text)


def _filter_rows_by_code(df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    code_cols = [c for c in df.columns if any(k in str(c) for k in ("代码", "股票代码", "证券代码", "symbol", "ts_code"))]
    if not code_cols:
        return df

    target = _normalize_code(stock_code)
    for col in code_cols:
        try:
            series = df[col].astype(str).map(_normalize_code)
            filtered = df[series == target]
            if not filtered.empty:
                return filtered
        except Exception:
            continue
    return pd.DataFrame()


def _normalize_report_date(value: Any) -> Optional[str]:
    parsed = _safe_datetime(value)
    return parsed.date().isoformat() if parsed else None


def _annual_lrb_dates(max_years: int = 8) -> List[str]:
    # Annual reports for the current calendar year are not available before year-end.
    latest_possible_year = datetime.now().year - 1
    return [
        f"{year}1231"
        for year in range(latest_possible_year, latest_possible_year - max(1, max_years), -1)
    ]


def _extract_year_from_report_date(value: Any) -> Optional[int]:
    parsed = _safe_datetime(value)
    if parsed is not None:
        return parsed.year
    text = _safe_str(value)
    match = re.search(r"(20\d{2}|19\d{2})", text)
    if match:
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            return None
    return None


def _build_revenue_growth_payload(rows: List[Dict[str, Any]], max_rows: int = 5) -> Dict[str, Any]:
    normalized_rows: List[Dict[str, Any]] = []
    seen_years = set()
    for row in rows:
        year = row.get("fiscal_year")
        revenue = _safe_float(row.get("revenue"))
        if year is None or revenue is None:
            continue
        try:
            year_int = int(year)
        except (TypeError, ValueError):
            continue
        if year_int in seen_years:
            continue
        seen_years.add(year_int)
        normalized_rows.append(
            {
                "fiscal_year": year_int,
                "report_date": row.get("report_date"),
                "revenue": revenue,
                "revenue_yoy": _safe_float(row.get("revenue_yoy")),
                "announcement_date": row.get("announcement_date"),
            }
        )

    normalized_rows.sort(key=lambda item: int(item.get("fiscal_year") or 0), reverse=True)
    normalized_rows = normalized_rows[:max(1, max_rows)]
    if not normalized_rows:
        return {}
    return {
        "rows": normalized_rows,
        "unit": "yuan",
        "frequency": "annual",
        "source": "stock_lrb_em",
    }


def _build_profitability_payload(rows: List[Dict[str, Any]], max_rows: int = 5) -> Dict[str, Any]:
    normalized_rows: List[Dict[str, Any]] = []
    seen_periods = set()
    for row in rows:
        period = _safe_str(row.get("period") or row.get("report_date"))
        report_date = _normalize_report_date(row.get("report_date") or period)
        if not period and report_date:
            period = report_date
        if not period:
            continue

        gross_margin = _safe_float(row.get("gross_margin"))
        net_margin = _safe_float(row.get("net_margin"))
        roe = _safe_float(row.get("roe"))
        if gross_margin is None and net_margin is None and roe is None:
            continue

        dedupe_key = report_date or period
        if dedupe_key in seen_periods:
            continue
        seen_periods.add(dedupe_key)
        normalized_rows.append(
            {
                "period": period,
                "report_date": report_date,
                "gross_margin": gross_margin,
                "net_margin": net_margin,
                "roe": roe,
            }
        )

    normalized_rows.sort(key=lambda item: item.get("report_date") or item.get("period") or "", reverse=True)
    normalized_rows = normalized_rows[:max(1, max_rows)]
    if not normalized_rows:
        return {}
    return {
        "rows": normalized_rows,
        "unit": "percent",
        "frequency": "report_period",
        "source": "stock_financial_analysis_indicator_em",
    }


def _build_dividend_payload(
    dividend_df: pd.DataFrame,
    stock_code: str,
    max_events: int = 5,
) -> Dict[str, Any]:
    work_df = _filter_rows_by_code(dividend_df, stock_code)
    if work_df.empty:
        return {}

    now_date = datetime.now().date()
    ttm_start_date = now_date - timedelta(days=365)
    dedupe_keys = set()
    events: List[Dict[str, Any]] = []

    for _, row in work_df.iterrows():
        if not isinstance(row, pd.Series):
            continue
        ex_dt = _safe_datetime(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["ex_dividend_date"]))
        record_dt = _safe_datetime(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["record_date"]))
        announce_dt = _safe_datetime(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["announce_date"]))
        event_dt = ex_dt or record_dt or announce_dt
        if event_dt is None:
            continue
        event_date = event_dt.date()
        if event_date > now_date:
            continue

        per_share = _extract_cash_dividend_per_share(row)
        if per_share is None or per_share <= 0:
            continue

        dedupe_key = (event_date.isoformat(), round(per_share, 6))
        if dedupe_key in dedupe_keys:
            continue
        dedupe_keys.add(dedupe_key)

        events.append(
            {
                "event_date": event_date.isoformat(),
                "ex_dividend_date": ex_dt.date().isoformat() if ex_dt else None,
                "record_date": record_dt.date().isoformat() if record_dt else None,
                "announcement_date": announce_dt.date().isoformat() if announce_dt else None,
                "cash_dividend_per_share": round(per_share, 6),
                "is_pre_tax": True,
            }
        )

    if not events:
        return {}

    events.sort(key=lambda item: item.get("event_date") or "", reverse=True)
    ttm_events: List[Dict[str, Any]] = []
    for item in events:
        event_dt = _safe_datetime(item.get("event_date"))
        if event_dt is None:
            continue
        event_date = event_dt.date()
        if ttm_start_date <= event_date <= now_date:
            ttm_events.append(item)

    return {
        "events": events[:max(1, max_events)],
        "ttm_event_count": len(ttm_events),
        "ttm_cash_dividend_per_share": (
            round(sum(float(item.get("cash_dividend_per_share") or 0.0) for item in ttm_events), 6)
            if ttm_events else None
        ),
        "coverage": "cash_dividend_pre_tax",
        "as_of": now_date.isoformat(),
    }


def _extract_latest_row(df: pd.DataFrame, stock_code: str) -> Optional[pd.Series]:
    """
    Select the most relevant row for the given stock.
    """
    if df is None or df.empty:
        return None

    code_cols = [c for c in df.columns if any(k in str(c) for k in ("代码", "股票代码", "证券代码", "ts_code", "symbol"))]
    target = _normalize_code(stock_code)
    if code_cols:
        for col in code_cols:
            try:
                series = df[col].astype(str).map(_normalize_code)
                matched = df[series == target]
                if not matched.empty:
                    return matched.iloc[0]
            except Exception:
                continue
        return None

    # Fallback: use latest row
    return df.iloc[0]


class AkshareFundamentalAdapter:
    """AkShare adapter for fundamentals, capital flow and dragon-tiger signals."""

    def _call_df_candidates(
        self,
        candidates: List[Tuple[str, Dict[str, Any]]],
    ) -> Tuple[Optional[pd.DataFrame], Optional[str], List[str]]:
        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return None, None, [f"import_akshare:{type(exc).__name__}"]

        for func_name, kwargs in candidates:
            fn = getattr(ak, func_name, None)
            if fn is None:
                continue
            try:
                df = fn(**kwargs)
                if isinstance(df, pd.Series):
                    df = df.to_frame().T
                if isinstance(df, pd.DataFrame) and not df.empty:
                    return df, func_name, errors
            except Exception as exc:
                errors.append(f"{func_name}:{type(exc).__name__}")
                continue
        return None, None, errors

    def _fetch_annual_revenue_growth(self, stock_code: str, max_rows: int = 5) -> Tuple[Dict[str, Any], List[str]]:
        rows: List[Dict[str, Any]] = []
        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return {}, [f"import_akshare:{type(exc).__name__}"]

        fn = getattr(ak, "stock_lrb_em", None)
        if fn is None:
            return {}, ["stock_lrb_em:not_available"]

        target = _normalize_code(stock_code)
        for report_date in _annual_lrb_dates(max_years=max_rows + 3):
            if len(rows) >= max_rows:
                break
            try:
                df = fn(date=report_date)
            except Exception as exc:
                errors.append(f"stock_lrb_em:{report_date}:{type(exc).__name__}")
                continue
            if isinstance(df, pd.Series):
                df = df.to_frame().T
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue

            code_cols = [c for c in df.columns if any(k in str(c) for k in ("股票代码", "代码", "证券代码", "symbol", "ts_code"))]
            filtered = pd.DataFrame()
            for col in code_cols:
                try:
                    series = df[col].astype(str).map(_normalize_code)
                    matched = df[series == target]
                    if not matched.empty:
                        filtered = matched
                        break
                except Exception:
                    continue
            if filtered.empty and not code_cols:
                filtered = _filter_rows_by_code(df, target)
            if filtered.empty:
                continue
            row = filtered.iloc[0]
            revenue = _safe_float(_pick_by_keywords(row, ["营业总收入", "营业收入", "营收", "钀ヤ笟鎬绘敹鍏", "钀ヤ笟鏀跺叆"]))
            if revenue is None:
                continue
            rows.append(
                {
                    "fiscal_year": _extract_year_from_report_date(report_date),
                    "report_date": _normalize_report_date(report_date),
                    "revenue": revenue,
                    "revenue_yoy": _safe_float(
                        _pick_by_keywords(row, ["营业总收入同比", "营业收入同比", "营收同比", "同比增长", "钀ヤ笟鏀跺叆鍚屾瘮"])
                    ),
                    "announcement_date": _normalize_report_date(_pick_by_keywords(row, ["公告日期", "鍏憡鏃ユ湡"])),
                }
            )

        return _build_revenue_growth_payload(rows, max_rows=max_rows), errors

    def _fetch_annual_revenue_growth_direct(self, stock_code: str, max_rows: int = 5) -> Tuple[Dict[str, Any], List[str]]:
        rows: List[Dict[str, Any]] = []
        errors: List[str] = []
        target = _normalize_code(stock_code)
        for report_date in _annual_lrb_dates(max_years=max_rows + 3):
            if len(rows) >= max_rows:
                break
            report_date_iso = f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}"
            try:
                import requests

                response = requests.get(
                    "https://datacenter-web.eastmoney.com/api/data/v1/get",
                    params={
                        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
                        "sortTypes": "-1,-1",
                        "pageSize": "1",
                        "pageNumber": "1",
                        "reportName": "RPT_DMSK_FN_INCOME",
                        "columns": "ALL",
                        "filter": (
                            '(SECURITY_TYPE_CODE in ("058001001","058001008"))'
                            '(TRADE_MARKET_CODE!="069001017")'
                            f'(SECURITY_CODE="{target}")'
                            f"(REPORT_DATE='{report_date_iso}')"
                        ),
                    },
                    timeout=0.5,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                errors.append(f"stock_lrb_em_direct:{report_date}:{type(exc).__name__}")
                continue

            result_obj = payload.get("result") if isinstance(payload, dict) else None
            data_rows = result_obj.get("data") if isinstance(result_obj, dict) else None
            if not isinstance(data_rows, list) or not data_rows:
                continue
            row = data_rows[0]
            if not isinstance(row, dict):
                continue
            revenue = _safe_float(row.get("TOTAL_OPERATE_INCOME"))
            if revenue is None:
                continue
            rows.append(
                {
                    "fiscal_year": _extract_year_from_report_date(report_date),
                    "report_date": _normalize_report_date(row.get("REPORT_DATE") or report_date_iso),
                    "revenue": revenue,
                    "revenue_yoy": _safe_float(row.get("TOI_RATIO")),
                    "announcement_date": _normalize_report_date(row.get("NOTICE_DATE")),
                }
            )

        return _build_revenue_growth_payload(rows, max_rows=max_rows), errors

    def _fetch_profitability_indicators(self, stock_code: str, max_rows: int = 5) -> Tuple[Dict[str, Any], List[str]]:
        rows: List[Dict[str, Any]] = []
        errors: List[str] = []
        try:
            import akshare as ak
        except Exception as exc:
            return {}, [f"import_akshare:{type(exc).__name__}"]

        fn = getattr(ak, "stock_financial_analysis_indicator_em", None)
        if fn is None:
            return {}, ["stock_financial_analysis_indicator_em:not_available"]

        df: Optional[pd.DataFrame] = None
        for symbol in _a_share_secu_code_candidates(stock_code):
            try:
                candidate_df = fn(symbol=symbol)
            except Exception as exc:
                errors.append(f"stock_financial_analysis_indicator_em:{symbol}:{type(exc).__name__}")
                continue
            if isinstance(candidate_df, pd.Series):
                candidate_df = candidate_df.to_frame().T
            if isinstance(candidate_df, pd.DataFrame) and not candidate_df.empty:
                df = candidate_df
                break

        if not isinstance(df, pd.DataFrame) or df.empty:
            return {}, errors

        work_df = _filter_rows_by_code(df, stock_code)
        if work_df.empty:
            work_df = df

        for _, row in work_df.iterrows():
            if not isinstance(row, pd.Series):
                continue
            report_date_value = _pick_by_keywords(
                row,
                [
                    "日期",
                    "报告期",
                    "报告日期",
                    "截止日期",
                    "REPORT_DATE",
                    "report_date",
                    "date",
                ],
            )
            rows.append(
                {
                    "period": _safe_str(report_date_value),
                    "report_date": report_date_value,
                    "gross_margin": _safe_float(
                        _pick_by_keywords(
                            row,
                            [
                                "销售毛利率",
                                "毛利率",
                                "GROSS_PROFIT_MARGIN",
                                "GROSSPROFIT_MARGIN",
                                "GROSS_PROFIT_RATIO",
                                "GROSSPROFIT_RATIO",
                                "GROSS_MARGIN",
                                "GP_MARGIN",
                                "XSMLL",
                                "gross margin",
                                "gross_margin",
                            ],
                        )
                    ),
                    "net_margin": _safe_float(
                        _pick_by_keywords(
                            row,
                            [
                                "销售净利率",
                                "净利率",
                                "NET_PROFIT_MARGIN",
                                "NETPROFIT_MARGIN",
                                "NET_PROFIT_RATIO",
                                "NETPROFIT_RATIO",
                                "NET_MARGIN",
                                "NP_MARGIN",
                                "XSJLL",
                                "net margin",
                                "net_margin",
                            ],
                        )
                    ),
                    "roe": _safe_float(
                        _pick_by_keywords(
                            row,
                            [
                                "净资产收益率",
                                "ROE",
                                "WEIGHTAVG_ROE",
                                "WEIGHTED_ROE",
                                "ROEJQ",
                                "ROEKCJQ",
                                "JQJZCSYL",
                                "roe",
                            ],
                        )
                    ),
                }
            )

        return _build_profitability_payload(rows, max_rows=max_rows), errors

    def get_fundamental_bundle(self, stock_code: str) -> Dict[str, Any]:
        """
        Return normalized fundamental blocks from AkShare with partial tolerance.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "growth": {},
            "earnings": {},
            "institution": {},
            "source_chain": [],
            "errors": [],
        }

        def _attach_revenue_growth_payload(revenue_growth_payload: Dict[str, Any]) -> None:
            if not revenue_growth_payload:
                return
            financial_report_payload = result["earnings"].get("financial_report")
            if not isinstance(financial_report_payload, dict):
                financial_report_payload = {}
            financial_report_payload["revenue_growth"] = revenue_growth_payload
            latest_row = revenue_growth_payload.get("rows", [{}])[0]
            if financial_report_payload.get("report_date") is None:
                financial_report_payload["report_date"] = latest_row.get("report_date")
            if financial_report_payload.get("revenue") is None:
                financial_report_payload["revenue"] = latest_row.get("revenue")
            if result["growth"].get("revenue_yoy") is None:
                result["growth"]["revenue_yoy"] = latest_row.get("revenue_yoy")
            result["earnings"]["financial_report"] = financial_report_payload

        def _attach_profitability_payload(profitability_payload: Dict[str, Any]) -> None:
            if not profitability_payload:
                return
            financial_report_payload = result["earnings"].get("financial_report")
            if not isinstance(financial_report_payload, dict):
                financial_report_payload = {}
            financial_report_payload["profitability"] = profitability_payload
            latest_row = profitability_payload.get("rows", [{}])[0]
            if financial_report_payload.get("report_date") is None:
                financial_report_payload["report_date"] = latest_row.get("report_date")
            if financial_report_payload.get("roe") is None:
                financial_report_payload["roe"] = latest_row.get("roe")
            if result["growth"].get("roe") is None:
                result["growth"]["roe"] = latest_row.get("roe")
            if result["growth"].get("gross_margin") is None:
                result["growth"]["gross_margin"] = latest_row.get("gross_margin")
            result["earnings"]["financial_report"] = financial_report_payload

        revenue_growth_payload, revenue_growth_errors = self._fetch_annual_revenue_growth_direct(stock_code, max_rows=5)
        result["errors"].extend(revenue_growth_errors)
        if revenue_growth_payload:
            _attach_revenue_growth_payload(revenue_growth_payload)
            result["source_chain"].append("revenue_growth:stock_lrb_em")

        profitability_payload, profitability_errors = self._fetch_profitability_indicators(stock_code, max_rows=5)
        result["errors"].extend(profitability_errors)
        if profitability_payload:
            _attach_profitability_payload(profitability_payload)
            result["source_chain"].append("profitability:stock_financial_analysis_indicator_em")

        # Financial indicators
        fin_df, fin_source, fin_errors = self._call_df_candidates([
            ("stock_financial_abstract", {"symbol": stock_code}),
            ("stock_financial_analysis_indicator", {"symbol": stock_code}),
            ("stock_financial_analysis_indicator", {}),
        ])
        result["errors"].extend(fin_errors)
        if fin_df is not None:
            row = _extract_latest_row(fin_df, stock_code)
            if row is not None:
                revenue_yoy = _safe_float(_pick_by_keywords(row, ["营业收入同比", "营收同比", "收入同比", "同比增长"]))
                profit_yoy = _safe_float(_pick_by_keywords(row, ["净利润同比", "净利同比", "归母净利润同比"]))
                roe = _safe_float(_pick_by_keywords(row, ["净资产收益率", "ROE", "净资产收益"]))
                gross_margin = _safe_float(_pick_by_keywords(row, ["毛利率"]))
                report_date = _normalize_report_date(_pick_by_keywords(row, _DIVIDEND_KEYWORD_MAP["report_date"]))
                revenue = _safe_float(_pick_by_keywords(row, ["营业总收入", "营业收入", "营收"]))
                net_profit_parent = _safe_float(_pick_by_keywords(row, ["归母净利润", "母公司股东净利润", "净利润"]))
                operating_cash_flow = _safe_float(
                    _pick_by_keywords(row, ["经营活动产生的现金流量净额", "经营现金流", "经营活动现金流"])
                )
                result["growth"] = {
                    "revenue_yoy": revenue_yoy,
                    "net_profit_yoy": profit_yoy,
                    "roe": roe,
                    "gross_margin": gross_margin,
                }
                financial_report_payload = {
                    "report_date": report_date,
                    "revenue": revenue,
                    "net_profit_parent": net_profit_parent,
                    "operating_cash_flow": operating_cash_flow,
                    "roe": roe,
                }
                existing_financial_report = result["earnings"].get("financial_report")
                if isinstance(existing_financial_report, dict) and existing_financial_report.get("revenue_growth"):
                    financial_report_payload["revenue_growth"] = existing_financial_report.get("revenue_growth")
                if isinstance(existing_financial_report, dict) and existing_financial_report.get("profitability"):
                    financial_report_payload["profitability"] = existing_financial_report.get("profitability")
                if any(v is not None for v in financial_report_payload.values()):
                    result["earnings"]["financial_report"] = financial_report_payload
                result["source_chain"].append(f"growth:{fin_source}")

        financial_report_payload = result["earnings"].get("financial_report")
        if not isinstance(financial_report_payload, dict) or not financial_report_payload.get("revenue_growth"):
            revenue_growth_payload, revenue_growth_errors = self._fetch_annual_revenue_growth_direct(stock_code, max_rows=5)
            result["errors"].extend(revenue_growth_errors)
            if revenue_growth_payload:
                _attach_revenue_growth_payload(revenue_growth_payload)
                result["source_chain"].append("revenue_growth:stock_lrb_em")

        # Earnings forecast
        forecast_df, forecast_source, forecast_errors = self._call_df_candidates([
            ("stock_yjyg_em", {"symbol": stock_code}),
            ("stock_yjyg_em", {}),
            ("stock_yjbb_em", {"symbol": stock_code}),
            ("stock_yjbb_em", {}),
        ])
        result["errors"].extend(forecast_errors)
        if forecast_df is not None:
            row = _extract_latest_row(forecast_df, stock_code)
            if row is not None:
                result["earnings"]["forecast_summary"] = _safe_str(
                    _pick_by_keywords(row, ["预告", "业绩变动", "内容", "摘要", "公告"])
                )[:200]
                result["source_chain"].append(f"earnings_forecast:{forecast_source}")

        # Earnings quick report
        quick_df, quick_source, quick_errors = self._call_df_candidates([
            ("stock_yjkb_em", {"symbol": stock_code}),
            ("stock_yjkb_em", {}),
        ])
        result["errors"].extend(quick_errors)
        if quick_df is not None:
            row = _extract_latest_row(quick_df, stock_code)
            if row is not None:
                result["earnings"]["quick_report_summary"] = _safe_str(
                    _pick_by_keywords(row, ["快报", "摘要", "公告", "说明"])
                )[:200]
                result["source_chain"].append(f"earnings_quick:{quick_source}")

        # Dividend details (cash dividend, pre-tax)
        dividend_df, dividend_source, dividend_errors = self._call_df_candidates([
            ("stock_fhps_detail_em", {"symbol": stock_code}),
            ("stock_history_dividend_detail", {"symbol": stock_code, "indicator": "分红", "date": ""}),
            ("stock_dividend_cninfo", {"symbol": stock_code}),
        ])
        result["errors"].extend(dividend_errors)
        if dividend_df is not None:
            dividend_payload = _build_dividend_payload(dividend_df, stock_code, max_events=5)
            if dividend_payload:
                result["earnings"]["dividend"] = dividend_payload
                result["source_chain"].append(f"dividend:{dividend_source}")

        # Institution / top shareholders
        inst_df, inst_source, inst_errors = self._call_df_candidates([
            ("stock_institute_hold", {}),
            ("stock_institute_recommend", {}),
        ])
        result["errors"].extend(inst_errors)
        if inst_df is not None:
            row = _extract_latest_row(inst_df, stock_code)
            if row is not None:
                inst_change = _safe_float(_pick_by_keywords(row, ["增减", "变化", "变动", "持股变化"]))
                result["institution"]["institution_holding_change"] = inst_change
                result["source_chain"].append(f"institution:{inst_source}")

        top10_df, top10_source, top10_errors = self._call_df_candidates([
            ("stock_gdfx_top_10_em", {"symbol": stock_code}),
            ("stock_gdfx_top_10_em", {}),
            ("stock_zh_a_gdhs_detail_em", {"symbol": stock_code}),
            ("stock_zh_a_gdhs_detail_em", {}),
        ])
        result["errors"].extend(top10_errors)
        if top10_df is not None:
            row = _extract_latest_row(top10_df, stock_code)
            if row is not None:
                holder_change = _safe_float(_pick_by_keywords(row, ["增减", "变化", "持股变化", "变动"]))
                result["institution"]["top10_holder_change"] = holder_change
                result["source_chain"].append(f"top10:{top10_source}")

        has_content = bool(result["growth"] or result["earnings"] or result["institution"])
        result["status"] = "partial" if has_content else "not_supported"
        return result

    def get_capital_flow(self, stock_code: str, top_n: int = 5) -> Dict[str, Any]:
        """
        Return stock + sector capital flow.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "stock_flow": {},
            "sector_rankings": {"top": [], "bottom": []},
            "source_chain": [],
            "errors": [],
        }

        stock_df, stock_source, stock_errors = self._call_df_candidates([
            ("stock_individual_fund_flow", {"stock": stock_code}),
            ("stock_individual_fund_flow", {"symbol": stock_code}),
            ("stock_individual_fund_flow", {}),
            ("stock_main_fund_flow", {"symbol": stock_code}),
            ("stock_main_fund_flow", {}),
        ])
        result["errors"].extend(stock_errors)
        if stock_df is not None:
            row = _extract_latest_row(stock_df, stock_code)
            if row is not None:
                net_inflow = _safe_float(_pick_by_keywords(row, ["主力净流入", "净流入", "净额"]))
                inflow_5d = _safe_float(_pick_by_keywords(row, ["5日", "五日"]))
                inflow_10d = _safe_float(_pick_by_keywords(row, ["10日", "十日"]))
                result["stock_flow"] = {
                    "main_net_inflow": net_inflow,
                    "inflow_5d": inflow_5d,
                    "inflow_10d": inflow_10d,
                }
                result["source_chain"].append(f"capital_stock:{stock_source}")

        sector_df, sector_source, sector_errors = self._call_df_candidates([
            ("stock_sector_fund_flow_rank", {}),
            ("stock_sector_fund_flow_summary", {}),
        ])
        result["errors"].extend(sector_errors)
        if sector_df is not None:
            name_col = next((c for c in sector_df.columns if any(k in str(c) for k in ("板块", "行业", "名称", "name"))), None)
            flow_col = next((c for c in sector_df.columns if any(k in str(c) for k in ("净流入", "主力", "flow", "净额"))), None)
            if name_col and flow_col:
                work_df = sector_df[[name_col, flow_col]].copy()
                work_df[flow_col] = pd.to_numeric(work_df[flow_col], errors="coerce")
                work_df = work_df.dropna(subset=[flow_col])
                top_df = work_df.nlargest(top_n, flow_col)
                bottom_df = work_df.nsmallest(top_n, flow_col)
                result["sector_rankings"] = {
                    "top": [{"name": _safe_str(r[name_col]), "net_inflow": float(r[flow_col])} for _, r in top_df.iterrows()],
                    "bottom": [{"name": _safe_str(r[name_col]), "net_inflow": float(r[flow_col])} for _, r in bottom_df.iterrows()],
                }
                result["source_chain"].append(f"capital_sector:{sector_source}")

        has_content = bool(result["stock_flow"] or result["sector_rankings"]["top"] or result["sector_rankings"]["bottom"])
        result["status"] = "partial" if has_content else "not_supported"
        return result

    def get_dragon_tiger_flag(self, stock_code: str, lookback_days: int = 20) -> Dict[str, Any]:
        """
        Return dragon-tiger signal in lookback window.
        """
        result: Dict[str, Any] = {
            "status": "not_supported",
            "is_on_list": False,
            "recent_count": 0,
            "latest_date": None,
            "source_chain": [],
            "errors": [],
        }

        df, source, errors = self._call_df_candidates([
            ("stock_lhb_stock_statistic_em", {}),
            ("stock_lhb_detail_em", {}),
            ("stock_lhb_jgmmtj_em", {}),
        ])
        result["errors"].extend(errors)
        if df is None:
            return result

        # Try code filter
        code_cols = [c for c in df.columns if any(k in str(c) for k in ("代码", "股票代码", "证券代码"))]
        target = _normalize_code(stock_code)
        matched = pd.DataFrame()
        for col in code_cols:
            try:
                series = df[col].astype(str).map(_normalize_code)
                cur = df[series == target]
                if not cur.empty:
                    matched = cur
                    break
            except Exception:
                continue
        if matched.empty:
            result["source_chain"].append(f"dragon_tiger:{source}")
            result["status"] = "ok" if code_cols else "partial"
            return result

        date_col = next((c for c in matched.columns if any(k in str(c) for k in ("日期", "上榜", "交易日", "time"))), None)
        parsed_dates: List[datetime] = []
        if date_col is not None:
            for val in matched[date_col].astype(str).tolist():
                try:
                    parsed_dates.append(pd.to_datetime(val).to_pydatetime())
                except Exception:
                    continue
        now = datetime.now()
        start = now - timedelta(days=max(1, lookback_days))
        recent_dates = [d for d in parsed_dates if start <= d <= now]

        result["is_on_list"] = bool(recent_dates)
        result["recent_count"] = len(recent_dates) if recent_dates else int(len(matched))
        result["latest_date"] = max(recent_dates).date().isoformat() if recent_dates else (
            max(parsed_dates).date().isoformat() if parsed_dates else None
        )
        result["status"] = "ok"
        result["source_chain"].append(f"dragon_tiger:{source}")
        return result
