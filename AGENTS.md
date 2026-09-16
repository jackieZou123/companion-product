## Learned User Preferences
- 按可上线陪伴产品开发，不要教程、demo、playground 或「学习实验室」口径，也不做智能客服 / FAQ。
- 用户会自己查文档；不要把实现降成入门讲解，FastAPI 等该用就用。
- 文件与模块用语义化命名（如 `pages`、`index`、`src/app`）。角色名、角色文件、展示文案用玫莉蔻（id：`mei_li_kou`）；不要把 Python 包改成产品拼音，也不要用 `jiuban`。禁止自行给角色编花名或意象名，没有给定称呼就问。产品对外名称是「玫莉蔻」。
- 写 Python 时加简短中文注释，不要写成长篇说明。
- 未明确要求时，不要做前端、语音、Avatar、群聊、用户自建角色或主动消息。
- 提出需求后先确认方案再动手（含前端框架），不要自行拍板后直接开工。
- 生成或改 Python 后不要留类型检查报红；先读真实函数签名再写调用，做完跑 `pyrefly check src tests`。

## Learned Workspace Facts
- 默认角色是玫莉蔻（`mei_li_kou`）：皮肤问答专家；只懂皮肤，其他一概不懂；不接工单、不当医生；仍是 AI，不能声称真人、不能上门。人设在 `src/app/character/profiles/mei_li_kou.json`。仓库只保留这一身份，已作废人设不得残留在角色文件、测试、评测或技能里。
- Python 包名为 `companion`，应用代码在 `src/app/`，FastAPI 入口为 `app.index`。
- 技术栈：FastAPI + SSE；LangChain 经 `ChatModelFactory` 接 OpenAI 兼容网关或 DeepSeek；LangGraph 编排对话图；LangSmith 追踪/评测；SQLAlchemy（本地 SQLite，可换 Postgres）。密钥只在 `.env`。
- 对话图：START → safety → refuse | react → generate。安全门先于模型，命中未成年 / 自伤 / 违法 / 改身份时不调模型。
- 呼唤「玫莉蔻」：纯喊走应声回复池；情绪低落呼唤走关心池；喊了人后面还有正事则带口吻再生成。
- 对话用标准普通话、不用方言；口吻偏专业。创建会话须先选性别：女称「姐姐」、男称「哥哥」。
- T7 一体机设备 Skill（相机、手柄、护理 IPC）不搬进本仓。皮肤问答事实见 `.cursor/skills/skin-qa-domain/`。
- 对话展示界面在 `web/`（React + Vite）。
- Git `origin` 为 `git@github.com:jackieZou123/companion-product.git`，默认分支 `main`。
- 本机访问 GitHub 22 端口会被拦，需经 `ssh.github.com:443` 使用 SSH。
