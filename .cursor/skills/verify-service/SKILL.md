---
name: verify-service
description: Runs pytest and the matching FastAPI/SSE checks after backend changes. Use when finishing a feature, before calling work done, or when the user asks to verify, 跑通, or 验收.
---

# 验收改动

## 必做

```bash
source .venv/bin/activate
pyrefly check src tests
pytest
```

类型检查和测试都要过才能说做完。`FakeModel` 必须满足 `ChatModel` 的 `invoke` / `astream` 签名，不能写成单参数 `messages`。

## 按改动补打

| 改了什么 | 做什么 |
| --- | --- |
| 安全 / 角色 | `pytest tests/test_character_and_safety.py tests/test_conversations.py` |
| 对话图 / 流式 | 单测 SSE；需要真模型时再打 `/turns/stream` |
| 存储 / API | `GET /v1/conversations/{id}` 能读到刚写入的 messages |
| 配置 / 供应商 | `/readyz`；不要把 Key 打进终端输出 |

真模型请求：

```bash
curl -s http://127.0.0.1:8000/readyz
# POST /v1/conversations → POST .../turns 或 .../turns/stream
```

服务未起：`uvicorn app.index:app --reload --host 0.0.0.0 --port 8000`

## 不要

- 只贴一段模型回复当验收
- 单测里打付费网关
- 把 `.env` 里的 Key 写进聊天或 git
