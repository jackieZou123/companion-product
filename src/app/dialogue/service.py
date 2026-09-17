"""对话服务：非流式走 LangGraph，流式共用安全门和 Prompt。"""

import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.character import (
    CharacterNotFoundError,
    CharacterProfile,
    CharacterRepository,
)
from app.character.address import fill_address
from app.character.react import ReactPolicy
from app.config import Settings
from app.dialogue.generate import Generation, astream_generation
from app.dialogue.graph import build_dialogue_graph, build_model_messages
from app.dialogue.intent import ActionProposal, IntentPolicy, NONE
from app.dialogue.store import (
    Conversation,
    ConversationNotFoundError,
    SqlConversationStore,
)
from app.llm import ChatModelFactory, LLMConfigurationError
from app.memory.models import MemorySnapshot
from app.memory.store import SqlMemoryStore
from app.nudge.models import Nudge
from app.nudge.policy import IDLE_CARE, NudgePolicy, pick_reply
from app.nudge.store import SqlNudgeStore
from app.observability.metrics import LatencyWindow
from app.observability.tracing import dialogue_trace, turn_run_config
from app.safety import SafetyPolicy


@dataclass(frozen=True)
class TurnResult:
    conversation_id: str
    assistant_text: str
    safety_action: str
    safety_code: str
    react_action: str
    react_code: str
    model: str
    degraded: bool
    latency_ms: int
    action: ActionProposal = ActionProposal()


@dataclass(frozen=True)
class StreamEvent:
    event: str
    data: dict[str, Any]


def _action_from_graph(result: dict[str, Any]) -> ActionProposal:
    code = result.get("intent_code") or NONE
    if code == NONE:
        return ActionProposal()
    slots = result.get("intent_slots") or {}
    return ActionProposal(
        code=code,
        slots=dict(slots),
        confirm_required=bool(result.get("intent_confirm")),
    )


