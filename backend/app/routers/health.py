import asyncio
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal

router = APIRouter(tags=["health"])

_VERSION = settings.git_sha


@router.get("/health")
async def health():
    return {"status": "ok", "version": _VERSION}


async def _check_db() -> str:
    try:
        async with AsyncSessionLocal() as session:
            await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=1.0)
        return "ok"
    except Exception as exc:
        return str(exc)[:80]


async def _check_anthropic() -> str:
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get("https://api.anthropic.com")
        # 401/403 = API reachable, credentials needed (expected without auth)
        return "ok" if r.status_code in (200, 401, 403) else f"http_{r.status_code}"
    except Exception as exc:
        return str(exc)[:80]


async def _check_langfuse() -> str:
    if not settings.langfuse_enabled:
        return "disabled"
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            r = await client.get(settings.langfuse_base_url)
        return "ok" if r.status_code < 500 else f"http_{r.status_code}"
    except Exception as exc:
        return str(exc)[:80]


@router.get("/health/deep")
async def health_deep():
    db, anthropic, langfuse = await asyncio.gather(
        _check_db(),
        _check_anthropic(),
        _check_langfuse(),
    )
    checks: dict[str, Any] = {"db": db, "anthropic": anthropic, "langfuse": langfuse}
    status = "ok" if db == "ok" else "degraded"
    http_code = 200 if db == "ok" else 503
    return JSONResponse(
        content={"status": status, "version": _VERSION, "checks": checks},
        status_code=http_code,
    )
