---
name: onion-image-iterate
description: Use when 用户已有图组或图片，想基于 G-XXX / 爆款图继续迭代、扩同类、换形式、微调、换 IP/场景/版式/CTA/Logo/比例，或说量好再扩、量不行换思路、这套图再来几套、拿这张相似再来。
---

# onion-image-iterate

## 任务目标

基于已有图组或用户上传图片做迭代。新图可以是轻微修改、同类扩展或推翻重做，但必须保留可追溯血缘。用户上传旧图后要求换文案、换角色、扩同类、同款再来，也属于这个 skill，而不是 `onion-image` 的探索生图入口。

成功结果是新图组和原图组之间的关系清楚：为什么改、改了哪些轴、保留了什么、是否应该写 `父图组`。

## 输入契约

必填输入：

- `基准图组`：G-XXX / image_groups record_id / 用户上传的原图。
- `迭代力度`：微调 / 扩同类 / 换形式。
- `改动轴`：IP、文案、场景细节、比例、Logo/CTA、风格参考图等。

可推断输入：

- 原图组的渠道、图片形式、比例、关联文案、关联方向、Logo、IP、原始 prompt 和附件参考图；用户给 G-XXX 但上下文没有内容时先回查 Base。
- 新图组的父图组：基于 G-XXX 迭代时默认写原图组 record_id；用户明确说不要血缘才留空。
- 临时图片锚点：用户直接上传旧图或给当前对话生成的图片，并要求换文案、换角色、换 CTA、扩类似时，可直接以这张图为锚点，不强制回查方向或文案。
- 数量：扩同类默认 3 套；微调默认 1 套；换形式按新出图 brief 判断。

## 推断原则

先判断力度，再判断轴。力度表示改动幅度；轴表示改哪里。两者正交。

| 力度 | 改动幅度 | 典型信号 |
|---|---|---|
| 微调 | 保留 95%，只改 1-2 个细节 | 换 CTA、换比例、换 Logo、调一处细节 |
| 扩同类 | 保留 70%，同方向同卖点，换部分表现 | 跑量好再扩、换 IP、换场景、换文案 |
| 换形式 | 推翻重做，保留血缘 | 跑不动、换思路、单图改三图、换方向 |

轴可跨力度共享。例如“微调 x IP”在用户只想替换角色且其他不变时成立；“扩同类 x IP+场景”是常见扩展；“微调 x 图片形式”不成立，因为图片形式变化会改变结构和张数，应切换到换形式。

上游血缘是可用信息，不是负担。用户给 G-XXX 时回查并保留父图组；用户只给图片文件或当前对话里的图时，当前图就是视觉锚点，写入 Base 时可以没有 `父图组`、`关联文案`、`关联方向`。

## 反问原则

只问阻塞项：

- 缺基准图组时，问用户给 G-XXX、选择最近图组，或上传图片。
- 缺力度时，问微调 / 扩同类 / 换形式。
- 缺改动轴时，问具体想改 IP、文案、场景、比例、Logo/CTA、风格中的哪些。
- 用户说“改 G-005”但不说怎么改时，不要直接生图。

有交互 UI 时一次性收集力度和轴；没有 UI 时用一句话问清关键缺口。具体运行时适配见 `../../shared/references/runtime-adapters.md`。

## 硬约束

- 基于已有图组迭代时，新图组默认写 `父图组` 指向原图组。
- 微调不能改变图片形式；单图改三图、双图改单图都属于换形式。
- 扩同类保持原方向、核心卖点和图片形式，除非用户明确升级为换形式。
- branch / iterate prompt 默认使用原图作为参考，保持 SAME 项。
- 不要主动增加用户没要求的变化轴。
- 用户确认采纳后才写 Base；上传新图组附件前默认压缩，版位有明确 KB 上限时按该上限压缩，否则默认 200KB；pending 或 rejected 不写图组。
- 使用付费生图前仍需按 `render.py --validate-only` 检查。

## 按需 Reference

- 力度和轴定义：`references/力度规则.md`。
- 系列一致性和 SAME/CHANGE：`references/系列一致性.md`。
- 血缘字段：`references/血缘关系.md`。
- 渠道版位、视觉资产、合规规则复用 `../onion-image/references/`。
- 涉及产品边界或品牌说法时读 `../../shared/references/advertiser-subject.md`。
- 用户给 G-XXX / C-XXX / record_id 或要求断点续跑时读 `../../shared/references/record-lookup.md`。
- branch delta 写法读 `../../shared/recipes/branch-prompt.md`。
- 渲染接口读 `../../shared/recipes/render-chain.md`。
- 写 Base 前读 `../../shared/base_schema.md` 的 image_groups。

## 工具调用

用户给 G-XXX 但上下文没有图组内容时，先用 `../../shared/scripts/lookup_record.py --id G-XXX --include-attachments --follow-upstream` 回查。拿到原图组 record_id 后，新图组默认把它写入 `父图组`。用户上传图片或引用当前对话图片时，不需要回查 Base。

渲染仍使用 `../onion-image/scripts/render.py`，按 `../../shared/recipes/render-chain.md` 的单张接口和链式规则执行。

用户确认采纳后，用 `../../shared/scripts/write_image_group.py` 写入新 image_groups。基于 G-XXX 时传 `--parent-group-id`，有可信 directions/copies record_id 时传 `--direction-id` / `--copy-id`；临时上传图没有上游时可以不传。脚本默认上传压缩后的图片附件；如果版位规则给了明确 KB 上限，把目标值作为 `--target-kb` 或 metadata 的 `目标KB` 传入。写入成功后只更新实际关联到的原图组、文案和方向；已经是已用或废弃的记录不要重复改。

不要传 `图组ID`、创建时间、创建人、最后更新时间；飞书会按当前 `--as user` 账号自动记录迭代图组的作者和入库时间。
