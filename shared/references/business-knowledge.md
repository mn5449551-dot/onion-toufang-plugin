# 业务知识加载规则

本文件说明如何把素材平台和已爬取 APP 图文资料用于 onion Skills。业务知识源在：

`/Users/xhh/app_tixiao/sucai/ai-ad-platform/docs/business-knowledge`

`/Users/xhh/app_tixiao/skill_toufang/app图文`

## 加载原则

优先级：

1. `canonical/` 是权威业务定义，适合沉淀为硬规则或字段语义。
2. `app图文/洋葱广告skills/_shared/knowledge/卖点库.md` 是已爬取 APP 功能和通用卖点的主参考，适合补全功能-卖点矩阵。
3. `references/for-stage-*` 是按生产阶段加载的经验材料，只在对应任务需要时读取。
4. `references/archived/` 是历史材料，默认不读、不迁移，除非用户明确要追溯旧方案。

不要把整包业务知识塞进任一 `SKILL.md`。Skill 只保留决策原则和少量事实，具体经验放在 reference，按任务阶段读取。

## 阶段对应

| Skill | 可参考的业务知识 | 用途 |
|---|---|---|
| `onion-direction` | `canonical/字段定义-方向.md`、`canonical/好方向示例.md`、`canonical/时间节点推荐表-2026-通用.md`、`references/for-stage-2b/*` | 方向字段语义、切入角度、多样性、时间节点、痛点和卖点 |
| `onion-copy` | `canonical/字段定义-文案.md`、`canonical/广告主语约束.md`、`references/for-stage-3b/*` | 文案字段、copyType、渠道语气 |
| `onion-image` | `canonical/字段定义-图片.md`、`canonical/广告主语约束.md`、`references/for-stage-4b/*` | 图组字段、视觉合规、系列一致性、CTA/Logo/IP |
| `onion-image-iterate` | `references/for-stage-4b/图片生成参考/series-consistency.md`、`image-to-image-tips.md` | SAME/CHANGE、基准图继承、Logo/IP/CTA 一致性 |

## 冲突处理

发现业务知识和当前投放 Skill 不一致时，不直接覆盖线上规则：

- `canonical/渠道与平台.md` 的新平台 MVP 只列 OPPO/vivo/小米；当前 onion Skill 仍保留华为/荣耀等既有投放版位。改渠道范围会影响现有 Base 选项和历史数据，需业务确认后再改。
- 业务知识的方向字段是 10 字段模型；当前 Base 的 directions 是 6 个核心业务字段 + 辅助字段。当前只吸收 10 字段里的语义，不改 Base schema。
- `canonical/字段定义-图片.md` 包含 `fileSizeKb`、`width`、`height`、`fileFormat` 等资产字段；当前 Base 没有这些字段。图片上传已压缩，但是否增加可写元数据字段需单独确认。
- `canonical/拒绝原因.md` 只保留“说不清楚”作为快捷拒绝原因；当前 feedbacks 表保留更丰富反馈类型。暂不收窄反馈体系。

## 使用边界

业务知识能帮助模型判断，但不能替代用户现场输入：

- 用户明确给了渠道、版位、素材目标时，以用户输入为主。
- 用户给了新卖点但不在卖点库时，不编造成既有能力；先确认或作为待沉淀反馈。
- 业务知识中带日期的时间节点只作为参考；当前日期或排期不覆盖时，不硬套。
