---
name: onion-image
description: Use when 用户要基于文案、文案 ID、方向 ID、刚生成的第 N 条文案或已有文案内容生成洋葱学园投放广告图、营销图、信息流单图、应用商店双/三图、学习机图片，或指定 IP/Logo/风格参考图调用 gpt-image-2 生图；触发词包括出图、生图、做图、给我几套图、用这个文案出图、选择第二条出图。
---

# onion-image

## 任务目标

把已确认的文案转成可投放图片。这个 skill 会调用付费图片 API，因此每次进入实际生图前都必须先打开图片配置页，让用户确认版位、套数、Logo、IP、CTA 和参考图策略，再生成 prompt、validate、渲染。

成功结果是一组可供用户选择的图片方案，并能在用户确认后写入 `image_groups` 表，供后续投放和迭代追踪。

## 输入契约

必填输入：

- `文案`：C-XXX / copies record_id / 用户粘贴的主副标题或短句。
- `图片形式`：单图 / 双图 / 三图；从 copies 记录继承时不再问。
- `渠道/版位`：用户可以为同一文案一次选择多个渠道和多个版位；从 copies 记录继承时仍可追加或覆盖。
- `视觉配置`：版位、Logo、IP、CTA、界面/功能参考图、风格参考、套数；这些字段必须来自本轮图片配置页保存的 `image-config-result.json`。

默认和推断：

- 文案记录有渠道和图片形式时直接继承；用户给 C-XXX 但上下文没有内容时先回查 Base。
- 用户只给 D-XXX 想直接出图时，先回查方向；若没有可用文案，先产出/确认文案或转 `onion-copy`，不要跳过文案层直接生图。
- 用户给当前对话里的临时文案，或上传一张旧图要求“换文案/换角色/类似再来”，可以把这段文案或这张图作为本次锚点，不强制追溯方向、文案或图组血缘。
- 未指定 Logo、CTA、IP 或界面/功能参考图时，不要替用户静默决定；在图片配置页一次性确认。文本主导方案可以把“不用 IP”作为建议选项，但仍要让用户在配置页确认。
- 未指定字体时，默认从 `assets/font-references/` 的洋葱专属字体参考图里随机/轮换选 1 张；字体不是阻塞项，不因为缺字体反问。prompt 只要求学习字形气质、描边、排版节奏并和画面融合，不要求 100% 复刻，不复制参考图里的示例文字。
- 视觉配置只让用户选版位，不让用户盲选比例。版位规则来自 `config/channel-placement-rules.json`；每个版位绑定 `target_size`、`render_size`、压缩 KB 和一期支持状态。
- 多版位共用一套业务配置和文案锚点，但每个版位必须单独生成 prompt，并按该版位的尺寸/渠道约束渲染与导出。随机 IP、随机字体按每张图重新抽取，不因为共用配置而锁定同一个资产。
- 套数默认 2 套；用户说“几套”按形式换算张数，用户说“几张”时先澄清。
- 11-50 套属于批量变体任务，prompt 生成要分批精写，不一次性粗糙吐完。

## 推断原则

先按图片形式路由：

| 形式 | 生成方式 | 读什么 |
|---|---|---|
| 单图 | 每套独立生成 1 张 | `../../shared/recipes/single-prompt.md` |
| 双图 | 图1 base 先生成，图2 用图1做 delta | `base-prompt.md` + `branch-prompt.md` |
| 三图 | 图1 base 先生成，图2/图3 都用图1做 delta | `base-prompt.md` + `branch-prompt.md` |

图片配置页是所有付费生图的强制入口。无论用户在聊天里给得多完整，都先启动 `scripts/interactive_server.py` 打开 `/image-config`；已给的 C-XXX、版位、Logo、IP、CTA、形式、套数只允许作为 `--context` 或页面预填/提示，不能作为跳过配置页的理由。只有当前请求已经有用户保存过的、request_id 匹配的 `image-config-result.json`，才继续 prompt、validate 和渲染。

非线性入口要承认：用户可能直接拿 C-XXX 生图，或拿一段临时文案生图；只要文案锚点明确，不要求先走方向和文案全流程，但仍必须经过图片配置页。

选择续跑要更谨慎：用户说“选择第 N 条文案 / 第二条 / 就用这个出图”只代表文案被选中，不代表视觉配置完整。若渠道、图片形式、版位、Logo、CTA、IP、参考图任一项缺失，先问配置，不要直接默认信息流竖版、默认 Logo、默认无 IP 或默认无 CTA。

轻量图片改造也要承认：用户上传旧图并要求换文案、换 IP、换比例或同款扩几套时，当前图片就是视觉锚点。除非用户给了 G-XXX 或明确要求查历史记录，否则不要为了补全链路去回查 Base。

