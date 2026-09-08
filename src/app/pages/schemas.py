"""请求/响应模型。"""

from datetime import datetime

from typing import Literal

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.character import CharacterNotFoundError
from app.dialogue.errors import (
    AdultNotConfirmedError,
    ConversationNotFoundError,
    GenderRequiredError,
)
from app.dialogue.service import LLMConfigurationError
from app.dialogue.store import Conversation


class CreateConversationBody(BaseModel):
    character_id: str | None = None
    adult_confirmed: bool = False
    gender: Literal["female", "male"] = Field(..., description="female 称姐姐，male 称哥哥")


class MessageOut(BaseModel):
    role: str
    content: str


class ConversationOut(BaseModel):
    conversation_id: str
    user_id: str
    character_id: str
    adult_confirmed: bool = True
    gender: Literal["female", "male"] = "female"
    ai_disclosure: str = ""
    messages: list[MessageOut] = []

    @classmethod
    def from_entity(
        cls, conversation: Conversation, *, disclosure: str = ""
    ) -> "ConversationOut":
        return cls(
            conversation_id=conversation.id,
            user_id=conversation.user_id,
            character_id=conversation.character_id,
            adult_confirmed=conversation.adult_confirmed,
            gender="male" if conversation.gender == "male" else "female",
            ai_disclosure=disclosure,
            messages=[
                MessageOut(role=item["role"], content=item["content"])
                for item in conversation.messages
            ],
        )


class ConversationSummaryOut(BaseModel):
    conversation_id: str
    character_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class UserExportOut(BaseModel):
    user_id: str
    conversations: list[ConversationOut]


class DeletedOut(BaseModel):
    deleted: int


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

    @app.exception_handler(AdultNotConfirmedError)
    async def adult_not_confirmed(_: Request, __: AdultNotConfirmedError):
        return JSONResponse(status_code=403, content={"detail": "需要确认已成年"})

    @app.exception_handler(GenderRequiredError)
    async def gender_required(_: Request, __: GenderRequiredError):
        return JSONResponse(status_code=422, content={"detail": "需要选择性别"})

    @app.exception_handler(CharacterNotFoundError)
    async def character_not_found(_: Request, __: CharacterNotFoundError):
        return JSONResponse(status_code=404, content={"detail": "角色不存在"})

    @app.exception_handler(LLMConfigurationError)
    async def llm_config(_: Request, exc: LLMConfigurationError):
        return JSONResponse(status_code=500, content={"detail": str(exc)})
