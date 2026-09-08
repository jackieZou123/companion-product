"""LangSmith 开关与每轮对话的 trace 上下文。没 Key 不允许只开 tracing。"""

from contextlib import nullcontext
import os
from typing import Any

from langsmith import trace as langsmith_trace
from langchain_core.runnables import RunnableConfig

from app.config import Settings

_LANGSMITH_TRACING = "LANGSMITH_TRACING"
_LANGCHAIN_TRACING = "LANGCHAIN_TRACING_V2"


class _NoopRun:
    """tracing 关闭时占位，调用方不用分支。"""

    def end(self, **_kwargs: Any) -> None:
        return None


def configure_tracing(settings: Settings) -> None:
    if not settings.langsmith_tracing:
        # Settings 为准，避免测试或上一进程把 tracing 留在 true
        os.environ[_LANGSMITH_TRACING] = "false"
        os.environ[_LANGCHAIN_TRACING] = "false"
        return
    if not settings.langsmith_api_key:
        raise RuntimeError("已开启 LANGSMITH_TRACING，但未配置 LANGSMITH_API_KEY")
    os.environ[_LANGSMITH_TRACING] = "true"
    os.environ[_LANGCHAIN_TRACING] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project


def turn_run_config(
    *,
    conversation_id: str,
    character_id: str,
    user_id: str,
    request_id: str,
    mode: str,
) -> RunnableConfig:
    """传给 LangGraph / ChatModel，让 LLM span 挂上会话元数据。"""
    return {
        "run_name": f"dialogue_{mode}",
        "tags": ["companion", "dialogue", mode],
        "metadata": {
            "conversation_id": conversation_id,
            "character_id": character_id,
            "user_id": user_id,
            "request_id": request_id,
        },
    }


def dialogue_trace(
    *,
    enabled: bool,
    name: str,
    project: str,
    inputs: dict[str, Any],
    metadata: dict[str, Any],
    tags: list[str],
) -> Any:
    if not enabled:
        return nullcontext(_NoopRun())
    return langsmith_trace(
        name,
        run_type="chain",
        inputs=inputs,
        metadata=metadata,
        tags=tags,
        project_name=project,
    )
