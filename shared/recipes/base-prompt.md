# Base Image Prompt Recipe

Use for image 1 of double/triple image groups. The base image establishes the visual world that branch images inherit.

## Goal

Image 1 must define:

- scene layout;
- character/IP appearance;
- Logo and typography;
- color and lighting;
- the first text beat;
- enough visual context for image 2/3 to continue without restating all assets.

## Tradeoffs

| Decision | Guidance |
|---|---|
| Relationship | Choose pain->solution, action->result, old->new, or parallel proof based on the copy |
| Stability | More detail in base reduces branch drift |
| Text | Only include sentence 1 in base; leave sentence 2/3 for branches |
| Asset proof | Full references belong here, not repeatedly in branches |

## Style Choice

有 IP 时，base 图必须建立统一的高质量动漫插画 / 半写实动漫广告风格，让 IP、学生、场景、Logo、字体和道具融在同一个视觉体系。IP 保真细节写进 `参考图说明`；正文第一次出现角色时用括号绑定参考图编号，例如“豆包（参考图2）”。

无 IP 时，从视觉风格池随机选择一种，base 图负责锁定该套图的风格世界，branch 图继承这个世界观。可选方向包括毛毡手作、半写实广告插画、写实广告合成感、扁平矢量插画、赛璐珞动漫、软萌 3D 卡通、高质量家庭动画电影感、纸雕/剪纸层叠、黏土/软陶质感、水彩插画、粉笔黑板手绘、轻拟物 UI 插画等。不要写第三方品牌风格名；如果用户用品牌式风格描述，改写成通用视觉语言。

## Required Elements

- full scene description;
- exact text for image 1 only;
- IP/person appearance if used;
- Logo placement;
- CTA placement and text if configured;
- font reference for on-image Chinese text; by default choose one `assets/font-references/字体参考-XX.png` and ask the model to learn its overall typography feel while blending with the current image;
- visual style;
- intended branch direction in your private notes.

When reference images are used, describe their roles explicitly in the same order passed to `render.py`: Logo, IP, font, style, then user references. Use `参考图1/参考图2/...` labels and manifest paths so the model can bind each file to the right role. Default font still uses an Onion font reference image; do not ask the user to choose it.

## Size Handling

Prompt 正文不写具体像素、`target_size`、`render_size`、KB 上限或比例数字。这些是配置和工具参数，只从配置页的 `placements[]` 读取，并传给 `render.py --size`、导出和压缩脚本。

Prompt 里只保留竖版 / 横版 / 方图等构图语境，例如“横版应用商店三图的第 1 张”“竖版信息流双图的第 1 张”。不要写具体像素生成与导出信息，也不要写比例数字。

## Screen UI Gate

有真实截图时：if image 1 establishes a readable Onion APP / learning UI on a device screen, set `screen_ui_reference_required=true`, include the uploaded screenshot in `reference_images`, and label it in the reference map.

没有真实截图时：do not invent a readable Onion APP page. Use 弱化/模糊屏幕, generic unreadable cards, or a screen angled away from camera. The base image can show product action through scene, posture, light, and abstract proof cards, but not a specific fake UI.

## Positive Example

This art-direction example is derived from the real "闭环通关"拍题精学 case in `功能-拍题精学.md`: find the stuck knowledge point, unlock the method, then practice similar questions.

Input: 三图，短句「题目卡壳一拍精学 / 归纳重点解锁大招 / 智能推题举一反三」。

Base prompt shape with a real screen screenshot:

> 参考图说明：参考图1 是豆包角色参考图；参考图2 是洋葱专属字体参考图；参考图3 是用户上传的洋葱 APP 拍题界面截图。横版应用商店三图的第 1 张。明亮书桌场景，学生对着一道数学题卡住，手机屏幕参考图3的真实拍题界面结构表现“拍题精学正在识别”，不复制截图里的无关文字。豆包站在屏幕旁像小老师一样指向手机，表情专注但不夸张。画面文字只写「题目卡壳一拍精学」，学习参考图2的字形气质、描边和标题排版节奏，但要和当前画面的配色、光线、构图融合，不要求完全一致，不复制参考图2中的示例文字。左上角洋葱学园 Logo，字体清晰，留出后续两张图延续“解锁大招、推同类题”的布局节奏。

Base prompt shape without a screen screenshot:

> 参考图说明：参考图1 是豆包角色参考图；参考图2 是洋葱专属字体参考图。横版应用商店三图的第 1 张。明亮书桌场景，学生对着一道数学题卡住，手机屏幕只做弱化/模糊屏幕，不展示可识别 APP 界面；用光效和不可读的小卡片表达“拍题识别中”。豆包站在书桌旁像小老师一样指向题目，表情专注但不夸张。画面文字只写「题目卡壳一拍精学」，学习参考图2的字形气质、描边和标题排版节奏，但要和当前画面的配色、光线、构图融合，不要求完全一致，不复制参考图2中的示例文字。左上角洋葱学园 Logo，字体清晰，留出后续两张图延续“解锁大招、推同类题”的布局节奏。

## Hidden Failure Example

> 三张图都要讲拍题精学很快，请画第一张，顺便放上所有三句文案。

Why it fails:

- base image contains branch text, breaking text isolation;
- no stable scene/character details for branch;
- branch will not know what to preserve.

## Decision Checklist

Use this checklist privately. Only summarize issues to the user if asked why.

- Does base include only sentence 1?
- Are all selected visual references present here?
- Did you privately note what should change in branch images?
- Is the base concrete enough for SAME locking?
- Does the reference map in the prompt match the `reference_images` order?
- Does any readable screen UI have a real screenshot and `screen_ui_reference_required=true`? If not, use 弱化/模糊屏幕.
