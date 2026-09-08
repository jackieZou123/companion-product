"""对话内核公开接口。"""

from app.dialogue.errors import (
    AdultNotConfirmedError,
    ConversationNotFoundError,
    GenderRequiredError,
)
from app.dialogue.service import (
    CharacterNotFoundError,
    DialogueService,
    LLMConfigurationError,
    StreamEvent,
    TurnResult,
)

__all__ = [
    "AdultNotConfirmedError",
    "CharacterNotFoundError",
    "ConversationNotFoundError",
    "GenderRequiredError",
    "DialogueService",
    "LLMConfigurationError",
    "StreamEvent",
    "TurnResult",
]
