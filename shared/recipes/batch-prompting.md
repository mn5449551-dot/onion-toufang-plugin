# Batch Prompting Strategy

Use when a user asks for many image sets from the same copy, or asks to expand from an existing image into many variants.

## Core Choice

Default to agent-authored prompts in small batches. Do not ask an external planner to directly produce 50 final prompts unless the user explicitly prefers speed over prompt quality.

| Requested sets | Prompt generation mode |
|---|---|
| 1-5 | Write all prompts in one pass |
| 6-10 | Write all prompts in one careful pass, then self-check diversity |
| 11-50 | Split into batches of 5-10 sets; finish one batch of prompts before moving to the next |
| >50 | Treat as a production batch; propose a queue/manifest workflow before rendering |

Rendering can still be concurrent. The batching rule is for prompt authoring quality, not for image API execution.

## Batch Loop

For 11-50 sets:

1. Create a `batch_manifest` with all requested set ids and planned diversity axes.
2. Generate final prompts for only the next 5-10 sets.
3. Self-check the batch against previous batches.
4. Validate prompts and asset paths.
5. Render that batch, or queue it if the user wants all prompts reviewed before paid rendering.
6. Continue with the next batch, carrying forward the used diversity ledger.

Do not produce a vague “50 concepts” list and render it directly. Each set must have concrete prompt text and reference paths before paid rendering.

## Diversity Ledger

Maintain a compact private ledger while batching:

```json
{
  "used_ips": {"豆包": 2, "上官": 1},
  "used_scenes": {"晚间书桌": 2, "教室课间": 1},
  "used_cameras": {"近景侧拍": 2, "俯拍": 1},
  "used_layouts": {"上方大标题": 2, "左右分栏": 1},
  "used_visual_metaphors": {"解析卡片浮现": 2, "步骤拆解": 1}
}
```

Use the ledger to avoid accidental sameness across batches.

## Diversity Axes

Change at least two axes between any two sets:

- IP: 豆包、上官、小锤（王小锤）、雷婷、豆花（田豆花）、狗蛋（李狗蛋/李狗蛋儿）、不用 IP.
- Scene: 晚间书桌、教室课间、周末客厅、考前复习桌、学习机屏幕前、错题订正现场.
- Camera: 近景、俯拍、侧拍、第一人称、分屏、低机位.
- Action: 拍题、点步骤、看解析、订正错题、规划复习、预习新知.
- Visual metaphor: 解析卡片浮现、等待转圈消失、步骤拆解、错题收纳、知识点亮起、得分点清单.
- Layout: 上方大标题、左右分栏、中心大字、屏幕卡片式、三段递进、标题环绕主体.

If the user locks an axis, such as `IP=豆包`, do not vary that axis. Increase diversity on scene, camera, action, metaphor, and layout instead.

## Quality Gate

Before rendering a batch, check every set:

- It still serves the same copy and does not switch to a new selling point.
- It has a concrete visual subject and scene.
- It is not a near-duplicate of earlier batches.
- On-image text is exactly the copy fields for that image index.
- IP/Logo/font/reference paths match the prompt wording.
- Strong emotion, promise words, and device/brand risks are absent.
- For double/triple sets, image 1 establishes the world and branches only change the current beat.

If fewer than 80% of a batch passes, rewrite the batch before rendering.

## Existing Image Expansion

When the user provides an existing image and asks for many variants:

- Treat the original image as the visual anchor.
- Keep brand, main subject, tone, and successful composition traits.
- Batch changes across controlled axes: IP if unlocked, scene detail, CTA, layout, ratio, camera crop, background texture.
- Do not turn expansion into a new unrelated concept unless the user asks for “换思路”.

For each batch, write prompts as deltas from the original or from the new batch base image, not as unrelated full prompts.

## External Planner Use

External planner API is optional, not default. Use it when:

- the user explicitly prefers speed;
- the requested count is large and rough diversity is enough;
- or the agent needs a first-pass idea pool before writing final prompts.

Even then, treat planner output as `creativeBrief`, not final prompt. Final prompts still need batch-level quality checks before rendering.
