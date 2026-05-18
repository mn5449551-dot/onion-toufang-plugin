# Single Image Prompt Recipe

Use for `imageForm=单图`. A single image must communicate the pain point, product action, and desired feeling in one frame.

## Goal

The viewer should understand in 1-3 seconds:

- this is my learning pain;
- this product gives a concrete answer;
- I want to continue or click.

## Tradeoffs

| Decision | Guidance |
|---|---|
| Emotion strength | 信息流 can be sharper; 应用商店 should be calmer and clearer; 学习机 should sound like a student, not a parent |
| Person vs tool |人物 catches attention; screen/tool details prove the selling point |
| Text size | 信息流 title can dominate; 应用商店/学习机 should leave more room for product proof |
| IP usage | Use IP when it helps emotion or guidance; skip IP for text-led functional ads |

## Style Choice

有 IP 时，正文第一句优先定成统一的高质量动漫插画 / 半写实动漫广告风格，让角色、学生、场景、道具和光效处在同一视觉体系内。IP 保真细节写进 `参考图说明`，正文只在角色第一次出现时用括号标注参考图编号，例如“小锤（参考图2）”。

无 IP 时，从视觉风格池随机选择一种，发挥创意，不要默认回到同一种广告模板。可选方向包括毛毡手作、半写实广告插画、写实广告合成感、扁平矢量插画、赛璐珞动漫、软萌 3D 卡通、高质量家庭动画电影感、纸雕/剪纸层叠、黏土/软陶质感、水彩插画、粉笔黑板手绘、轻拟物 UI 插画等。不要写第三方品牌风格名；如果用户用品牌式风格描述，改写成通用视觉语言。

## Required Elements

Prompt should specify:

- scene and moment;
- main person or IP, if any;
- product proof: screen, parsing card, step card, or learning action;
- exact on-image text;
- Logo and CTA rules;
- font reference for on-image Chinese text; by default choose one `assets/font-references/字体参考-XX.png` and ask the model to learn its typography feel while blending with the current image;
- style and composition.

Do not force these into a fixed paragraph order. Make the prompt read like a precise art direction brief.

## Size Handling

Prompt 正文不写具体像素、`target_size`、`render_size`、KB 上限或比例数字。这些是工具参数和导出压缩策略，只从配置页的 `placements[]` 读取，并传给 `render.py --size`、导出和压缩脚本。

Prompt 里只保留竖版 / 横版 / 方图等构图语境，例如“竖版信息流广告海报”“横版应用商店单图”“方形图标式广告”。不要写具体像素生成与导出信息，也不要写比例数字。

## Screen UI Gate

有真实截图时：if the final image needs recognizable Onion APP / learning UI on a phone, tablet, computer, learning device, projection screen, or other electronic screen, include the uploaded screenshot in `reference_images`, label it in the reference map, and describe how to use it.

没有真实截图时：do not invent a readable Onion APP page. Keep the device screen weak, blurred, angled away, overexposed, or represented by generic unreadable cards. The prompt must say `弱化/模糊屏幕` and should not describe specific screenshots, question frames, answer pages, or chat UI.

不要编造可识别的洋葱 APP 界面. Concrete UI proof requires `screen_ui_reference_required=true` and a real uploaded screenshot.

## References

Default order for full references:

1. Logo
2. IP
3. style reference
4. font reference
5. screen UI screenshot, only when provided

Only include references that are actually selected. The default font is an Onion font reference image, but it is selected by the agent from `assets/font-references/` without asking the user.

When two or more references are selected, start the prompt with a short reference map:

> 参考图说明：参考图1 是品牌 Logo；参考图2 是豆包正常版角色参考图。左上角使用参考图1，参考图2的豆包站在屏幕旁指向解析卡片。

The `reference_images` array passed to `render.py` must use the same labels and order. Prefer manifest paths such as `assets/ip-roles/doubao/doubao-junior-standard-001.png`, not ad hoc or legacy shortcut paths.

## Positive Example

This art-direction example is derived from the real "识别准确"拍题精学 case in `功能-拍题精学.md`: repeated failed recognition, then Onion gives a trustworthy result.

Input: 信息流单图，文案「拍了改、改了拍，识别不出来？ / 洋葱拍题精学，一拍识别，答案就是准」，IP=豆包，Logo=洋葱学园。

Prompt shape with a real screen screenshot:

> 参考图说明：参考图1 是品牌 Logo；参考图2 是豆包角色参考图；参考图3 是洋葱专属字体参考图；参考图4 是用户上传的洋葱 APP 拍题结果页截图。竖版信息流广告海报。晚上书桌场景，初中生用手机反复拍同一道数学题，旁边浮现两个浅灰色失败提示卡片：识别失败、答案不确定；手机屏幕参考图4的真实界面结构，表现洋葱拍题精学的清晰结果页和校准可信感，不复制截图里的无关细节。豆包站在屏幕旁指向正确解析，学生表情从皱眉变成松一口气。画面上方大字「拍了改、改了拍，识别不出来？」，下方副标题「洋葱拍题精学，一拍识别，答案就是准」。文字学习参考图3的字形气质、描边和标题排版节奏，但要和当前画面的配色、光线、构图融合，不要求完全一致，不复制参考图3中的示例文字。左上角放洋葱学园 Logo，整体清晰、高对比、学习工具可信感强。

Prompt shape without a screen screenshot:

> 参考图说明：参考图1 是品牌 Logo；参考图2 是豆包角色参考图；参考图3 是洋葱专属字体参考图。竖版信息流广告海报。晚上书桌场景，初中生拿着手机准备拍题，手机屏幕只做弱化/模糊屏幕，不展示可识别 APP 界面；旁边用抽象光效和不可读卡片表达“识别更准、解析更可信”的产品动作。豆包站在书桌旁指向题目，学生表情从皱眉变成松一口气。画面上方大字「拍了改、改了拍，识别不出来？」，下方副标题「洋葱拍题精学，一拍识别，答案就是准」。文字学习参考图3的字形气质、描边和标题排版节奏，但要和当前画面的配色、光线、构图融合，不要求完全一致，不复制参考图3中的示例文字。左上角放洋葱学园 Logo，整体清晰、高对比、学习工具可信感强。

## Hidden Failure Example

> 画一个学生崩溃抱头，旁边有豆包和洋葱 Logo，文字写“拍题超准”。

Why it fails:

- strong negative emotion may trigger moderation;
- no concrete product proof;
- IP face/clothing details are underspecified, causing drift;
- no layout or text hierarchy.

## Decision Checklist

Use this checklist privately. Only summarize issues to the user if asked why.

- Does the image prove the product action, not just show a sad student?
- Does on-image text match the selected copy exactly?
- Are Logo and CTA consistent with configuration?
- Are reference paths selected in the same order as prompt references?
- Does the prompt mention every labeled reference image?
- If a readable product screen is described, is there a real screenshot reference and `screen_ui_reference_required=true`?
