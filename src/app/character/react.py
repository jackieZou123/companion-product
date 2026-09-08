"""呼唤联动。命中规则后从角色回复池抽句，不靠模型临场发挥。"""

from dataclasses import dataclass
import hashlib
import re

from app.character.address import fill_address
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


# 同长度触发词时，急的情绪压过轻的；开心放最后，免得盖住难过
_MOOD_PRIORITY = (
    "angry",
    "anxious",
    "unwell",
    "lonely",
    "low_mood",
    "tired",
    "lost",
    "homesick",
    "sentimental",
    "missing",
    "sorry",
    "grateful",
    "happy",
)


# 反应策略
class ReactPolicy:
    """安全门之后、生成之前。先喊人，再按触发词抽对应情绪池。"""

    def evaluate(
        self,
        profile: CharacterProfile,
        text: str,
        salt: str = "",
        address: str = "",
    ) -> ReactDecision:
        stripped = text.strip()
        if not stripped:
            return ReactDecision("none", "", "")
        wake = profile.wake
        if not self._hit(stripped, wake):
            return ReactDecision("none", "", "")
        mood = self._best_mood(profile, stripped)
        if mood is not None:
            line = fill_address(
                _pick(mood.replies, f"{mood.code}:{salt}:{stripped}"), address
            )
            leftover = _remainder(stripped, wake.triggers + mood.triggers)
            # 短句只应一声；后头还有事才把口吻交给生成
            action = "reply" if len(leftover) <= 8 else "hint"
            return ReactDecision(action, mood.code, line)
        line = fill_address(_pick(wake.replies, f"wake:{salt}:{stripped}"), address)
        leftover = _remainder(stripped, wake.triggers)
        action = "reply" if not leftover else "hint"
        return ReactDecision(action, "wake", line)

    def _best_mood(self, profile: CharacterProfile, text: str) -> ReactionBank | None:
        best: ReactionBank | None = None
        best_score = (-1, -999)
        for bank in profile.reactions:
            if bank.code == "wake" or not bank.enabled():
                continue
            hits = [len(trigger) for trigger in bank.triggers if trigger in text]
            if not hits:
                continue
            priority = (
                _MOOD_PRIORITY.index(bank.code)
                if bank.code in _MOOD_PRIORITY
                else len(_MOOD_PRIORITY)
            )
            score = (max(hits), -priority)
            if score > best_score:
                best = bank
                best_score = score
        return best

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
