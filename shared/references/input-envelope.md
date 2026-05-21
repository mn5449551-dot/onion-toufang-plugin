# 统一输入信封（Input Envelope）

用户输入可以是不稳定的自然语言、ID、截图、复制粘贴内容或 HTML 页面 JSON；skill 内部交接必须稳定。Input Envelope 是每个 onion skill 开始执行前整理出来的内部工作对象，不是让用户填写的表单。

## 核心原则

- 用户可以自然表达；Agent 负责把可用信息归一化。
- 凡是会影响工具调用、Base 写入、HTML 页面、生图 API 或下游 skill 的字段必须结构化。
- 只帮助创意判断的 brief、调研、案例、审美要求、参考文案可以先保留为非结构化材料，再由对应 skill 提炼。
- 缺阻塞字段才问用户；非阻塞字段由 Agent 合理推断，并在候选内容里自然体现。
- Envelope 不替代状态机。图片流程阶段仍以 `skills/onion-image/scripts/image_workflow.py status` 为准。

## 通用结构

```json
{
  "request_id": "",
  "source": "user_text|base_id|selection_json|config_page|upload|resume",
  "intent": "route|diagnose|generate_direction|generate_copy|generate_image|iterate_image|write_base",
  "target_skill": "onion-using|onion-help|onion-direction|onion-copy|onion-image|onion-image-iterate",
  "mode": "new|expand|edit|select|iterate|diagnose|resume",
  "anchors": {
    "direction_id": "",
    "direction_record_id": "",
    "copy_id": "",
    "copy_record_id": "",
    "image_group_id": "",
    "image_group_record_id": "",
    "temporary_text": "",
    "uploaded_images": [],
    "uploaded_image_role": "owned_old_ad|competitor_reference|layout_reference|style_reference|ip_reference|screen_ui_reference|unknown"
  },
  "business": {
    "feature": "",
    "stage": "",
    "stage_source": "user|time_inferred|default",
    "audience": "",
    "selling_points": [],
    "channel": "",
    "placement": "",
    "image_form": "",
    "copy": {}
  },
  "creative_brief": {
    "level": "full|lite|unknown",
    "feature": "",
    "target_user": "",
    "user_scene": "",
    "barrier_or_emotion": "",
    "product_action": "",
    "perceived_change": "",
    "anchor_source": "",
    "fact_source": "user|knowledge|base|inferred",
    "missing": []
  },
  "visual": {
    "placements": [],
    "sets": 1,
    "logo": "",
    "ip": "",
    "cta": "",
    "font_reference_enabled": true,
    "screen_ui_reference_required": false,
    "reference_images": []
  },
  "iteration": {
    "base_image_role": "",
    "iteration_mode": "tweak|expand_similar|reframe",
    "intensity": "",
    "change_axes": [],
    "keep_axes": [],
    "inherit": {
      "placement": true,
      "image_form": true,
      "logo": true,
      "ip": true,
      "cta": true,
      "style": true,
      "copy": true
    },
    "per_image_notes": {}
  },
  "workflow": {
    "state": "",
    "output_dir": "",
    "config_result_path": "",
    "selection_result_path": "",
    "accepted_schemes": [],
    "package_zip": "",
    "can_render": false,
    "can_write_base": false
  },
  "write_policy": {
    "write_base": "never|after_user_confirmed|ready",
    "versioning": "create_new",
    "status_updates": []
  },
  "raw_materials": [],
  "missing": []
}
```

字段为空不代表错误。每个 skill 只校验自己负责的切片。

## Creative Brief 边界

`creative_brief` 是 Agent 内部交接结构，不要求用户填写，也不一定写 Base。它用于在方向、文案、图片 prompt 和扩同类创意之间传递“功能 × 用户”理解；不是配置页字段，也不是机械流程门禁。

`creative_brief.level` 使用 `full|lite|unknown`：

- `full`：从方向或完整 brief 开始，功能事实、目标用户、场景、产品动作和可感知变化都比较清楚。
- `lite`：从文案、C-ID、临时文案、图片需求中途进入，只能保留锚点、目标用户、已知产品动作和缺失项。
- `unknown`：只有旧图、模糊需求或外部素材，关键功能事实缺失。

