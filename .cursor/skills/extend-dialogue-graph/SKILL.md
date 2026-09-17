---
name: extend-dialogue-graph
description: Adds or changes LangGraph dialogue nodes (safety, generate, refuse, memory, relationship) without stuffing a single prompt. Use when editing the conversation graph, stream_turn, or splitting a new capability out of the LLM call.
---

# 扩展对话图

## 何时用

新能力是「另一类决策或副作用」（记忆写入、关系判断、主动消息、审核、预约意图），不是多写两句人设。预约/进度走 `IntentPolicy`，见 `companion-actions`。

## 步骤

1. 先定节点输入输出，写进 `DialogueState`（`src/app/dialogue/state.py`）。不要把新字段只塞进 Prompt。
2. 在 `src/app/dialogue/graph.py` 加 node + edge。`safety` 必须仍是 `START` 后的第一跳。
3. `generate` 只负责说话。读写存储放独立节点或 `DialogueService`，不要在 generate 里偷偷 `append`。
4. `stream_turn`（`src/app/dialogue/service.py`）与图共用：
   - 同一 `SafetyPolicy`、`ReactPolicy`、`IntentPolicy`
   - 同一 `build_model_messages`
   - 落库时机与非流式一致
5. 非流式走 `ainvoke`，流式自己迭代 token。两边最终 `TurnResult` 字段对齐。
6. 补测试：放行路径、拒绝路径、如有状态则第二轮能读到。

## 反例

- 在 `mei_li_kou.json` 的 identity 里写完整记忆协议
- 为 SSE 复制一套 system prompt
- 跳过 safety 直接 `model.astream`
