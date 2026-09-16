"""主动消息领域对象。"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Nudge:
    id: int
    user_id: str
    character_id: str
    code: str
    text: str
    created_at: datetime
    expires_at: datetime
    acked_at: datetime | None = None
    dismissed_at: datetime | None = None
