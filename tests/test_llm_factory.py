import pytest

from tests.helpers import FakeModel

from app.config import Settings
from app.llm import ChatModelFactory, LLMConfigurationError


def test_factory_requires_api_key():
    factory = ChatModelFactory(
        Settings(_env_file=None, llm_provider="openai", openai_api_key="")
    )
    with pytest.raises(LLMConfigurationError):
        factory.chat_model()


def test_factory_fallback_override_skips_network():
    stub = FakeModel("ok")
    backup = FakeModel("backup")
    factory = ChatModelFactory(
        Settings(_env_file=None, openai_api_key="x", llm_fallback_provider="deepseek"),
        override=stub,
        fallback_override=backup,
    )
    assert factory.chat_model() is stub
    assert factory.fallback_chat_model() is backup


def test_factory_fallback_none_when_unset():
    factory = ChatModelFactory(Settings(_env_file=None, openai_api_key="x"))
    assert factory.fallback_chat_model() is None
