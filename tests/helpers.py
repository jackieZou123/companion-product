"""测试替身。invoke/astream 签名必须与 ChatModel 一致。"""

from collections.abc import AsyncIterator, Callable, Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.index import create_app


class FrozenClock:
    """测试把「现在」拨快，不真睡 24 小时。"""

    def __init__(self, now: datetime | None = None) -> None:
        self.now = now or datetime.now(timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs: Any) -> None:
        self.now = self.now + timedelta(**kwargs)


class FakeChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeModel:
    def __init__(
        self,
        text: str = "屏障先稳住。今晚把刺激的步骤停掉。",
        *,
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.error = error
        self.calls = 0
        self.last_messages: Any = None
        self.last_config: Any = None

    def _emit(self, input: Any, config: Any) -> FakeChunk:
        self.calls += 1
        self.last_messages = input
        self.last_config = config
        if self.error is not None:
            raise self.error
        return FakeChunk(self.text)

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> FakeChunk:
        return self._emit(input, config)

    def stream(self, input: Any, config: Any = None, **kwargs: Any) -> Generator[FakeChunk, None, None]:
        yield self._emit(input, config)

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[FakeChunk]:
        yield self._emit(input, config)


def test_settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "app_env": "test",
        "openai_api_key": "test-key",
        "llm_provider": "openai",
        "llm_model": "gpt-5.4-mini",
        "langsmith_tracing": False,
        "database_url": "sqlite+aiosqlite:///:memory:",
    }
    data.update(overrides)
    return Settings(_env_file=None, **data)


def start_conversation(client: TestClient, **payload: Any):
    body = {"adult_confirmed": True, "gender": "female", **payload}
    return client.post("/v1/conversations", json=body)


def build_app(
    model: FakeModel | None = None,
    fallback_model: FakeModel | None = None,
    clock: Callable[[], datetime] | None = None,
    **settings_overrides: Any,
) -> FastAPI:
    return create_app(
        settings=test_settings(**settings_overrides),
        llm_override=model or FakeModel(),
        llm_fallback_override=fallback_model,
        clock=clock,
    )


@contextmanager
def api_client(
    model: FakeModel | None = None,
    fallback_model: FakeModel | None = None,
    *,
    user_id: str = "u_1",
    clock: Callable[[], datetime] | None = None,
    **settings_overrides: Any,
) -> Generator[TestClient, None, None]:
    with TestClient(build_app(model, fallback_model, clock, **settings_overrides)) as client:
        client.headers.update({"X-User-Id": user_id})
        yield client
