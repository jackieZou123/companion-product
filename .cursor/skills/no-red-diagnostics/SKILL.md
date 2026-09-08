---
name: no-red-diagnostics
description: >-
  生成或修改 Python 后必须消掉编辑器报红（语法、Pyrefly、Ruff）。
  写代码、改签名、改 dataclass/ORM、用户提到报红、语法、lints、Pyrefly 时使用。
---

# 生成代码不能留报红

请注意代码生成的时候的语法问题，别每次都这样。

## 做完前清单

1. 先读被调用函数的真实签名，再写关键字参数；禁止凭印象编 `address=` / `gender=`。
2. 给 dataclass、SQLAlchemy 行、Pydantic 模型加字段后，所有读写点一起改。
3. `pyrefly check src tests` 必须 0 error。
4. 对改过的文件跑 ReadLints；还有 ERROR 就修，不准交给用户。
5. `pytest` 绿了但编辑器仍说「没有属性 / 意外关键字」：先看源码是否真有该字段。有则多半是循环 import，把新符号放到能独立导入的模块（如 `app.dialogue.errors`），不要让 `pages` 只从 `app.dialogue` 包入口拿新异常。

## 本仓库常见坑

- `from app.dialogue import 新异常` 会先执行 `dialogue/__init__.py` → `service.py`。分析失败时，编辑器会假装新符号不存在。
- 测试用 `from app import character`，不要 `import app.character as character`。
- 不要用 `# type: ignore` 盖报红，除非是第三方假阳性并写明原因。

## 不要

- CLI 过了就说做完，无视编辑器红线
- 只改调用方、不改被调用签名