多套新图要有创意差异：场景细节、构图、切入角度、视觉节奏至少错开；但同一套内的双/三图要保持统一世界观。

批量变体默认由当前 Agent 分批生成 prompt。1-10 套可一次写完；11-50 套按 5-10 套一批推进，每批继承前面已用的 IP、场景、镜头、排版和视觉隐喻 ledger，保证跨批不重复。外部 planner API 只作为可选 idea pool，不作为默认最终 prompt 生产方式。

## 反问原则

只问阻塞项：

- 缺文案时，问用户选文案或直接粘文案。
- 缺图片形式且不能从文案记录继承时，问单图 / 双图 / 三图。
- 缺版位时，先问目标版位；可多选，且选项必须展示目标尺寸、gpt 出图尺寸、KB 上限和是否一期可用，不要让用户单独选比例。
- 缺付费生图所需资产选择时，只问缺失的视觉配置：Logo 要不要、CTA 写什么或不用、IP 用谁/随机/不用、是否加界面/功能卖点参考图、是否使用用户上传图/风格参考图。IP 选项必须来自 `assets/asset-manifest.json` 的本地真实资产，不要只硬编码 6 个标准名；有全身照、学段、Q3 等变体时要列出可选变体。

有交互 UI 时一次性收集缺口；没有 UI 时用一句话列出关键缺口。对 `onion-image` 来说，本地 `/image-config` 配置页就是默认交互 UI。具体运行时适配见 `../../shared/references/runtime-adapters.md`。

Codex / Claude Code 没有稳定原生选择卡时，必须使用本 skill 的本地交互页：启动 `scripts/interactive_server.py`，让用户在 `/image-config` 页面完成图片配置；保存后读取同目录的 `image-config-result.json`，再进入 prompt 和付费渲染。

配置页交互规则：

- 版位先选大类：应用商店 / 学习机 / 信息流 / 百度；再在该大类下选具体版位。已选版位跨大类保留，允许同一文案一次生成多个渠道/版位。
- 版位卡片必须展示 `target_size`、`render_size`、目标 KB、直出能力和不可选原因。扩图、合成、双图/三图/组图等一期不支持项置灰，不允许提交。
- 套数是手动数字输入，范围 1-50；超过 10 套仍按批次推进 prompt 和渲染。
- Logo 和 IP 必须显示本地资产缩略图，数据来自 `assets/asset-manifest.json`，不要只给纯文字下拉；IP 额外提供“随机 IP”。
- 字体参考只有启用 / 不启用。启用时由 Agent 从 `assets/font-references/` 为每张图完全随机抽取一张，不让用户选具体字体参考。
- CTA 按具体版位的 `cta_policy` 显示；任一选中版位允许 CTA 时才收 CTA。
- 界面 / 功能参考图不在 HTML 里上传；需要时让用户直接在 Codex 对话里上传截图。
- 补充说明只用于生图建议，例如画面风格、文字多少、主体位置，不承载结构化字段。
- 当前配置页代表“探索生成”模式；“同类扩展 / 基于已有图继续扩”属于后续迭代模式，不混在探索配置里。

## 硬约束

