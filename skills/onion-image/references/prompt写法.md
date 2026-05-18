# Prompt 写法索引

本文件只做导航和机制说明。具体 prompt 写法在 `shared/recipes/`，供 `onion-image` 和 `onion-image-iterate` 复用。

## 按图片形式读取

| 场景 | 读取 | 作用 |
|---|---|---|
| 单图 | `shared/recipes/single-prompt.md` | 独立生成 1 张图 |
| 双/三图的图1 | `shared/recipes/base-prompt.md` | 建立整套图的世界观和视觉资产 |
| 双/三图的图2/3 | `shared/recipes/branch-prompt.md` | 基于图1 PNG 做 delta |
| 11-50 套批量变体 | `shared/recipes/batch-prompting.md` | 分批精写 prompt，维护多样性 ledger |
| 渲染接口 | `shared/recipes/render-chain.md` | `render.py` 参数、链式顺序、错误处理 |
| 参考图命名与标注 | `references/资产命名与参考图标注.md` | asset_id、标准路径、参考图1/2/3 对应关系 |

## 链式机制

```
single: prompt + full references -> render.py -> PNG

double: base prompt + full references -> img1 PNG
        branch prompt + img1 PNG only -> img2 PNG

triple: base prompt + full references -> img1 PNG
        branch prompt + img1 PNG only -> img2 PNG
        branch prompt + img1 PNG only -> img3 PNG
```

关键点：

- 图1决定风格、人物、Logo、字体和整体场景。
- 图2/图3默认只看图1，不重复传 Logo/IP/风格/字体。
- 图2和图3可以在图1落盘后并发，但不能早于图1。

## 套级差异

多套图不要只是同一画面换颜色。可变化维度：

- 场景：书桌、客厅、教室、错题订正现场。
- 镜头：近景、俯视、侧拍、第一人称。
- 人物动作：拍题、思考、点步骤、看解析。
- 视觉隐喻：解析卡片浮现、步骤拆解、等待消失。
- 排版：上方大标题、左右分栏、文字嵌入屏幕。

任意两套至少 2 维不同；同一套内的多张图保持同一世界观。

## 批量 prompt 生成

1-10 套可以一次性精写。11-50 套不要一次粗糙生成全部最终 prompt；按 5-10 套一批生成，并维护跨批 ledger，记录已经用过的 IP、场景、镜头、动作、视觉隐喻和排版。

渲染可以并发，但 prompt authoring 要分批把关。每一批必须先通过合规、重复度、资产路径和文案一致性检查，再进入 `render.py`。

如果用户提供已有图片做扩展，批量 prompt 应写成从原图或本批 base 图出发的受控 delta，不要变成无关新概念。

## 决策检查表（内部）

Use this checklist privately. Only summarize issues to the user if asked why.

- Logo 配置和画面是否一致。
- CTA 为空时，画面是否真的没有按钮。
- 强情绪词是否已替换为轻情绪表达。
- 多图文字是否隔离：图1只放短句1，图2只放短句2，图3只放短句3。
- reference 顺序是否符合当前场景：single/base 用完整资产，branch 默认只用 base PNG。
- prompt 是否显式写了“参考图说明”，并逐一使用 `参考图1/参考图2/...` 对应实际传入顺序。
- 资产路径是否真实存在。
- 批量任务是否保留 diversity ledger，且本批没有和前批重复。

## 资产路径

- 资产清单：`skills/onion-image/assets/asset-manifest.json`
- IP：`skills/onion-image/assets/ip-roles/<slug>/<slug>-<stage>-<variant>-001.png`
- Logo：`skills/onion-image/assets/logos/onion-logo-standard-001.png` 或 `onion-logo-app-001.png`
- 字体：`skills/onion-image/assets/font-references/<参考名>.png`
- base PNG：`/tmp/onion-ad/<request_id>/setN_img1.png`
