---
name: onion-help
description: Use when 用户首次安装 onion 投放 plugin、切设备、核心 skill 出错、想确认环境就绪、初始化或检查飞书 Base 结构、查看 Base 进度、检查 pending 队列或待审反馈；触发词包括环境检查、配置好了吗、我能跑了吗、装好了没、初始化 Base、Base 结构、看下进度、待审反馈、onion 状态。
---

# onion-help（状态诊断）

用最小必要检查面回答"现在能不能跑、卡在哪里、Base 里还有什么"。它是诊断入口，不是工作流调度器；只解释现状和可选下一步，不替用户强行分流。

## 启动加载

1. Read `~/.onion-ad/.env`，只看配置是否存在和关键变量是否可读。
2. Read `../../shared/base_schema.md`，拿 4 张表的 table_id 和状态字段。
3. Read `../../shared/references/runtime-adapters.md`，确认当前运行时如何收集选择、反馈和异步任务。
4. Read `../../shared/references/base-setup.md`，确认共享 Base / 空 Base 初始化策略。
5. Read `references/环境自检清单.md`，按需执行环境、脚本、pending 队列检查。
6. Read `references/状态摘要查询.md`，按需查询 4 张 Base 表状态。
7. Read `../../shared/references/record-lookup.md`，确认 D/C/G ID 断点续跑入口。

## 判断用户目标

先判断用户真正想知道什么，再选择检查面：

| 用户意图 | 检查面 |
|---|---|
| "装好了没 / 能跑吗 / 环境检查 / 核心 skill 报错" | 环境自检 + pending 队列；无阻塞时再给 Base 摘要 |
| "初始化 Base / Base 结构 / 空表 / 表不存在" | Base schema 检查；缺表缺字段时按 setup 文档给维护人创建方案，不自动创建 |
| "看下进度 / Base 状态 / 还有啥没标注" | Base 摘要 + pending 队列；不跑老张 API 连通性，除非用户怀疑出图失败 |
| "onion 状态 / 帮我看看 / 现在能干啥" | 环境自检 + Base 摘要 + 轻量下一步建议 |
| "pending / 重试 / 写入失败" | 只看 pending 队列和共享脚本状态；不要自动 retry，除非用户明确要求 |

不要为了形式完整而跑无关检查。状态查询要快，故障排查才需要更深。

## 环境自检输出

按 `references/环境自检清单.md` 的项目执行，结果用三档：

```text
✅ 通过：能继续使用
⚠️ 警告：建议修，但不阻塞主流程
🔴 阻塞：需要先处理，否则核心 skill 大概率失败
```

报告必须覆盖这些新架构检查：

- `runtime-adapters.md` 是否存在，避免 skill 依赖单一 Claude 运行时语法。
- 共享 Base 的 4 张表和关键字段是否存在；缺失时读 `../../shared/references/base-setup.md`。
- `../../shared/scripts/*.py` 是否能编译。
- `write_record.py`、`update_status.py` 是否能 dry-run。
- `render.py --validate-only` 是否能通过基本参数校验。
- `~/.onion-ad/pending.jsonl` 是否有未完成项、`retry_count >= 3` 项、`ambiguous: true` 项。

如果存在 🔴 阻塞项，先输出修复命令或修复位置；除非用户明确要求，不继续跑昂贵或会写入外部系统的检查。

## Base 摘要输出

按 `references/状态摘要查询.md` 查询 4 张表，输出固定为一屏内摘要：

```text
📊 Base 当前状态（截至 <NOW>）

directions    待用 8 / 已用 12 / 废弃 3 / 共 23 条
copies        待用 12 / 已用 35 / 废弃 5 / 共 52 条
image_groups  待用 5 / 已用 18 / 废弃 2 / 共 25 套
feedbacks     ⚠️ 待审 3 / 已转规则 4 / 已驳回 1 / 已采纳 0
pending       ⚠️ 未完成 2 / ambiguous 1 / retry>=3 0
```

显示规则：

- 常规表按 `待用 / 已用 / 废弃 / 共` 排序。
- feedbacks 按 `待审 / 已转SKILL.md规则 / 已采纳到下次迭代 / 已驳回` 排序。
- pending 队列独立显示，不混进 Base 表计数。
- 待审反馈或 pending 异常存在时，用 `⚠️` 提醒，但不要把它们说成核心流程阻塞，除非实际会导致写入失败。

## 下一步建议

只给 1-3 条可选建议，用"你可以"，不要写成强制流程：

- directions 有待用：可以调 `onion-copy` 出文案。
- copies 有待用：可以调 `onion-image` 出图。
- image_groups 有待用：可以调 `onion-image-iterate` 扩同类或换形式。
- feedbacks 有待审：可以抽时间在 Base 里处理，通常不阻塞主流程。
- pending 有 `ambiguous: true`：先人工核对 Base 是否已写入，再决定是否重试。

最后可以提醒非线性流程可用：用户也能直接基于已有图组迭代，不必从方向开始。

## 边界

| 不做 | 原因 |
|---|---|
| 自动修复登录态、权限、API key | 涉及账号或密钥，给命令让用户自己执行 |
| 自动 retry pending | ambiguous 写入可能已成功，盲重试会重复写记录 |
| 强制用户先跑 A 再跑 B | 真实投放经常跳过链路，help 只呈现状态 |
| 收集方向/文案/图的业务反馈 | 这些反馈应由对应核心 skill 处理 |
| 把诊断结果改写进 SKILL.md | 规则沉淀要经过用户确认或 feedback 表处理 |

## references 索引

| 文件 | 何时读取 |
|---|---|
| `环境自检清单.md` | 环境、脚本、API、pending 队列诊断 |
| `状态摘要查询.md` | Base 4 表状态计数和下一步建议模板 |
| `../../shared/references/base-setup.md` | 共享 Base 校验、空 Base 初始化和建表边界 |
| `../../shared/references/record-lookup.md` | D/C/G ID 回查、任意入口启动和断点续跑 |
