---
name: onion-image
description: Use when 用户要基于已确认文案、文案 ID、刚生成的第 N 条文案或临时文案内容生成洋葱学园投放广告图、营销图、信息流单图、应用商店双/三图、学习机图片，或指定 IP/Logo/版位/风格参考图调用 gpt-image-2 生图；触发词包括出图、生图、做图、给我几套图、用这个文案出图、选择第二条出图。
---

# onion-image

## 任务目标

把已确认的文案转成可投放图片。这个 skill 会调用付费图片 API，因此每次进入实际生图前都必须先打开图片配置页，让用户确认版位、套数、Logo、IP、CTA 和参考图策略，再生成 prompt、validate、渲染。

成功结果是一组可供用户选择的图片方案，并能在用户确认后写入 `image_groups` 表，供后续投放和迭代追踪。

每次继续生图流程前，先用 `scripts/image_workflow.py status --request-id <request_id> --output-dir <output_dir>` 判断当前阶段。不要只凭聊天记忆决定下一步；以脚本返回的 `stage` 为准。

## 输入契约

进入新图流程前，先按 `../../shared/references/input-envelope.md` 整理 Input Envelope。本 skill 必须高度结构化：文案锚点、`business.channel`、`business.image_form`、`visual`、`workflow`、配置页结果、选择页结果和写 Base 准入都必须落到字段里。风格建议、画面补充、审美描述可以留在 `raw_materials`，但不能替代结构化视觉配置。

首启环境门禁：启动配置页、检查 API key、render、压缩、打包或写 Base 前，先确认 `~/.onion-ad/usage-state.json` 和 `~/.onion-ad/setup-status.json` 存在且没有明显阻塞；缺本地使用记录时先转 `onion-help` 运行 `setup_wizard.py ensure`，缺失或过期时先环境检查。纯解释流程可以继续，但付费生图和外部写入不能跳过环境检查。

## 入口门禁

本 skill 只处理“基于已确认文案生成全新图片”。D-XXX / 方向 ID 不是生图锚点，必须先转 `onion-copy` 形成或确认文案；G-XXX、旧广告图、同款再来、扩同类、换角色、换文案、换 CTA 属于 `onion-image-iterate`；环境检查和 API key 问题转 `onion-help`。

越界时不要启动配置页、不要写 prompt、不要调用 render。只整理当前可用锚点和缺失项，交给目标 skill 继续。

必填输入：

- `文案`：C-XXX / copies record_id / 用户粘贴的主副标题或短句。
- `图片形式`：单图 / 双图 / 三图；从 copies 记录继承时不再问。
- `渠道/版位`：用户可以为同一文案一次选择多个渠道和多个版位；从 copies 记录继承时仍可追加或覆盖。
- `视觉配置`：版位、Logo、IP、CTA、界面/功能参考图、风格参考、套数；这些字段必须来自本轮图片配置页保存的 `image-config-result.json`。界面/功能截图不是独立入口，只是屏幕内容风险的补充材料。

下游写 Base 前，Envelope 必须包含 `request_id`、`workflow.state=ready_to_write_base`、`selection_result_path`、`accepted_schemes`、本地 zip 路径和 `write_result_path`。缺任一项都不能把图片上传到飞书。

默认和推断：

- 文案记录有渠道和图片形式时直接继承；用户给 C-XXX 但上下文没有内容时先回查 Base。
- 方向 ID 不是生图锚点。用户只给 D-XXX / 方向 ID 时，不进入本 skill 的生图流程；转 `onion-copy` 基于该方向生成或确认文案，不要启动配置页、不要直接用方向字段做图中文字。
- 用户给当前对话里的临时文案，可以把这段文案作为本次锚点，不强制追溯方向或文案血缘。
- 用户给 G-XXX、用户上传旧图，或要求基于旧图扩同类、换文案、换角色、换 CTA、换比例时，转 `onion-image-iterate`；这不是探索生图入口。
- 上传图如果只是 APP 截图、风格参考图或 IP 参考图，它是本次新图的参考素材，仍走 `onion-image`，不因为“上传了图”就转迭代。只有用户把上传图当作旧广告图锚点，要求照这张改、扩同类、换角色、换文案、同款再来时，才转 `onion-image-iterate`。
- 不要靠是否有文案判断上传图角色，也不要靠图片像不像洋葱判断。用户上传作业帮等竞品/外部参考图时，除非明确说这是自有旧素材，否则只能当 `competitor_reference` / `layout_reference` / `style_reference` 使用，不写 `父图组`，prompt 只抽象参考构图、信息层级、节奏或色彩，不复刻竞品品牌、UI、人物或文案。
- 上传图角色、图片用途、是否属于自有旧广告图有一点不清楚就追问；正确优先于少问。
- 未指定 Logo、CTA 或 IP 时，不要替用户静默决定；在图片配置页一次性确认。文本主导方案可以把“不用 IP”作为建议选项，但仍要让用户在配置页确认。
- 界面/功能截图只有在最终画面需要出现手机、平板、电脑、学习机、投影屏、电子屏幕，且屏幕上展示可识别的洋葱 APP/学习界面屏幕内容时才触发。若画面不展示具体 UI，或屏幕只是弱化/模糊背景，不要要求用户上传截图。
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