- 不允许绕过配置页直接生图；不允许调用聊天内置 imagegen 或其它通用图片工具来替代本 skill 的 `render.py` 链路。没有本轮有效的 `image-config-result.json` 时，下一步只能是打开配置页或让用户补文案锚点。
- 付费调用前必须先确认 `LAOZHANG_API_KEY` 存在且不是占位符，再用 `render.py --validate-only` 检查 prompt、`render_size`、输出路径和参考图路径。缺 key 时直接提示用户先跑 `onion-help` 环境检查或补 `~/.onion-ad/.env`，不要等到渲染阶段才失败。
- 只渲染配置里 `enabled=true` 的版位。`directness=expand/composite` 或双图/三图/组图的一期置灰版位不能绕过配置页直接生成。
- 使用 Logo/IP/字体/风格参考图时，必须在 prompt 里写“参考图说明”，用 `参考图1/参考图2/...` 对应实际传入顺序；不能只写“参考上图”或“用豆包参考图”。
- 画面有中文文字时，prompt 必须明确字体策略。用户没指定字体时，选 1 张洋葱专属字体参考图并加入 `reference_images`；同一套双/三图用同一张字体参考，branch 图通过 base PNG 继承，不重复传。prompt 写“学习参考图的字体气质，使文字和画面融合，不要求完全一致，不复制参考图文字”。
- 批量任务先完成当前批次 prompt 的质量检查，再进入付费渲染；不要为了并发出图而直接渲染未审的 50 条 prompt。
- 双/三图必须真实链式：图1 PNG 落盘后，再用图1 PNG 生成 branch。
- branch 参考图默认只传图1 PNG；不要重复传 Logo/IP/风格/字体资产。
- 强情绪词、提分承诺、保过、100%、唯一、第一等风险词要避开。
- 不要让手机设备出现明显违规外观或虚构平台 UI。
- 广告主语默认是洋葱学园 APP 学生端，不把教师版、校园版、合作硬件或其他产品线画成主角。
- HTML 选择页里未采纳或 pending 的方案不写入 Base。
- 成图后必须进入 `templates/image-selection.html` 选择页或等价的明确选择流程；不能只在聊天里贴图后结束。只有用户在选择页或对话里明确采纳的图组才能写入 Base。
- 构建选择页必须调用 `scripts/build_selection_page.py` 或等价脚本，把本次生成的所有图组写进 HTML；脚本会把不在 HTML 输出目录里的图片复制到 `selection-assets/`，保证 `file://` 和本地 `http.server` 都能加载。不能只给一个空模板或只贴本地图片列表。
- 当本次使用了本地交互服务收集配置，成图后继续把 `image-selection.html` 放在同一输出目录，并给用户同一服务下的 `/image-selection.html` 链接；配置页和标注/选择页必须在同一个 `interactive_server.py` 服务内运行。流程顺序是先配置页，后标注/选择页。用户在选择页提交后优先写入 `image-selection-result.json`，再由 Agent 读取结果决定写 Base。
- 批量或续生成图片时，页面不应依赖手动重建才能看到新图；每生成完一套或一批，Agent 要把该批 schemes POST 到 `/api/image-sets`，服务会原子更新 `image-sets.json`，已打开的选择页会轮询 `/api/image-sets` 并保留用户已有标注状态。
- 打开选择页后，不要让用户在聊天里回复“选 set1 / 选 set2 / 选第 N 套”来触发入库。选择页的标注结果才是入库依据：优先读取 `image-selection-result.json`；如果页面无法保存，再让用户粘贴页面复制出的同结构 JSON。只有 JSON 里的 `accepted_schemes` 能写飞书。
- 用户确认采纳后才写 `image_groups`；上传 `图1/图2/图3` 前默认按版位 `target_size` 导出并压缩，版位有明确 KB 上限时按该上限压缩，否则默认 200KB；同时按上游关系更新 copies / directions 状态。
- 读取 `image-selection-result.json` 后，先调用 `scripts/package_accepted_images.py` 把所有 `accepted_schemes` 打成一个本地 zip。zip 只包含采纳图，默认放按目标尺寸导出的压缩 JPG，并带 `manifest.json`；`rejected_schemes` 和 pending 不进 zip。
- 原始 PNG 不长期堆积：`write_image_group.py` 成功写入 Base 后会 best-effort 调用 `scripts/cleanup_image_outputs.py` 清理 `/tmp/onion-ad` 下超过 7 天的原始 PNG。压缩 JPG、zip、HTML、JSON 默认保留，便于复盘和交付。

## 按需 Reference

- 渠道/版位/尺寸怎么选：`references/渠道与版位.md` 路由索引，结构化事实源是 `config/channel-placement-rules.json`，说明见 `references/版位比例与尺寸.md`。
- 压缩、导出和多版位适配：`references/压缩与导出.md`。
- 渠道化 prompt 风格和复盘：`references/渠道风格与复盘.md`。
- IP、Logo、字体、风格资产：`references/视觉元素规范.md`。
- 资产命名、manifest、参考图标签和 `render.py` 输入对象：`references/资产命名与参考图标注.md`。
- 合规和视觉雷区：`references/合规视觉雷区.md`。
- 涉及产品边界或品牌说法时读 `../../shared/references/advertiser-subject.md`。
- 需要判断哪些业务知识可加载时读 `../../shared/references/business-knowledge.md`。
- 用户给 D-XXX / C-XXX / record_id 或要求断点续跑时读 `../../shared/references/record-lookup.md`。
- prompt 总索引：`references/prompt写法.md`。
- 11-50 套批量变体或基于已有图扩多套时读 `../../shared/recipes/batch-prompting.md`。
- 单图读 `../../shared/recipes/single-prompt.md`。
- 双/三图读 `../../shared/recipes/base-prompt.md` 和 `../../shared/recipes/branch-prompt.md`。
- render 接口和链式调度读 `../../shared/recipes/render-chain.md`。
- 写 Base 前读 `../../shared/base_schema.md` 的 image_groups / copies / directions。

