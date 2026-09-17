"""HTTP 会话接口。鉴权和满 18 岁由客户端做完，内核只认请求头。"""

import json
import logging
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.audience import parse_audience
from app.character import CharacterNotFoundError
from app.dialogue import (
    ConversationNotFoundError,
    DialogueService,
    LLMConfigurationError,
    StreamEvent,
)
from app.pages.schemas import (
    ActionOut,
    ConversationOut,
    ConversationSummaryOut,
    CreateConversationBody,
    CreateTurnBody,
    DeletedOut,
    MemoryOut,
    NudgeOut,
    PatchMemoryProfileBody,
    SafetyOut,
    TurnOut,
    UserExportOut,
)

router = APIRouter(prefix="/v1", tags=["conversations"])
logger = logging.getLogger(__name__)


def _service(request: Request) -> DialogueService:
    return request.app.state.dialogue


def _user_id(x_user_id: str | None) -> str:
    value = (x_user_id or "").strip()
    if not value or len(value) > 64:
        raise HTTPException(status_code=401, detail="缺少 X-User-Id")
    return value


@dataclass(frozen=True)
class Caller:
    """客户端鉴权、满 18 岁校验之后带来的身份。"""

    user_id: str
    audience: str


def get_caller(
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_audience: str | None = Header(default=None, alias="X-Audience"),
) -> Caller:
    # JWT 和满 18 岁由客户端验完；这里只认头，不重复核年龄
    try:
        audience = parse_audience(x_audience)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-Audience 只接受 customer 或 staff")
    return Caller(user_id=_user_id(x_user_id), audience=audience)


def _sse(event: StreamEvent) -> str:
    return (
        f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
    )


def _conversation_out(request: Request, conversation) -> ConversationOut:
    disclosure = _service(request).disclosure_for(conversation.character_id)
    return ConversationOut.from_entity(conversation, disclosure=disclosure)


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    body: CreateConversationBody,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> ConversationOut:
    conversation = await _service(request).create_conversation(
        caller.user_id,
        body.character_id,
    )
    return _conversation_out(request, conversation)


