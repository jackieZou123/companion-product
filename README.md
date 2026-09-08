# 我依旧陪在你身边

面向成年用户的中文 AI 陪伴对话内核。一对一、长期关系、文本主链路。语音 / 视频 / Avatar 以旁路接入，不进入主对话路径。

产品目标不是把模型接上就能聊，而是同时满足：

- 听得懂：上下文进入会话状态，而不是单次请求
- 像同一个人：角色来自结构化 Profile，而不是一段会漂移的 System Prompt
- 说得自然：内容、语气、边界由编排层约束
- 记得准确且可控：消息全量落库，送进模型的是截断后的短期窗口
- 需要时能拒绝：安全门是图上的节点，不依赖模型自觉

## 架构

```
src/app/
  index.py              # 入口：uvicorn app.index:app
  pages/                # HTTP 路由
    index.py            # / /healthz /readyz /metrics
    conversations.py    # /v1/conversations
  dialogue/             # LangGraph 编排
  character/            # 角色 Profile
  llm/                  # 供应商适配
```

```
客户端
  → FastAPI（REST + SSE）
      → DialogueService
          → LangGraph：safety → refuse | react → generate → review
          → SSE 流式生成（与图共用安全门、呼唤池、出口审核和角色 Prompt）
          → CharacterRepository
          → ChatModelFactory（超时、重试、供应商适配）
          → SqlConversationStore（SQLite / Postgres；会话按 X-User-Id 隔离）
```

| 层 | 职责 | 替换点 |
| --- | --- | --- |
| LangChain | 消息、Chat 模型、供应商适配 | `ChatModelFactory` |
| LangGraph | 会话编排：安全门、呼唤、生成、出口审核、拒绝 | `dialogue/graph.py` |
| LangSmith | 每轮对话 span；人设 / 拒绝 / 重复率评测集 | `LANGSMITH_TRACING`；`python -m app.eval --sync` |
| 存储 | SQLAlchemy。本地 SQLite，生产换 `postgresql+asyncpg://` | `SqlConversationStore` |

业务代码禁止写死 `base_url`。换网关只改环境变量。

## 当前能力

- `POST /v1/conversations` 创建一对一会话（`X-User-Id` + `adult_confirmed`）
- `GET /v1/conversations` 当前用户的会话列表
- `GET /v1/conversations/{id}` 含历史消息；别人的会话返回 404
- `DELETE /v1/conversations/{id}` 删除一条会话
- `GET /v1/me/export` / `DELETE /v1/me` 导出或清空该用户数据
- `POST /v1/conversations/{id}/turns` 完整一轮
- `POST /v1/conversations/{id}/turns/stream` SSE：`safety` / `react` / `token` / `done`
- 角色「周德贵」：四川农村老爷爷、老辈子口吻，不懂也不装懂科技；创建会话返回 AI 披露
- 呼唤联动：喊「老辈子」走回复池；带情绪则走对应池（伤心、开心、愤怒、感慨等）；纯呼唤不调模型
- 规则安全门：未成年、自伤、越权改身份、违法协助；生成后再审出口（自称真人 / 教违法）
- 模型超时与重试、主模型失败后备用供应商、再失败则角色口吻降级
- JSON 日志（带 request_id）、`x-request-id`、CORS
- `/healthz` `/readyz`（未就绪 503）`/metrics`（turn 的 P50 / P95）
- 固定评测集：人设、拒绝、重复率（`src/app/eval/datasets/`，硬规则打分）
- Alembic 迁移：`make migrate`；CI 跑 pyrefly + pytest

## 下一步

1. **P1**：用户画像、事件记忆、关系状态机；记忆可纠正、可删除、可隔离
2. **P1**：主动消息（触发、频控、TTL）
3. **P2**：把评测集接到真实模型跑分，补记忆准确性
4. **旁路**：ASR / TTS / RTC、Avatar

## 本地运行

```bash
cd ~/Desktop/langchain-study-lab
source .venv/bin/activate
pip install -e ".[dev]" -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
```

```bash
uvicorn app.index:app --reload --host 0.0.0.0 --port 8000
```

```bash
curl -s http://127.0.0.1:8000/readyz
curl -s http://127.0.0.1:8000/v1/conversations \
  -H 'content-type: application/json' \
  -H 'X-User-Id: u_1' \
  -d '{"character_id":"zhou_de_gui","adult_confirmed":true}'
curl -s http://127.0.0.1:8000/v1/conversations/<conversation_id>/turns \
  -H 'content-type: application/json' \
  -H 'X-User-Id: u_1' \
  -d '{"text":"地里活干不完，腰又酸"}'
curl -N http://127.0.0.1:8000/v1/conversations/<conversation_id>/turns/stream \
  -H 'content-type: application/json' \
  -H 'X-User-Id: u_1' \
  -d '{"text":"还是停不下来"}'
```

评测（默认 FakeModel，不打网关）：

```bash
python -m app.eval
# 有 LANGSMITH_API_KEY 时把样本同步到 LangSmith
python -m app.eval --sync
```

生产数据库：

```bash
pip install -e ".[postgres]"
# DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/companion
alembic upgrade head
```

```bash
pytest
docker build -t companion:0.1.0 .
docker run --env-file .env -p 8000:8000 companion:0.1.0
```

## 关键取舍

- **文本主链路，语音旁路**：陪伴质量取决于角色、状态、记忆和拒绝。
- **规则门禁先于模型**：未成年与危机话术在图节点拦截。
- **消息全量落库，上下文窗口截断**：不把「模型能看多少」和「用户数据留多久」绑死。
- **SSE 先于 WebSocket**：先把流式生成做稳，打断和全双工下一轮再上。
- **一个角色先做深**：先把周德贵的一致性做硬，再开放用户自建角色。
- **主观体验进固定样本**：人设、拒绝、重复率用仓库 JSON + 硬规则打分；LangSmith 是追踪和同步，不是验收本身。
