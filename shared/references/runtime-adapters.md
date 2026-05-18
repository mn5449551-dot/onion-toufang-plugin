# Runtime Adapters

This file keeps platform-specific interaction details out of core `SKILL.md` files. Skills should describe the interaction intent; the current runtime decides how to perform it.

## Collecting User Choices

Core wording:

> If an interactive UI is available, collect the missing options in one compact choice prompt. If not, ask the user one concise question that names only the blocking missing inputs.

Use this when the skill needs user-provided values that cannot be inferred from Base records, prior context, or safe defaults.

Do not ask again for values already provided by the user or inherited from a trusted record.

Do not rely on modal popups as a product guarantee. In Codex / Claude Code default chat flows, a production Skill may not be able to force a Plan-mode style choice window. When no interactive picker is available, the fallback must still be clear: ask one short question and include explicit numbered or named options for every blocking choice. Avoid vague wording such as "给我配置一下" or "你想怎么做".

For dense and reusable option sets, a skill may provide a local HTML interaction page instead of a native modal. The page must save a machine-readable JSON result in the work output directory, and the agent must read that JSON before continuing. For `onion-image`, the runtime sequence is: open image config page, read `image-config-result.json`, render, build `image-selection.html`, then open the selection/annotation page in the same local service. Long image batches should update `image-sets.json` through `/api/image-sets`; the page polls that endpoint and preserves existing annotations.

For ambiguous selection intents, ask for the next action instead of guessing:

- Direction selected: "已选方向 2。要入库后继续出文案，还是只入库？"
- Multiple directions selected: "这两个方向都入库后，是分别出文案，还是只基于其中一个出？"
- Copy selected: "已选文案 4。要入库、基于它出图，还是继续改文案？"

## Async Feedback

Core wording:

> After the main user-visible work is complete, feedback analysis may run asynchronously when the runtime supports it. Feedback collection must not block the user, and failure to write feedback must not fail the main task.

If async workers are unavailable, keep brief observation notes in the final state and let the next explicit feedback or maintenance pass handle them.

## Task Tracking

Core wording:

> When the runtime has a task tool, use it for multi-step follow-up tracking. Otherwise, continue inline with concise status updates.

Do not make task tracking a hard dependency for any production skill.

## Claude Code / Codex Adapter

Claude Code / Codex-style runtimes may implement the abstractions above with their own choice prompts, background agents, task tools, or inline questions. Keep those concrete calls in runtime-specific operational notes, not in the production skill body.

## Non-Interactive Adapter

In a plain chat or CLI runtime:

- Ask short direct questions instead of showing cards.
- Prefer one question covering all blocking missing inputs.
- If async feedback is unavailable, skip it without blocking the primary task.
- If a task tool is unavailable, use a short checklist in the response.
