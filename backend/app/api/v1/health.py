"""Application health endpoints."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.core.database import check_database_connection

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("/live")
def live() -> dict[str, str]:
    """Return process liveness."""

    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, Any]:
    """Check database, Qdrant, and embedding dependencies."""

    checks = {
        "database": _check_database(),
        "qdrant": _check_qdrant(),
        "embedding": _check_embedding(),
    }
    healthy = all(item["ok"] for item in checks.values())
    payload = {
        "status": "ok" if healthy else "unhealthy",
        "checks": checks,
    }

    if not healthy:
        raise HTTPException(status_code=503, detail=payload)

    return payload


def _check_database() -> dict[str, Any]:
    try:
        metadata = check_database_connection()
    except Exception as exc:  # pragma: no cover - runtime dependency check
        return {
            "ok": False,
            "error": type(exc).__name__,
        }

    return {
        "ok": True,
        "metadata": metadata,
    }


def _check_qdrant() -> dict[str, Any]:
    base_url = _qdrant_base_url()
    timeout = _float_env("QDRANT_TIMEOUT_SECONDS", 5.0)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(f"{base_url}/collections")
            response.raise_for_status()
            data = response.json()
    except Exception as exc:  # pragma: no cover - runtime dependency check
        return {
            "ok": False,
            "url": base_url,
            "error": type(exc).__name__,
        }

    collections = data.get("result", {}).get("collections", [])
    return {
        "ok": True,
        "url": base_url,
        "collection_count": len(collections) if isinstance(collections, list) else None,
    }


def _check_embedding() -> dict[str, Any]:
    base_url = os.environ.get("EMBEDDING_BASE_URL", "http://127.0.0.1:8088").rstrip("/")
    timeout = _float_env("EMBEDDING_TIMEOUT_SECONDS", 10.0)

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{base_url}/embed",
                json={"inputs": "health check"},
            )

            if response.status_code == 404:
                response = client.get(f"{base_url}/health")

            response.raise_for_status()
    except Exception as exc:  # pragma: no cover - runtime dependency check
        return {
            "ok": False,
            "url": base_url,
            "error": type(exc).__name__,
        }

    return {
        "ok": True,
        "url": base_url,
        "status_code": response.status_code,
    }


def _qdrant_base_url() -> str:
    if os.environ.get("QDRANT_URL"):
        return os.environ["QDRANT_URL"].rstrip("/")

    host = os.environ.get("QDRANT_HOST", "127.0.0.1")
    port = os.environ.get("QDRANT_HTTP_PORT", "6333")
    scheme = "https" if os.environ.get("QDRANT_USE_HTTPS") == "true" else "http"
    return f"{scheme}://{host}:{port}"


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default
