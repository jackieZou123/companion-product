"""请求/响应模型。"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.character import CharacterNotFoundError
from app.dialogue import ConversationNotFoundError, LLMConfigurationError
from app.dialogue.store import Conversation


class CreateConversationBody(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    character_id: str | None = None


class MessageOut(BaseModel):
    role: str
    content: str


class ConversationOut(BaseModel):
    conversation_id: str
    user_id: str
    character_id: str
    messages: list[MessageOut] = []

    @classmethod
    def from_entity(cls, conversation: Conversation) -> "ConversationOut":
        return cls(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            character_id=conversation.character_id,
            messages=[MessageOut(role=item["role"], content=item["content"]) for item in conversation.messages],
        )


class CreateTurnBody(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SafetyOut(BaseModel):
    action: str
    code: str


class TurnOut(BaseModel):
    conversation_id: str
    assistant_text: str
    safety: SafetyOut
    react: SafetyOut
    model: str
    degraded: bool = False
    latency_ms: int


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found(_: Request, __: ConversationNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "会话不存在"})

    @app.exception_handler(CharacterNotFoundError)
    async def character_not_found(_: Request, __: CharacterNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "角色不存在"})

    @app.exception_handler(LLMConfigurationError)
    async def llm_config(_: Request, exc: LLMConfigurationError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})
