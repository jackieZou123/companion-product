"""HTTP 会话接口。"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.pages.schemas import (
    ConversationOut,
    CreateConversationBody,
    CreateTurnBody,
    SafetyOut,
    TurnOut,
)
from app.character import CharacterNotFoundError
from app.dialogue import (
    ConversationNotFoundError,
    DialogueService,
    LLMConfigurationError,
    StreamEvent,
)

router = APIRouter(prefix="/v1", tags=["conversations"])
logger = logging.getLogger(__name__)


def _service(request: Request) -> DialogueService:
    return request.app.state.dialogue


def _sse(event: StreamEvent) -> str:
    return (
        f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
    )


@router.post("/conversations", response_model=ConversationOut)
async def create_conversation(
    body: CreateConversationBody, request: Request
) -> ConversationOut:
    conversation = await _service(request).create_conversation(
        body.user_id, body.character_id
    )
    return ConversationOut.from_entity(conversation)


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, request: Request) -> ConversationOut:
    conversation = await _service(request).get_conversation(conversation_id)
    return ConversationOut.from_entity(conversation)


@router.post("/conversations/{conversation_id}/turns", response_model=TurnOut)
async def create_turn(
    conversation_id: str, body: CreateTurnBody, request: Request
) -> TurnOut:
    try:
        result = await _service(request).turn(
            conversation_id,
            body.text,
            request_id=getattr(request.state, "request_id", ""),
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
        model=result.model,
        degraded=result.degraded,
        latency_ms=result.latency_ms,
    )


@router.post("/conversations/{conversation_id}/turns/stream")
async def stream_turn(
    conversation_id: str, body: CreateTurnBody, request: Request
) -> StreamingResponse:
    service = _service(request)
    await service.get_conversation(
        conversation_id
    )  # 先 404，避免 SSE 里才发现会话不存在

    async def events():
        try:
            async for item in service.stream_turn(
                conversation_id,
                body.text,
                request_id=getattr(request.state, "request_id", ""),
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