流程状态由 `scripts/image_workflow.py` 兜底：

| stage | 允许的下一步 |
|---|---|
| `needs_config` | 启动 `interactive_server.py`，打开 `/image-config` |
| `needs_ui_reference_upload` | 提醒用户回到 Codex 上传截图，或确认改成弱化/模糊屏幕 |
| `needs_api_key` | 先跑 `onion-help` 或补 `LAOZHANG_API_KEY`，不能 render |
| `invalid_config` / `invalid_artifacts` | 停止续跑，重新保存配置或确认 request_id/output_dir |
| `ready_to_render` | 写 prompt，先 `render.py --validate-only`，再正式渲染并 POST `/api/image-sets` |
| `needs_selection` | 构建/打开 `image-selection.html`，让用户在页面标注提交 |
| `invalid_selection_feedback` | 选择页里有不完整的不采纳反馈，回页面补齐或选择跳过 |
| `needs_feedback_write` | 调 `write_selection_feedback.py` 写入 rejected_schemes 中的固定规则 / 主观感受 |
| `needs_package` | 调 `package_accepted_images.py` 打包采纳图 |
| `ready_to_write_base` | 调 `write_image_group.py` 写 Base 并上传压缩附件 |

如果脚本返回的 `can_render=false`，不能写 prompt 后直接付费渲染；如果 `can_write_base=false`，不能上传飞书附件。

非线性入口要承认：用户可能直接拿 C-XXX 生图，或拿一段临时文案生图；只要文案锚点明确，不要求先走方向和文案全流程，但仍必须经过图片配置页。方向 ID 不能直接跳到图，必须先形成可用文案。

选择续跑要更谨慎：用户说“选择第 N 条文案 / 第二条 / 就用这个出图”只代表文案被选中，不代表视觉配置完整。若渠道、图片形式、版位、Logo、CTA、IP、参考图任一项缺失，先问配置，不要直接默认信息流竖版、默认 Logo、默认无 IP 或默认无 CTA。

已有图不是本 skill 的生图锚点。用户上传旧图、给 G-XXX、或说扩同类、换文案、换角色、同款再来时，停止 `onion-image` 的探索生图流程，转 `onion-image-iterate` 处理血缘、力度和改动轴。

上传图先判断角色：参考素材留在当前 `onion-image`，旧广告图锚点才转 `onion-image-iterate`。如果用户只上传图片但没说明用途，先问“这张图是作为旧图来改，还是作为 APP 截图/风格/IP 参考图？”不要默认分流。

竞品/外部参考图不等于旧图锚点。用户说“参考这个作业帮版式给洋葱做一张”时仍是新图参考素材；用户说“把这张作业帮图改成洋葱”时也不要当父图组迭代，应抽象成 layout_reference 重新创作，并避开竞品品牌、UI、人物和原文案。

多套新图要有创意差异：场景细节、构图、切入角度、视觉节奏至少错开；但同一套内的双/三图要保持统一世界观。

批量变体默认由当前 Agent 分批生成 prompt。1-10 套可一次写完；11-50 套按 5-10 套一批推进，每批继承前面已用的 IP、场景、镜头、排版和视觉隐喻 ledger，保证跨批不重复。外部 planner API 只作为可选 idea pool，不作为默认最终 prompt 生产方式。

