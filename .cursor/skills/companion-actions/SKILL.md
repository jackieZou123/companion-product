---
name: companion-actions
description: >-
  Adds customer companion actions (booking, status) via IntentPolicy and SSE
  action events, without stuffing ERP into the character prompt. Use when
  adding 预约、进度、排班、店员查询、点奶茶式帮忙、intent 节点、action 事件, or when
  the user mentions 实质性帮助 / 工作中帮忙.
---

# 陪伴里的实质性帮忙

帮忙处理工作和查询，本质也是陪伴。好的伴侣不只给情绪价值，还要在工作中提供实质性帮助。

分开的不是「情感 / 工作」，而是**谁开口、谁对数字负责**。

## 何时用

加客户预约/进度、店员排班/产品状态，或改 `IntentPolicy`、SSE `action`、浮窗确认条。

## 做法

1. 规则写在 `src/app/dialogue/intent.py`（`IntentPolicy`），安全门之后、生成之前。不要另调一次 LLM 去猜意图。
2. 稳定 `code`：现有 `care_booking` / `booking_status` / `care_status` / `none`。新 code 同步评测 `src/app/eval/datasets/action.json`。
3. 流式与非流式都发同一结构：`{code, slots, confirm_required}`。拒绝路径、纯呼唤不发 `action`。
4. `generate` 只加**本轮** `intent_hint`（和呼唤 hint 一样），禁止写进 `mei_li_kou.json` 的 identity。
5. 真预约、排班、产品状态由宿主调业务接口。本仓不查表、不落预约、不编档期。
6. `stream_turn` 必须复用同一套 `IntentPolicy` 和 `build_model_messages`。

```
START → safety → refuse | react → intent → recall → generate → review → remember
```

## 客户 vs 店员

| 谁 | 进 `/v1` | 做什么 |
|---|---|---|
| 客户 | 对玫莉蔻说话 | 意图出 `action`，人话仍是她；确认卡/结果在壳上 |
| 店员 | 排班、产品状态**不要**进对话图 | 店员壳 + 业务 API；误打进来标 `none`，按「皮肤以外不懂」说 |

## 不要

- 把排班表、库存、已约成功写进 Prompt 或人设
- 用 function calling 在本仓直连 ERP
- 把玫莉蔻改成客服/前台口吻
- 安全门未过就发 `action`

## 测试

- 命中样本 → `action.code` 与槽位正确；回复禁止值班/已经约好/客服套话
- 脸干 → `action` 为空
- 未成年/改身份 → 无 `action`，不调模型
