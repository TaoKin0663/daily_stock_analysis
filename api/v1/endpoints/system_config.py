# -*- coding: utf-8 -*-
"""System configuration endpoints."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_system_config_service, get_current_user, require_admin
from src.user_context import CurrentUser
from api.v1.schemas.common import ErrorResponse
from api.v1.schemas.system_config import (
    DiscoverLLMChannelModelsRequest,
    DiscoverLLMChannelModelsResponse,
    ExportSystemConfigResponse,
    ImportSystemConfigRequest,
    SystemConfigConflictResponse,
    SystemConfigResponse,
    SystemConfigSchemaResponse,
    SystemConfigValidationErrorResponse,
    TestLLMChannelRequest,
    TestLLMChannelResponse,
    UpdateSystemConfigRequest,
    UpdateSystemConfigResponse,
    ValidateSystemConfigRequest,
    ValidateSystemConfigResponse,
)
from src.services.system_config_service import (
    ConfigConflictError,
    ConfigImportError,
    ConfigValidationError,
    SystemConfigService,
)
from src.permissions import SUPER_ADMIN_ROLE_KEY
from src.core.config_registry import get_field_definition

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_request_user(value: object) -> bool:
    return isinstance(value, CurrentUser)


def _is_admin_config_context(current_user: CurrentUser) -> bool:
    return getattr(current_user, "account_type", "web") in {"admin", "system"}


def _setting_access_level(key: str, item: dict | None = None) -> str:
    schema = (item or {}).get("schema") or {}
    if schema:
        return str(schema.get("access_level") or "admin")
    return str(get_field_definition(str(key or "").upper()).get("access_level") or "admin")



def _has_all_setting_permissions(current_user: CurrentUser) -> bool:
    return bool(
        _is_admin_config_context(current_user)
        or current_user.is_admin
        or current_user.role_key == SUPER_ADMIN_ROLE_KEY
    )


def _filter_config_payload_for_user(payload: dict, current_user: CurrentUser) -> dict:
    if not _is_request_user(current_user):
        return payload

    admin_context = _is_admin_config_context(current_user)
    allowed = set(current_user.setting_permissions or ())
    payload = dict(payload)
    filtered = []
    for item in payload.get("items", []):
        key = str(item.get("key") or "").upper()
        is_platform = _setting_access_level(key, item) == "admin"
        if admin_context:
            filtered.append(item)
            continue
        if is_platform:
            continue
        if _has_all_setting_permissions(current_user) or key in allowed:
            filtered.append(item)
    payload["items"] = filtered
    return payload


def _filter_schema_payload_for_user(payload: dict, current_user: CurrentUser) -> dict:
    if not _is_request_user(current_user):
        return payload

    admin_context = _is_admin_config_context(current_user)
    allowed = set(current_user.setting_permissions or ())
    payload = dict(payload)
    categories = []
    for category in payload.get("categories", []):
        category_payload = dict(category)
        fields = []
        for field in category_payload.get("fields", []):
            key = str(field.get("key") or "").upper()
            is_platform = str(field.get("access_level") or "admin") == "admin"
            if admin_context:
                fields.append(field)
                continue
            if is_platform:
                continue
            if _has_all_setting_permissions(current_user) or key in allowed:
                fields.append(field)
        category_payload["fields"] = fields
        if category_payload["fields"]:
            categories.append(category_payload)
    payload["categories"] = categories
    return payload


def _ensure_setting_write_permissions(keys: list[str], current_user: CurrentUser) -> None:
    if not _is_request_user(current_user):
        return

    admin_context = _is_admin_config_context(current_user)
    platform_keys = [
        key for key in keys
        if _setting_access_level(key) == "admin"
    ]
    user_keys = [
        key for key in keys
        if _setting_access_level(key) != "admin"
    ]
    if admin_context:
        denied = []
    else:
        denied = platform_keys
    if denied:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "setting_permission_denied",
                "message": "Current context cannot modify one or more setting fields",
                "settingKeys": denied,
            },
        )

    if _has_all_setting_permissions(current_user):
        return

    allowed = set(current_user.setting_permissions or ())
    denied = [
        key
        for key in user_keys
        if str(key or "").upper() not in allowed
    ]
    if denied:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "setting_permission_denied",
                "message": "Current role cannot modify one or more setting fields",
                "settingKeys": denied,
            },
        )


def _ensure_desktop_mode() -> None:
    """Restrict desktop backup/restore endpoints to desktop runtime only."""
    if os.getenv("DSA_DESKTOP_MODE", "").strip().lower() != "true":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "desktop_only_feature",
                "message": "This endpoint is only available in desktop mode",
            },
        )


@router.get(
    "/config",
    response_model=SystemConfigResponse,
    responses={
        200: {"description": "Configuration loaded"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Get system configuration",
    description="Read current configuration from .env and return raw values.",
)
def get_system_config(
    include_schema: bool = Query(True, description="Whether to include schema metadata"),
    service: SystemConfigService = Depends(get_system_config_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> SystemConfigResponse:
    """Load and return current system configuration."""
    try:
        payload = service.get_config(include_schema=include_schema)
        payload = _filter_config_payload_for_user(payload, current_user)
        return SystemConfigResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to load system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to load system configuration",
            },
        )


@router.put(
    "/config",
    response_model=UpdateSystemConfigResponse,
    responses={
        200: {"description": "Configuration updated"},
        400: {"description": "Validation failed", "model": SystemConfigValidationErrorResponse},
        409: {"description": "Version conflict", "model": SystemConfigConflictResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Update system configuration",
    description="Update key-value pairs in .env. Mask token preserves existing secret values.",
)
def update_system_config(
    request: UpdateSystemConfigRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> UpdateSystemConfigResponse:
    """Validate and persist system configuration updates."""
    _ensure_setting_write_permissions([item.key for item in request.items], current_user)

    try:
        payload = service.update(
            config_version=request.config_version,
            items=[item.model_dump() for item in request.items],
            mask_token=request.mask_token,
            reload_now=request.reload_now,
        )
        return UpdateSystemConfigResponse.model_validate(payload)
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_failed",
                "message": "System configuration validation failed",
                "issues": exc.issues,
            },
        )
    except ConfigConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "config_version_conflict",
                "message": "Configuration has changed, please reload and retry",
                "current_config_version": exc.current_version,
            },
        )
    except Exception as exc:
        logger.error("Failed to update system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to update system configuration",
            },
        )


@router.get(
    "/config/export",
    response_model=ExportSystemConfigResponse,
    responses={
        200: {"description": "Desktop env exported"},
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Desktop mode only", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Export desktop env backup",
    description="Desktop-only endpoint that returns the raw saved .env content.",
)
def export_desktop_system_config(
    service: SystemConfigService = Depends(get_system_config_service),
) -> ExportSystemConfigResponse:
    """Export the active `.env` file for desktop backup."""
    _ensure_desktop_mode()
    try:
        payload = service.export_desktop_env()
        return ExportSystemConfigResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to export desktop system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to export desktop system configuration",
            },
        )


@router.post(
    "/config/import",
    response_model=UpdateSystemConfigResponse,
    responses={
        200: {"description": "Desktop env imported"},
        400: {
            "description": "Import failed",
            "content": {
                "application/json": {
                    "schema": {
                        "anyOf": [
                            {"$ref": "#/components/schemas/ErrorResponse"},
                            {"$ref": "#/components/schemas/SystemConfigValidationErrorResponse"},
                        ]
                    }
                }
            },
        },
        401: {"description": "Unauthorized", "model": ErrorResponse},
        403: {"description": "Desktop mode only", "model": ErrorResponse},
        409: {"description": "Version conflict", "model": SystemConfigConflictResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Import desktop env backup",
    description="Desktop-only endpoint that merges raw .env text into the saved configuration.",
)
def import_desktop_system_config(
    request: ImportSystemConfigRequest,
    service: SystemConfigService = Depends(get_system_config_service),
) -> UpdateSystemConfigResponse:
    """Import a desktop `.env` backup into the active config."""
    _ensure_desktop_mode()
    try:
        payload = service.import_desktop_env(
            config_version=request.config_version,
            content=request.content,
            reload_now=request.reload_now,
        )
        return UpdateSystemConfigResponse.model_validate(payload)
    except ConfigImportError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_import_file",
                "message": exc.message,
            },
        )
    except ConfigValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "validation_failed",
                "message": "System configuration validation failed",
                "issues": exc.issues,
            },
        )
    except ConfigConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "config_version_conflict",
                "message": "Configuration has changed, please reload and retry",
                "current_config_version": exc.current_version,
            },
        )
    except Exception as exc:
        logger.error("Failed to import desktop system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to import desktop system configuration",
            },
        )


@router.post(
    "/config/validate",
    response_model=ValidateSystemConfigResponse,
    responses={
        200: {"description": "Validation completed"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Validate system configuration",
    description="Validate submitted configuration values without writing to .env.",
)
def validate_system_config(
    request: ValidateSystemConfigRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> ValidateSystemConfigResponse:
    """Run pre-save validation only."""
    _ensure_setting_write_permissions([item.key for item in request.items], current_user)
    try:
        payload = service.validate(items=[item.model_dump() for item in request.items])
        return ValidateSystemConfigResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to validate system configuration: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to validate system configuration",
            },
        )


@router.post(
    "/config/llm/test-channel",
    response_model=TestLLMChannelResponse,
    responses={
        200: {"description": "Channel test completed"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Test one LLM channel",
    description="Run a minimal LLM request against one unsaved or saved channel definition.",
)
def test_llm_channel(
    request: TestLLMChannelRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    _admin: None = Depends(require_admin()),
) -> TestLLMChannelResponse:
    """Validate and test one channel definition without writing `.env`."""
    try:
        payload = service.test_llm_channel(
            name=request.name,
            protocol=request.protocol,
            base_url=request.base_url,
            api_key=request.api_key,
            models=request.models,
            enabled=request.enabled,
            timeout_seconds=request.timeout_seconds,
        )
        return TestLLMChannelResponse.model_validate(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Failed to test LLM channel: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to test LLM channel",
            },
        )


@router.post(
    "/config/llm/discover-models",
    response_model=DiscoverLLMChannelModelsResponse,
    responses={
        200: {"description": "Model discovery completed"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Discover models for one LLM channel",
    description="Call one unsaved or saved channel's `/models` endpoint and return discovered model IDs.",
)
def discover_llm_channel_models(
    request: DiscoverLLMChannelModelsRequest,
    service: SystemConfigService = Depends(get_system_config_service),
    _admin: None = Depends(require_admin()),
) -> DiscoverLLMChannelModelsResponse:
    """Discover models for one channel definition without writing `.env`."""
    try:
        payload = service.discover_llm_channel_models(
            name=request.name,
            protocol=request.protocol,
            base_url=request.base_url,
            api_key=request.api_key,
            models=request.models,
            timeout_seconds=request.timeout_seconds,
        )
        return DiscoverLLMChannelModelsResponse.model_validate(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": str(exc),
            },
        )
    except Exception as exc:
        logger.error("Failed to discover LLM channel models: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to discover LLM channel models",
            },
        )


@router.get(
    "/config/schema",
    response_model=SystemConfigSchemaResponse,
    responses={
        200: {"description": "Schema loaded"},
        500: {"description": "Internal server error", "model": ErrorResponse},
    },
    summary="Get system configuration schema",
    description="Return categorized field metadata used for dynamic settings form rendering.",
)
def get_system_config_schema(
    service: SystemConfigService = Depends(get_system_config_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> SystemConfigSchemaResponse:
    """Return schema metadata for system configuration fields."""
    try:
        payload = service.get_schema()
        payload = _filter_schema_payload_for_user(payload, current_user)
        return SystemConfigSchemaResponse.model_validate(payload)
    except Exception as exc:
        logger.error("Failed to load system configuration schema: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "Failed to load system configuration schema",
            },
        )
