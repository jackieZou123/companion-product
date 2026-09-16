import asyncio

from tests.helpers import FakeModel, test_settings as settings_for_test

from app.eval.cases import DATASET_NAME, Expectation, load_cases
from app.eval.runner import make_runtime, run_case
from app.eval.scorers import score_text
from app.eval.sync import sync_dataset


def test_dataset_covers_three_suites():
    cases = load_cases()
    suites = {case.suite for case in cases}
    assert suites == {"character", "refusal", "repetition", "memory"}
    assert {case.id for case in cases} >= {
        "refuse_underage",
        "refuse_role_break",
        "prompt_identity",
        "pair_diverse_rest",
        "extract_skin_type_dry",
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
