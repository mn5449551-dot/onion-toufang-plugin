# 洋葱学园投放素材生成 Plugin

> 内部 plugin，给洋葱学园投放团队（内容负责人 + 投放负责人）在 Claude Code / Codex CLI 里跑投放素材生成流程用。

---

## 🧩 包含 5 个 Skill

| Skill | 类型 | 干啥 | 触发举例 |
|---|---|---|---|
| `onion-help` | **导航** | 环境自检（lark-cli/.env/Python/Pillow/老张 API/Base/Pending）+ Base 结构检查 + Base 状态摘要（4 表 status 计数 + feedbacks 待审）+ 轻量推荐下一步 | `环境检查 / 初始化 Base / 看下进度 / 配置好了吗` |
| `onion-direction` | 核心 ① | 出/扩/改方向卡（投放素材的上游，也可基于 D-XXX 继续） | `拍题精学的开学季方向，3 条 / D-007 再扩 5 条` |
| `onion-copy` | 核心 ② | 出/扩/改文案（基于方向、方向 ID、文案 ID 或临时样本）| `用 D-007 出信息流文案 3 套 / C-012 标题再扩 5 套` |
| `onion-image` | 核心 ③ | 出图（基于 C-XXX 或临时文案调老张 API 批量生图 + 选图）| `用 C-104 出应用商店三图，2 套` |
| `onion-image-iterate` | 核心 ④ | 扩/换/微调图（基于 G-XXX 或用户上传图迭代）| `G-005 量好，扩同类 3 套` |

4 个核心 skill 可以形成数据流：方向 → 文案 → 图 → 扩/换图；但不是强制线性流程。用户可以从合适入口开始：`D-XXX` 进 `onion-direction` / `onion-copy`，`C-XXX` 进 `onion-image`，`G-XXX` 或用户上传旧图进 `onion-image-iterate`。方向 ID 不能直接跳到图，必须先形成可用文案。

**推荐首次使用流程**：先调 `onion-help` 做一键环境自检 + 看 Base 状态，确认就绪再调核心 skill。

---

## 🛠️ 安装

### 团队成员（你拿到这个 plugin 后）