屏幕内容闸门：界面截图不是独立入口。Agent 在写 prompt 前要判断最终画面是否会出现可识别的洋葱 APP/学习界面屏幕内容，例如拍题结果页、解析页、继续追问、步骤讲解、学习报告等。如果会出现，配置 JSON 必须有 `screen_ui_reference_required=true` 和兼容字段 `ui_reference_required=true`，并且必须先拿到用户在 Codex 对话上传的真实截图；没有截图时，只能改成弱化/模糊屏幕内容，或暂停等待用户上传。

## 反问原则

只问阻塞项：

- 缺文案时，问用户选文案或直接粘文案。
- 缺图片形式且不能从文案记录继承时，问单图 / 双图 / 三图。
- 缺版位时，先问目标版位；可多选，且选项必须展示目标尺寸、gpt 出图尺寸、KB 上限和是否一期可用，不要让用户单独选比例。
- 缺付费生图所需资产选择时，只问缺失的视觉配置：Logo 要不要、CTA 写什么或不用、IP 用谁/随机/不用、是否使用用户上传图/风格参考图。界面/功能截图只在画面有可识别电子屏幕且要展示洋葱 APP 功能界面时追问；否则不要把截图当常规缺口。IP 选项必须来自 `assets/asset-manifest.json` 的本地真实资产，不要只硬编码 6 个标准名；有全身照、学段、Q3 等变体时要列出可选变体。

有交互 UI 时一次性收集缺口；没有 UI 时用一句话列出关键缺口。对 `onion-image` 来说，本地 `/image-config` 配置页就是默认交互 UI。具体运行时适配见 `../../shared/references/runtime-adapters.md`。

Codex / Claude Code 没有稳定原生选择卡时，必须使用本 skill 的本地交互页：启动 `scripts/interactive_server.py`，让用户在 `/image-config` 页面完成图片配置；保存后读取同目录的 `image-config-result.json`，再进入 prompt 和付费渲染。

配置页模板在 `templates/image-config.html`。`interactive_server.py` 只负责注入 request_id / 配置数据、提供 API 和写结果 JSON；不要把大段配置页 HTML/CSS/JS 重新写回 Python。

配置页交互规则：

- 版位先选大类：应用商店 / 学习机 / 信息流 / 百度；再在该大类下选具体版位。已选版位跨大类保留，允许同一文案一次生成多个渠道/版位。
- 版位卡片必须展示 `target_size`、`render_size`、目标 KB、直出能力和不可选原因。双图/三图是可生成的图片形式；只有本次文案/用户意图已确定为单图时，双图/三图版位才临时置灰（反之亦然）。如果文案已经是主标题/副标题结构，只能选单图版位；如果是短句1+短句2，只能选双图版位；如果是短句1+短句2+短句3，只能选三图版位。
- 如果上游文案或用户要求已经明确渠道，配置页必须临时锁定对应大类：信息流单图只能选信息流单图版位，应用商店单图/双图/三图只能选应用商店对应形式版位，学习机素材只能选学习机对应版位。其他渠道/形式卡片置灰并展示原因，后端保存时也必须拒绝绕过禁用规则的提交。
- 套数是手动数字输入，范围 1-50；超过 10 套仍按批次推进 prompt 和渲染。
- Logo 和 IP 必须显示本地资产缩略图，数据来自 `assets/asset-manifest.json`，不要只给纯文字下拉；IP 额外提供“随机 IP”。
- 字体参考只有启用 / 不启用。启用时由 Agent 从 `assets/font-references/` 为每张图完全随机抽取一张，不让用户选具体字体参考。
- CTA 按具体版位的 `cta_policy` 显示；任一选中版位允许 CTA 时才收 CTA。
- 界面 / 功能参考图不在 HTML 里上传；配置页只提供“画面需要展示洋葱 APP 界面/功能截图”开关。只有最终画面里出现手机、平板、电脑、学习机、投影屏、电子屏幕，并且屏幕要展示可识别的洋葱 APP/学习界面屏幕内容时才勾选。用户选择后，配置 JSON 必须写 `screen_ui_reference_required=true`、兼容字段 `ui_reference_required=true`、`ui_reference_upload_status=awaiting_codex_upload`。
- 如果 `screen_ui_reference_required=true` / `ui_reference_required=true`，读取配置后必须提醒用户回到 Codex 对话上传截图。没有收到截图前不能进入 prompt、validate-only 或 render；截图收到后再把它作为 `reference_images` 的一项，并在 prompt 参考图说明里标清“洋葱 APP 界面/功能截图”。如果用户不上传截图，只能改成弱化/模糊屏幕内容，不能编造真实 APP 界面。
- 补充说明只用于生图建议，例如画面风格、文字多少、主体位置，不承载结构化字段。
- 配置页默认是“探索生成”模式；“同类扩展 / 基于已有图继续扩”使用同一页面的 `generation_mode=iterate` 继承型配置，不允许绕过配置页。