## 工具调用

用户给 C-XXX 但上下文没有文案内容时，先用 `../../shared/scripts/lookup_record.py --id C-XXX --follow-upstream` 回查。用户给 D-XXX 想直接出图时，先回查方向并补齐文案层，不要凭方向字段直接造图中文字。用户只给临时文案或上传图片时，不需要回查上游。

生图使用 `scripts/render.py`。输入是完整 prompt、版位绑定的 `render_size`、输出 PNG 路径和参考图路径；先确认 API key 可用，再 validate-only，确认无误后再付费调用。

文案锚点明确后，实际生图前一律使用 `scripts/interactive_server.py`：

```bash
python3 skills/onion-image/scripts/interactive_server.py \
  --request-id <request_id> \
  --output-dir /tmp/onion-ad/<request_id>
```

脚本会输出 `url` 和 `result_path`。把 `url` 给用户打开，用户点击“保存配置”后读取 `<output-dir>/image-config-result.json`。这个 JSON 的 `placements[]` 是后续 prompt、`render.py --size`、导出 `target_size`、压缩 `target_kb`、参考图路径和 Base metadata 的唯一配置来源；不要再用聊天里的旧默认值覆盖它。聊天里已经给出的配置只能写入 `--context` 供页面展示/预填，最终仍以用户保存的 JSON 为准。若用户不能打开网页，再退回到文字选项，但仍按同一字段结构整理配置。

批量任务中，prompt authoring 和 render 分开：先按 `batch-prompting.md` 生成一批完整 prompt，再按 `render-chain.md` 并发渲染该批。若同一文案选了多个版位，每个版位都要有自己的 prompt 和 `render_size`，不能把一个 prompt 机械套到所有尺寸。渲染可以并发，prompt 质量不能批量省略。

选择页继续使用 `templates/image-selection.html`，调用 `scripts/build_selection_page.py` 写入初始 `SETS_DATA`，并在同目录写 `image-sets.json`。每套至少带本地图片路径、套数序号、渠道、版位、目标尺寸、gpt 出图尺寸、Logo、IP、CTA、参考图摘要和 prompt 摘要；用户选择结果决定哪些方案写入 Base。

若页面通过 `interactive_server.py` 打开：

- 继续生成新图片时，POST `/api/image-sets` 追加或更新 schemes；页面自动轮询刷新，不需要用户重新打开。
- 用户提交标注会保存 `<output-dir>/image-selection-result.json`。给用户的下一步话术应是“请在页面完成标注并点击提交；提交后告诉我已提交”，而不是让用户口头选择 set。
- `image-selection-result.json` 里的 `accepted_schemes` 是唯一允许写入飞书 `image_groups` 的图组清单；`rejected_schemes` 和 `pending_scheme_ids` 只能用于反馈和复盘，不能上传。

若只是 `file://` 打开，则退回复制 JSON，仍按同一结构处理。

若本次已经启动 `interactive_server.py`，选择页也放在同一个 `--output-dir`，直接给 `http://127.0.0.1:<port>/image-selection.html`。若没有启动本地服务，HTML 和图片在同一输出目录时可以给 `file://`；若当前运行时打不开本地 HTML 或图片不显示，再启动本地服务或 `python3 -m http.server`。

用户确认采纳后，用 `../../shared/scripts/write_image_group.py` 写 image_groups 并上传图1/图2/图3附件。若本次有可信的 directions/copies record_id，分别传 `--direction-id` / `--copy-id`；临时文案或用户上传图没有上游时可以不传。脚本默认调用 `image_compress.py` 生成压缩 JPG；如果版位规则给了 `target_size` 和 `<150KB`、`<100KB` 等明确上限，在 images 里传 `target_width` / `target_height` / `target_kb`，或传 `--target-kb` / metadata 的 `目标KB`。成功后只更新实际关联到的 copies 和 directions 的 `状态=已用`。

写入 Base 前先打包采纳图：

```bash
python3 skills/onion-image/scripts/package_accepted_images.py \
  --selection-result /tmp/onion-ad/<request_id>/image-selection-result.json \
  --target-kb <版位KB或200>
```

脚本输出的 zip 是给运营本地留档/交付的“通过图片包”。不要把未采纳或 pending 图片放进去。

原图清理默认自动发生在 `write_image_group.py` 成功写 Base 后。需要手动检查时可运行：

```bash
python3 skills/onion-image/scripts/cleanup_image_outputs.py --root /tmp/onion-ad --dry-run
```

不要传 `图组ID`、创建时间、创建人、最后更新时间；飞书会按当前 `--as user` 账号自动记录这套图是谁入库、什么时候入库。
