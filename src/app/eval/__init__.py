"""陪伴质量评测：固定样本、硬规则打分、可选同步到 LangSmith。"""

from app.eval.cases import DATASET_NAME, DATASET_VERSION, load_cases
from app.eval.runner import run_case
from app.eval.scorers import score_case
from app.eval.sync import sync_dataset

__all__ = [
    "DATASET_NAME",
    "DATASET_VERSION",
    "load_cases",
    "run_case",
    "score_case",
    "sync_dataset",
]
