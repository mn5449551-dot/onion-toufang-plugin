# 飞书 Base Schema 速查

> 4 张表的字段映射 + field_id 缓存指引。本文件是业务 schema 事实源；运行时写入优先走 `shared/scripts/*`，不要在主 Skill 里手拼 Base 命令。
> Schema 真相源：`/Users/xhh/app_tixiao/skill_toufang/技能设计/09-Base表结构详细设计.md`

---

## ⚡ 前置 skill：`lark-base`

本 plugin 操作飞书 Base 时应先加载 / 使用 `lark-base` skill 来确认命令细节（`lark-cli base +record-batch-create` 等命令格式、字段类型映射、429 重试、写入 SOP 等）。

不要依赖模型"自动加载"其他 skill。本文件只写"本 plugin 专属"的业务信息（4 张表是什么、字段叫什么、值范围）。lark-cli 命令的语法 / 错误处理 / 限流策略 → 以 lark-base skill 的 references 和 `lark-cli ... --help` 为准。

---

## 运行时使用方式

1. Read 本文件 → 确认 4 张表的 table_id、字段名和值域。
2. 业务写入优先调用共享脚本：`write_record.py`、`write_image_group.py`、`update_status.py`、`retry_pending.py`。
3. 共享脚本会加载 `~/.onion-ad/.env`，并统一处理 user 身份、重试和 pending 兜底。
4. 只有人工排查或维护脚本需要直接使用 `lark-cli` 时，才按 `lark-base` skill 和 `lark-cli ... --help` 确认命令语法。
5. 失败响应里若提示 field_id 不存在 → 重新做 Base 结构检查；schema 可能被维护人改动。

---

## 🔧 项目级配置（.env 默认值，可由维护人统一替换）

```
Base Token: WIoGb0ksnaREvJsPtQCcW8Lsnfg
Base URL: https://guanghe.feishu.cn/base/WIoGb0ksnaREvJsPtQCcW8Lsnfg

| 表 | table_id | 主字段 | 字段数 |
|---|---|---|---|
| directions  | tblLWPSHrZT95oy7 | 素材方向（text）| 13 |
| copies      | tblFdwXSbjANQjlh | 文案ID（auto_number C-XXX）| 14 |
| image_groups| tblGpuukciptN3PP | 图组ID（auto_number G-XXX）| 25 |
| feedbacks   | tblsPpNNcNH5KXoZ | 反馈ID（auto_number F-XXX）| 11 |
```

调 lark-cli 时优先用 `~/.onion-ad/.env` 里的 `ONION_BASE_APP_TOKEN` + 对应 `ONION_BASE_*_TID`。如果 env 缺失，再用本文件里的默认值兜底。

用户给 `D-XXX` / `C-XXX` / `G-XXX` 但上下文没有记录内容时，先用 `shared/scripts/lookup_record.py` 回查 Base 并取得真实 `record_id`。不要把自动编号直接写入 link 字段。用户只给临时文案或上传图片时，不需要为了补全上游链路而回查 Base。

> ⚠️ **正式上线时切到生产 Base**：徐豪建好生产 Base 后，把本文件和 `.env.template` 里的 Base Token + 4 个 table_id 改成生产值，git commit + push。团队成员 pull 后复制新版模板，或手动同步 `~/.onion-ad/.env`。
>
> 用户通常只需要手动填写 **`LAOZHANG_API_KEY`**；Base token/TID 使用模板默认值。

---

## 表 1：`directions`（方向卡，13 字段）

| 中文字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `素材方向` | text（主字段）| ✅ | 一句话点睛，如"方向：主打识别准确——拍三遍还不对，洋葱一拍就准" |
| `方向ID` | auto_number（D-XXX）| 自动 | 不传，飞书自动生成 |
| `功能` | select 单 | ✅ | 当前常见选项：拍题精学 / 同步课 / 总复习 / 学情报告 / 学习机 / 其他；完整功能矩阵见 `shared/knowledge/卖点库.md`，新增功能需先确认 Base 选项或映射为 `其他` |
| `卖点` | select 多 | ✅ | 多选，从 `shared/knowledge/卖点库.md` 同步；字段选项未同步时先记录 pending，不静默改 schema |
| `目标人群` | text | ✅ | 30-50 字具体场景化描述（参考即可，合理超出 OK）|
| `适配阶段` | select 单 | ✅ | 日常学习 / P0-寒假 / P0-开学 / 期中前 / 期末前 / 暑期 / 其他 |
| `1 能解决用户在"具体哪个场景里的哪个问题"` | text | ✅ | 长字段名，JSON 转义引号注意 |
| `2 能带来什么不一样的"一听很惊艳"的解法？` | text | ✅ | 同上 |
| `3 因此带来了哪个场景下的什么"奇效"？` | text | ✅ | 同上 |
| `状态` | select 单 | ✅ | 待用 / 已用 / 废弃（AI 默认"待用"；被引用时改"已用"；用户手动改"废弃"）|
| `创建时间` | created_at | 自动 | **不传**，飞书原生 |
| `创建人` | created_by | 自动 | **不传**，飞书原生（读飞书 CLI 账号）|
| `最后更新时间` | updated_at | 自动 | **不传**，飞书原生 |

