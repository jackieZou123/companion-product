"""进程探活与就绪。"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

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


@router.get("/readyz")
async def readyz(request: Request) -> dict[str, str]:
    settings: Settings = request.app.state.settings
    provider = settings.llm_provider.strip().lower()
    if provider == "openai" and not settings.openai_api_key.strip():
        return {"status": "not_ready", "reason": "openai_api_key_missing"}
    if provider == "deepseek" and not settings.deepseek_api_key.strip():
        return {"status": "not_ready", "reason": "deepseek_api_key_missing"}
    service: DialogueService | None = getattr(request.app.state, "dialogue", None)
    if service is None:
        return {"status": "not_ready", "reason": "runtime_not_started"}
    try:
        await service.ping()
    except Exception:
        return {"status": "not_ready", "reason": "database"}
    return {
        "status": "ready",
        "provider": provider,
        "model": settings.llm_model,
        "tracing": "on" if settings.langsmith_tracing else "off",
    }


@router.get("/metrics")
def metrics(request: Request) -> dict[str, dict[str, int]]:
    service: DialogueService = request.app.state.dialogue
    return {"turns": service.latency_snapshot()}
