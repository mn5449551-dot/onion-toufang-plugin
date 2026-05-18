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

## Screen UI Gate

有真实截图时：when a branch keeps the same readable UI from the base, the base PNG is enough. When a branch must add or replace readable Onion APP / learning UI, include the user-uploaded screenshot as a new reference and say which screen content changes.

没有真实截图时：do not add or replace readable product UI. Keep screen/card content generic, unreadable, or 弱化/模糊屏幕. 新增或替换屏幕内容 without a screenshot must be abstract proof, not a fake app page.

## Positive Example

Reference: `set1_img1.png` with text「题目卡壳一拍精学」. Branch text:「归纳重点解锁大招」。

Prompt shape:

> 参考图 1 是基准图。保持参考图 1 的书桌场景、豆包形象、Logo 位置、字体风格、暖色光线和整体构图。若参考图 1 已有真实截图驱动的可识别屏幕 UI，则保持其界面体系，只把屏幕内容推进到同一截图体系下的下一步；若没有真实截图，则手机屏幕继续弱化/模糊屏幕，只用不可读方法卡片和光效表达“解题大招已归纳”。豆包手势从指向题目变为指向方法卡片；学生表情更放松。画面文字只写「归纳重点解锁大招」，不要出现上一张图的文字。

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
- If changing readable screen UI, is the screenshot reference present? If not, keep 弱化/模糊屏幕.
