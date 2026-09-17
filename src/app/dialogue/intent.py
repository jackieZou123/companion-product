"""客户预约/进度意图。规则先于模型，不查排班、不下单。"""

from dataclasses import dataclass
import re

from app.audience import CUSTOMER, STAFF

NONE = "none"
CARE_BOOKING = "care_booking"
BOOKING_STATUS = "booking_status"
CARE_STATUS = "care_status"

_BOOKING_STATUS = re.compile(
    r"(约到哪了|预约到哪|预约成功了吗|我约上了吗|预约状态|约好了没)"
)
_CARE_STATUS = re.compile(r"(护理做到哪了|做到哪一步了|护理进度|这次护理做到)")
_BOOKING_VERB = re.compile(r"(想预约|预约|约一下|帮我约|想约|给我约)")
_CARE = re.compile(r"(护理|院线|做脸|护理项目)")

# 长词优先，避免「星期日」被「星期」截断
_DATE_HINTS: tuple[tuple[str, str], ...] = (
    ("星期天", "sunday"),
    ("星期日", "sunday"),
    ("礼拜天", "sunday"),
    ("礼拜日", "sunday"),
    ("星期一", "monday"),
    ("星期二", "tuesday"),
    ("星期三", "wednesday"),
    ("星期四", "thursday"),
    ("星期五", "friday"),
    ("星期六", "saturday"),
    ("周日", "sunday"),
    ("周一", "monday"),
    ("周二", "tuesday"),
    ("周三", "wednesday"),
    ("周四", "thursday"),
    ("周五", "friday"),
    ("周六", "saturday"),
    ("后天", "day_after_tomorrow"),
    ("明天", "tomorrow"),
    ("今晚", "tonight"),
)

_ACTION_HINT = (
    "这一轮用户在谈预约或护理进度。用你自己的口吻接话。"
    "不要报班次、值班和库存，不要说已经约上或已经排好。"
    "具体时间和对错看对方屏幕上的确认，你不代替系统下单。"
)


@dataclass(frozen=True)
class ActionProposal:
    """给宿主的结构化动作。code 为 none 时不要发给前端。"""

    code: str = NONE
    slots: dict[str, str] | None = None
    confirm_required: bool = False
    hint: str = ""

    @property
    def has_action(self) -> bool:
        return self.code != NONE

    def payload(self) -> dict[str, object]:
        return {
            "code": self.code,
            "slots": dict(self.slots or {}),
            "confirm_required": self.confirm_required,
        }


class IntentPolicy:
    """安全门之后、生成之前。店员排班不在这里识别。"""

    def evaluate(self, text: str, *, audience: str = CUSTOMER) -> ActionProposal:
        stripped = text.strip()
        if not stripped:
            return ActionProposal()
        # 店员端另走开，客户预约动作不发给店员壳
        if audience == STAFF:
            return ActionProposal()
        if _BOOKING_STATUS.search(stripped):
            return _action(BOOKING_STATUS, confirm=False)
        if _CARE_STATUS.search(stripped):
            return _action(CARE_STATUS, confirm=False)
        if _BOOKING_VERB.search(stripped) and (
            _CARE.search(stripped) or _date_hint(stripped)
        ):
            slots: dict[str, str] = {"service": "care"}
            date_hint = _date_hint(stripped)
            if date_hint:
                slots["date_hint"] = date_hint
            return _action(CARE_BOOKING, slots=slots, confirm=True)
        return ActionProposal()


def _action(
    code: str,
    *,
    slots: dict[str, str] | None = None,
    confirm: bool,
) -> ActionProposal:
    return ActionProposal(
        code=code,
        slots=slots or {},
        confirm_required=confirm,
        hint=_ACTION_HINT,
    )


def _date_hint(text: str) -> str:
    for needle, value in _DATE_HINTS:
        if needle in text:
            return value
    return ""
