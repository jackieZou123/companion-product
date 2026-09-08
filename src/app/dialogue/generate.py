"""主模型 → 备用供应商 → 角色口吻。图和 SSE 共用，避免两套失败路径。"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
import logging
from typing import Any

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig

from app.character import CharacterProfile
from app.llm import ChatModel, ChatModelFactory, LLMConfigurationError

logger = logging.getLogger(__name__)

DEGRADED_MODEL = "degraded"


@dataclass
class Generation:
    """一次生成结果。degraded 表示没用模型，用了角色口吻兜底。"""

    text: str
    model: str
    degraded: bool


def _candidates(factory: ChatModelFactory) -> list[tuple[str, ChatModel]]:
    # 配置错误也往下走，让角色口吻兜底，而不是把 500 抛给用户
    items: list[tuple[str, ChatModel]] = []
    try:
        items.append((factory.primary_label(), factory.chat_model()))
    except LLMConfigurationError:
        logger.exception("llm_primary_not_configured")
    try:
        fallback = factory.fallback_chat_model()
    except LLMConfigurationError:
        logger.exception("llm_fallback_not_configured")
        return items
    if fallback is None or (items and fallback is items[0][1]):
        return items
    items.append((factory.fallback_label() or "fallback", fallback))
    return items


def _full_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    return ""


def _token_text(content: Any) -> str:
    # 流式分片不能 strip，否则会把词间空格吃掉
    if isinstance(content, str) and content:
        return content
    return ""


def invoke_generation(
    factory: ChatModelFactory,
    character: CharacterProfile,
    messages: list[BaseMessage],
    config: RunnableConfig,
) -> Generation:
    """非流式：依次 invoke，都失败再用角色降级话术。"""
    for label, model in _candidates(factory):
        try:
            response = model.invoke(messages, config=config)
            text = _full_text(response.content)
            if text:
                return Generation(text=text, model=label, degraded=False)
            logger.warning("llm_empty_content", extra={"model": label})
        except Exception:
            logger.exception("llm_invoke_failed")
    return Generation(
        text=character.degraded_text(), model=DEGRADED_MODEL, degraded=True
    )


async def astream_generation(
    factory: ChatModelFactory,
    character: CharacterProfile,
    messages: list[BaseMessage],
    config: RunnableConfig,
) -> AsyncIterator[str | Generation]:
    """流式：先吐 token，最后一条是 Generation。一个 token 都没出来才换源。"""
    last_error: Exception | None = None
    for label, model in _candidates(factory):
        emitted = False
        try:
            async for chunk in model.astream(messages, config=config):
                token = _token_text(getattr(chunk, "content", ""))
                if token:
                    emitted = True
                    yield token
            if emitted:
                yield Generation(text="", model=label, degraded=False)
                return
            logger.warning("llm_empty_content", extra={"model": label})
        except Exception as exc:
            last_error = exc
            if emitted:
                # 已经给客户端发过半句，不能再换嘴
                raise
            logger.exception("llm_astream_failed")
    if last_error is not None:
        logger.warning("llm_degraded_copy")
    yield character.degraded_text()
    yield Generation(text="", model=DEGRADED_MODEL, degraded=True)
