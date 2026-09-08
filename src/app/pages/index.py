"""进程探活与就绪。"""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import Settings
from app.dialogue import DialogueService

router = APIRouter(tags=["health"])


@router.get("/")
def root() -> RedirectResponse:
    """浏览器打开站点时进 Swagger，避免根路径 404。"""
    return RedirectResponse(url="/docs")


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """进程活着即可。依赖检查走 /readyz。"""
    return {"status": "ok"}


@router.get("/readyz", response_model=None)
async def readyz(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    provider = settings.llm_provider.strip().lower()
    payload: dict[str, Any]
    if provider == "openai" and not settings.openai_api_key.strip():
        payload = {"status": "not_ready", "reason": "openai_api_key_missing"}
    elif provider == "deepseek" and not settings.deepseek_api_key.strip():
        payload = {"status": "not_ready", "reason": "deepseek_api_key_missing"}
    else:
        service: DialogueService | None = getattr(request.app.state, "dialogue", None)
        if service is None:
            payload = {"status": "not_ready", "reason": "runtime_not_started"}
        else:
            try:
                await service.ping()
                payload = {
                    "status": "ready",
                    "provider": provider,
                    "model": settings.llm_model,
                    "tracing": "on" if settings.langsmith_tracing else "off",
                }
            except Exception:
                payload = {"status": "not_ready", "reason": "database"}
    if payload["status"] != "ready":
        return JSONResponse(status_code=503, content=payload)
    return JSONResponse(status_code=200, content=payload)


@router.get("/metrics")
def metrics(request: Request) -> dict[str, dict[str, int]]:
    service: DialogueService = request.app.state.dialogue
    return {"turns": service.latency_snapshot()}
