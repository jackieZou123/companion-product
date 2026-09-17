---
name: add-character
description: Adds or edits a companion character profile JSON and keeps system prompt assembly, refusals, and safety codes in sync. Use when creating a new character, changing 玫莉蔻, editing character/profiles, or naming a character.
---

# 加 / 改角色

人设是数据，不是一段写死在代码里的 System Prompt。

## 步骤

1. 复制 `src/app/character/profiles/mei_li_kou.json` 为新文件，`id` 与文件名一致（snake_case）。角色名用用户给的称呼；玫莉蔻的 id 就是 `mei_li_kou`。工程目录仍用语义名（`pages`、`dialogue`、`app`），不要把 Python 包改成产品拼音。
2. 填齐：`identity` / `values` / `speech_style` / `relationship_stance` / `boundaries` / `never_do` / `refusals` / `degraded`。
3. `refusals` 的 key 必须覆盖 `SafetyPolicy` 全部 refuse code，外加 `default`。`degraded` 是模型全失败时的角色口吻，不要写成系统错误或客服公告。面向用户的 AI 披露放 `disclosure`。
4. 有呼唤口吻时配 `reactions`：`wake` 是喊名；其余是情绪池（`low_mood` / `happy` / `angry` 等，triggers + replies）。由 `ReactPolicy` 抽句，不要写进 identity。新池只要 JSON 加一段，代码会按最长触发词选用。闲置回访配 `nudges.idle_care.replies`，由 `NudgePolicy` 抽句。
5. 必须写明：这是 AI、禁止声称人类、禁止线下见面。
6. `name`、`id`、呼唤词只用用户给定或仓库已有的称呼。没有就问，不要编。
7. 说话方式写可执行约束（短句、不复读、不清单安慰、不接工单），不要写「要有趣」。皮肤事实以 `skin-qa-domain` 为准，不要把检测 IPC 写进 identity。
8. `CharacterRepository` 会加载目录下全部 JSON；默认角色仍是 `mei_li_kou`，除非改 `default_id()`。
9. 加测试：能 `get(id)`，`system_prompt()` 含名字和「不是人类」。

## 不要

- 仓库只留玫莉蔻这一个身份；已作废的旧人设不要加回来
- 把客服、工单、FAQ、老师人设混进来
- 在 Python 里 if character_id 拼另一套 Prompt
- 让皮肤问答专家突然变成导购、医生或客服口吻，或对皮肤以外的问题装懂
- 把预约协议、排班表写进 identity；客户预约走 `IntentPolicy`（`companion-actions`）
- 禁止AI自己意象起名字。不要编花名、昵称、草本意象人名；对外名字就是用户给的那个 `name`
