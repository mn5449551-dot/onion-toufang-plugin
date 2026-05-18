# 记录 ID 回查与非线性入口

这个 plugin 不是线性工作流。用户可以从任意入口开始：直接出方向、基于方向出文案、基于文案出图、基于旧图组迭代，也可以拿一个 ID 来扩写、编辑或继续生产。

## 入口识别

| 用户给的对象 | 表 | 典型后续 |
|---|---|---|
| `D-XXX` | `directions` | 出文案、扩方向、改方向、基于方向直接出图前先补文案 |
| `C-XXX` | `copies` | 出图、扩文案、改文案、换渠道/图片形式 |
| `G-XXX` | `image_groups` | 扩同类、微调、换形式、复盘旧图 |
| `rec...` | 需要用户或上下文说明表 | 直接按 record_id 读取 |

如果 ID 对应记录不在上下文里，先回查 Base，不要让用户重复粘贴。回查失败时再请用户粘贴内容或确认权限。

如果用户没有给 ID，只是粘贴了一段文案、方向样本或上传了一张图片，并要求类似、扩写、换文案、换角色，就以当前输入为锚点；不要为了补全方向 → 文案 → 图组链路而追问或回查上游。

## 统一工具

使用共享脚本，不在各个 Skill 里手拼 `lark-cli`：

```bash
python shared/scripts/lookup_record.py --id D-007
python shared/scripts/lookup_record.py --id C-002 --follow-upstream
python shared/scripts/lookup_record.py --id G-005 --include-attachments --follow-upstream
python shared/scripts/lookup_record.py --table copies --id recABC123
```

脚本会：

- 根据 `D/C/G/F` 前缀推断表。
- 用当前用户身份 `--as user` 读取 Base，保留真实权限语义。
- 把 `D-XXX / C-XXX / G-XXX` 转成后续写 link 字段需要的 `record_id`。
- 默认只读任务需要的字段，避免把附件和长字段全部塞进上下文。
- `--follow-upstream` 会把 copy 关联的 direction、image group 关联的 copy / direction 一并带回。
- image group 只有 `关联文案` 但没有直接写 `关联方向` 时，`--follow-upstream` 会继续从 copy 里追 direction。
- `--include-attachments` 只在旧图迭代、下载附件或需要拿 Base 图作为参考图时使用。

## 继承与反问

- 从可信 Base 记录读到的字段不要再问用户确认，例如 `C-XXX` 里已有渠道和图片形式时，`onion-image` 直接继承。
- 只有缺少阻塞信息时才问。例如 `D-007 出信息流文案` 缺图片形式，可以只问单图/双图/三图；不要再问方向内容。
- 用户明确说“扩 / 类似 / 再来 / 换说法”时，默认先展示结果，不自动写 Base。
- 用户明确说“改掉 / 更新 / 这条不要 / 标废弃”时，这是编辑或状态更新意图，写入前需要确认具体目标和改法。

## 状态和血缘

- 基于 `D-XXX` 写文案：文案入库成功后，把方向状态改为 `已用`。
- 基于 `C-XXX` 写图：图组入库成功后，把文案状态改为 `已用`；如果文案有关联方向，也把方向状态改为 `已用`。
- 基于 `G-XXX` 迭代：新图组默认写 `父图组` 为原图组 record_id，除非用户明确不要血缘。
- 扩写或编辑过程不写 Base；只有用户确认“就这样 / 存进去 / 更新它 / 标废弃”后才执行写入或状态更新。

## 常见断点续跑

| 用户说法 | 推荐处理 |
|---|---|
| “用 D-007 出三套信息流文案” | 回查 directions，继承方向字段，只问缺失的图片形式 |
| “C-012 直接出应用商店三图” | 回查 copies，继承文案字段；若用户指定形式覆盖记录形式，先说明是换形式 |
| “G-008 这套量好，再扩 5 套” | 回查 image_groups + 附件，按扩同类处理，写父图组 |
| “这个标题再来 5 个” | 走 `onion-copy` 扩文案；若无 C-ID，只基于用户粘贴内容生成 |
| “这个方向再扩一些” | 走 `onion-direction` 扩方向；若给 D-ID 先回查原方向 |
| “把 G-003 的 CTA 改一下” | 走 `onion-image-iterate` 微调；只改 CTA 轴，不主动换 IP/场景 |
| “用这张图换成上官，再把文案改成这句” | 当前图片作为视觉锚点，不要求 G-ID；只在用户确认入库时写图组 |
