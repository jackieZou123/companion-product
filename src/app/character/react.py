"""呼唤联动。命中规则后从角色回复池抽句，不靠模型临场发挥。"""

from dataclasses import dataclass
import hashlib
import re

from app.character.models import CharacterProfile, ReactionBank

# 去掉标点和应声词后，剩下才算「还有正事」
_FILLER = re.compile(
    r"[\s，。！？、,.!?~～…「」\"'（）()]+|啊+|呀+|嘛+|喂+|哟+|哈+|呢+|吧+"
)


# 反应决策
@dataclass(frozen=True)
class ReactDecision:
    action: str
    code: str
    text: str

    @property
    def skips_model(self) -> bool:
        return self.action == "reply"


# 反应策略
class ReactPolicy:
    """安全门之后、生成之前。低落呼唤优先于单纯喊人。"""

    def evaluate(
        self, profile: CharacterProfile, text: str, *, salt: str = ""
    ) -> ReactDecision:
        stripped = text.strip()
        if not stripped:
            return ReactDecision("none", "", "")
        if self._hit(stripped, profile.low_mood) and self._hit(stripped, profile.wake):
            line = _pick(profile.low_mood.replies, f"low_mood:{salt}:{stripped}")
            leftover = _remainder(
                stripped, profile.wake.triggers + profile.low_mood.triggers
            )
            # 短句只应一声；后头还有事才把口吻交给生成
            action = "reply" if len(leftover) <= 8 else "hint"
            return ReactDecision(action, "low_mood", line)
        if self._hit(stripped, profile.wake):
            line = _pick(profile.wake.replies, f"wake:{salt}:{stripped}")
            leftover = _remainder(stripped, profile.wake.triggers)
            action = "reply" if not leftover else "hint"
            return ReactDecision(action, "wake", line)
        return ReactDecision("none", "", "")

    def _hit(self, text: str, bank: ReactionBank) -> bool:
        return bank.enabled() and any(trigger in text for trigger in bank.triggers)


# 剩余文本
def _remainder(text: str, triggers: tuple[str, ...]) -> str:
    leftover = text
    for trigger in sorted(triggers, key=len, reverse=True):
        leftover = leftover.replace(trigger, "")
    leftover = _FILLER.sub("", leftover)
    leftover = leftover.replace("在不在", "").replace("你在吗", "").replace("在吗", "")
    return leftover.strip()


# 随机选择回复
def _pick(replies: tuple[str, ...], salt: str) -> str:
    if not replies:
        return ""
    digest = hashlib.sha256(salt.encode("utf-8")).digest()
    return replies[int.from_bytes(digest[:4], "big") % len(replies)]
