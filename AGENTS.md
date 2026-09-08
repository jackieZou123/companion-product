## Learned User Preferences
- 按可上线陪伴产品开发，不要教程、demo、playground 或「学习实验室」口径，也不做智能客服 / FAQ。
- 用户会自己查文档；不要把实现降成入门讲解，FastAPI 等该用就用。
- 禁止使用 `jiuban` 作为包名、模块名或文案；产品对外名称是「我依旧陪在你身边」。
- 文件与模块用语义化命名（如 `pages`、`index`、`src/app`），不要用产品代号当包名。
- 写 Python 时加简短中文注释，不要写成长篇说明。
- 未明确要求时，不要做前端、语音、Avatar、群聊、用户自建角色或主动消息。

## Learned Workspace Facts
- 默认角色是周德贵（`zhou_de_gui`）：74 岁四川乡下老爷爷，人称「老辈子」；不懂手机电脑、不装懂；仍是 AI，不能声称真人、不能上门。人设在 `src/app/character/profiles/zhou_de_gui.json`。
- Python 包名为 `companion`，应用代码在 `src/app/`，FastAPI 入口为 `app.index`。
- 技术栈：FastAPI + SSE；LangChain 接模型；LangGraph 编排对话图；LangSmith 追踪/评测；SQLAlchemy（本地 SQLite，可换 Postgres）。密钥只在 `.env`。
- 对话图：START → safety → refuse | react → generate。安全门先于模型，命中未成年 / 自伤 / 违法 / 改身份时不调模型。
- 呼唤「老辈子」：纯喊走斥责回复池；情绪低落呼唤走关心池；喊了人后面还有正事则带口吻再生成。
- Git `origin` 为 `git@github.com:jackieZou123/companion-product.git`，默认分支 `main`。
- 本机访问 GitHub 22 端口会被拦，需经 `ssh.github.com:443` 使用 SSH。