## 硬约束

- 不允许绕过配置页直接生图；不允许调用聊天内置 imagegen 或其它通用图片工具来替代本 skill 的 `render.py` 链路。没有本轮有效的 `image-config-result.json` 时，下一步只能是打开配置页或让用户补文案锚点。
- 继续任何已有 request_id 前必须先运行 `scripts/image_workflow.py status --request-id <request_id> --output-dir <output_dir>`；不得凭聊天记忆跳过配置页、截图闸门、选择页、打包或 Base 写入前检查。
- 如果 `image-config-result.json` 里 `screen_ui_reference_required=true` 或 `ui_reference_required=true`，但当前对话没有用户上传的界面/功能截图，下一步只能提醒用户上传截图或征得用户同意改成弱化/模糊屏幕内容；不能进入 prompt、validate-only 或 render。
- 如果 prompt 方案里会出现可识别的洋葱 APP/学习界面屏幕内容，即使用户没有在配置页勾选，也必须先补问是否上传真实截图；不上传时，prompt 必须明确“屏幕内容弱化/模糊，不展示具体 UI”。不要在无截图时编造拍题结果页、解析页、继续追问页或学习报告。
- 付费调用前必须先确认 `LAOZHANG_API_KEY` 存在且不是占位符，再用 `render.py --validate-only` 检查 prompt、`render_size`、输出路径和参考图路径。缺 key 时直接提示用户先跑 `onion-help` 环境检查或补 `~/.onion-ad/.env`，不要等到渲染阶段才失败。
- 只渲染配置里 `enabled=true` 的版位。`directness=expand/composite` 或与本次图片形式不匹配而被配置页临时置灰的版位，不能绕过配置页直接生成。
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
- 打开选择页后，不要让用户在聊天里回复“选 set1 / 选 set2 / 选第 N 套”来触发入库。选择页的标注结果才是入库依据：用户在页面提交后告诉我已提交，Agent 优先读取 `image-selection-result.json`，不要让用户粘贴 JSON。只有 JSON 里的 `accepted_schemes` 能写飞书。
- 标注页提交后，`rejected_schemes` 里用户写明的固定规则 / 主观感受必须先通过 `scripts/write_selection_feedback.py` 写入 `feedbacks` 表；选择“跳过反馈”可以不写。反馈写入是复盘沉淀，不允许把 rejected 或 pending 图组上传到 `image_groups`。
- 用户确认采纳后才写 `image_groups`；上传 `图1/图2/图3` 前默认按版位 `target_size` 导出并压缩，版位有明确 KB 上限时按该上限压缩，否则默认 200KB；同时按上游关系更新 copies / directions 状态。
- 读取 `image-selection-result.json` 后，先调用 `scripts/package_accepted_images.py` 把所有 `accepted_schemes` 打成一个本地 zip。zip 里只包含采纳图片，不放 `manifest.json` 或其它机器文件；追溯 manifest 写在 zip 同目录的 `<zip-stem>-manifest.json`。`rejected_schemes` 和 pending 不进 zip。
- 原始 PNG 不长期堆积：`write_image_group.py` 成功写入 Base 后会 best-effort 调用 `scripts/cleanup_image_outputs.py` 清理输出根目录下超过 7 天的原始 PNG。输出根目录由 `ONION_AD_OUTPUT_ROOT` 或系统临时目录决定；压缩 JPG、zip、HTML、JSON 默认保留，便于复盘和交付。

## 按需 Reference