关键功能事实缺失且会影响方向、文案、图片 prompt、新卖点或换功能时，先查知识库；仍不清楚就追问。纯视觉微调、配置页保存、状态查询、压缩、打包、Base 写入等机械流程不因为 `creative_brief` 不完整而阻塞。

## 结构化与非结构化边界

必须结构化：

- `D/C/G` ID、record_id、用户选择第几条。
- 功能、卖点、适配阶段、渠道、版位、图片形式、套数。`business.stage` 仍要结构化，但不是 `onion-direction` 的用户必填项；缺阶段时由时间节点推断并写 `stage_source=time_inferred`，无法命中节点时写 `stage_source=default`。
- Logo、IP、CTA、字体参考开关、是否需要 APP 界面截图。
- 上传图角色：`owned_old_ad`、`competitor_reference`、`layout_reference`、`style_reference`、`ip_reference`、`screen_ui_reference` 或 `unknown`。只要图片角色会影响路由、父图组、prompt 参考方式或是否要追问，就必须结构化。
- request_id、output_dir、配置页结果、选择页结果、accepted_schemes、本地 `package_zip`。
- 是否允许写 Base、写入哪个表、是否创建新版、是否更新上游状态。

可以保留为非结构化原料：

- 用户 brief、调研材料、访谈纪要、真实案例、复盘意见。
- 参考文案、风格描述、画面建议、审美要求。
- “更像应用商店”“不要太信息流”“高级一点”这类创意判断。

## 每个 skill 的职责

| Skill | 负责填写/校验 | 不负责 |
|---|---|---|
| `onion-using` | `intent`、`target_skill`、`mode`、`source`、`anchors`、分诊阻塞项 | 业务生成、图片配置、Base 写入 |
| `onion-help` | `intent=diagnose`、诊断目标、检查面、阻塞/警告结果 | 方向/文案/图片生产 |
| `onion-direction` | `business.feature`、`business.selling_points`、`business.stage`、`business.stage_source`、方向原料、方向候选、方向写入策略 | 渠道版位、生图配置 |
| `onion-copy` | 方向/文案锚点、`business.channel`、`business.image_form`、文案候选、文案写入策略 | 图片视觉配置、实际生图 |
| `onion-image` | 文案锚点、`visual`、`workflow`、配置页/选择页结果、图片写入准入 | 方向直跳生图、旧图迭代 |
| `onion-image-iterate` | 图组/旧图锚点、`iteration`、继承/改动轴、图片写入准入 | 新方向和新文案主流程 |

## 交接契约

方向交给文案：

```json
{
  "source_skill": "onion-direction",
  "handoff_to": "onion-copy",
  "direction_id": "D-007",
  "direction_record_id": "rec...",
  "direction_fields": {},
  "missing": ["channel", "image_form"]
}
```

文案交给新图：

```json
{
  "source_skill": "onion-copy",
  "handoff_to": "onion-image",
  "copy_id": "C-012",
  "copy_record_id": "rec...",
  "copy_fields": {},
  "channel": "应用商店",
  "image_form": "三图",
  "missing": ["visual_config"]
}
```

图片交给 Base 写入：

```json
{
  "source_skill": "onion-image",
  "request_id": "req...",
  "workflow_state": "ready_to_write_base",
  "selection_result_path": "<output-dir>/image-selection-result.json",
  "accepted_schemes": [],
  "package_zip": "<output-dir>/accepted-images.zip",
  "write_result_path": "<output-dir>/image-write-result.json"
}
```

## 追问规则

- 路由不明才问目标 skill；能路由就交给目标 skill。
- 图片角色、选择对象、父图组、写 Base 准入、竞品/自有素材归属有一点不清楚就追问。这里正确优先于少问，不用为了减少轮次而猜。
- ID 不在上下文时先按 `record-lookup.md` 回查，不让用户重复粘贴。
- “选择第 N 条”必须先绑定到方向、文案或图片方案；上下文不足就问。
- 付费生图前缺配置页结果、API key、必要截图或选择页结果时必须停下。
- 写 Base 前必须有用户确认或选择页 `accepted_schemes`，不能用模型猜测采纳项。

## 输出要求

给用户看的候选内容可以自然排版；交给下游 skill、脚本或 Base 的内容必须按 Envelope 中对应字段稳定表达。不要把关键字段只藏在段落描述里。
