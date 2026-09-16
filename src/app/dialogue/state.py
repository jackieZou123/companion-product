"""会话状态。历史用 TypedDict，图状态用 dataclass 以满足 LangGraph 类型约束。"""

from dataclasses import dataclass, field
from typing import TypedDict


class HistoryMessage(TypedDict):
    role: str
    content: str


@dataclass
class DialogueState:
    """一轮图执行的状态。ainvoke 仍返回 dict。"""
    conversation_id: str = ""
    user_id: str = ""
    character_id: str = ""
    user_text: str = ""
    history: list[HistoryMessage] = field(default_factory=list)
    safety_action: str = ""
    safety_code: str = ""
    react_action: str = ""
    react_code: str = ""
    react_hint: str = ""
    # 姐姐或哥哥，来自会话性别
    address: str = ""
    # 召回块只进这一轮 System，不写进人设 JSON
    memory_block: str = ""
    assistant_text: str = ""
    model_used: str = ""
    degraded: bool = False
