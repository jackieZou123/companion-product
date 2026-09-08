"""业务侧 Chat 接口，避免把 ChatOpenAI 泄漏到对话层。"""

from collections.abc import AsyncIterator
from typing import Any, Protocol


class ChatModel(Protocol):
    """业务侧 Chat 接口。ChatOpenAI 与测试替身都走这一组方法。"""

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any: ...

    def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[Any]: ...