class DialogueService:
    """一对一回合编排。拒绝和纯呼唤不调用模型。"""

    def __init__(
        self,
        settings: Settings,
        store: SqlConversationStore,
        characters: CharacterRepository,
        llm_factory: ChatModelFactory,
        memory: SqlMemoryStore,
        nudges: SqlNudgeStore,
        safety: SafetyPolicy | None = None,
        react: ReactPolicy | None = None,
        latency: LatencyWindow | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._settings = settings
        self._store = store
        self._characters = characters
        self._llm_factory = llm_factory
        self._memory = memory
        self._nudges = nudges
        self._safety = safety or SafetyPolicy()
        self._react = react or ReactPolicy()
        self._intent = IntentPolicy()
        self._latency = latency or LatencyWindow()
        self._nudge_policy = NudgePolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._graph = build_dialogue_graph(
            characters,
            llm_factory,
            self._safety,
            self._react,
            memory=memory,
        )

    async def ping(self) -> None:
        await self._store.ping()

    def latency_snapshot(self) -> dict[str, int]:
        return self._latency.snapshot()

    async def create_conversation(
        self,
        user_id: str,
        character_id: str | None,
    ) -> Conversation:
        resolved = character_id or self._characters.default_id()
        self._characters.get(resolved)
        return await self._store.create(
            user_id=user_id,
            character_id=resolved,
        )

    async def get_conversation(
        self, conversation_id: str, *, user_id: str | None = None
    ) -> Conversation:
        return await self._store.get(conversation_id, user_id=user_id)

    async def list_conversations(self, user_id: str) -> list[Conversation]:
        return await self._store.list_for_user(user_id)

    async def export_user(self, user_id: str) -> list[Conversation]:
        return await self._store.export_for_user(user_id)

    async def delete_conversation(self, conversation_id: str, *, user_id: str) -> None:
        await self._store.delete(conversation_id, user_id=user_id)

    async def delete_user_data(self, user_id: str) -> int:
        deleted = await self._store.delete_all_for_user(user_id)
        await self._memory.delete_all_for_user(user_id)
        await self._nudges.delete_all_for_user(user_id)
        return deleted

    def _character_id(self, character_id: str | None) -> str:
        resolved = character_id or self._characters.default_id()
        self._characters.get(resolved)
        return resolved

    async def get_memory(
        self, user_id: str, character_id: str | None = None
    ) -> MemorySnapshot:
        return await self._memory.recall(user_id, self._character_id(character_id))

    async def export_memory(self, user_id: str) -> list[MemorySnapshot]:
        return await self._memory.list_for_user(user_id)

    async def patch_memory_profile(
        self,
        user_id: str,
        slot: str,
        value: str,
        character_id: str | None = None,
    ) -> MemorySnapshot:
        return await self._memory.patch_profile(
            user_id, self._character_id(character_id), slot, value
        )

    async def delete_memory_event(
        self, event_id: int, *, user_id: str, character_id: str | None = None
    ) -> None:
        await self._memory.delete_event(
            event_id, user_id=user_id, character_id=self._character_id(character_id)
        )

    async def delete_memory(
        self, user_id: str, character_id: str | None = None
    ) -> None:
        await self._memory.delete_all(user_id, self._character_id(character_id))

    def _now(self) -> datetime:
        return self._clock()

    async def list_nudges(
        self, user_id: str, character_id: str | None = None
    ) -> list[Nudge]:
        resolved = self._character_id(character_id)
        now = self._now()
        pending = await self._nudges.list_pending(user_id, resolved, now=now)
        if pending:
            return pending
        created = await self._maybe_create_nudge(user_id, resolved, now)
        return [created] if created is not None else []

    async def export_nudges(self, user_id: str) -> list[Nudge]:
        return await self._nudges.list_for_user(user_id, now=self._now())

    async def ack_nudge(self, nudge_id: int, *, user_id: str) -> Nudge:
        return await self._nudges.ack(nudge_id, user_id=user_id, now=self._now())

    async def dismiss_nudge(self, nudge_id: int, *, user_id: str) -> Nudge:
        return await self._nudges.dismiss(nudge_id, user_id=user_id, now=self._now())

    async def _maybe_create_nudge(
        self, user_id: str, character_id: str, now: datetime
    ) -> Nudge | None:
        snapshot = await self._memory.recall(user_id, character_id)
        latest = await self._store.latest_for_user(user_id, character_id)
        last_created = await self._nudges.last_created_at(user_id, character_id)
        bank = self._characters.get(character_id).nudge(IDLE_CARE)
        decision = self._nudge_policy.evaluate(
            stage=snapshot.stage,
            profile_count=len(snapshot.profile),
            last_spoken_at=None if latest is None else latest.updated_at,
            pending_count=0,
            last_created_at=last_created,
            now=now,
            idle=timedelta(hours=self._settings.nudge_idle_hours),
            rate=timedelta(hours=self._settings.nudge_rate_hours),
            has_replies=bank.enabled(),
        )
        if not decision.should_create or latest is None:
            return None
        text = fill_address(
            pick_reply(bank.replies, f"{user_id}:{character_id}:{now.isoformat()}")
        )
        return await self._nudges.create(
            user_id=user_id,
            character_id=character_id,
            code=decision.code,
            text=text,
            created_at=now,
            expires_at=now + timedelta(hours=self._settings.nudge_ttl_hours),
        )

    def disclosure_for(self, character_id: str) -> str:
        return self._characters.get(character_id).disclosure

    async def turn(
        self,
        conversation_id: str,
        user_text: str,
        *,
        request_id: str = "",
        user_id: str | None = None,
    ) -> TurnResult:
        conversation = await self._store.get(conversation_id, user_id=user_id)
        started = time.perf_counter()
        text = user_text.strip()
        config = turn_run_config(
            conversation_id=conversation.id,
            character_id=conversation.character_id,
            user_id=conversation.user_id,
            request_id=request_id,
            mode="turn",
        )
        async with dialogue_trace(
            enabled=self._settings.langsmith_tracing,
            name="dialogue_turn",
            project=self._settings.langsmith_project,
            inputs={"user_text": text, "history_messages": len(conversation.messages)},
            metadata=config["metadata"],
            tags=config["tags"],
        ) as run:
            result = await self._graph.ainvoke(
                self._initial_state(conversation, text), config=config
            )
            assistant_text = result["assistant_text"]
            await self._store.append(conversation.id, text, assistant_text)
            finished = self._finish(
                conversation.id,
                assistant_text,
                result["safety_action"],
                result["safety_code"],
                result.get("react_action") or "none",
                result.get("react_code") or "",
                result.get("model_used") or self._settings.llm_model,
                bool(result.get("degraded")),
                started,
                _action_from_graph(result),
            )
            run.end(
                outputs={
                    "assistant_text": finished.assistant_text,
                    "safety_action": finished.safety_action,
                    "safety_code": finished.safety_code,
                    "react_action": finished.react_action,
                    "react_code": finished.react_code,
                    "model": finished.model,
                    "degraded": finished.degraded,
                    "latency_ms": finished.latency_ms,
                    "action": finished.action.payload() if finished.action.has_action else None,
                }
            )
            return finished

    async def stream_turn(
        self,
        conversation_id: str,
        user_text: str,
        *,
        request_id: str = "",
        user_id: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """SSE：safety → action? → token* → done。拒绝也走 token，客户端协议一致。"""
        conversation = await self._store.get(conversation_id, user_id=user_id)
        started = time.perf_counter()
        text = user_text.strip()
        config = turn_run_config(
            conversation_id=conversation.id,
            character_id=conversation.character_id,
            user_id=conversation.user_id,
            request_id=request_id,
            mode="stream",
        )
        async with dialogue_trace(
            enabled=self._settings.langsmith_tracing,
            name="dialogue_stream_turn",
            project=self._settings.langsmith_project,
            inputs={"user_text": text, "history_messages": len(conversation.messages)},
            metadata=config["metadata"],
            tags=config["tags"],
        ) as run:
            character = self._characters.get(conversation.character_id)
            decision = self._safety.evaluate(text)
            yield StreamEvent(
                "safety", {"action": decision.action, "code": decision.code}
            )
            pieces: list[str] = []
            react_action = "none"
            react_code = ""
            proposal = ActionProposal()
            model_used = self._settings.llm_model
            degraded = False
            used_model = False
            input_allowed = decision.allowed
            if not input_allowed:
                assistant_text = character.refusal_text(decision.code)
                pieces.append(assistant_text)
                yield StreamEvent("react", {"action": "none", "code": ""})
                yield StreamEvent("token", {"text": assistant_text})
            else:
                salt = f"{conversation.id}:{len(conversation.messages)}"
                reaction = self._react.evaluate(
                    character,
                    text,
                    salt=salt,
                )
                react_action = reaction.action
                react_code = reaction.code
                yield StreamEvent(
                    "react", {"action": reaction.action, "code": reaction.code}
                )
                if reaction.skips_model:
                    pieces.append(reaction.text)
                    yield StreamEvent("token", {"text": reaction.text})
                else:
                    used_model = True
                    proposal = self._intent.evaluate(text)
                    if proposal.has_action:
                        yield StreamEvent("action", proposal.payload())
                    snapshot = await self._memory.recall(
                        conversation.user_id, conversation.character_id
                    )
                    generation: Generation | None = None
                    async for item in self._iter_tokens(
                        conversation,
                        character,
                        text,
                        config,
                        react_hint=reaction.text,
                        intent_hint=proposal.hint,
                        memory_block=snapshot.prompt_block(),
                    ):
                        if isinstance(item, Generation):
                            generation = item
                            continue
                        pieces.append(item)
                        yield StreamEvent("token", {"text": item})
                    if generation is not None:
                        model_used = generation.model
                        degraded = generation.degraded
                    assistant_text = "".join(pieces).strip()
                    if not assistant_text:
                        raise RuntimeError("模型返回空内容")

            assistant_text = "".join(pieces).strip()
            if used_model:
                reviewed = self._safety.evaluate_output(assistant_text)
                if not reviewed.allowed:
                    assistant_text = character.refusal_text("output_blocked")
                    decision = reviewed
                    yield StreamEvent(
                        "review",
                        {"action": reviewed.action, "code": reviewed.code},
                    )
            await self._store.append(conversation.id, text, assistant_text)
            if input_allowed:
                await self._memory.remember(
                    conversation.user_id,
                    conversation.character_id,
                    text,
                    conversation.id,
                )
            result = self._finish(
                conversation.id,
                assistant_text,
                decision.action,
                decision.code,
                react_action,
                react_code,
                model_used,
                degraded,
                started,
                proposal,
            )
            run.end(
                outputs={
                    "assistant_text": result.assistant_text,
                    "safety_action": result.safety_action,
                    "safety_code": result.safety_code,
                    "react_action": result.react_action,
                    "react_code": result.react_code,
                    "model": result.model,
                    "degraded": result.degraded,
                    "latency_ms": result.latency_ms,
                    "action": result.action.payload() if result.action.has_action else None,
                }
            )
            yield StreamEvent(
                "done",
                {
                    "conversation_id": result.conversation_id,
                    "assistant_text": result.assistant_text,
                    "safety": {
                        "action": result.safety_action,
                        "code": result.safety_code,
                    },
                    "react": {"action": result.react_action, "code": result.react_code},
                    "action": result.action.payload() if result.action.has_action else None,
                    "model": result.model,
                    "degraded": result.degraded,
                    "latency_ms": result.latency_ms,
                },
            )

    async def _iter_tokens(
        self,
        conversation: Conversation,
        character: CharacterProfile,
        user_text: str,
        config: RunnableConfig,
        react_hint: str = "",
        intent_hint: str = "",
        memory_block: str = "",
    ) -> AsyncIterator[str | Generation]:
        history = conversation.messages[-self._settings.short_term_turn_limit * 2 :]
        messages = build_model_messages(
            character,
            history,
            user_text,
            react_hint=react_hint,
            intent_hint=intent_hint,
            memory_block=memory_block,
        )
        async for item in astream_generation(
            self._llm_factory, character, messages, config
        ):
            yield item

    def _finish(
        self,
        conversation_id: str,
        assistant_text: str,
        safety_action: str,
        safety_code: str,
        react_action: str,
        react_code: str,
        model: str,
        degraded: bool,
        started: float,
        action: ActionProposal | None = None,
    ) -> TurnResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        self._latency.observe(latency_ms)
        return TurnResult(
            conversation_id=conversation_id,
            assistant_text=assistant_text,
            safety_action=safety_action,
            safety_code=safety_code,
            react_action=react_action,
            react_code=react_code,
            model=model,
            degraded=degraded,
            latency_ms=latency_ms,
            action=action or ActionProposal(),
        )

    def _initial_state(self, conversation: Conversation, user_text: str) -> dict:
        # LangGraph ainvoke 吃 dict；窗口截断只影响模型上下文
        limit = self._settings.short_term_turn_limit * 2
        return {
            "conversation_id": conversation.id,
            "user_id": conversation.user_id,
            "character_id": conversation.character_id,
            "user_text": user_text.strip(),
            "history": list(conversation.messages[-limit:]),
            "safety_action": "",
            "safety_code": "",
            "react_action": "",
            "react_code": "",
            "react_hint": "",
            "intent_code": NONE,
            "intent_slots": {},
            "intent_confirm": False,
            "intent_hint": "",
            "memory_block": "",
            "assistant_text": "",
            "model_used": "",
            "degraded": False,
        }


__all__ = [
    "CharacterNotFoundError",
    "ConversationNotFoundError",
    "DialogueService",
    "LLMConfigurationError",
    "StreamEvent",
    "TurnResult",
]
