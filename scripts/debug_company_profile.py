#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fetch and print the companyProfile data path used by analysis reports."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_provider.base import DataFetcherManager  # noqa: E402
from src.utils.data_processing import extract_company_profile_detail_field  # noqa: E402


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Debug companyProfile fetching and API-field extraction."
    )
    parser.add_argument("stock_code", help="Stock code, for example 600519, HK00700, or AAPL.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override company profile fetch timeout in seconds.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    manager = DataFetcherManager()
    block = manager.get_company_profile_context(args.stock_code, budget_seconds=args.timeout)
    api_field = extract_company_profile_detail_field(
        context_snapshot=None,
        fallback_fundamental_payload={"company_profile": block},
    )

    print("=== fundamental_context.company_profile ===")
    print(_json_dump(block))
    print()
    print("=== report.details.company_profile ===")
    print(_json_dump(api_field))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
