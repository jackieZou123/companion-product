"""记忆领域对象。和 ORM 行分开，避免对话层碰到表结构。"""

from dataclasses import dataclass, field
from datetime import datetime

STAGE_LABELS = {
    "new": "初识",
    "ongoing": "持续护理",
    "familiar": "熟客",
}
SLOT_LABELS = {
    "skin_type": "肤质",
    "concern": "在意",
}
FAMILIAR_TURNS = 8


@dataclass(frozen=True)
class ProfileSlot:
    slot: str
    value: str


@dataclass(frozen=True)
class MemoryEvent:
    id: int
    slot: str
    value: str
    source_text: str
    source: str
    created_at: datetime


@dataclass
class MemorySnapshot:
    """某一用户对某一角色的可注入记忆。"""

    user_id: str
    character_id: str
    stage: str = "new"
    turn_count: int = 0
    conversation_count: int = 0
    profile: list[ProfileSlot] = field(default_factory=list)
    events: list[MemoryEvent] = field(default_factory=list)

    def prompt_block(self) -> str:
        """没有记下任何事时不注入，避免空套话进 System。"""
        if not self.profile and not self.events:
            return ""
        lines = ["已知对方（可纠正，不是病历；没有的不要编）："]
        for item in self.profile:
            label = SLOT_LABELS.get(item.slot, item.slot)
            lines.append(f"- {label}：{item.value}")
        for item in self.events[-3:]:
            lines.append(f"- 最近：{item.value}")
        stage = STAGE_LABELS.get(self.stage, self.stage)
        lines.append(f"关系阶段：{stage}。不是医生也不是恋人。")
        return "\n".join(lines)


def relationship_stage(*, profile_count: int, conversation_count: int, turn_count: int) -> str:
    has_profile = profile_count >= 1
    if has_profile and turn_count >= FAMILIAR_TURNS:
        return "familiar"
    if has_profile or conversation_count >= 2:
        return "ongoing"
    return "new"
