"""用 DialogueService 跑需要走图的样本。单测里必须配 FakeModel。"""

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from app.character import CharacterRepository
from app.config import Settings
from app.db import create_engine, create_schema, create_session_factory
from app.dialogue import DialogueService, TurnResult
from app.dialogue.store import SqlConversationStore
from app.eval.cases import EvalCase
from app.eval.scorers import Score, score_case
from app.llm import ChatModel, ChatModelFactory
from app.observability.metrics import LatencyWindow
from app.safety import SafetyPolicy


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
    engine: AsyncEngine
    model: Any


async def make_runtime(settings: Settings, model: ChatModel) -> EvalRuntime:
    engine = create_engine(settings.database_url)
    await create_schema(engine)
    store = SqlConversationStore(create_session_factory(engine))
    service = DialogueService(
        settings=settings,
        store=store,
        characters=CharacterRepository(),
        llm_factory=ChatModelFactory(settings, override=model),
        safety=SafetyPolicy(),
        latency=LatencyWindow(),
    )
    return EvalRuntime(service=service, store=store, engine=engine, model=model)


async def run_case(runtime: EvalRuntime, case: EvalCase) -> CaseResult:
    if case.runner == "prompt":
        text = CharacterRepository().get(case.character_id).system_prompt()
        return CaseResult(case, score_case(case, text=text), text, 0)
    if case.runner in {"reply", "reply_pair"}:
        return CaseResult(case, score_case(case, text=case.assistant_text), case.assistant_text, 0)
    if case.runner != "service":
        raise ValueError(f"未知 runner: {case.runner}")

    service = runtime.service
    conversation = await service.create_conversation(
        user_id=f"eval:{case.id}",
        character_id=case.character_id,
        adult_confirmed=True,
    )
    for user_text, assistant_text in _history_pairs(case):
        await runtime.store.append(conversation.id, user_text, assistant_text)
    before = int(getattr(runtime.model, "calls", 0))
    result: TurnResult = await service.turn(conversation.id, case.user_text, request_id=f"eval:{case.id}")
    calls = int(getattr(runtime.model, "calls", 0)) - before
    score = score_case(
        case,
        text=result.assistant_text,
        safety_action=result.safety_action,
        safety_code=result.safety_code,
        model_calls=calls,
    )
    return CaseResult(case, score, result.assistant_text, calls)


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
