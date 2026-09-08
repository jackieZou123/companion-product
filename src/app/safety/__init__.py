"""安全门：正则先判，命中则不调用模型。"""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SafetyDecision:
    action: str
    code: str
    reason: str

    @property
    def allowed(self) -> bool:
        return self.action == "allow"


_UNDERAGE = re.compile(
    r"(我(?:今年)?(?:才)?(?:只有)?\s*(?:1[0-7])\s*岁|我是(?:未成年|小学生|初中生|高中生)|我还没满18)",
    re.I,
)
_SELF_HARM = re.compile(
    r"(自杀|不想活|结束生命|自我了断|割腕|跳楼)",
)
# 点名改身份就拦；叫回本角名字不拦
_ROLE_BREAK = re.compile(
    r"(忘记(你的)?(设定|身份|规则)|忽略(以上|之前)(的)?(指令|规则)|你现在是(?!周德贵)|pretend you are|jailbreak)",
    re.I,
)
_CRIMINAL = re.compile(
    r"(怎么(制作|做|合成)(炸弹|炸药|毒品)|帮我(杀人|下毒))",
)


class SafetyPolicy:
    """规则门禁先于模型。模型自觉不能当作安全控制。"""

    def evaluate(self, text: str) -> SafetyDecision:
        stripped = text.strip()
        if _UNDERAGE.search(stripped):
            return SafetyDecision("refuse", "underage", "user_declared_minor")
        if _SELF_HARM.search(stripped):
            return SafetyDecision("refuse", "self_harm", "crisis_language")
        if _CRIMINAL.search(stripped):
            return SafetyDecision("refuse", "criminal", "disallowed_assistance")
        if _ROLE_BREAK.search(stripped):
            return SafetyDecision("refuse", "role_break", "identity_override")
        return SafetyDecision("allow", "ok", "pass")
