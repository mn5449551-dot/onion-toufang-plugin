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

## References

Default order for full references:

1. Logo
2. IP
3. style reference
4. font reference

Only include references that are actually selected. The default font is an Onion font reference image, but it is selected by the agent from `assets/font-references/` without asking the user.

When two or more references are selected, start the prompt with a short reference map:

> 参考图说明：参考图1 是品牌 Logo；参考图2 是豆包正常版角色参考图。左上角使用参考图1，参考图2的豆包站在屏幕旁指向解析卡片。

The `reference_images` array passed to `render.py` must use the same labels and order. Prefer manifest paths such as `assets/ip-roles/doubao/doubao-junior-standard-001.png`, not ad hoc or legacy shortcut paths.

## Positive Example

This art-direction example is derived from the real "识别准确"拍题精学 case in `功能-拍题精学.md`: repeated failed recognition, then Onion gives a trustworthy result.

Input: 信息流单图，文案「拍了改、改了拍，识别不出来？ / 洋葱拍题精学，一拍识别，答案就是准」，IP=豆包，Logo=洋葱学园，9:16。

Prompt shape:

> 参考图说明：参考图1 是品牌 Logo；参考图2 是豆包角色参考图；参考图3 是洋葱专属字体参考图。竖版 9:16 信息流广告图。晚上书桌场景，初中生用手机反复拍同一道数学题，旁边浮现两个浅灰色失败提示卡片：识别失败、答案不确定；中间切到洋葱拍题精学的清晰结果页，题目框选准确，解析卡片带对勾和“AI + 名师校准”可信标识。豆包站在屏幕旁指向正确解析，学生表情从皱眉变成松一口气。画面上方大字「拍了改、改了拍，识别不出来？」，下方副标题「洋葱拍题精学，一拍识别，答案就是准」。文字学习参考图3的字形气质、描边和标题排版节奏，但要和当前画面的配色、光线、构图融合，不要求完全一致，不复制参考图3中的示例文字。左上角放洋葱学园 Logo，整体清晰、高对比、学习工具可信感强。

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
