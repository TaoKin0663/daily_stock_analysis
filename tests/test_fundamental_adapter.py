# -*- coding: utf-8 -*-
"""
Tests for fundamental adapter helpers.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.fundamental_adapter import (
    AkshareFundamentalAdapter,
    _a_share_secu_code_candidates,
    _build_dividend_payload,
    _extract_latest_row,
    _parse_dividend_plan_to_per_share,
)


class TestFundamentalAdapter(unittest.TestCase):
    def test_parse_dividend_plan_to_per_share_supports_cn_patterns(self) -> None:
        self.assertAlmostEqual(_parse_dividend_plan_to_per_share("10派3元(含税)"), 0.3, places=6)
        self.assertAlmostEqual(_parse_dividend_plan_to_per_share("每10股派发2.5元"), 0.25, places=6)
        self.assertAlmostEqual(_parse_dividend_plan_to_per_share("每股派0.8元"), 0.8, places=6)
        self.assertIsNone(_parse_dividend_plan_to_per_share("仅送股，不现金分红"))

    def test_extract_latest_row_returns_none_when_code_mismatch(self) -> None:
        df = pd.DataFrame(
            {
                "股票代码": ["600000", "000001"],
                "值": [1, 2],
            }
        )
        row = _extract_latest_row(df, "600519")
        self.assertIsNone(row)

    def test_extract_latest_row_fallback_when_no_code_column(self) -> None:
        df = pd.DataFrame({"值": [1, 2]})
        row = _extract_latest_row(df, "600519")
        self.assertIsNotNone(row)
        self.assertEqual(row["值"], 1)

    def test_a_share_secu_code_candidates_adds_market_suffix(self) -> None:
        self.assertEqual(_a_share_secu_code_candidates("600519"), ["600519.SH", "600519"])
        self.assertEqual(_a_share_secu_code_candidates("300308"), ["300308.SZ", "300308"])
        self.assertEqual(_a_share_secu_code_candidates("000066.SZ"), ["000066.SZ", "000066"])

    def test_dragon_tiger_no_match_with_code_column_is_ok(self) -> None:
        adapter = AkshareFundamentalAdapter()
        df = pd.DataFrame(
            {
                "股票代码": ["600000"],
                "日期": ["2026-01-01"],
            }
        )
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_lhb_stock_statistic_em", [])):
            result = adapter.get_dragon_tiger_flag("600519")
        self.assertEqual(result["status"], "ok")
        self.assertFalse(result["is_on_list"])
        self.assertEqual(result["recent_count"], 0)

    def test_dragon_tiger_match_is_ok(self) -> None:
        adapter = AkshareFundamentalAdapter()
        today = pd.Timestamp.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "股票代码": ["600519"],
                "日期": [today],
            }
        )
        with patch.object(adapter, "_call_df_candidates", return_value=(df, "stock_lhb_stock_statistic_em", [])):
            result = adapter.get_dragon_tiger_flag("600519")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["is_on_list"])
        self.assertGreaterEqual(result["recent_count"], 1)

    def test_fundamental_bundle_includes_financial_report_and_dividend_payload(self) -> None:
        adapter = AkshareFundamentalAdapter()
        now = datetime.now()
        within_ttm = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        future_day = (now + timedelta(days=10)).strftime("%Y-%m-%d")
        old_day = (now - timedelta(days=500)).strftime("%Y-%m-%d")
        fin_df = pd.DataFrame(
            {
                "股票代码": ["600519"],
                "报告期": [within_ttm],
                "营业总收入": [1000.0],
                "归母净利润": [300.0],
                "经营活动产生的现金流量净额": [500.0],
                "净资产收益率": [18.2],
                "营业收入同比": [12.0],
                "净利润同比": [9.5],
            }
        )
        forecast_df = pd.DataFrame({"股票代码": ["600519"], "预告": ["预增"]})
        quick_df = pd.DataFrame({"股票代码": ["600519"], "快报": ["快报摘要"]})
        dividend_df = pd.DataFrame(
            {
                "股票代码": ["600519", "600519", "600519", "600519"],
                "除息日": [within_ttm, within_ttm, future_day, old_day],
                "分配方案": ["10派3元(含税)", "10派3元(含税)", "10派5元", "10派1元"],
            }
        )

        with patch.object(
            adapter,
            "_call_df_candidates",
            side_effect=[
                (fin_df, "stock_financial_abstract", []),
                (forecast_df, "stock_yjyg_em", []),
                (quick_df, "stock_yjkb_em", []),
                (dividend_df, "stock_fhps_detail_em", []),
                (None, None, []),
                (None, None, []),
            ],
        ):
            result = adapter.get_fundamental_bundle("600519")

        financial_report = result["earnings"].get("financial_report", {})
        self.assertEqual(financial_report.get("report_date"), within_ttm)
        self.assertEqual(financial_report.get("revenue"), 1000.0)
        self.assertEqual(financial_report.get("net_profit_parent"), 300.0)
        self.assertEqual(financial_report.get("operating_cash_flow"), 500.0)
        self.assertEqual(financial_report.get("roe"), 18.2)

        dividend_payload = result["earnings"].get("dividend", {})
        events = dividend_payload.get("events", [])
        self.assertEqual(len(events), 2)  # duplicate + future day filtered
        self.assertEqual(dividend_payload.get("ttm_event_count"), 1)
        self.assertAlmostEqual(dividend_payload.get("ttm_cash_dividend_per_share"), 0.3, places=6)

    def test_annual_revenue_growth_uses_stock_lrb_em(self) -> None:
        adapter = AkshareFundamentalAdapter()
        current_year = datetime.now().year
        annual_payloads = {
            f"{current_year - 1}1231": pd.DataFrame(
                {
                    "股票代码": ["600519", "000001"],
                    "营业总收入": [15000000000.0, 1.0],
                    "营业总收入同比": [12.5, 1.0],
                    "公告日期": [f"{current_year}-03-30", f"{current_year}-03-30"],
                }
            ),
            f"{current_year - 2}1231": pd.DataFrame(
                {
                    "股票代码": ["600519"],
                    "营业总收入": [12000000000.0],
                    "营业总收入同比": [8.2],
                    "公告日期": [f"{current_year - 1}-03-30"],
                }
            ),
        }

        def fake_stock_lrb_em(date: str) -> pd.DataFrame:
            return annual_payloads.get(date, pd.DataFrame())

        fake_akshare = SimpleNamespace(stock_lrb_em=fake_stock_lrb_em)
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            payload, errors = adapter._fetch_annual_revenue_growth("600519", max_rows=2)

        self.assertEqual(errors, [])
        rows = payload.get("rows", [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["fiscal_year"], current_year - 1)
        self.assertEqual(rows[0]["revenue"], 15000000000.0)
        self.assertEqual(rows[0]["revenue_yoy"], 12.5)
        self.assertEqual(payload.get("unit"), "yuan")
        self.assertEqual(payload.get("source"), "stock_lrb_em")

    def test_annual_revenue_growth_direct_uses_eastmoney_payload(self) -> None:
        adapter = AkshareFundamentalAdapter()
        current_year = datetime.now().year
        annual_payloads = {
            f"{current_year - 1}-12-31": {
                "TOTAL_OPERATE_INCOME": 15000000000.0,
                "TOI_RATIO": 12.5,
                "REPORT_DATE": f"{current_year - 1}-12-31 00:00:00",
                "NOTICE_DATE": f"{current_year}-03-30 00:00:00",
            },
            f"{current_year - 2}-12-31": {
                "TOTAL_OPERATE_INCOME": 12000000000.0,
                "TOI_RATIO": 8.2,
                "REPORT_DATE": f"{current_year - 2}-12-31 00:00:00",
                "NOTICE_DATE": f"{current_year - 1}-03-30 00:00:00",
            },
        }

        def fake_get(_url, params=None, timeout=None):
            filter_text = (params or {}).get("filter", "")
            row = next((value for key, value in annual_payloads.items() if key in filter_text), None)
            response = SimpleNamespace()
            response.raise_for_status = lambda: None
            response.json = lambda: {
                "success": True,
                "result": {"data": [row] if row else []},
            }
            return response

        with patch("requests.get", side_effect=fake_get):
            payload, errors = adapter._fetch_annual_revenue_growth_direct("600519", max_rows=2)

        self.assertEqual(errors, [])
        rows = payload.get("rows", [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["fiscal_year"], current_year - 1)
        self.assertEqual(rows[0]["revenue"], 15000000000.0)
        self.assertEqual(rows[0]["revenue_yoy"], 12.5)
        self.assertEqual(payload.get("unit"), "yuan")
        self.assertEqual(payload.get("source"), "stock_lrb_em")

    def test_profitability_indicators_use_stock_financial_analysis_indicator_em(self) -> None:
        adapter = AkshareFundamentalAdapter()

        def fake_stock_financial_analysis_indicator_em(symbol: str) -> pd.DataFrame:
            self.assertEqual(symbol, "600519.SH")
            return pd.DataFrame(
                {
                    "日期": ["2025-12-31", "2024-12-31", "2023-12-31"],
                    "销售毛利率": [42.61, 38.2, None],
                    "销售净利率": [28.2, 25.1, None],
                    "净资产收益率": [43.84, 32.5, None],
                }
            )

        fake_akshare = SimpleNamespace(
            stock_financial_analysis_indicator_em=fake_stock_financial_analysis_indicator_em
        )
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            payload, errors = adapter._fetch_profitability_indicators("600519", max_rows=2)

        self.assertEqual(errors, [])
        rows = payload.get("rows", [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["period"], "2025-12-31")
        self.assertEqual(rows[0]["gross_margin"], 42.61)
        self.assertEqual(rows[0]["net_margin"], 28.2)
        self.assertEqual(rows[0]["roe"], 43.84)
        self.assertEqual(payload.get("unit"), "percent")
        self.assertEqual(payload.get("source"), "stock_financial_analysis_indicator_em")

    def test_profitability_indicators_support_eastmoney_raw_field_names(self) -> None:
        adapter = AkshareFundamentalAdapter()

        def fake_stock_financial_analysis_indicator_em(symbol: str) -> pd.DataFrame:
            self.assertEqual(symbol, "300308.SZ")
            return pd.DataFrame(
                {
                    "REPORT_DATE": ["2025-12-31", "2024-12-31"],
                    "XSMLL": [50.4, 45.2],
                    "XSJLL": [28.2, 24.6],
                    "ROEJQ": [43.84, 31.7],
                }
            )

        fake_akshare = SimpleNamespace(
            stock_financial_analysis_indicator_em=fake_stock_financial_analysis_indicator_em
        )
        with patch.dict(sys.modules, {"akshare": fake_akshare}):
            payload, errors = adapter._fetch_profitability_indicators("300308", max_rows=5)

        self.assertEqual(errors, [])
        rows = payload.get("rows", [])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["period"], "2025-12-31")
        self.assertEqual(rows[0]["gross_margin"], 50.4)
        self.assertEqual(rows[0]["net_margin"], 28.2)
        self.assertEqual(rows[0]["roe"], 43.84)

    def test_build_dividend_payload_returns_empty_when_code_not_matched(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "股票代码": ["000001"],
                "除息日": [now],
                "分配方案": ["10派3元(含税)"],
            }
        )

        payload = _build_dividend_payload(df, stock_code="600519")
        self.assertEqual(payload, {})

    def test_build_dividend_payload_skips_after_tax_plan(self) -> None:
        now = datetime.now().strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "股票代码": ["600519"],
                "除息日": [now],
                "分配方案": ["10派3元(税后)"],
            }
        )

        payload = _build_dividend_payload(df, stock_code="600519")
        self.assertEqual(payload, {})

    def test_build_dividend_payload_ttm_window_boundary(self) -> None:
        now = datetime.now()
        day_365 = (now - timedelta(days=365)).strftime("%Y-%m-%d")
        day_366 = (now - timedelta(days=366)).strftime("%Y-%m-%d")
        df = pd.DataFrame(
            {
                "股票代码": ["600519", "600519"],
                "除息日": [day_365, day_366],
                "分配方案": ["10派3元(含税)", "10派5元(含税)"],
            }
        )

        payload = _build_dividend_payload(df, stock_code="600519")
        self.assertEqual(payload.get("ttm_event_count"), 1)
        self.assertAlmostEqual(payload.get("ttm_cash_dividend_per_share"), 0.3, places=6)


if __name__ == "__main__":
    unittest.main()