### directions 写入 JSON 模板

下面用真实业务案例提炼字段形态，来源参考 `功能-拍题精学.md` 方向 11。

```json
{
  "fields": [
    "素材方向",
    "功能",
    "卖点",
    "目标人群",
    "适配阶段",
    "1 能解决用户在\"具体哪个场景里的哪个问题\"",
    "2 能带来什么不一样的\"一听很惊艳\"的解法？",
    "3 因此带来了哪个场景下的什么\"奇效\"？",
    "状态"
  ],
  "rows": [
    [
      "方向：主打识别准确——拍三遍还不对，洋葱一拍就准",
      "拍题精学",
      ["识别准确", "AI+名师校准"],
      "频繁使用各种拍题 App、但反复踩坑被迫换工具的中小学生",
      "日常学习",
      "用其他 App 拍了三遍题目，总说无法识别；好不容易识别出来了，答案解析还是错的。",
      "洋葱拍题精学一拍精准识别题目，答案经过 AI + 名师教研团队校准，不是 AI 瞎编的看着像对。",
      "拍一次就对一次，不用再拍了改、改了拍，也不用拿错答案交作业被打回来。",
      "待用"
    ]
  ]
}
```

---

## 表 2：`copies`（文案，14 字段）

| 中文字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `文案ID` | auto_number（C-XXX）| 自动 | 不传 |
| `关联方向` | link → directions | ❌ 选填 | 多对一；用户手加场景或临时扩写可空。传 directions 表的 record_id 数组（如 `["recXXX"]`）|
| `渠道` | select 单 | ✅ | 信息流 / 应用商店 / 学习机 / 百度 |
| `图片形式` | select 单 | ✅ | 单图 / 双图 / 三图 |
| `文案类型` | select 单 | ❌ | 钩子 / 共情 / 数字 / 反差 / 故事 |
| `主标题` | text | ❌（单图必填）| 单图用 |
| `副标题` | text | ❌（单图必填）| 单图用 |
| `短句1` / `短句2` / `短句3` | text | ❌（双/三图必填）| 双/三图用 |
| `状态` | select 单 | ✅ | 待用 / 已用 / 废弃 |
| 通用 3 字段 | 自动 | | created_at / created_by / updated_at 不传 |

---

## 表 3：`image_groups`（图组 / 一行 = 一套图，25 字段）

| 中文字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `图组ID` | auto_number（G-XXX）| 自动 | |
| `关联方向` | link → directions | ❌ 选填 | 有可信方向 record_id 时写；临时图片/临时文案可空 |
| `关联文案` | link → copies | ❌ 选填 | 有可信文案 record_id 时写；临时图片/临时文案可空 |
| `渠道` | select 单 | ✅ | 信息流 / 应用商店 / 学习机 / 百度 |
| `图片形式` | select 单 | ✅ | 单图 / 双图 / 三图 |
| `版位` | text 或 select 单 | ❌ | 优先写精确版位名，如 `OPPO 常规-富媒体 横版大图 1280x720`；若仍是 select，维护人需同步选项 |
| `比例` | select 单 / text | ✅ | 兼容旧字段；新流程优先由 `target_size` / `render_size` 驱动，不让用户手选比例 |
| `IP形象` | select 单 | ❌ | 豆包 / 上官 / 小锤 / 雷婷 / 豆花 / 狗蛋 / 不用；别名先归一，如王小锤→小锤、田豆花→豆花、李狗蛋儿→狗蛋 |
| `IP参考图引用` | text | ❌ | manifest 标准相对路径，如 `assets/ip-roles/doubao/doubao-junior-standard-001.png` |
| `Logo` | select 单 | ❌ | 洋葱学园 / 洋葱学园+APP / 不用 |
| `Logo参考图引用` | text | ❌ | manifest 标准相对路径，如 `assets/logos/onion-logo-standard-001.png` |
| `CTA文字` | text | ❌ | 仅信息流有 |
| `风格参考图引用` | text | ❌ | 内置：本地相对路径；多个用逗号 |
| `风格参考图_用户上传` | attachment | ❌ | 用户当场上传的图，等维护人定期升级为内置 |
| `图1` | attachment | ✅ | 第 1 张图，永远填；上传前默认压缩 |
| `图1提示词` | text | ✅ | 生成 prompt（投放视图可隐藏）|
| `图2` | attachment | ❌（双/三图必填）| 上传前默认压缩 |
| `图2提示词` | text | ❌（双/三图必填）| |
| `图3` | attachment | ❌（仅三图必填）| 上传前默认压缩 |
| `图3提示词` | text | ❌（仅三图必填）| |
| `状态` | select 单 | ✅ | 待用 / 已用 / 废弃 |
| `父图组` | link → image_groups | ❌ | 扩/换图时指向被基于的原图组（追溯血缘）|
| 通用 3 字段 | 自动 | | |

