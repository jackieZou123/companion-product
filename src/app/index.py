"""应用入口：组装 FastAPI、数据库和对话服务。"""

from contextlib import asynccontextmanager
from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from app.pages.conversations import router as conversation_router
from app.pages.index import router as health_router
from app.pages.schemas import register_error_handlers
from app.pages.site import WEB_DIR
from app.character import CharacterRepository
from app.config import Settings, get_settings
from app.db import create_engine, create_schema, create_session_factory
from app.dialogue import DialogueService
from app.dialogue.store import SqlConversationStore
from app.llm import ChatModel, ChatModelFactory
from app.memory.store import SqlMemoryStore
from app.nudge.store import SqlNudgeStore
from app.observability import configure_logging, request_id_ctx
from app.observability.metrics import LatencyWindow
from app.observability.tracing import configure_tracing
from app.safety import SafetyPolicy


class RequestIdMiddleware(BaseHTTPMiddleware):
    """给每个请求补 x-request-id，方便对日志。"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
        finally:
            request_id_ctx.reset(token)


def _cors_origins(value: str) -> list[str]:
    if value.strip() == "*":
        return ["*"]
    return [item.strip() for item in value.split(",") if item.strip()]


def create_app(
    settings: Settings | None = None,
    llm_override: ChatModel | None = None,
    llm_fallback_override: ChatModel | None = None,
    clock: Callable[[], datetime] | None = None,
) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    configure_tracing(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时建表、注入对话服务；关闭时释放连接池
        engine = create_engine(resolved.database_url)
        await create_schema(engine)
        session_factory = create_session_factory(engine)
        app.state.dialogue = DialogueService(
            settings=resolved,
            store=SqlConversationStore(session_factory),
            characters=CharacterRepository(),
            llm_factory=ChatModelFactory(
                resolved,
                override=llm_override,
                fallback_override=llm_fallback_override,
            ),
            memory=SqlMemoryStore(session_factory),
            nudges=SqlNudgeStore(session_factory),
            safety=SafetyPolicy(),
            latency=LatencyWindow(),
            clock=clock,
        )
        yield
        await engine.dispose()

    app = FastAPI(
        title="玫莉蔻",
        version="0.1.0",
        summary="面向成年用户的一对一中文 AI 陪伴对话内核",
        lifespan=lifespan,
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(resolved.cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    app.state.settings = resolved
    app.include_router(health_router)
    app.include_router(conversation_router)
    assets = WEB_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.index:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
