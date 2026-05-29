# -*- coding: utf-8 -*-
"""
===================================
API 依赖注入模块
===================================

职责：
1. 提供数据库 Session 依赖
2. 提供配置依赖
3. 提供服务层依赖
"""

from typing import Generator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.system_config_service import SystemConfigService
from src.user_context import CurrentUser
from src.permissions import SUPER_ADMIN_ROLE_KEY


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库 Session 依赖
    
    使用 FastAPI 依赖注入机制，确保请求结束后自动关闭 Session
    
    Yields:
        Session: SQLAlchemy Session 对象
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    获取配置依赖
    
    Returns:
        Config: 配置单例对象
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    获取数据库管理器依赖
    
    Returns:
        DatabaseManager: 数据库管理器单例对象
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service


def get_credit_service():
    """Get CreditService singleton."""
    from src.services.credit_service import CreditService
    return CreditService.get_instance()


def require_min_balance():
    """Dependency: block request if user has no credits."""
    def dependency(
        current_user: CurrentUser = Depends(get_current_user),
        cs=Depends(get_credit_service),
    ):
        if not cs.check_balance(current_user.id):
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "insufficient_credits",
                    "message": "积分不足，请充值",
                },
            )
    return dependency


def require_admin():
    """Dependency: block request if user is not an admin."""
    def dependency(current_user: CurrentUser = Depends(get_current_user)):
        if not current_user.is_admin and current_user.role_key != SUPER_ADMIN_ROLE_KEY:
            raise HTTPException(
                status_code=403,
                detail={"error": "admin_required", "message": "仅管理员可执行此操作"},
            )
    return dependency


def require_permission(menu_key: str):
    """Dependency: block request if user lacks a menu permission."""
    def dependency(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.is_admin or current_user.role_key == SUPER_ADMIN_ROLE_KEY:
            return
        if menu_key not in set(current_user.menu_permissions or ()):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "permission_denied",
                    "message": "当前角色无权访问该功能",
                    "menuKey": menu_key,
                },
            )
    return dependency


def require_any_permission(menu_keys: list[str]):
    """Dependency: allow users with any permission from a set."""
    def dependency(current_user: CurrentUser = Depends(get_current_user)):
        if current_user.is_admin or current_user.role_key == SUPER_ADMIN_ROLE_KEY:
            return
        permissions = set(current_user.menu_permissions or ())
        if not any(menu_key in permissions for menu_key in menu_keys):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "permission_denied",
                    "message": "当前角色无权访问该功能",
                    "menuKeys": menu_keys,
                },
            )
    return dependency


def get_current_user(request: Request) -> CurrentUser:
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Login required"},
        )
    return user
