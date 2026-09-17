"""用 DialogueService 跑需要走图的样本。单测里必须配 FakeModel。"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from app.character import CharacterRepository
from app.config import Settings, get_settings
from app.db import create_engine, create_schema, create_session_factory
from app.dialogue import DialogueService, TurnResult
from app.dialogue.store import SqlConversationStore
from app.eval.cases import EvalCase
from app.eval.scorers import Score, score_case
from app.llm import ChatModel, ChatModelFactory
from app.memory.extract import extract, render_facts
from app.memory.store import SqlMemoryStore
from app.nudge.store import SqlNudgeStore
from app.observability.metrics import LatencyWindow
from app.observability.tracing import configure_tracing
from app.safety import SafetyPolicy

STUB_REPLY = "先别抓。干燥发紧多半是屏障在叫。"


@dataclass(frozen=True)
class CaseResult:
    case: EvalCase
    score: Score
    assistant_text: str
    model_calls: int


@dataclass
class EvalRuntime:
    service: DialogueService
    store: SqlConversationStore
    memory: SqlMemoryStore
    engine: AsyncEngine
    model: Any


class EvalStubModel:
    """CLI 默认替身。不打网关。单测请用 FakeModel。"""

    def __init__(self, text: str = STUB_REPLY) -> None:
        self.text = text
        self.calls = 0

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        self.calls += 1
        return _StubChunk(self.text)

    async def astream(
        self, input: Any, config: Any = None, **kwargs: Any
    ) -> AsyncIterator[Any]:
        self.calls += 1
        yield _StubChunk(self.text)


class CountingModel:
    """给评测数调用次数。ChatOpenAI 本身没有 calls。"""

    def __init__(self, inner: ChatModel) -> None:
        self._inner = inner
        self.calls = 0

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        self.calls += 1
        return self._inner.invoke(input, config=config, **kwargs)

    async def astream(
        self, input: Any, config: Any = None, **kwargs: Any
    ) -> AsyncIterator[Any]:
        self.calls += 1
        async for chunk in self._inner.astream(input, config=config, **kwargs):
            yield chunk


class _StubChunk:
    def __init__(self, content: str) -> None:
        self.content = content


def eval_settings(*, live: bool) -> Settings:
    """默认内存库 + Stub；--live 才读 .env 里的供应商。"""
    if not live:
        return Settings(
            _env_file=None,
            app_env="test",
            openai_api_key="eval-local",
            langsmith_tracing=False,
            database_url="sqlite+aiosqlite:///:memory:",
        )
    # 评测写入内存，避免污染本地会话库；密钥仍走环境
    return get_settings().model_copy(
        update={"database_url": "sqlite+aiosqlite:///:memory:"}
    )


def eval_model(settings: Settings, *, live: bool) -> ChatModel:
    """live=False 用 Stub；live=True 走 ChatModelFactory，缺 Key 直接抛。"""
    if not live:
        return EvalStubModel()
    return CountingModel(ChatModelFactory(settings).chat_model())


async def make_runtime(settings: Settings, model: ChatModel) -> EvalRuntime:
    configure_tracing(settings)
    engine = create_engine(settings.database_url)
    await create_schema(engine)
    session_factory = create_session_factory(engine)
    store = SqlConversationStore(session_factory)
    memory = SqlMemoryStore(session_factory)
    service = DialogueService(
        settings=settings,
        store=store,
        characters=CharacterRepository(),
        llm_factory=ChatModelFactory(settings, override=model),
        memory=memory,
        nudges=SqlNudgeStore(session_factory),
        safety=SafetyPolicy(),
        latency=LatencyWindow(),
    )
    return EvalRuntime(
        service=service, store=store, memory=memory, engine=engine, model=model
    )


async def run_case(runtime: EvalRuntime, case: EvalCase) -> CaseResult:
    if case.runner == "prompt":
        text = CharacterRepository().get(case.character_id).system_prompt()
        return CaseResult(case, score_case(case, text=text), text, 0)
    if case.runner == "extract":
        text = render_facts(extract(case.user_text))
        return CaseResult(case, score_case(case, text=text), text, 0)
    if case.runner in {"reply", "reply_pair"}:
        return CaseResult(case, score_case(case, text=case.assistant_text), case.assistant_text, 0)
    if case.runner not in {"service", "service_turns"}:
        raise ValueError(f"未知 runner: {case.runner}")

    user_id = f"eval:{case.id}"
    service = runtime.service
    conversation = await service.create_conversation(
        user_id=user_id,
        character_id=case.character_id,
    )
    for user_text, assistant_text in _history_pairs(case):
        await runtime.store.append(conversation.id, user_text, assistant_text)
    # 记忆准确性必须连续 turn：append 历史不会走 remember
    before = int(getattr(runtime.model, "calls", 0))
    result: TurnResult | None = None
    for index, user_text in enumerate(_turn_texts(case)):
        result = await service.turn(
            conversation.id,
            user_text,
            request_id=f"eval:{case.id}:{index}",
        )
    if result is None:
        raise ValueError(f"{case.id} 没有可跑的回合")
    calls = int(getattr(runtime.model, "calls", 0)) - before
    recalled = await _recalled_block(runtime, user_id, case.character_id)
    score = score_case(
        case,
        text=result.assistant_text,
        safety_action=result.safety_action,
        safety_code=result.safety_code,
        intent_code=result.action.code,
        model_calls=calls,
        recalled_text=recalled,
    )
    return CaseResult(case, score, result.assistant_text, calls)


def _turn_texts(case: EvalCase) -> list[str]:
    if case.runner == "service_turns":
        texts = [item for item in case.turns if item.strip()]
        if not texts:
            raise ValueError(f"{case.id} 缺少 turns")
        return texts
    return [case.user_text]


async def _recalled_block(
    runtime: EvalRuntime, user_id: str, character_id: str
) -> str:
    snapshot = await runtime.memory.recall(user_id, character_id)
    return snapshot.prompt_block()


def _history_pairs(case: EvalCase) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    history = list(case.history)
    index = 0
    while index + 1 < len(history):
        left, right = history[index], history[index + 1]
        if left.get("role") == "user" and right.get("role") == "assistant":
            pairs.append((left["content"], right["content"]))
            index += 2
        else:
            index += 1
    return pairs
