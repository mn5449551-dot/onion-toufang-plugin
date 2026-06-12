# 业务知识加载规则

本文件说明 onion Skills 运行时从哪里获取业务知识。外部业务知识已全部提炼为插件内文件；**运行时只读插件内路径，不要尝试读取插件目录外的任何业务知识目录**。

> 溯源说明（仅维护人）：插件内业务知识提炼自维护人本机的 `ai-ad-platform/docs/business-knowledge` 和 `app图文` 目录。这两个目录不随插件分发，团队成员机器上不存在；更新业务知识时由维护人把变化同步进下表对应的插件内文件。

## 加载原则

优先级：

1. `shared/knowledge/卖点库.md` 是 APP 功能和通用卖点的主参考，适合补全功能-卖点矩阵。
2. `shared/knowledge/功能-洋葱私教班.md` 是洋葱私教班课程事实、卖点和文案手册规则的主参考；涉及私教班、AI定制班、30 分钟课堂、AI+真人辅导时优先读取。
3. 各 skill 的 `references/` 已吸收对应阶段的权威字段定义和经验材料，按各 SKILL.md 的「按需 Reference」指引读取。

不要把整包业务知识塞进任一 `SKILL.md`。Skill 只保留决策原则和少量事实，具体经验放在 reference，按任务阶段读取。

功能事实不足时，优先加载对应功能知识库；仍不足时追问用户。不要为了写出强共鸣而编功能，也不要把不同功能事实互相迁移。

Creative Brief 使用 `shared/references/creative-brief.md` 的规则：先建立“功能 × 用户”理解，再进入方向、文案、图片 prompt 或扩同类创意。机械流程、Base 写入、图片压缩和打包不需要业务知识补全。

## 阶段对应（全部为插件内路径）

| Skill | 业务知识文件 | 用途 |
|---|---|---|
| `onion-direction` | `skills/onion-direction/references/字段与生成规则.md`、`经验参考.md`、`时间节点策略.md`、`shared/knowledge/卖点库.md` | 方向字段语义、切入角度、多样性、时间节点、痛点和卖点 |
| `onion-copy` | `skills/onion-copy/references/字段定义-文案.md`、`学生视角与网感.md`、`渠道.md`、`规格.md`、`常见误区.md`、`shared/references/advertiser-subject.md`、`shared/knowledge/卖点库.md`、`shared/knowledge/功能-洋葱私教班.md` | 文案字段、学生表达资产、文案类型、渠道语气、功能事实和课程卖点 |
| `onion-image` | `skills/onion-image/references/视觉元素规范.md`、`合规视觉雷区.md`、`渠道风格与复盘.md`、`shared/references/advertiser-subject.md` | 视觉合规、渠道风格、CTA/Logo/IP |
| `onion-image-iterate` | `skills/onion-image-iterate/references/系列一致性.md`、`力度规则.md`、`血缘关系.md` | SAME/CHANGE、基准图继承、Logo/IP/CTA 一致性 |

## 功能事实边界

| 功能 | 主要知识源 | 不能迁移 |
|---|---|---|
| 拍题精学 | `shared/knowledge/卖点库.md`、拍题相关用户资料、运营认可文案提炼 | 不把私教班的诊断分班、AI+真人辅导写成拍题精学能力 |
| 洋葱私教班 | `shared/knowledge/功能-洋葱私教班.md` | 不把拍题精学的一拍解析、分步讲解、继续追问写成私教班独有能力 |
| 其它功能 | 卖点库、用户提供资料、Base 历史记录 | 不从拍题精学或私教班硬套场景和功能词 |

## 冲突处理（维护人备忘：外部知识库与线上规则的已知差异）

发现业务知识和当前投放 Skill 不一致时，不直接覆盖线上规则：

- 外部知识库的新平台 MVP 只列 OPPO/vivo/小米；当前 onion Skill 仍保留华为/荣耀等既有投放版位。改渠道范围会影响现有 Base 选项和历史数据，需业务确认后再改。
- 外部知识库的方向字段是 10 字段模型；当前 Base 的 directions 是 6 个核心业务字段 + 辅助字段。当前只吸收 10 字段里的语义，不改 Base schema。
- 外部图片字段定义包含 `fileSizeKb`、`width`、`height`、`fileFormat` 等资产字段；当前 Base 没有这些字段。图片上传已压缩，但是否增加可写元数据字段需单独确认。
- 图片标注页的不采纳反馈保留 `固定规则反馈 / 主观感受反馈 / 跳过反馈`；当前 feedbacks 表只写固定规则反馈和主观感受反馈，跳过不入库。

## 使用边界

业务知识能帮助模型判断，但不能替代用户现场输入：

- 用户明确给了渠道、版位、素材目标时，以用户输入为主。
- 用户给了新卖点但不在卖点库时，不编造成既有能力；先确认或作为待沉淀反馈。
- 业务知识中带日期的时间节点只作为参考；当前日期或排期不覆盖时，不硬套。
