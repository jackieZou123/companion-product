"""闲置回访要不要发。规则先于模型，避免突然想说话。"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib

IDLE_CARE = "idle_care"


@dataclass(frozen=True)
class NudgeDecision:
    action: str
    code: str
    reason: str

    @property
    def should_create(self) -> bool:
        return self.action == "create"


class NudgePolicy:
    """只做 idle_care。初识、无画像、未满闲置、频控内、已有待取都不发。"""

    def evaluate(
        self,
        *,
        stage: str,
        profile_count: int,
        last_spoken_at: datetime | None,
        pending_count: int,
        last_created_at: datetime | None,
        now: datetime,
        idle: timedelta,
        rate: timedelta,
        has_replies: bool,
    ) -> NudgeDecision:
        if not has_replies:
            return NudgeDecision("skip", IDLE_CARE, "no_replies")
        if pending_count > 0:
            return NudgeDecision("skip", IDLE_CARE, "pending")
        if stage == "new" or profile_count < 1:
            return NudgeDecision("skip", IDLE_CARE, "not_ready")
        if last_spoken_at is None:
            return NudgeDecision("skip", IDLE_CARE, "no_conversation")
        if now - _aware(last_spoken_at) < idle:
            return NudgeDecision("skip", IDLE_CARE, "idle_wait")
        if last_created_at is not None and now - _aware(last_created_at) < rate:
            return NudgeDecision("skip", IDLE_CARE, "rate_limited")
        return NudgeDecision("create", IDLE_CARE, "idle_care")


def pick_reply(replies: tuple[str, ...], salt: str) -> str:
    if not replies:
        return ""
    digest = hashlib.sha256(salt.encode("utf-8")).digest()
    return replies[int.from_bytes(digest[:4], "big") % len(replies)]


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