@router.get("/conversations", response_model=list[ConversationSummaryOut])
async def list_conversations(
    request: Request,
    caller: Caller = Depends(get_caller),
) -> list[ConversationSummaryOut]:
    items = await _service(request).list_conversations(caller.user_id)
    return [
        ConversationSummaryOut(
            conversation_id=item.id,
            character_id=item.character_id,
            created_at=item.created_at,
            updated_at=item.updated_at,
            message_count=item.message_count,
        )
        for item in items
    ]


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(
    conversation_id: str,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> ConversationOut:
    conversation = await _service(request).get_conversation(
        conversation_id, user_id=caller.user_id
    )
    return _conversation_out(request, conversation)


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> None:
    await _service(request).delete_conversation(
        conversation_id, user_id=caller.user_id
    )


@router.get("/me/export", response_model=UserExportOut)
async def export_me(
    request: Request,
    caller: Caller = Depends(get_caller),
) -> UserExportOut:
    user_id = caller.user_id
    conversations = await _service(request).export_user(user_id)
    memory = await _service(request).export_memory(user_id)
    nudges = await _service(request).export_nudges(user_id)
    return UserExportOut(
        user_id=user_id,
        conversations=[_conversation_out(request, item) for item in conversations],
        memory=[MemoryOut.from_snapshot(item) for item in memory],
        nudges=[NudgeOut.from_entity(item) for item in nudges],
    )


@router.delete("/me", response_model=DeletedOut)
async def delete_me(
    request: Request,
    caller: Caller = Depends(get_caller),
) -> DeletedOut:
    deleted = await _service(request).delete_user_data(caller.user_id)
    return DeletedOut(deleted=deleted)


@router.get("/me/memory", response_model=MemoryOut)
async def get_memory(
    request: Request,
    caller: Caller = Depends(get_caller),
    character_id: str | None = Query(default=None),
) -> MemoryOut:
    snapshot = await _service(request).get_memory(caller.user_id, character_id)
    return MemoryOut.from_snapshot(snapshot)


@router.patch("/me/memory/profile", response_model=MemoryOut)
async def patch_memory_profile(
    body: PatchMemoryProfileBody,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> MemoryOut:
    snapshot = await _service(request).patch_memory_profile(
        caller.user_id,
        body.slot,
        body.value,
        character_id=body.character_id,
    )
    return MemoryOut.from_snapshot(snapshot)


@router.delete("/me/memory/events/{event_id}", status_code=204)
async def delete_memory_event(
    event_id: int,
    request: Request,
    caller: Caller = Depends(get_caller),
    character_id: str | None = Query(default=None),
) -> None:
    await _service(request).delete_memory_event(
        event_id, user_id=caller.user_id, character_id=character_id
    )


@router.delete("/me/memory", status_code=204)
async def delete_memory(
    request: Request,
    caller: Caller = Depends(get_caller),
    character_id: str | None = Query(default=None),
) -> None:
    await _service(request).delete_memory(caller.user_id, character_id)


@router.get("/me/nudges", response_model=list[NudgeOut])
async def list_nudges(
    request: Request,
    caller: Caller = Depends(get_caller),
    character_id: str | None = Query(default=None),
) -> list[NudgeOut]:
    items = await _service(request).list_nudges(caller.user_id, character_id)
    return [NudgeOut.from_entity(item) for item in items]


@router.post("/me/nudges/{nudge_id}/ack", response_model=NudgeOut)
async def ack_nudge(
    nudge_id: int,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> NudgeOut:
    item = await _service(request).ack_nudge(nudge_id, user_id=caller.user_id)
    return NudgeOut.from_entity(item)


@router.post("/me/nudges/{nudge_id}/dismiss", response_model=NudgeOut)
async def dismiss_nudge(
    nudge_id: int,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> NudgeOut:
    item = await _service(request).dismiss_nudge(nudge_id, user_id=caller.user_id)
    return NudgeOut.from_entity(item)


@router.post("/conversations/{conversation_id}/turns", response_model=TurnOut)
async def create_turn(
    conversation_id: str,
    body: CreateTurnBody,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> TurnOut:
    try:
        result = await _service(request).turn(
            conversation_id,
            body.text,
            request_id=getattr(request.state, "request_id", ""),
            user_id=caller.user_id,
            audience=caller.audience,
        )
    except (ConversationNotFoundError, CharacterNotFoundError, LLMConfigurationError):
        raise
    except Exception as exc:
        logger.exception("dialogue_turn_failed")
        raise HTTPException(status_code=503, detail="模型调用失败") from exc
    return TurnOut(
        conversation_id=result.conversation_id,
        assistant_text=result.assistant_text,
        safety=SafetyOut(action=result.safety_action, code=result.safety_code),
        react=SafetyOut(action=result.react_action, code=result.react_code),
        action=(
            ActionOut(
                code=result.action.code,
                slots=dict(result.action.slots or {}),
                confirm_required=result.action.confirm_required,
            )
            if result.action.has_action
            else None
        ),
        model=result.model,
        degraded=result.degraded,
        latency_ms=result.latency_ms,
    )


@router.post("/conversations/{conversation_id}/turns/stream")
async def stream_turn(
    conversation_id: str,
    body: CreateTurnBody,
    request: Request,
    caller: Caller = Depends(get_caller),
) -> StreamingResponse:
    service = _service(request)
    user_id = caller.user_id
    await service.get_conversation(
        conversation_id, user_id=user_id
    )  # 先 404，避免 SSE 里才发现会话不存在

    async def events():
        try:
            async for item in service.stream_turn(
                conversation_id,
                body.text,
                request_id=getattr(request.state, "request_id", ""),
                user_id=user_id,
                audience=caller.audience,
            ):
                yield _sse(item)
        except Exception:
            logger.exception("dialogue_stream_failed")
            yield _sse(StreamEvent("error", {"detail": "模型调用失败", "status": 503}))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },  # 关掉 nginx 缓冲，token 才能马上出去
    )
