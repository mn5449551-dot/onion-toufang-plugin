# Image Config Guardrails Design

**Goal:** Prevent image configuration pages from misleading users when a request is meant to be double-image creative but stale pages, loose context, Windows encoding, or placement filtering make double-image slots appear unavailable.

**Scope:** This design covers `onion-image` configuration startup and Base attachment upload compatibility. It does not add remote version management, automatic plugin updates, or global process killing.

## Problem

A Windows user requested Huawei double-image creative with text equivalent to:

```text
图一：复习没方向，找洋葱私教班
图二：先找弱点再补救 提分快准狠
```

The user started a new config page on port `8766` because `8765` was already occupied. They then reported that double-image placement could not be selected and that the page showed only single-image options. Current source rules show Huawei double-image placement `huawei-app-slot-slot-480x422` is enabled, so the likely failure mode is not a placement-rule business restriction. The likely causes are stale browser tabs, stale local services, non-standard context shape, or weak page diagnostics.

## Design Principles

- Make the page self-explanatory: users should see what image form and channel the page actually recognized.
- Fix input compatibility at the boundary: agents should be allowed to pass common shorthand context without breaking the page.
- Do not silently destroy user state: old local servers should be detected and made visible, not killed automatically.
- Keep diagnostics available but unobtrusive: operational details belong in a collapsible section, not in the main workflow.
- Prefer precise failure reasons over broad labels like "一期不支持".

## Approach

### 1. Context Normalization

Add a `normalize_context(context)` function in `skills/onion-image/scripts/interactive_server.py`.

It should accept the existing canonical shape:

```json
{
  "image_form": "双图",
  "copy_drafts": [
    {
      "copyDraftId": "draft-1",
      "short1": "复习没方向，找洋葱私教班",
      "short2": "先找弱点再补救 提分快准狠",
      "imageForm": "双图"
    }
  ]
}
```

It should also accept a common Windows/PowerShell shorthand:

```json
{
  "image_form": "双图",
  "copy": [
    "图一：复习没方向，找洋葱私教班",
    "图二：先找弱点再补救 提分快准狠"
  ]
}
```

The shorthand should be converted into one `copy_drafts` item only when at least one of these is true:

- `image_form` / `imageForm` / `图片形式` explicitly normalizes to `双图`.
- The strings contain explicit image-position markers such as `图一`, `图1`, `第一张`, `图二`, `图2`, or `第二张`.

If neither condition is true, the `copy` array remains as raw context because it may represent multiple candidate copies rather than one double-image copy.

The function should preserve the original context under a diagnostic field such as `_raw_context` or expose it through a separate `diagnostics` payload, without changing downstream submitted `image-config-result.json` semantics.

### 2. Windows-Safe Context Parsing

Update `parse_context(value)` to read context files with `encoding="utf-8-sig"`.

This handles PowerShell-created UTF-8 files with a BOM while keeping existing UTF-8 files working.

### 3. Config Page Status Summary

Add a compact status strip to `skills/onion-image/templates/image-config.html`.

It should display:

```text
当前识别：双图 · 应用商店
可选双图版位：4 个
Request: onion-dual-review-20260522-163408
启动时间：2026-05-22 16:34
```

The exact visual style should be quiet and utilitarian. It should not compete with placement cards.

The status strip should be derived from the server payload, not recomputed independently in the browser.

### 4. Collapsible Diagnostics

Add a collapsible diagnostics block below the status strip.

It should include:

- plugin version from `.codex-plugin/plugin.json` when available;
- rules file path;
- rules file hash;
- whether placement rules loaded from `channel-placement-rules.json` or fallback slots;
- `desiredImageForm`;
- `desiredChannels`;
- enabled placement counts by image form;
- disabled reason counts;
- current server request id;
- page URL request id.

This block is for support and debugging. It should be closed by default.

### 5. Request ID Mismatch Guard

If a browser opens `/image-config?request_id=<url-id>` and `<url-id>` does not match the running server's request id, the server should return a clear error page instead of rendering the config UI.

The error page should say:

```text
你打开的是旧配置页或旧 request。
当前服务 request_id: <server-id>
URL request_id: <url-id>
请打开本次启动输出里的链接。
```

This avoids the common port-stale-tab failure without terminating other users' or other tasks' local servers.

### 6. No-Available-Placement Explanation

When the current form is `双图` and there are zero enabled double-image placements, the page should show a focused warning above the placement grid.

The warning should list concrete detected reasons:

