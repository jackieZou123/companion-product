"""角色 Profile。人设来自 JSON，不在代码里拼长 Prompt。"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReactionBank:
    """一类呼唤。触发词和回复池都在角色 JSON 里。"""

    triggers: tuple[str, ...] = ()
    replies: tuple[str, ...] = ()

    def enabled(self) -> bool:
        return bool(self.triggers) and bool(self.replies)


@dataclass(frozen=True)
class CharacterProfile:
    id: str
    name: str
    age: int
    occupation: str
    identity: str
    values: list[str]
    speech_style: list[str]
    relationship_stance: str
    boundaries: list[str]
    never_do: list[str]
    refusals: dict[str, str]
    degraded: str = ""
    wake: ReactionBank = field(default_factory=ReactionBank)
    low_mood: ReactionBank = field(default_factory=ReactionBank)

    def system_prompt(self) -> str:
        """每次调用现拼，保证和 JSON 同步。"""
        values = "\n".join(f"- {item}" for item in self.values)
        style = "\n".join(f"- {item}" for item in self.speech_style)
        bounds = "\n".join(f"- {item}" for item in self.boundaries)
        never = "\n".join(f"- {item}" for item in self.never_do)
        return (
            f"你是「{self.name}」，{self.age} 岁，{self.occupation}。\n"
            "你是面向成年用户的 AI 陪伴角色，不是人类，禁止声称自己有肉体、住址或可线下见面。\n"
            f"{self.identity}\n\n"
            f"价值观：\n{values}\n\n"
            f"说话方式：\n{style}\n\n"
            f"关系立场：{self.relationship_stance}\n\n"
            f"边界：\n{bounds}\n\n"
            f"禁止：\n{never}\n\n"
            "要求：保持身份、价值观和语气稳定；先回应情绪再给观点；"
            "不要无脑赞同；不要用安慰套话堆砌；不要主动诱导用户依赖你。"
        )

    def refusal_text(self, code: str) -> str:
        return self.refusals.get(code) or self.refusals["default"]

    def degraded_text(self) -> str:
        """模型全失败时的角色口吻，不说系统错误。"""
        return self.degraded or self.refusals["default"]
