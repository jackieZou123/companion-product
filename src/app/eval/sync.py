"""把仓库内评测集同步到 LangSmith。本地 JSON 仍是权威来源。"""

from langsmith import Client
from langsmith.utils import LangSmithNotFoundError

from app.config import Settings
from app.eval.cases import DATASET_NAME, DATASET_VERSION, EvalCase, load_cases


def sync_dataset(settings: Settings, cases: list[EvalCase] | None = None) -> str:
    if not settings.langsmith_api_key.strip():
        raise RuntimeError("未配置 LANGSMITH_API_KEY，无法同步评测集")
    payload = cases if cases is not None else load_cases()
    client = Client(api_key=settings.langsmith_api_key.strip())
    dataset = _ensure_dataset(client)
    existing = {
        str((example.metadata or {}).get("case_id"))
        for example in client.list_examples(dataset_id=dataset.id)
    }
    pending = [case.to_example() for case in payload if case.id not in existing]
    if pending:
        client.create_examples(dataset_id=dataset.id, examples=pending)
    return dataset.name


def _ensure_dataset(client: Client):
    try:
        return client.read_dataset(dataset_name=DATASET_NAME)
    except LangSmithNotFoundError:
        return client.create_dataset(
            dataset_name=DATASET_NAME,
            description="玫莉蔻 陪伴质量评测：人设、拒绝、重复率、记忆。权威样本在仓库 JSON。",
            metadata={"version": DATASET_VERSION, "product": "companion"},
        )
