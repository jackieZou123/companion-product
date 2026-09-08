"""python -m app.eval ：本地跑评测；--sync 推到 LangSmith。"""

from collections.abc import AsyncIterator
import argparse
import asyncio
import sys
from typing import Any

from app.config import Settings, get_settings
from app.eval.cases import DATASET_NAME, load_cases
from app.eval.runner import make_runtime, run_case
from app.eval.sync import sync_dataset


class _StubChunk:
    def __init__(self, content: str) -> None:
        self.content = content


class _StubModel:
    """CLI 默认替身。单测请用 tests.helpers.FakeModel。"""

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = 0

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> _StubChunk:
        self.calls += 1
        return _StubChunk(self.text)

    async def astream(self, input: Any, config: Any = None, **kwargs: Any) -> AsyncIterator[_StubChunk]:
        self.calls += 1
        yield _StubChunk(self.text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="玫莉蔻 陪伴质量评测")
    parser.add_argument("--sync", action="store_true", help="把样本同步到 LangSmith，不跑模型")
    args = parser.parse_args(argv)
    if args.sync:
        name = sync_dataset(get_settings())
        print(f"synced {name}")
        return 0
    return asyncio.run(_run_local())


async def _run_local() -> int:
    settings = Settings(
        _env_file=None,
        app_env="test",
        openai_api_key="eval-local",
        langsmith_tracing=False,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    runtime = await make_runtime(settings, _StubModel("先别抓。干燥发紧多半是屏障在叫。"))
    failed = 0
    try:
        for case in load_cases():
            result = await run_case(runtime, case)
            mark = "ok" if result.score.passed else "FAIL"
            print(f"{mark}\t{case.suite}\t{case.id}")
            if not result.score.passed:
                failed += 1
                for check in result.score.checks:
                    if not check.passed:
                        print(f"\t{check.name}: {check.detail}")
    finally:
        await runtime.engine.dispose()
    print(f"{DATASET_NAME}: failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
