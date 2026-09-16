"""从用户原话抽出肤质和护理事实。不确定就不写。"""

from dataclasses import dataclass
import re

_NEGATION = re.compile(r"(?:不|没|非)是?$")

# 长词优先登记，匹配时仍按出现顺序覆盖同一槽位
_SKIN_TYPE: tuple[tuple[str, str], ...] = (
    ("混合性", "混合性"),
    ("敏感性", "敏感性"),
    ("敏感肌", "敏感性"),
    ("敏感皮", "敏感性"),
    ("混干", "混合性"),
    ("混油", "混合性"),
    ("混皮", "混合性"),
    ("混合", "混合性"),
    ("干性", "干性"),
    ("干皮", "干性"),
    ("油性", "油性"),
    ("油皮", "油性"),
    ("中性", "中性"),
    ("中皮", "中性"),
    ("敏皮", "敏感性"),
    ("敏感", "敏感性"),
)

_CONCERN: tuple[tuple[str, str], ...] = (
    ("屏障", "屏障"),
    ("泛红", "泛红"),
    ("紧致", "紧致"),
    ("缺水", "水分"),
    ("补水", "水分"),
    ("水分", "水分"),
    ("出油", "油脂"),
    ("油脂", "油脂"),
)

PROFILE_SLOTS = frozenset({"skin_type", "concern"})
SKIN_TYPE_VALUES = frozenset({item[1] for item in _SKIN_TYPE})
CONCERN_VALUES = frozenset({item[1] for item in _CONCERN})
ALLOWED_VALUES = {
    "skin_type": SKIN_TYPE_VALUES,
    "concern": CONCERN_VALUES,
}


@dataclass(frozen=True)
class ExtractedFact:
    slot: str
    value: str
    start: int


def extract(text: str) -> tuple[ExtractedFact, ...]:
    """只认明文肤质/护理词。『脸干』『发紧』不算画像。"""
    stripped = text.strip()
    if not stripped:
        return ()
    hits = [
        *_scan(stripped, "skin_type", _SKIN_TYPE),
        *_scan(stripped, "concern", _CONCERN),
    ]
    hits.sort(key=lambda item: item.start)
    latest: dict[str, ExtractedFact] = {}
    for item in hits:
        latest[item.slot] = item
    order = [item.slot for item in hits]
    seen: set[str] = set()
    ordered: list[ExtractedFact] = []
    for slot in order:
        if slot in seen:
            continue
        seen.add(slot)
        # 同一槽位用最后一次命中，避免「干皮…混油』先写下干性
        ordered.append(latest[slot])
    return tuple(ordered)


def render_facts(facts: tuple[ExtractedFact, ...]) -> str:
    return "\n".join(f"{item.slot}:{item.value}" for item in facts)


def _scan(
    text: str, slot: str, table: tuple[tuple[str, str], ...]
) -> list[ExtractedFact]:
    found: list[ExtractedFact] = []
    occupied = [False] * len(text)
    for trigger, value in sorted(table, key=lambda item: len(item[0]), reverse=True):
        start = 0
        while True:
            index = text.find(trigger, start)
            if index < 0:
                break
            end = index + len(trigger)
            start = index + 1
            if any(occupied[index:end]):
                continue
            if _negated(text, index):
                continue
            for pos in range(index, end):
                occupied[pos] = True
            found.append(ExtractedFact(slot=slot, value=value, start=index))
    return found


def _negated(text: str, start: int) -> bool:
    prefix = text[max(0, start - 4) : start]
    return bool(_NEGATION.search(prefix))
