"""python -m app.eval ：本地跑评测；--live 打真模型；--sync 推到 LangSmith。"""

import argparse
import asyncio
import sys

from app.config import Settings, get_settings
from app.eval.cases import DATASET_NAME, load_cases
from app.eval.runner import eval_model, eval_settings, make_runtime, run_case
from app.eval.sync import sync_dataset
from app.llm import ChatModel, LLMConfigurationError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="玫莉蔻 陪伴质量评测")
    parser.add_argument("--sync", action="store_true", help="把样本同步到 LangSmith，不跑模型")
    parser.add_argument(
        "--live",
        action="store_true",
        help="用 .env 里的真实模型跑 service 样本；默认仍是 Stub",
    )
    args = parser.parse_args(argv)
    if args.sync and args.live:
        print("--sync 只上传样本，不要和 --live 一起用", file=sys.stderr)
        return 2
    if args.sync:
        name = sync_dataset(get_settings())
        print(f"synced {name}")
        return 0
    try:
        settings = eval_settings(live=args.live)
        model = eval_model(settings, live=args.live)
    except LLMConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.live:
        print(
            f"live\t{settings.llm_provider}\t{settings.llm_model}",
            file=sys.stderr,
        )
    return asyncio.run(_run_local(settings, model))


async def _run_local(settings: Settings, model: ChatModel) -> int:
    runtime = await make_runtime(settings, model)
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
