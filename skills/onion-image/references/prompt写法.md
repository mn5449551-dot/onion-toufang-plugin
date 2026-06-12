# Prompt 写法索引

本文件只做路由：按当前场景读对应文件，写法细节不在这里复述（避免和正文分叉）。

## 按场景读取

| 场景 | 读取 | 作用 |
|---|---|---|
| 单图 | `shared/recipes/single-prompt.md` | 独立生成 1 张图 |
| 双/三图的图1 | `shared/recipes/base-prompt.md` | 建立整套图的世界观和视觉资产 |
| 双/三图的图2/3 | `shared/recipes/branch-prompt.md` | 基于图1 PNG 做 delta，链式顺序也在这 |
| 11-50 套批量变体 | `shared/recipes/batch-prompting.md` | 分批精写、多样性 ledger、套级差异维度 |
| 渲染接口与链式调度 | `shared/recipes/render-chain.md` | `render.py` 参数、依赖规则、错误处理 |
| 参考图命名与标注 | `references/资产命名与参考图标注.md` | asset_id、标准路径、参考图1/2/3 对应关系 |
| IP/Logo/字体/风格资产 | `references/视觉元素规范.md` + `assets/asset-manifest.json` | 资产选择与路径事实源 |

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