- 统一输入信封、视觉配置字段和写入交接：`../../shared/references/input-envelope.md`。
- 执行深度和追问边界：`../../shared/references/execution-policy.md`。
- 渠道/版位/尺寸怎么选：`references/渠道与版位.md` 路由索引，结构化事实源是 `config/channel-placement-rules.json`，说明见 `references/版位比例与尺寸.md`。
- 压缩、导出和多版位适配：`references/压缩与导出.md`。
- 渠道化 prompt 风格和复盘：`references/渠道风格与复盘.md`。
- IP、Logo、字体、风格资产：`references/视觉元素规范.md`。
- 资产命名、manifest、参考图标签和 `render.py` 输入对象：`references/资产命名与参考图标注.md`。
- 合规和视觉雷区：`references/合规视觉雷区.md`。
- 涉及产品边界或品牌说法时读 `../../shared/references/advertiser-subject.md`。
- 需要判断哪些业务知识可加载时读 `../../shared/references/business-knowledge.md`。
- 用户给 C-XXX / copies record_id 或要求断点续跑时读 `../../shared/references/record-lookup.md`。
- prompt 总索引：`references/prompt写法.md`。
- 11-50 套批量文案变体生图时读 `../../shared/recipes/batch-prompting.md`。
- 单图读 `../../shared/recipes/single-prompt.md`。
- 双/三图读 `../../shared/recipes/base-prompt.md` 和 `../../shared/recipes/branch-prompt.md`。
- render 接口和链式调度读 `../../shared/recipes/render-chain.md`。
- 写 Base 前读 `../../shared/base_schema.md` 的 image_groups / copies / directions。

## 工具调用

用户给 C-XXX 但上下文没有文案内容时，先用 `../../shared/scripts/lookup_record.py --id C-XXX --follow-upstream` 回查。用户只给 D-XXX / 方向 ID 时，不查方向直接硬生图，也不启动 `/image-config`；明确转 `onion-copy` 先基于方向生成或确认文案。用户给 G-XXX、上传旧图或要求扩图/换图时，转 `onion-image-iterate`。用户上传 APP 截图、风格图或 IP 参考图时，把它作为 `reference_images` 参考素材留在 `onion-image`。用户只给临时文案时，不需要回查上游。

生图使用 `scripts/render.py`。输入是完整 prompt、版位绑定的 `render_size`、输出 PNG 路径和参考图路径；先确认 API key 可用，再 validate-only，确认无误后再付费调用。

文案锚点明确后，实际生图前一律使用 `scripts/interactive_server.py`：

```bash
python3 skills/onion-image/scripts/interactive_server.py \
  --request-id <request_id>
```

脚本会按当前系统自动选择输出根目录（Mac/Linux 常见 `/tmp/onion-ad`，Windows 常见 `%TEMP%\onion-ad`，也可用 `ONION_AD_OUTPUT_ROOT` 覆盖），并输出 `url` 和 `result_path`。把 `url` 给用户打开，用户点击“保存配置”后读取 `<output-dir>/image-config-result.json`。这个 JSON 的 `placements[]` 是后续 prompt、`render.py --size`、导出 `target_size`、压缩 `target_kb`、参考图路径和 Base metadata 的唯一配置来源；不要再用聊天里的旧默认值覆盖它。聊天里已经给出的配置只能写入 `--context` 供页面展示/预填，最终仍以用户保存的 JSON 为准。若用户不能打开网页，再退回到文字选项，但仍按同一字段结构整理配置。

已有 request_id 续跑或用户说“继续 / 已提交 / 入库 / 重新生成一批”时，先检查状态：

```bash
python3 skills/onion-image/scripts/image_workflow.py status \
  --request-id <request_id>
```

脚本返回 `needs_config` 就只开配置页；返回 `needs_selection` 就只开选择页；返回 `needs_package` 就先打包；返回 `ready_to_write_base` 才允许写 Base。
脚本返回 `needs_feedback_write` 时，先写选择页里的 rejected 反馈，再重新检查状态；不要为了快而跳过反馈沉淀。

批量任务中，prompt authoring 和 render 分开：先按 `batch-prompting.md` 生成一批完整 prompt，再按 `render-chain.md` 并发渲染该批。若同一文案选了多个版位，每个版位都要有自己的 prompt 和 `render_size`，不能把一个 prompt 机械套到所有尺寸。渲染可以并发，prompt 质量不能批量省略。

选择页继续使用 `templates/image-selection.html`，调用 `scripts/build_selection_page.py` 写入初始 `SETS_DATA`，并在同目录写 `image-sets.json`。每套至少带本地图片路径、套数序号、渠道、版位、目标尺寸、gpt 出图尺寸、Logo、IP、CTA、参考图摘要和 prompt 摘要；用户选择结果决定哪些方案写入 Base。

若页面通过 `interactive_server.py` 打开：

