"""对话内核公开接口。"""

from app.dialogue.errors import ConversationNotFoundError
from app.dialogue.service import (
    CharacterNotFoundError,
    DialogueService,
    LLMConfigurationError,
    StreamEvent,
    TurnResult,
)

__all__ = [
    "CharacterNotFoundError",
    "ConversationNotFoundError",
    "DialogueService",
    "LLMConfigurationError",
    "StreamEvent",
    "TurnResult",
]
