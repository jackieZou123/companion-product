"""从 profiles/*.json 加载角色。"""

import json
from pathlib import Path

from app.character.models import CharacterProfile, NudgeBank, ReactionBank

_PROFILES_DIR = Path(__file__).resolve().parent / "profiles"


class CharacterNotFoundError(KeyError):
    pass


class CharacterRepository:
    def __init__(self, profiles_dir: Path | None = None) -> None:
        directory = profiles_dir or _PROFILES_DIR
        self._profiles = {
            profile.id: profile
            for profile in (
                _load_profile(path) for path in sorted(directory.glob("*.json"))
            )
        }
        if not self._profiles:
            raise RuntimeError(f"未找到角色配置：{directory}")

    def get(self, character_id: str) -> CharacterProfile:
        try:
            return self._profiles[character_id]
        except KeyError as exc:
            raise CharacterNotFoundError(character_id) from exc

    def default_id(self) -> str:
        # 项目默认陪伴是玫莉蔻；目录里没有时再退到任意已加载角色
        return (
            "mei_li_kou"
            if "mei_li_kou" in self._profiles
            else next(iter(self._profiles))
        )


def _load_profile(path: Path) -> CharacterProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    return CharacterProfile(
        id=data["id"],
        name=data["name"],
        age=data["age"],
        occupation=data["occupation"],
        identity=data["identity"],
        values=data["values"],
        speech_style=data["speech_style"],
        relationship_stance=data["relationship_stance"],
        boundaries=data["boundaries"],
        never_do=data["never_do"],
        refusals=data["refusals"],
        degraded=str(data.get("degraded") or ""),
        disclosure=str(data.get("disclosure") or ""),
        reactions=_load_reactions(data.get("reactions") or {}),
        nudges=_load_nudges(data.get("nudges") or {}),
    )


def _load_reactions(raw: object) -> tuple[ReactionBank, ...]:
    if not isinstance(raw, dict):
        return ()
    return tuple(_bank(code, item) for code, item in raw.items() if isinstance(code, str))


def _bank(code: str, raw: object) -> ReactionBank:
    if not isinstance(raw, dict):
        return ReactionBank(code=code)
    return ReactionBank(
        code=code,
        triggers=tuple(raw.get("triggers") or ()),
        replies=tuple(raw.get("replies") or ()),
    )


def _load_nudges(raw: object) -> tuple[NudgeBank, ...]:
    if not isinstance(raw, dict):
        return ()
    banks: list[NudgeBank] = []
    for code, item in raw.items():
        if not isinstance(code, str) or not isinstance(item, dict):
            continue
        banks.append(
            NudgeBank(code=code, replies=tuple(item.get("replies") or ()))
        )
    return tuple(banks)