### 附件字段（图1/2/3 + 风格参考图_用户上传）

走单独接口：`lark-cli base +record-upload-attachment --record-id <rid> --field-id <fid> --file <local-path>`

`图1/图2/图3` 上传的是按版位目标尺寸导出并压缩后的投放附件，不是 render.py 原始 PNG。默认压缩目标是 200KB；如果版位规则给了明确文件大小上限，以该上限作为 `target_kb`。原始 PNG 只保留在本地临时目录，不写入 Base。

---

## 表 4：`feedbacks`（反馈收集池，11 字段）

| 中文字段名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `反馈ID` | auto_number（F-XXX）| 自动 | |
| `反馈对象类型` | select 单 | ✅ | 方向 / 文案 / 图组 / Skill本身 |
| `被反馈对象ID` | text | ✅ | `D-001` / `C-101` / `G-201` / Skill 名 |
| `反馈类型` | select 单 | ✅ | 固定规则 / 主观评价 |
| `反馈内容` | text | ✅ | 用户原话 |
| `建议改法` | text | ❌ | |
| `处置状态` | select 单 | ✅ | 待审 / 已转SKILL.md规则 / 已采纳到下次迭代 / 已驳回 |
| `处置备注` | text | ❌ | 维护人审完写 |
| 通用 3 字段 | 自动 | | |

---

## 写入注意事项

| 注意点 | 说明 |
|---|---|
| `created_at / created_by / updated_at` | **绝对不传**，飞书原生维护，传了会失败 |
| `link` 字段 | 传被关联记录的 `record_id` 数组（不是名字），如 `["recABC123"]` |
| `select` 单选 | 传选项 name 字符串，如 `"信息流"` |
| `select` 多选 | 传字符串数组，如 `["拍题秒出", "分步解析"]` |
| 长字段名 | 包含双引号的字段名（如「1 能解决用户在"具体哪个场景里的哪个问题"」）调 JSON 时正确转义 |
| `attachment` 字段 | 不能在 +record-batch-create 时直接传文件，要先建 record，再用 +record-upload-attachment 单独上传 |
| 写入失败 3 次 | 整批操作写到 `~/.onion-ad/pending.jsonl`；只有用户明确要求重试，且确认不是 ambiguous 重复写入风险时，才运行 `retry_pending.py` |

## Base 初始化与共享方式

默认团队共用同一个 Base：

- Base URL: `https://guanghe.feishu.cn/base/WIoGb0ksnaREvJsPtQCcW8Lsnfg`
- Base token: `WIoGb0ksnaREvJsPtQCcW8Lsnfg`
- 4 张表必须存在且名称为 `directions / copies / image_groups / feedbacks`。
- `.env.template` 内置的是这套 Base 的 token 和 table_id；团队成员通常只需要填写 `LAOZHANG_API_KEY`，并确保自己的飞书账号是 Base 可编辑协作者。

如果维护人给的是一个空 Base，而不是上面的共享 Base：

1. 先用 `onion-help` 做 Base 结构检查。
2. 缺表或缺字段时，不要让核心 skill 自动创建；核心生产 skill 只负责业务写入。
3. 由维护人在 setup 阶段按 `shared/references/base-setup.md` 创建 4 张表和字段。
4. 创建完成后，把新的 Base token 和 4 个 table_id 写回 `.env.template`，团队成员同步到 `~/.onion-ad/.env`。

## 多人共用归因规则

这套 Base 目前靠飞书系统字段记录归因：

- `创建人`：由飞书根据 `lark-cli --as user` 的当前登录账号自动填充。
- `创建时间`：由飞书在记录创建成功时自动填充，是入库时间。
- `最后更新时间`：由飞书在记录被更新时自动填充。

因此团队成员必须各自执行 `lark-cli auth login`，并用自己的飞书账号获得 Base 编辑权限。共享脚本固定使用 user 身份写入；不要改成 bot 身份，否则 `创建人` 会变成 bot/应用身份，无法代表真实作者。

如果未来需要记录“生成时间”而不是“入库时间”，或需要在统一服务号代写时保留“发起人”，应在 Base 新增自定义可写字段，例如 `生成者`、`生成时间`、`发起运行时`，再把这些字段加入脚本 metadata。不要把飞书系统字段当作可写字段传入。
