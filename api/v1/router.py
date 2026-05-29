# -*- coding: utf-8 -*-
"""
===================================
API v1 路由聚合
===================================

职责：
1. 聚合 v1 版本的所有 endpoint 路由
2. 统一添加 /api/v1 前缀
"""

from fastapi import APIRouter, Depends

from api.deps import require_permission
from api.v1.endpoints import admin, analysis, auth, history, stocks, backtest, system_config, agent, usage, payment, portfolio

# 创建 v1 版本主路由
router = APIRouter(prefix="/api/v1")

router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"]
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"],
    dependencies=[Depends(require_permission("chat"))],
)

router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"],
    dependencies=[Depends(require_permission("home"))],
)

router.include_router(
    history.router,
    prefix="/history",
    tags=["History"],
    dependencies=[Depends(require_permission("home"))],
)

router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["Stocks"]
)

router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtest"],
    dependencies=[Depends(require_permission("backtest"))],
)

router.include_router(
    system_config.router,
    prefix="/system",
    tags=["SystemConfig"],
    dependencies=[Depends(require_permission("settings"))],
)

router.include_router(
    usage.router,
    prefix="/usage",
    tags=["Usage"]
)

router.include_router(
    payment.router,
    prefix="/payment",
    tags=["Payment"],
    dependencies=[Depends(require_permission("payment"))],
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"],
    dependencies=[Depends(require_permission("portfolio"))],
)

router.include_router(
    admin.router,
    prefix="/admin",
    tags=["Admin"],
)
