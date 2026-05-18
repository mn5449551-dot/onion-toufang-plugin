# Branch Image Prompt Recipe

Use for image 2/3 in double/triple groups and for iterate tasks based on an existing image. A branch is a controlled delta from a reference PNG.

## Goal

Preserve the base world while changing only what the next text beat requires.

## SAME / CHANGE Model

Default SAME:

- scene layout and camera angle;
- character identity and clothing;
- Logo position and style;
- CTA text, position, size, color and button style when present;
- typography and color hierarchy;
- lighting and overall visual style;
- layout rhythm.

CHANGE should be specific:

- expression;
- gesture/action;
- screen/card content;
- one or two scene details;
- exact on-image text for this branch.

Use explicit `SAME` wording for anything that must not drift: same face, same hair, same outfit, same scene, same lighting, same palette, same typography, same Logo area, and same CTA style.

## References

Default branch references:

1. base PNG only.

Do not pass Logo/IP/style/font again unless the user explicitly changes that asset.

Prompt should define the branch reference explicitly:

> 参考图说明：参考图1 是同套图第 1 张基准图。保持参考图1的角色、Logo、字体、配色、构图和光线，只改变……

If the branch changes IP/Logo/style, add that asset as `参考图2` and state exactly which part changes.

## Positive Example

Reference: `set1_img1.png` with text「题目卡壳一拍精学」. Branch text:「归纳重点解锁大招」。

Prompt shape:

> 参考图 1 是基准图。保持参考图 1 的书桌场景、豆包形象、Logo 位置、字体风格、暖色光线和整体构图。相对参考图 1，只改变学生手机屏幕上的内容：从“卡点识别中”推进到“解题大招已归纳”的方法卡片；豆包手势从指向题目变为指向大招卡片；学生表情更放松。画面文字只写「归纳重点解锁大招」，不要出现上一张图的文字。

## Hidden Failure Example

> 参考上一张，换个场景，文字改成“归纳重点解锁大招”。

Why it fails:

- "换个场景" unlocks too much and destroys series consistency;
- SAME items are not specified;
- branch may drift in IP, font, Logo, and layout.

## Decision Checklist

Use this checklist privately. Only summarize issues to the user if asked why.

- Is the reference list only the base PNG by default?
- Are SAME items explicit enough?
- Is CHANGE limited to 2-4 concrete changes?
- Does text include only the current branch sentence?
- Is the branch emotion equal or more positive than base?