- 继续生成新图片时，POST `/api/image-sets` 追加或更新 schemes；页面自动轮询刷新，不需要用户重新打开。
- 用户提交标注会保存 `<output-dir>/image-selection-result.json`。给用户的下一步话术应是“请在页面完成标注并点击提交；提交后告诉我已提交”，而不是让用户口头选择 set。
- `image-selection-result.json` 里的 `accepted_schemes` 是唯一允许写入飞书 `image_groups` 的图组清单；`rejected_schemes` 和 `pending_scheme_ids` 只能用于反馈和复盘，不能上传。
- `rejected_schemes[].annotation.ruleFeedback` 写入 `feedbacks.反馈类型=固定规则`；`rejected_schemes[].annotation.note` 写入 `feedbacks.反馈类型=主观评价`（页面上叫“主观感受”）。被反馈对象 ID 优先用已有 G-ID；新生成但未采纳的方案用 `<request_id>:<set_id>` 临时锚点，便于后续统一拉取分析。

正常流程必须让页面保存 `image-selection-result.json`，不要让用户复制 JSON。若 `file://` 无法保存，启动 `interactive_server.py` 或临时本地服务后重试保存。

若本次已经启动 `interactive_server.py`，选择页也放在同一个 `--output-dir`，直接给 `http://127.0.0.1:<port>/image-selection.html`。若没有启动本地服务，HTML 和图片在同一输出目录时可以给 `file://`；若当前运行时打不开本地 HTML 或图片不显示，再启动本地服务或 `python3 -m http.server`。

用户确认采纳后，用 `../../shared/scripts/write_image_group.py` 写 image_groups 并上传图1/图2/图3附件。若本次有可信的 directions/copies record_id，分别传 `--direction-id` / `--copy-id`；临时文案或用户上传图没有上游时可以不传。脚本默认调用 `image_compress.py` 生成压缩 JPG；如果版位规则给了 `target_size` 和 `<150KB`、`<100KB` 等明确上限，在 images 里传 `target_width` / `target_height` / `target_kb`，或传 `--target-kb` / metadata 的 `目标KB`。成功后只更新实际关联到的 copies 和 directions 的 `状态=已用`。

写 Base 时必须传 `--write-result <output-dir>/image-write-result.json`，或确保图片路径能让脚本自动把完成标记写到同一输出目录。完成标记存在后，`image_workflow.py status` 会返回 `complete`，避免同一 request 重复写入 image_groups。

写入 Base 前先打包采纳图：

```bash
python3 skills/onion-image/scripts/write_selection_feedback.py \
  --selection-result <output-dir>/image-selection-result.json
```

这个脚本只处理未采纳方案里的明确反馈：固定规则和主观感受会写入 `feedbacks`，选择“跳过反馈”不写，避免污染反馈池。它会在同目录写 `image-feedback-result.json`，让 `image_workflow.py status` 知道反馈已处理。

```bash
python3 skills/onion-image/scripts/package_accepted_images.py \
  --selection-result <output-dir>/image-selection-result.json \
  --target-kb <版位KB或200>
```

脚本输出的 zip 是给运营本地留档/交付的“通过图片包”。zip 里只能放图片文件，不放 manifest、HTML、JSON 或未采纳方案。包内目录和文件名由脚本统一生成，例如 `set01_set1/set01_img01_1280x720_150kb.jpg`。

调用 `write_image_group.py` 时把该路径作为 `--package-zip <zip_path>` 传入。写入成功后的最终回复必须包含：飞书图组记录 ID / G-ID（如果脚本返回）、本地图片包路径、外部 manifest 路径、`image-write-result.json` 路径。`image-write-result.json` 里也必须保留 `package_zip`，方便断点续跑和复盘。

最终回复里的本地图片包路径必须给可点击 Markdown 本地文件链接，而不是只贴纯文本路径。用脚本返回的实际绝对路径生成链接，例如 `[打开本地交付包](<actual-zip-path>)`；同时给 `[打开交付目录](<actual-output-dir>/)`，方便用户直接在本机查看 zip、manifest、选择页和写入结果。如果路径含空格，链接目标用尖括号包住。

原图清理默认自动发生在 `write_image_group.py` 成功写 Base 后。需要手动检查时可运行：

```bash
python3 skills/onion-image/scripts/cleanup_image_outputs.py --dry-run
```

不要传 `图组ID`、创建时间、创建人、最后更新时间；飞书会按当前 `--as user` 账号自动记录这套图是谁入库、什么时候入库。