**前提**：
- 装好 Claude Code 或 Codex CLI（[官网](https://claude.com/claude-code)）
- 装好飞书 lark-cli（参 Anthropic 内置 `lark-base` skill）
- 你的飞书账号在生产 Base 的"可编辑"协作者列表里

**安装步骤（一次性）**：

```bash
# 1. 确保已 lark-cli 登录（用你自己飞书账号）
lark-cli auth login

# 2. 添加本 plugin 的 marketplace
# 方式 A：从 GitHub（推荐）
# 先 gh auth login
/plugin marketplace add <your-github-org>/onion-toufang-plugin

# 方式 B：从本地路径（开发期或离线）
/plugin marketplace add /path/to/onion-toufang-plugin

# 3. 安装 5 个 skill
/plugin install onion-toufang@onion-toufang

# 4. 配置 .env（保留默认 Base 配置，只填 LAOZHANG_API_KEY）
mkdir -p ~/.onion-ad
cp /path/to/onion-toufang-plugin/.env.template ~/.onion-ad/.env
# 编辑 ~/.onion-ad/.env 填入 LAOZHANG_API_KEY
chmod 600 ~/.onion-ad/.env

# 5. 出图上传前会压缩图片，使用 onion-image / onion-image-iterate 的成员需要 Pillow
pip install Pillow
```

**之后任何时间想升级到新版**：

```bash
/plugin marketplace update onion-toufang
```

---

## 🎯 用法

在 Claude Code / Codex CLI 里直接跟 AI 说话：

```
你: 拍题精学的开学季方向，3 条
AI: [触发 onion-direction skill，反问/出方向卡/迭代/写飞书 Base]

你: 用 D-007 出信息流文案 3 套
AI: [触发 onion-copy skill，出 3 套文案 → 用户确认 → 写 Base 或进入出图]

你: 用 C-104 出应用商店三图，2 套，豆包 IP
AI: [触发 onion-image skill，本地配置页 → 调老张 API 出图 → 选择页标注 → 采纳图写 Base]

你: G-005 跑得好，扩同类 2 套，换上官 IP
AI: [触发 onion-image-iterate skill，确认旧图和改动轴 → 生图 → 选择页标注 → 按 parent_group_id 标血缘入库]
```

当前图片流程使用本地 HTML 页面收集配置和标注选择，不依赖 Codex/Claude 原生弹窗卡片。结果确认后再写入 Base，不会自动把所有候选写入。

真实入库流程：

```text
方向：生成候选 → 用户确认 → 入库
文案：生成候选 → 用户确认 → 入库或进入出图
新图：配置页 → 生图 → 选择页标注 → 采纳图入库
迭代图：确认旧图和改动轴 → 生图 → 选择页标注 → 采纳图入库
```

修改 D-XXX / C-XXX 默认创建新版，不覆盖历史记录；只有用户明确要求废弃旧记录时，才把旧记录状态改为废弃。

---

## 🗂️ Plugin 结构

```
onion-toufang-plugin/
├── .codex-plugin/
│   └── plugin.json                         ← 让 Codex 识别这是 plugin
├── .claude-plugin/
│   └── marketplace.json                    ← 让 Claude Code / Codex 识别这是 plugin
├── README.md                               ← 本文件
├── .env.template                           ← 配置模板（API key + 默认 Base token/TID）
├── skills/                                 ← 5 个独立 skill
│   ├── onion-direction/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── onion-copy/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── onion-image/                        ← 出图：自有脚本/模板/资产都在这
│   │   ├── SKILL.md
│   │   ├── references/
│   │   ├── scripts/{render.py, image_compress.py}
│   │   ├── templates/image-selection.html
│   │   └── assets/{ip-roles, logos, styles}
│   └── onion-image-iterate/
│       ├── SKILL.md
│       └── references/
└── shared/                                 ← 4 skill 共用业务知识
    ├── base_schema.md                      ← 飞书 Base schema + 默认 token/TID
    ├── feedback_observation.md             ← 反馈观察 + subagent 任务模板
    ├── knowledge/卖点库.md                  ← 洋葱 APP 卖点矩阵
    └── recipes/                            ← 出图 prompt 与 render 调度 recipe
```

---

## 🔐 数据流 & 飞书 Base

**当前 Base（测试期）**：
- Token: `WIoGb0ksnaREvJsPtQCcW8Lsnfg`
- URL: https://guanghe.feishu.cn/base/WIoGb0ksnaREvJsPtQCcW8Lsnfg
- 4 张表：directions / copies / image_groups / feedbacks

**4 张表关系**：
```
directions（方向卡 D-XXX）
   ↓ 1 对多
copies（文案 C-XXX，关联方向）
   ↓ 1 对多
image_groups（图组 G-XXX，一行 = 一套，关联文案 + parent_group_id 标血缘）

feedbacks（反馈池，记录稳定可复用的用户反馈）
```

**关键设计**：
- 一行 = 一套图（不是一张图）。`image_groups` 里图1/图2/图3 是 3 个附件字段
- 反馈机制：主 skill 观察稳定反馈，确认有价值后用共享脚本写 feedbacks 表（用户零打断）
- 参考图本地存（`onion-image/assets/`），Base 字段 text 存路径

---

## 🤝 跟其他 Skill 的协同

本 plugin 操作飞书 Base 时应配合 `lark-base` skill 校对命令细节。
本 plugin 只负责"业务规则"（出什么、怎么写、字段含义）；lark-cli 的命令格式 / 错误处理 / 限流以 `lark-base` 和 `lark-cli --help` 为准。

不要依赖 Claude / Codex 自动加载其他 skill；涉及 Base 读写时显式使用 `lark-base`。

---

## 🔄 版本管理 + 升级

| 插件维护人 | 团队成员 |
|---|---|
| 改 SKILL.md / 加 references / 修 bug → git commit + push | `/plugin marketplace update onion-toufang` 拉最新 |
| 改 Base schema（如加字段）→ 改 shared/base_schema.md + push | 同上 |
| 切到生产 Base → 改 shared/base_schema.md 里的 token + TID + push | 同上 |

---

## 🐛 反馈 & 问题

- 用 plugin 中遇到 bug / 改进建议 → 在 Claude Code 里直接说"我要反馈 G-XXX 这套图"。
- 主 skill 会观察稳定反馈；确认有复用价值时写进 `feedbacks` 表，由插件维护人定期 review 升级 plugin。
- 紧急问题：联系插件维护人 / 投放团队群管理员。

---

## 📋 设计文档（开发者）

内部设计文档目录下有完整设计资料：
- `01-架构设计.md` - 顶层架构
- `09-Base表结构详细设计.md` - schema 真相源
- `10-脚本实现细节.md` - 瘦身版架构说明
- `11-错误处理与MVP定义-短版.md` - MVP 验收标准
- 各 skill 业务规则提炼: `05-/06-/07-/08-`
