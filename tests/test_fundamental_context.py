# -*- coding: utf-8 -*-
"""
Tests for structured fundamental context (P0).
"""

import os
import sys
import time
import unittest
from threading import BoundedSemaphore, Event
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_provider.base import DataFetcherManager


class _DummyFetcher:
    def __init__(self, name: str, priority: int, rankings=None):
        self.name = name
        self.priority = priority
        self._rankings = rankings

    def get_sector_rankings(self, _n: int = 5):
        return self._rankings


class _DummyBoardFetcher:
    def __init__(self, name: str, priority: int, boards=None):
        self.name = name
        self.priority = priority
        self._boards = boards or []

    def get_belong_board(self, _stock_code: str):
        return self._boards


class TestFundamentalContext(unittest.TestCase):
    def test_non_cn_market_returns_not_supported(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "not_supported",
                    "source_chain": [],
                    "errors": [],
                    "data": {},
                }):
            ctx = manager.get_fundamental_context("AAPL")
        self.assertEqual(ctx["market"], "us")
        self.assertEqual(ctx["status"], "not_supported")
        self.assertEqual(ctx["coverage"].get("valuation"), "not_supported")
        self.assertEqual(ctx["coverage"].get("growth"), "not_supported")
        self.assertEqual(ctx["coverage"].get("earnings"), "not_supported")
        self.assertEqual(ctx["coverage"].get("institution"), "not_supported")
        self.assertEqual(ctx["coverage"].get("capital_flow"), "not_supported")
        self.assertEqual(ctx["coverage"].get("dragon_tiger"), "not_supported")
        self.assertEqual(ctx["coverage"].get("boards"), "not_supported")

    def test_etf_market_downgrades_to_partial_or_not_supported(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        quote = SimpleNamespace(
            pe_ratio=None,
            pb_ratio=None,
            total_mv=5.0e10,
            circ_mv=4.0e10,
            source=SimpleNamespace(value="tencent"),
        )
        # Mock get_fundamental_bundle so growth/earnings/institution are not_supported (no network).
        bundle = {
            "status": "not_supported",
            "growth": {},
            "earnings": {},
            "institution": {},
            "source_chain": [],
            "errors": [],
        }
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "not_supported",
                    "source_chain": [],
                    "errors": [],
                    "data": {},
                }), \
                patch.object(manager, "get_realtime_quote", return_value=quote), \
                patch(
                    "data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle",
                    return_value=bundle,
                ):
            ctx = manager.get_fundamental_context("159915")
        self.assertEqual(ctx["market"], "cn")
        self.assertIn(ctx["status"], ("partial", "not_supported"))
        self.assertEqual(ctx["coverage"].get("valuation"), "ok")
        self.assertEqual(ctx["coverage"].get("growth"), "not_supported")
        self.assertEqual(ctx["coverage"].get("earnings"), "not_supported")
        self.assertEqual(ctx["coverage"].get("institution"), "not_supported")
        self.assertEqual(ctx["coverage"].get("capital_flow"), "not_supported")
        self.assertEqual(ctx["coverage"].get("dragon_tiger"), "not_supported")
        self.assertEqual(ctx["coverage"].get("boards"), "not_supported")

    def test_sector_rankings_use_ordered_fallback(self) -> None:
        akshare = _DummyFetcher("AkshareFetcher", priority=5, rankings=None)
        tushare = _DummyFetcher(
            "TushareFetcher",
            priority=1,
            rankings=([{"name": "半导体", "change_pct": 1.0}], [{"name": "消费", "change_pct": -1.0}]),
        )
        efinance = _DummyFetcher(
            "EfinanceFetcher",
            priority=0,
            rankings=([{"name": "地产", "change_pct": 2.0}], [{"name": "煤炭", "change_pct": -2.0}]),
        )
        manager = DataFetcherManager(fetchers=[efinance, tushare, akshare])
        top, bottom = manager.get_sector_rankings(1)
        self.assertEqual(top[0]["name"], "地产")
        self.assertEqual(bottom[0]["name"], "煤炭")

    def test_fundamental_context_aggregates_blocks(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        quote = SimpleNamespace(
            pe_ratio=12.3,
            pb_ratio=2.1,
            total_mv=1.0e11,
            circ_mv=7.0e10,
            source=SimpleNamespace(value="tencent"),
        )
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "ok",
                    "source_chain": [],
                    "errors": [],
                    "data": {"full_name": "Kweichow Moutai Co., Ltd."},
                }), \
                patch.object(manager, "get_realtime_quote", return_value=quote), \
                patch("data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle", return_value={
                    "growth": {"revenue_yoy": 10.1, "net_profit_yoy": 8.5},
                    "earnings": {"forecast_summary": "预增"},
                    "institution": {"institution_holding_change": 1.2},
                    "source_chain": ["growth:akshare"],
                    "errors": [],
                }), \
                patch.object(manager, "get_capital_flow_context", return_value={"status": "partial", "source_chain": []}), \
                patch.object(manager, "get_dragon_tiger_context", return_value={"status": "partial", "source_chain": []}), \
                patch.object(manager, "get_board_context", return_value={"status": "partial", "source_chain": []}):
            ctx = manager.get_fundamental_context("600519", budget_seconds=1.5)
        self.assertEqual(ctx["market"], "cn")
        self.assertIn("valuation", ctx)
        self.assertIn("company_profile", ctx)
        self.assertEqual(ctx["company_profile"]["data"]["full_name"], "Kweichow Moutai Co., Ltd.")
        self.assertIn("growth", ctx)
        self.assertIn("capital_flow", ctx)
        self.assertIn("dragon_tiger", ctx)

    def test_fundamental_context_preserves_revenue_growth_and_profitability(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=0,
            fundamental_stage_timeout_seconds=2.0,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        revenue_growth = {
            "rows": [
                {
                    "fiscal_year": 2025,
                    "report_date": "2025-12-31",
                    "revenue": 15000000000.0,
                    "revenue_yoy": 12.5,
                }
            ],
            "unit": "yuan",
            "frequency": "annual",
            "source": "stock_lrb_em",
        }
        profitability = {
            "rows": [
                {
                    "period": "2025-12-31",
                    "report_date": "2025-12-31",
                    "gross_margin": 42.61,
                    "net_margin": 28.2,
                    "roe": 43.84,
                }
            ],
            "unit": "percent",
            "frequency": "report_period",
            "source": "stock_financial_analysis_indicator_em",
        }

        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={"status": "not_supported"}), \
                patch.object(manager, "get_realtime_quote", return_value=None), \
                patch(
                    "data_provider.fundamental_adapter.AkshareFundamentalAdapter._fetch_annual_revenue_growth_direct",
                    return_value=(revenue_growth, []),
                ), \
                patch(
                    "data_provider.fundamental_adapter.AkshareFundamentalAdapter._fetch_profitability_indicators",
                    return_value=(profitability, []),
                ), \
                patch("data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle", return_value={
                    "growth": {},
                    "earnings": {},
                    "institution": {},
                    "source_chain": [],
                    "errors": [],
                }), \
                patch.object(manager, "get_capital_flow_context", return_value={"status": "partial", "source_chain": []}), \
                patch.object(manager, "get_dragon_tiger_context", return_value={"status": "partial", "source_chain": []}), \
                patch.object(manager, "get_board_context", return_value={"status": "partial", "source_chain": []}):
            ctx = manager.get_fundamental_context("600519", budget_seconds=2.0)

        financial_report = ctx["earnings"]["data"]["financial_report"]
        self.assertEqual(financial_report["revenue_growth"], revenue_growth)
        self.assertEqual(financial_report["profitability"], profitability)
        self.assertEqual(financial_report["revenue"], 15000000000.0)
        self.assertEqual(financial_report["roe"], 43.84)

    def test_cn_company_profile_uses_cninfo_as_primary_source(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        cninfo_df = pd.DataFrame([{
            "公司名称": "贵州茅台酒股份有限公司",
            "A股简称": "贵州茅台",
            "所属行业": "酒、饮料和精制茶制造业",
            "法人代表": "张德芹",
            "上市日期": "2001-08-27",
            "官方网站": "www.moutaichina.com",
            "主营业务": "茅台酒及系列酒的生产与销售",
            "机构简介": "公司主要从事贵州茅台酒及系列酒的生产和销售。",
        }])
        value_df = pd.DataFrame([
            {"数据日期": "2024-12-31", "总股本": 1256197800, "流通股本": 1256197800},
            {"数据日期": "2025-01-02", "总股本": 1256197800, "流通股本": 1256197800},
        ])
        control_df = pd.DataFrame([{
            "证券代码": "600519",
            "证券简称": "贵州茅台",
            "变动日期": "2025-01-01",
            "实际控制人名称": "贵州省人民政府国有资产监督管理委员会",
            "控股数量": 678291955,
            "控股比例": 54.0,
            "直接控制人名称": "中国贵州茅台酒厂(集团)有限责任公司",
            "控制类型": "实际控制人",
        }])
        akshare_stub = SimpleNamespace(
            stock_profile_cninfo=lambda symbol: cninfo_df,
            stock_value_em=lambda symbol: value_df,
            stock_hold_control_cninfo=lambda symbol: control_df,
        )

        with patch("src.config.get_config", return_value=cfg), \
                patch.dict(sys.modules, {"akshare": akshare_stub}):
            block = manager.get_company_profile_context("600519", budget_seconds=1.0)

        self.assertEqual(block["status"], "ok")
        self.assertEqual(block["source_chain"][0]["provider"], "akshare_stock_profile_cninfo")
        self.assertEqual(block["data"]["full_name"], "贵州茅台酒股份有限公司")
        self.assertEqual(block["data"]["industry"], "酒、饮料和精制茶制造业")
        self.assertEqual(block["data"]["legal_representative"], "张德芹")
        self.assertEqual(block["data"]["listing_date"], "2001-08-27")
        self.assertEqual(block["data"]["website"], "www.moutaichina.com")
        self.assertEqual(block["data"]["main_business"], "茅台酒及系列酒的生产与销售")
        self.assertEqual(block["data"]["company_intro"], "公司主要从事贵州茅台酒及系列酒的生产和销售。")
        self.assertEqual(block["data"]["actual_controller"], "贵州省人民政府国有资产监督管理委员会")
        self.assertEqual(block["data"]["actual_controller_hold_ratio"], 54.0)
        self.assertEqual(block["data"]["direct_controller"], "中国贵州茅台酒厂(集团)有限责任公司")
        self.assertEqual(block["data"]["control_type"], "实际控制人")
        self.assertEqual(block["data"]["total_share_capital"], 1256197800)
        self.assertEqual(block["data"]["float_share_capital"], 1256197800)

    def test_cn_company_profile_keeps_cninfo_when_supplemental_source_fails(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        cninfo_df = pd.DataFrame([{
            "公司名称": "中信证券股份有限公司",
            "所属行业": "资本市场服务",
            "上市日期": "2003-01-06",
            "官方网站": "www.citics.com",
        }])

        def raise_supplemental_error(symbol):
            raise RuntimeError("supplemental unavailable")

        akshare_stub = SimpleNamespace(
            stock_profile_cninfo=lambda symbol: cninfo_df,
            stock_value_em=raise_supplemental_error,
        )

        with patch("src.config.get_config", return_value=cfg), \
                patch.dict(sys.modules, {"akshare": akshare_stub}):
            block = manager.get_company_profile_context("600030", budget_seconds=1.0)

        self.assertEqual(block["status"], "ok")
        self.assertEqual(block["data"]["full_name"], "中信证券股份有限公司")
        self.assertEqual(block["data"]["industry"], "资本市场服务")
        self.assertNotIn("total_share_capital", block["data"])

    def test_hk_company_profile_uses_eastmoney_company_profile(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        profile_df = pd.DataFrame([{
            "公司名称": "腾讯控股有限公司",
            "英文名称": "TENCENT HOLDINGS LIMITED",
            "所属行业": "软件服务",
            "员工人数": 108823,
            "公司网址": "www.tencent.com",
            "公司介绍": "腾讯是一家互联网科技公司。",
        }])
        indicator_df = pd.DataFrame([{
            "已发行股本(股)": 9350000000,
            "已发行股本-H股(股)": 9350000000,
        }])
        akshare_stub = SimpleNamespace(
            stock_hk_company_profile_em=lambda symbol: profile_df,
            stock_hk_financial_indicator_em=lambda symbol: indicator_df,
        )

        with patch("src.config.get_config", return_value=cfg), \
                patch.dict(sys.modules, {"akshare": akshare_stub}):
            block = manager.get_company_profile_context("hk00700", budget_seconds=1.0)

        self.assertEqual(block["status"], "ok")
        self.assertEqual(block["source_chain"][0]["provider"], "akshare_stock_hk_company_profile_em")
        self.assertEqual(block["data"]["full_name"], "腾讯控股有限公司")
        self.assertEqual(block["data"]["industry"], "软件服务")
        self.assertEqual(block["data"]["employee_count"], 108823)
        self.assertEqual(block["data"]["website"], "www.tencent.com")
        self.assertEqual(block["data"]["company_intro"], "腾讯是一家互联网科技公司。")
        self.assertEqual(block["data"]["total_share_capital"], 9350000000)
        self.assertEqual(block["data"]["float_share_capital"], 9350000000)

    def test_fundamental_context_derives_ttm_dividend_yield_from_quote_price(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        quote = SimpleNamespace(
            price=50.0,
            pe_ratio=12.3,
            pb_ratio=2.1,
            total_mv=1.0e11,
            circ_mv=7.0e10,
            source=SimpleNamespace(value="tencent"),
        )
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "not_supported",
                    "source_chain": [],
                    "errors": [],
                    "data": {},
                }), \
                patch.object(manager, "get_realtime_quote", return_value=quote), \
                patch("data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle", return_value={
                    "status": "partial",
                    "growth": {},
                    "earnings": {
                        "dividend": {
                            "ttm_cash_dividend_per_share": 2.5,
                            "ttm_event_count": 1,
                            "events": [{"event_date": "2026-01-01", "cash_dividend_per_share": 2.5}],
                        }
                    },
                    "institution": {},
                    "source_chain": [],
                    "errors": [],
                }), \
                patch.object(manager, "get_capital_flow_context", return_value={"status": "not_supported", "source_chain": []}), \
                patch.object(manager, "get_dragon_tiger_context", return_value={"status": "not_supported", "source_chain": []}), \
                patch.object(manager, "get_board_context", return_value={"status": "not_supported", "source_chain": []}):
            ctx = manager.get_fundamental_context("600519", budget_seconds=1.5)

        dividend_payload = ctx["earnings"]["data"]["dividend"]
        self.assertAlmostEqual(dividend_payload["ttm_dividend_yield_pct"], 5.0, places=6)
        self.assertIn("yield_formula", dividend_payload)

    def test_fundamental_context_dividend_yield_keeps_null_when_price_invalid(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        quote = SimpleNamespace(
            price=None,
            pe_ratio=12.3,
            pb_ratio=2.1,
            total_mv=1.0e11,
            circ_mv=7.0e10,
            source=SimpleNamespace(value="tencent"),
        )
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "not_supported",
                    "source_chain": [],
                    "errors": [],
                    "data": {},
                }), \
                patch.object(manager, "get_realtime_quote", return_value=quote), \
                patch("data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle", return_value={
                    "status": "partial",
                    "growth": {},
                    "earnings": {
                        "dividend": {
                            "ttm_cash_dividend_per_share": 1.2,
                            "events": [{"event_date": "2026-01-01", "cash_dividend_per_share": 1.2}],
                        }
                    },
                    "institution": {},
                    "source_chain": [],
                    "errors": [],
                }), \
                patch.object(manager, "get_capital_flow_context", return_value={"status": "not_supported", "source_chain": []}), \
                patch.object(manager, "get_dragon_tiger_context", return_value={"status": "not_supported", "source_chain": []}), \
                patch.object(manager, "get_board_context", return_value={"status": "not_supported", "source_chain": []}):
            ctx = manager.get_fundamental_context("600519", budget_seconds=1.5)

        dividend_payload = ctx["earnings"]["data"]["dividend"]
        self.assertIsNone(dividend_payload.get("ttm_dividend_yield_pct"))
        self.assertIn("invalid_price_for_ttm_dividend_yield", ctx["earnings"]["errors"])

    def test_non_etf_board_budget_not_forced_to_zero(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        quote = SimpleNamespace(
            pe_ratio=12.3,
            pb_ratio=2.1,
            total_mv=1.0e11,
            circ_mv=7.0e10,
            source=SimpleNamespace(value="tencent"),
        )
        bundle = {
            "status": "not_supported",
            "growth": {},
            "earnings": {},
            "institution": {},
            "source_chain": [],
            "errors": [],
        }
        budgets = {}

        def _capital_flow_side_effect(_stock_code: str, budget_seconds: float = 0.0):
            budgets["capital_flow"] = budget_seconds
            return {"status": "not_supported", "source_chain": [], "errors": [], "data": {}}

        def _dragon_tiger_side_effect(_stock_code: str, budget_seconds: float = 0.0):
            budgets["dragon_tiger"] = budget_seconds
            return {"status": "not_supported", "source_chain": [], "errors": [], "data": {}}

        def _boards_side_effect(_stock_code: str, budget_seconds: float = 0.0):
            budgets["boards"] = budget_seconds
            return {"status": "not_supported", "source_chain": [], "errors": [], "data": {}}

        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "not_supported",
                    "source_chain": [],
                    "errors": [],
                    "data": {},
                }), \
                patch.object(manager, "get_realtime_quote", return_value=quote), \
                patch(
                    "data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle",
                    return_value=bundle,
                ), \
                patch.object(manager, "get_capital_flow_context", side_effect=_capital_flow_side_effect), \
                patch.object(manager, "get_dragon_tiger_context", side_effect=_dragon_tiger_side_effect), \
                patch.object(manager, "get_board_context", side_effect=_boards_side_effect):
            manager.get_fundamental_context("600519")

        self.assertGreater(budgets.get("capital_flow", 0.0), 0.0)
        self.assertGreater(budgets.get("dragon_tiger", 0.0), 0.0)
        self.assertGreater(budgets.get("boards", 0.0), 0.0)

    def test_run_with_timeout_limits_hanging_workers(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        manager._fundamental_timeout_slots = BoundedSemaphore(1)

        unblock = Event()

        def _hanging_task():
            unblock.wait(timeout=0.5)
            return 1

        try:
            result, err, _ = manager._run_with_timeout(_hanging_task, 0.01, "hang")
            self.assertIsNone(result)
            self.assertIn("timeout", err or "")

            result2, err2, _ = manager._run_with_timeout(_hanging_task, 0.01, "hang")
            self.assertIsNone(result2)
            self.assertIn("worker pool exhausted", err2 or "")
        finally:
            unblock.set()
            time.sleep(0.02)

    def test_infer_block_status_treats_all_null_payload_as_non_ok(self) -> None:
        self.assertEqual(
            DataFetcherManager._infer_block_status(
                {"revenue_yoy": None, "net_profit_yoy": None, "summary": ""},
                "partial",
            ),
            "partial",
        )
        self.assertEqual(
            DataFetcherManager._infer_block_status(
                {"revenue_yoy": None, "net_profit_yoy": None},
                "not_supported",
            ),
            "not_supported",
        )
        self.assertEqual(
            DataFetcherManager._infer_block_status(
                {"revenue_yoy": 0.0},
                "partial",
            ),
            "ok",
        )

    def test_valuation_all_none_fields_should_not_be_ok(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        quote = SimpleNamespace(
            pe_ratio=None,
            pb_ratio=None,
            total_mv=None,
            circ_mv=None,
            source=SimpleNamespace(value="tencent"),
        )
        bundle = {
            "status": "not_supported",
            "growth": {},
            "earnings": {},
            "institution": {},
            "source_chain": [],
            "errors": [],
        }
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "get_company_profile_context", return_value={
                    "status": "not_supported",
                    "source_chain": [],
                    "errors": [],
                    "data": {},
                }), \
                patch.object(manager, "get_realtime_quote", return_value=quote), \
                patch(
                    "data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_fundamental_bundle",
                    return_value=bundle,
                ):
            ctx = manager.get_fundamental_context("600519")

        self.assertEqual(ctx["coverage"].get("valuation"), "partial")

    def test_fundamental_cache_key_isolated_by_budget_bucket(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        key_default = manager._get_fundamental_cache_key("600519")
        key_low = manager._get_fundamental_cache_key("600519", 0.4)
        key_high = manager._get_fundamental_cache_key("600519", 1.5)

        self.assertNotEqual(key_default, key_low)
        self.assertNotEqual(key_low, key_high)
        self.assertIn("budget=", key_low)

    def test_board_context_empty_rankings_mark_failed(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        with patch("src.config.get_config", return_value=cfg), \
                patch.object(manager, "_get_sector_rankings_with_meta", return_value=([], [], [], "all failed")):
            ctx = manager.get_board_context("600519", budget_seconds=0.5)
        self.assertEqual(ctx["status"], "failed")
        self.assertEqual(ctx["data"], {})

    def test_capital_flow_not_supported_status(self) -> None:
        manager = DataFetcherManager(fetchers=[])
        cfg = SimpleNamespace(
            enable_fundamental_pipeline=True,
            fundamental_cache_ttl_seconds=120,
            fundamental_stage_timeout_seconds=1.5,
            fundamental_fetch_timeout_seconds=0.8,
            fundamental_retry_max=1,
        )
        with patch("src.config.get_config", return_value=cfg), \
                patch(
                    "data_provider.fundamental_adapter.AkshareFundamentalAdapter.get_capital_flow",
                    return_value={
                        "status": "not_supported",
                        "stock_flow": {},
                        "sector_rankings": {"top": [], "bottom": []},
                        "source_chain": [],
                        "errors": [],
                    },
                ):
            ctx = manager.get_capital_flow_context("600519", budget_seconds=0.5)
        self.assertEqual(ctx["status"], "not_supported")

    def test_get_belong_boards_from_capability_probe(self) -> None:
        fetcher = _DummyBoardFetcher(
            "EfinanceFetcher",
            priority=0,
            boards=[{"name": "白酒"}, {"board_name": "消费"}],
        )
        manager = DataFetcherManager(fetchers=[fetcher])
        boards = manager.get_belong_boards("600519")
        self.assertEqual(len(boards), 2)
        self.assertEqual(boards[0]["name"], "白酒")
        self.assertEqual(boards[1]["name"], "消费")

    def test_get_belong_boards_preserves_cn_code_and_type_fields(self) -> None:
        fetcher = _DummyBoardFetcher(
            "EfinanceFetcher",
            priority=0,
            boards=[
                {"板块名称": "白酒", "板块代码": "BK0815", "板块类型": "行业"},
                {"板块": "消费", "代码": "BK0475", "类别": "概念"},
            ],
        )
        manager = DataFetcherManager(fetchers=[fetcher])
        boards = manager.get_belong_boards("600519")
        self.assertEqual(len(boards), 2)
        self.assertEqual(
            boards[0],
            {"name": "白酒", "code": "BK0815", "type": "行业"},
        )
        self.assertEqual(
            boards[1],
            {"name": "消费", "code": "BK0475", "type": "概念"},
        )

    def test_get_belong_boards_supports_extended_name_aliases_in_dict_payload(self) -> None:
        fetcher = _DummyBoardFetcher(
            "EfinanceFetcher",
            priority=0,
            boards=[
                {"所属板块": "新能源"},
                {"板块名": "半导体"},
                {"industry": "医药"},
                {"行业": "算力"},
            ],
        )
        manager = DataFetcherManager(fetchers=[fetcher])
        boards = manager.get_belong_boards("600519")
        self.assertEqual(
            boards,
            [
                {"name": "新能源"},
                {"name": "半导体"},
                {"name": "医药"},
                {"name": "算力"},
            ],
        )

    def test_missing_value_helpers_keep_common_null_compatibility(self) -> None:
        for value in (None, np.nan, "", "  ", "null", "NaN", " n/a "):
            self.assertTrue(DataFetcherManager._is_missing_board_value(value))
        self.assertFalse(DataFetcherManager._is_missing_board_value("白酒"))
        self.assertFalse(DataFetcherManager._has_meaningful_payload(np.array([None, np.nan])))
        self.assertTrue(DataFetcherManager._has_meaningful_payload(np.array([None, "白酒"])))

    def test_missing_value_helpers_log_expected_pd_isna_fallback(self) -> None:
        sentinel = object()
        with patch("data_provider.base.pd.isna", side_effect=ValueError("ambiguous")):
            with self.assertLogs("data_provider.base", level="DEBUG") as logs:
                self.assertFalse(DataFetcherManager._is_missing_board_value(sentinel))
                self.assertTrue(DataFetcherManager._has_meaningful_payload(sentinel))

        joined_logs = "\n".join(logs.output)
        self.assertIn("[board_value] pd.isna fallback", joined_logs)
        self.assertIn("[fundamental_payload] pd.isna fallback", joined_logs)

    def test_missing_value_helpers_propagate_array_protocol_pd_isna_errors(self) -> None:
        class _ArrayProtocolErrorPayload:
            def __array__(self):
                raise ValueError("boom")

        payload = _ArrayProtocolErrorPayload()
        with self.assertRaises(ValueError):
            DataFetcherManager._is_missing_board_value(payload)
        with self.assertRaises(ValueError):
            DataFetcherManager._has_meaningful_payload(payload)

    def test_missing_value_helpers_propagate_unexpected_pd_isna_errors(self) -> None:
        sentinel = object()
        with patch("data_provider.base.pd.isna", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                DataFetcherManager._is_missing_board_value(sentinel)
            with self.assertRaises(RuntimeError):
                DataFetcherManager._has_meaningful_payload(sentinel)


if __name__ == "__main__":
    unittest.main()
