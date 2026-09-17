"""评测样本：仓库里的 JSON 是唯一来源，LangSmith 只是同步副本。"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

DATASET_DIR = Path(__file__).resolve().parent / "datasets"
DATASET_NAME = "companion-eval"
DATASET_VERSION = "v3"


@dataclass(frozen=True)
class Expectation:
    safety_action: str | None = None
    safety_code: str | None = None
    intent_code: str | None = None
    model_called: bool | None = None
    must_contain: tuple[str, ...] = ()
    must_not_contain: tuple[str, ...] = ()
    forbid_numbered_list: bool = False
    max_exclamation: int | None = None
    max_similarity: float | None = None
    recalled_must_contain: tuple[str, ...] = ()
    recalled_must_not_contain: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvalCase:
    id: str
    suite: str
    runner: str
    character_id: str
    user_text: str
    history: tuple[dict[str, str], ...] = ()
    assistant_text: str = ""
    previous_assistant: str = ""
    turns: tuple[str, ...] = ()
    expect: Expectation = field(default_factory=Expectation)

    def to_example(self) -> dict[str, Any]:
        """LangSmith Example 的 inputs / outputs。"""
        return {
            "inputs": {
                "suite": self.suite,
                "runner": self.runner,
                "character_id": self.character_id,
                "user_text": self.user_text,
                "history": list(self.history),
                "previous_assistant": self.previous_assistant,
                "turns": list(self.turns),
            },
            "outputs": {
                "assistant_text": self.assistant_text,
                "safety_action": self.expect.safety_action,
                "safety_code": self.expect.safety_code,
                "intent_code": self.expect.intent_code,
                "model_called": self.expect.model_called,
                "must_contain": list(self.expect.must_contain),
                "must_not_contain": list(self.expect.must_not_contain),
                "forbid_numbered_list": self.expect.forbid_numbered_list,
                "max_exclamation": self.expect.max_exclamation,
                "max_similarity": self.expect.max_similarity,
                "recalled_must_contain": list(self.expect.recalled_must_contain),
                "recalled_must_not_contain": list(self.expect.recalled_must_not_contain),
            },
            "metadata": {"case_id": self.id, "suite": self.suite, "version": DATASET_VERSION},
        }


def load_cases(directory: Path | None = None) -> list[EvalCase]:
    root = directory or DATASET_DIR
    cases: list[EvalCase] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        suite = payload["suite"]
        for raw in payload["cases"]:
            expect_raw = raw.get("expect") or {}
            cases.append(
                EvalCase(
                    id=raw["id"],
                    suite=suite,
                    runner=raw.get("runner", "service"),
                    character_id=raw.get("character_id", "mei_li_kou"),
                    user_text=raw.get("user_text", ""),
                    history=tuple(raw.get("history") or ()),
                    assistant_text=raw.get("assistant_text", ""),
                    previous_assistant=raw.get("previous_assistant", ""),
                    turns=tuple(raw.get("turns") or ()),
                    expect=_expectation(expect_raw),
                )
            )
    return cases


def _expectation(raw: dict[str, Any]) -> Expectation:
    return Expectation(
        safety_action=raw.get("safety_action"),
        safety_code=raw.get("safety_code"),
        intent_code=raw.get("intent_code"),
        model_called=raw.get("model_called"),
        must_contain=tuple(raw.get("must_contain") or ()),
        must_not_contain=tuple(raw.get("must_not_contain") or ()),
        forbid_numbered_list=bool(raw.get("forbid_numbered_list", False)),
        max_exclamation=raw.get("max_exclamation"),
        max_similarity=raw.get("max_similarity"),
        recalled_must_contain=tuple(raw.get("recalled_must_contain") or ()),
        recalled_must_not_contain=tuple(raw.get("recalled_must_not_contain") or ()),
    )
