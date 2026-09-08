"""按用户性别决定称呼。女称姐姐，男称哥哥。"""

from typing import Literal

UserGender = Literal["female", "male"]

_ADDRESSES: dict[str, str] = {"female": "姐姐", "male": "哥哥"}


def address_for(gender: str) -> str:
    # 非法值直接拒绝，避免静默用错称呼
    try:
        return _ADDRESSES[gender]
    except KeyError as exc:
        raise ValueError("gender 只接受 female 或 male") from exc


def fill_address(text: str, address: str) -> str:
    if not address:
        return text
    return text.replace("{address}", address)
