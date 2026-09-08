---
name: code-comments
description: Adds brief Chinese comments when writing or editing Python. Use whenever generating, refactoring, or reviewing app source; whenever the user mentions 注释, comments, or 说明.
---

# 代码注释

生成或改 Python 时必须带注释。宁短，不要教程腔。

## 要写

- 每个模块顶部一行 docstring：这个文件干什么
- 类、公开函数：一句「为什么 / 边界」，名字已经能说明的可以不写
- 不明显的取舍：一行 `#`，写原因不写步骤

## 不要写

- 复述代码（`# 返回结果`、`# 循环列表`）
- 课次口吻、`demo`、逐步讲解
- 给每个 Settings 字段、每个 import 加注释

## 示例

```python
# ❌
# 调用模型生成回复
response = model.invoke(messages)

# ✅
# 流式与非流式共用，避免两套 Prompt
messages = build_model_messages(character, history, user_text)
```

```python
class SafetyPolicy:
    """规则门禁先于模型。不能靠模型自觉。"""
```

改完代码后扫一眼：新文件有模块说明，新分支有「为什么」。
