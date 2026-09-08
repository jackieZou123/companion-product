import os

import pytest

from tests.helpers import FakeModel, api_client, start_conversation, test_settings as settings_for_test

from app.observability.tracing import configure_tracing, turn_run_config


def test_tracing_off_does_not_require_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    configure_tracing(settings_for_test(langsmith_tracing=False, langsmith_api_key=""))
    assert os.environ["LANGSMITH_TRACING"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_tracing_on_requires_key():
    with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY"):
        configure_tracing(settings_for_test(langsmith_tracing=True, langsmith_api_key=""))


def test_tracing_on_writes_project(monkeypatch: pytest.MonkeyPatch):
    configure_tracing(
        settings_for_test(langsmith_tracing=True, langsmith_api_key="ls-test", langsmith_project="companion-eval")
    )
    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "companion-eval"
    configure_tracing(settings_for_test(langsmith_tracing=False))


def test_turn_run_config_carries_session_ids():
    config = turn_run_config(
        conversation_id="c1",
        character_id="mei_li_kou",
        user_id="u_1",
        request_id="req-9",
        mode="turn",
    )
    assert config["metadata"]["character_id"] == "mei_li_kou"
    assert config["metadata"]["request_id"] == "req-9"
    assert "dialogue" in config["tags"]


def test_turn_passes_trace_config_to_model():
    model = FakeModel("先歇一下。")
    with api_client(model) as client:
        conversation_id = start_conversation(client, character_id="mei_li_kou").json()[
            "conversation_id"
        ]
        turned = client.post(
            f"/v1/conversations/{conversation_id}/turns",
            json={"text": "脸干得发紧，晚上还刺"},
        )
        assert turned.status_code == 200
    assert model.last_config is not None
    assert model.last_config["metadata"]["character_id"] == "mei_li_kou"
    assert model.last_config["metadata"]["conversation_id"] == conversation_id


def test_readyz_reports_tracing_off():
    with api_client() as client:
        body = client.get("/readyz").json()
        assert body["tracing"] == "off"
