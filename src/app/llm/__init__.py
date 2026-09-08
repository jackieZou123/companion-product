"""供应商适配：业务只拿 ChatModel。主模型与备用模型分开缓存。"""

from langchain_openai import ChatOpenAI

from app.config import Settings
from app.llm.types import ChatModel

__all__ = ["ChatModel", "ChatModelFactory", "LLMConfigurationError"]


class LLMConfigurationError(RuntimeError):
    pass


class ChatModelFactory:
    """供应商适配层。业务代码只依赖 ChatModel，不写死 base_url。"""

    def __init__(
        self,
        settings: Settings,
        override: ChatModel | None = None,
        fallback_override: ChatModel | None = None,
    ) -> None:
        self._settings = settings
        self._override = override
        self._fallback_override = fallback_override
        self._cached: ChatModel | None = None
        self._cached_fallback: ChatModel | None = None

    def primary_label(self) -> str:
        return self._settings.llm_model

    def fallback_label(self) -> str:
        return self._settings.llm_fallback_model.strip() or self._settings.llm_fallback_provider

    def chat_model(self) -> ChatModel:
        # override 给测试替身；线上走缓存的真实客户端
        if self._override is not None:
            return self._override
        cached = self._cached
        if cached is None:
            cached = self._build(
                self._settings.llm_provider,
                self._settings.llm_model,
            )
            self._cached = cached
        return cached

    def fallback_chat_model(self) -> ChatModel | None:
        """未配置备用供应商时返回 None，生成层再走角色口吻降级。"""
        if self._fallback_override is not None:
            return self._fallback_override
        provider = self._settings.llm_fallback_provider.strip()
        if not provider:
            return None
        cached = self._cached_fallback
        if cached is None:
            model = self._settings.llm_fallback_model.strip()
            cached = self._build(provider, model)
            self._cached_fallback = cached
        return cached

    def _build(self, provider: str, model: str) -> ChatOpenAI:
        resolved_provider = provider.strip().lower()
        resolved_model = model.strip()
        temperature = self._settings.llm_temperature

        if resolved_provider == "deepseek":
            api_key = self._settings.deepseek_api_key.strip()
            if not api_key:
                raise LLMConfigurationError("DEEPSEEK_API_KEY 未配置")
            return ChatOpenAI(
                model=resolved_model or "deepseek-chat",
                api_key=api_key,
                base_url="https://api.deepseek.com",
                temperature=temperature,
                timeout=self._settings.llm_timeout_seconds,
                max_retries=self._settings.llm_max_retries,
            )

        if resolved_provider == "openai":
            api_key = self._settings.openai_api_key.strip()
            if not api_key:
                raise LLMConfigurationError("OPENAI_API_KEY 未配置")
            base_url = (self._settings.openai_base_url or "").strip() or None
            return ChatOpenAI(
                model=resolved_model,
                api_key=api_key,
                base_url=base_url,
                temperature=temperature,
                timeout=self._settings.llm_timeout_seconds,
                max_retries=self._settings.llm_max_retries,
            )

        raise LLMConfigurationError(f"不支持的 LLM_PROVIDER={resolved_provider!r}")