- current channel locks to `学习机`, where only single-image placement is supported;
- current recognized image form is not `双图`;
- placement rules failed to load and fallback slots are in use;
- all matching slots are disabled because of directness/postprocess constraints;
- no placement exists for the selected channel and form.

If Huawei double-image placement exists but is disabled, the warning should include its actual disabled reason. If it is enabled but hidden by the selected category, the warning should tell the user to switch to `应用商店`.

### 7. Reference Image Clarification

If context contains a `reference_image`, `uploaded_image`, or similar path, the page should show a short note:

```text
参考图只用于风格/版式参考，不决定本次版位。目标版位以下方选择为准。
```

This prevents a file named like `华为-984x422` from implicitly forcing a single-image placement when the user requested double-image creative.

### 8. Attachment Upload Compatibility

Move the already-proven local cache fix into source control in `shared/scripts/base_ops.py`.

For `attachment_upload`:

- do not pass `--name` to `lark-cli base +record-upload-attachment`;
- if `payload["file"]` is absolute, run `lark-cli` with `cwd` set to the file parent directory and pass `./<filename>` as `--file`.

This is separate from the double-image UI issue, but it is needed for the same Windows workflow to complete Base writes with current `lark-cli`.

## Data Flow

1. Agent starts `interactive_server.py` with `--context <json file>`.
2. `parse_context()` reads the JSON using `utf-8-sig`.
3. `normalize_context()` converts accepted shorthand into canonical context.
4. `build_config_payload()` computes desired form, channels, placement counts, and diagnostics.
5. `/image-config` validates URL request id against server request id.
6. The template renders a status strip, optional diagnostics, placement warning if needed, and normal placement cards.
7. User saves config; `normalize_config_result()` remains the single source of truth for render configuration.

## Non-Goals

- No automatic killing of old `interactive_server.py` processes.
- No remote GitHub version check in the config page.
- No automatic plugin update or cache invalidation.
- No attempt to infer placement from reference image file names.
- No broad rewrite of placement rules.

## Testing Plan

Add tests in `tests/test_interactive_server.py`:

- `test_parse_context_accepts_utf8_bom_file`: writes a BOM-prefixed context file and verifies parsed JSON is valid.
- `test_copy_array_with_double_form_normalizes_to_single_double_copy_ref`: verifies `copy: ["图一...", "图二..."]` plus `image_form: "双图"` becomes one draft with `short1`, `short2`, and `imageForm: "双图"`.
- `test_copy_array_without_double_markers_is_not_merged`: verifies two generic strings remain separate/raw when image form is not explicitly double and no image markers exist.
- `test_huawei_double_slot_enabled_for_double_context`: verifies `huawei-app-slot-slot-480x422` is enabled when `image_form: "双图"`.
- `test_huawei_double_slot_disabled_for_single_context_with_form_reason`: verifies the same slot is disabled for `image_form: "单图"` with a form-mismatch reason, not an "一期不支持" reason.
- `test_payload_contains_diagnostics`: verifies diagnostics include request id, rules source, rules hash, desired form, desired channels, and placement counts.
- `test_request_id_mismatch_returns_error_page`: verifies the server does not render normal config UI for mismatched URL request id.

Add tests in `tests/test_base_scripts.py`:

- `test_attachment_upload_command_omits_name`: verifies generated attachment upload commands do not include `--name`.
- `test_attachment_upload_absolute_file_runs_from_parent_with_relative_file`: verifies absolute attachment paths are converted to `cwd=<parent>` and `--file ./<basename>`.

Run focused tests before broader verification:

```bash
python3 -m pytest tests/test_interactive_server.py tests/test_base_scripts.py -q
```

Then run the existing full test suite if focused tests pass:

```bash
python3 -m pytest -q
```

## Rollout

1. Implement in the source repository, not only in Codex plugin cache.
2. Run focused and full tests.
3. Bump plugin version from `1.1.0` to `1.1.1`.
4. Commit and push to GitHub.
5. Ask Windows users to update the plugin.
6. Confirm the config page status strip shows:

```text
当前识别：双图 · 应用商店
可选双图版位：4 个
```

## Acceptance Criteria

- A Windows context file with BOM loads successfully.
- The user's shorthand double-image copy request opens a page where Huawei double-image placement is selectable.
- Opening an old or mismatched request URL shows an explicit old-request error page.
- When no double-image placement is available, the page explains why using detected state.
- Reference image file names do not force image form or placement.
- Base attachment uploads work with current `lark-cli` on macOS and Windows.
