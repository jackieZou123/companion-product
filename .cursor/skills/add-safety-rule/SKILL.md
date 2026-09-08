---
name: add-safety-rule
description: Adds a production safety gate code (regex, refusal copy, tests) that runs before the model. Use when adding refusal behavior, content policy, underage/crisis/jailbreak handling, or when the user mentions 安全门, 拒绝, 边界.
---

# 加安全规则

安全门是产品能力，不是 Prompt 礼貌。

## 步骤

1. 在 `src/app/safety/__init__.py` 增加正则和分支，返回稳定 `code`（小写 + 下划线）。
2. 每个已有角色的 `refusals` 补上该 `code`，口吻跟角色走，不要统一变成「根据相关法律法规」。
3. `CharacterProfile.refusal_text` 已按 code 取值；缺 key 会落到 `default`，上线前必须配齐。
4. 测试（`tests/test_character_and_safety.py` + API 测试）：
   - 命中样本 → `action == "refuse"` 且 `code` 正确
   - API 路径 `FakeModel.calls == 0`
   - 拒绝正文来自角色 JSON，不是模型输出
5. 过宽的正则不要合入（例如单独一个「死」字）。

## 现有 code

`underage` / `self_harm` / `criminal` / `role_break` / `ok`

## 自伤话术

拒绝陪伴式共情，给出离开屏幕和热线，不讨论方法。
