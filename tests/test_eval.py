import asyncio

import pytest
from tests.helpers import FakeModel, test_settings as settings_for_test

from app.eval.__main__ import main
from app.eval.cases import DATASET_NAME, Expectation, load_cases
from app.eval.runner import (
    CountingModel,
    EvalStubModel,
    eval_model,
    eval_settings,
    make_runtime,
    run_case,
)
from app.eval.scorers import score_case, score_text
from app.eval.sync import sync_dataset
from app.llm import ChatModelFactory, LLMConfigurationError


def test_dataset_covers_three_suites():
    cases = load_cases()
    suites = {case.suite for case in cases}
    assert suites == {"character", "refusal", "repetition", "memory", "action"}
    assert {case.id for case in cases} >= {
        "refuse_underage",
        "refuse_role_break",
        "prompt_identity",
        "pair_diverse_rest",
        "extract_skin_type_dry",
        "turns_dry_then_evening",
        "turns_correct_dry_to_combo",
        "service_book_sunday_care",
    }


def test_scorer_rejects_customer_service_and_lists():
    expect = Expectation(forbid_numbered_list=True, must_not_contain=("客服",), max_exclamation=1)
    bad = score_text(
        "很高兴为您服务。\n1. 先喝水\n2. 再睡觉\n3. 明天再说！！",
        expect,
    )
    failed = {item.name for item in bad if not item.passed}
    assert "forbid_numbered_list" in failed
    assert "not_customer_service" in failed
    assert "max_exclamation" in failed


def test_scorer_rejects_near_duplicate_replies():
    expect = Expectation(max_similarity=0.75)
    checks = score_text(
        "先别抓。干燥发紧多半是屏障在叫。",
        expect,
        previous="先别抓。干燥发紧多半是屏障在叫。",
    )
    assert any(item.name == "max_similarity" and not item.passed for item in checks)


def test_scorer_checks_recalled_profile_not_reply():
    case = next(item for item in load_cases() if item.id == "turns_dry_then_evening")
    missed = score_case(case, text="今晚先停刺激。", recalled_text="")
    assert any(
        item.name == "recalled_must_contain" and not item.passed for item in missed.checks
    )
    hit = score_case(
        case,
        text="今晚先停刺激。",
        safety_action="allow",
        model_calls=2,
        recalled_text="已知对方\n- 肤质：干性",
    )
    assert hit.passed


def test_service_turns_writes_then_recalls_skin_type():
    async def _run() -> str:
        runtime = await make_runtime(
            settings_for_test(),
            FakeModel("今晚先把刺激的步骤停掉。"),
        )
        try:
            case = next(item for item in load_cases() if item.id == "turns_dry_then_evening")
            result = await run_case(runtime, case)
            assert result.score.passed, result.score.checks
            snapshot = await runtime.memory.recall(f"eval:{case.id}", case.character_id)
            return snapshot.prompt_block()
        finally:
            await runtime.engine.dispose()

    block = asyncio.run(_run())
    assert "肤质：干性" in block


def test_eval_dataset_passes_with_fake_model():
    async def _run() -> list[str]:
        runtime = await make_runtime(
            settings_for_test(),
            FakeModel("先别抓。干燥发紧多半是屏障在叫。"),
        )
        failed: list[str] = []
        try:
            for case in load_cases():
                result = await run_case(runtime, case)
                if not result.score.passed:
                    detail = "; ".join(
                        f"{item.name}:{item.detail}" for item in result.score.checks if not item.passed
                    )
                    failed.append(f"{case.id} {detail}")
        finally:
            await runtime.engine.dispose()
        return failed

    failed = asyncio.run(_run())
    assert failed == [], failed


def test_sync_dataset_upserts_missing_examples(monkeypatch):
    created: dict = {}

    class _FakeDataset:
        id = "ds-1"
        name = DATASET_NAME

    class _FakeClient:
        def __init__(self, api_key: str) -> None:
            created["api_key"] = api_key

        def read_dataset(self, *, dataset_name: str):
            created["read"] = dataset_name
            return _FakeDataset()

        def list_examples(self, *, dataset_id: str):
            return []

        def create_examples(self, *, dataset_id: str, examples: list):
            created["dataset_id"] = dataset_id
            created["count"] = len(examples)

    monkeypatch.setattr("app.eval.sync.Client", _FakeClient)
    name = sync_dataset(settings_for_test(langsmith_api_key="ls-test"))
    assert name == DATASET_NAME
    assert created["count"] == len(load_cases())
    assert created["api_key"] == "ls-test"


def test_eval_model_default_is_stub():
    model = eval_model(settings_for_test(), live=False)
    assert isinstance(model, EvalStubModel)


def test_eval_model_live_requires_key():
    with pytest.raises(LLMConfigurationError, match="OPENAI_API_KEY"):
        eval_model(settings_for_test(openai_api_key=""), live=True)


def test_eval_model_live_wraps_factory_client(monkeypatch):
    inner = FakeModel("ok")
    monkeypatch.setattr(ChatModelFactory, "chat_model", lambda self: inner)
    model = eval_model(settings_for_test(), live=True)
    assert isinstance(model, CountingModel)
    assert model.calls == 0
    model.invoke([])
    assert model.calls == 1
    assert inner.calls == 1


def test_eval_settings_live_uses_memory_db(monkeypatch):
    monkeypatch.setattr(
        "app.eval.runner.get_settings",
        lambda: settings_for_test(database_url="sqlite+aiosqlite:///./data/app.db"),
    )
    live = eval_settings(live=True)
    assert live.database_url == "sqlite+aiosqlite:///:memory:"
    stub = eval_settings(live=False)
    assert stub.openai_api_key == "eval-local"


def test_main_stub_runs_dataset():
    assert main([]) == 0


def test_main_rejects_live_together_with_sync():
    assert main(["--live", "--sync"]) == 2


def test_main_live_without_key_exits(monkeypatch, capsys):
    monkeypatch.setattr(
        "app.eval.__main__.eval_settings",
        lambda live: settings_for_test(openai_api_key=""),
    )
    assert main(["--live"]) == 1
    captured = capsys.readouterr()
    assert "OPENAI_API_KEY" in captured.err
    assert "sk-" not in captured.err
