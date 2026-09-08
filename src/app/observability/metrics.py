"""进程内延迟窗口，给 /metrics 的 P50/P95。"""

from math import ceil
from collections import deque


class LatencyWindow:
    def __init__(self, size: int = 256) -> None:
        self._values: deque[int] = deque(maxlen=size)

    def observe(self, latency_ms: int) -> None:
        self._values.append(latency_ms)

    def snapshot(self) -> dict[str, int]:
        if not self._values:
            return {"count": 0, "p50_ms": 0, "p95_ms": 0}
        ordered = sorted(self._values)
        return {
            "count": len(ordered),
            "p50_ms": _percentile(ordered, 50),
            "p95_ms": _percentile(ordered, 95),
        }


def _percentile(ordered: list[int], percent: int) -> int:
    index = min(len(ordered) - 1, max(0, ceil(percent / 100 * len(ordered)) - 1))
    return ordered[index]
