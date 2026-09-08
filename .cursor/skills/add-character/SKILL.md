---
name: add-character
description: Adds or edits a companion character profile JSON and keeps system prompt assembly, refusals, and safety codes in sync. Use when creating a new character, changing 周德贵, or editing character/profiles.
---

# 加 / 改角色

人设是数据，不是一段写死在代码里的 System Prompt。

## 步骤

1. 复制 `src/app/character/profiles/zhou_de_gui.json` 为新文件，`id` 与文件名一致（snake_case）。
2. 填齐：`identity` / `values` / `speech_style` / `relationship_stance` / `boundaries` / `never_do` / `refusals` / `degraded`。
3. `refusals` 的 key 必须覆盖 `SafetyPolicy` 全部 refuse code，外加 `default`。`degraded` 是模型全失败时的角色口吻，不要写成系统错误或客服公告。
4. 有呼唤口吻时配 `reactions.wake` / `reactions.low_mood`（triggers + replies），由 `ReactPolicy` 抽句，不要写进 identity。
5. 必须写明：这是 AI、禁止声称人类、禁止线下见面。
6. 说话方式写可执行约束（短句、不复读、不清单安慰、不懂科技不装懂），不要写「要有趣」。
7. `CharacterRepository` 会加载目录下全部 JSON；默认角色仍是 `zhou_de_gui`，除非改 `default_id()`。
8. 加测试：能 `get(id)`，`system_prompt()` 含名字和「不是人类」。

## 不要

- 为了上线第二个角色稀释周德贵
- 把客服、助手、老师人设混进来
- 在 Python 里 if character_id 拼另一套 Prompt
- 让农村老辈子人设突然变成科技专家、城里时髦人或女人口吻
