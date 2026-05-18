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

## Positive Example

This art-direction example is derived from the real "闭环通关"拍题精学 case in `功能-拍题精学.md`: find the stuck knowledge point, unlock the method, then practice similar questions.

Input: 三图，短句「题目卡壳一拍精学 / 归纳重点解锁大招 / 智能推题举一反三」。

Base prompt shape:

> 参考图说明：参考图1 是豆包角色参考图；参考图2 是洋葱专属字体参考图。横版 3:2 应用商店三图的第 1 张。明亮书桌场景，学生对着一道数学题卡住，手机里打开洋葱拍题精学，相机框正对题目，题目边缘被清晰识别框选。豆包站在屏幕旁像小老师一样指向“卡点识别中”的卡片，表情专注但不夸张。画面文字只写「题目卡壳一拍精学」，学习参考图2的字形气质、描边和标题排版节奏，但要和当前画面的配色、光线、构图融合，不要求完全一致，不复制参考图2中的示例文字。左上角洋葱学园 Logo，字体清晰，留出后续两张图延续“解锁大招、推同类题”的布局节奏。

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
