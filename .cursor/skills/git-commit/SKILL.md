---
name: git-commit
description: >-
  Git 提交与 PR 说明规范：Conventional Commits 类型前缀保留英文，subject 与 body 一律中文。
  在用户要求提交代码、写 commit message、创建 PR 时使用。
---

# Git 提交说明规范

## 何时使用

- 用户要求 `git commit`、提交代码、写提交说明
- 创建 Pull Request 的标题与正文

**仅在用户明确要求提交时执行 commit**；本 skill 只规定**怎么写**。

---

## 格式

```
<type>(<scope>): <中文简述>

<中文正文，可选，说明原因与影响>
```

| 部分 | 语言 | 说明 |
|------|------|------|
| `type` | **英文** | 固定关键字，见下表 |
| `scope` | 英文小写 | 可选；如 `character`、`dialogue`、`safety` |
| subject | **中文** | 一句说清「做了什么」，≤ 72 字，句末不加句号 |
| body | **中文** | 可选；说清「为什么」 |

**禁止**：subject/body 用英文（类型前缀除外）；`WIP`、`update`、`fix bug`；用「老项目」当对照理由。

---

## type 对照表

| type | 何时使用 |
|------|----------|
| `feat` | 用户可感知的新能力 |
| `fix` | 修 bug |
| `docs` | README、Skill、注释（不改运行逻辑） |
| `refactor` | 结构调整，不改外部行为 |
| `test` | 新增或修改测试 |
| `chore` | 不影响 src 的维护 |

不确定时：**修问题用 `fix`，加能力用 `feat`，只动文档用 `docs`**。

---

## scope 建议

| scope | 范围 |
|-------|------|
| `character` | 人设 JSON、呼唤池、默认角色 |
| `dialogue` | 对话图、服务、流式 |
| `safety` | 安全门、拒绝 code |
| `eval` | 评测集、打分 |
| `web` | 陪伴页 |

---

## 示例

```
feat(character): 默认角色改为玫莉蔻皮肤问答专家

只保留皮肤领域；旧身份不再加载。
```

```
fix(safety): 改身份只放行本角姓名玫莉蔻
```

---

## 禁止

- 未经用户要求自动 `git push`
- `git commit --amend` 除非用户明确要求且符合安全协议
- `--no-verify` 跳过 hook（除非用户明确要求）
