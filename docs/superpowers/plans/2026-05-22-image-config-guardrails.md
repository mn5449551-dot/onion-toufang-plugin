# Image Config Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the onion-image config page correctly recognize double-image shorthand, expose stale-page diagnostics, and keep Base attachment upload compatible with current `lark-cli`.

**Architecture:** Normalize incoming context at the server boundary, enrich the existing payload with computed diagnostics, and render those diagnostics in the existing static template. Keep submission payload semantics unchanged. Update Base upload command preparation in the shared script without touching higher-level write flows.

**Tech Stack:** Python standard library HTTP server, unittest/pytest, static HTML/CSS/JS, `lark-cli` shell integration.

---

### Task 1: Add Context Normalization Tests

**Files:**
- Modify: `tests/test_interactive_server.py`

- [ ] **Step 1: Write failing tests**

Add tests for BOM context parsing, double-image shorthand normalization, generic `copy` arrays staying raw, Huawei double slot availability, and diagnostics payload fields:

```python
def test_parse_context_accepts_utf8_bom_file(self):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "context.json"
        path.write_bytes('{"image_form":"双图"}'.encode("utf-8-sig"))

        parsed = self.server.parse_context(str(path))

    self.assertEqual(parsed["image_form"], "双图")


def test_copy_array_with_double_form_normalizes_to_single_double_copy_ref(self):
    payload = self.server.build_config_payload(
        "req-double",
        context={"image_form": "双图", "copy": ["图一：复习没方向，找洋葱私教班", "图二：先找弱点再补救 提分快准狠"]},
    )

    self.assertEqual(payload["copyCount"], 1)
    self.assertEqual(payload["copyRefs"][0]["short1"], "复习没方向，找洋葱私教班")
    self.assertEqual(payload["copyRefs"][0]["short2"], "先找弱点再补救 提分快准狠")
    self.assertEqual(payload["copyRefs"][0]["imageForm"], "双图")


def test_copy_array_without_double_markers_is_not_merged(self):
    normalized = self.server.normalize_context({"copy": ["候选文案 A", "候选文案 B"]})

    self.assertNotIn("copy_drafts", normalized)
    self.assertEqual(normalized["copy"], ["候选文案 A", "候选文案 B"])


def test_huawei_double_slot_enabled_for_double_context(self):
    payload = self.server.build_config_payload("req-huawei", context={"image_form": "双图"})
    by_id = {slot["id"]: slot for slot in payload["slots"]}

    self.assertTrue(by_id["huawei-app-slot-slot-480x422"]["enabled"])
    self.assertEqual(by_id["huawei-app-slot-slot-480x422"]["imageForm"], "双图")


def test_huawei_double_slot_disabled_for_single_context_with_form_reason(self):
    payload = self.server.build_config_payload("req-huawei", context={"image_form": "单图"})
    by_id = {slot["id"]: slot for slot in payload["slots"]}

    self.assertFalse(by_id["huawei-app-slot-slot-480x422"]["enabled"])
    self.assertIn("本次图片形式为单图", by_id["huawei-app-slot-slot-480x422"]["disabled_reason"])
    self.assertNotIn("一期不支持", by_id["huawei-app-slot-slot-480x422"]["disabled_reason"])


def test_payload_contains_diagnostics(self):
    payload = self.server.build_config_payload("req-diag", context={"image_form": "双图"})
    diagnostics = payload["diagnostics"]

    self.assertEqual(diagnostics["serverRequestId"], "req-diag")
    self.assertEqual(diagnostics["desiredImageForm"], "双图")
    self.assertIn("rulesPath", diagnostics)
    self.assertIn("rulesHash", diagnostics)
    self.assertGreaterEqual(diagnostics["enabledPlacementCountsByForm"]["双图"], 1)
    self.assertEqual(diagnostics["statusSummary"]["imageForm"], "双图")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py::InteractiveServerTests::test_parse_context_accepts_utf8_bom_file tests/test_interactive_server.py::InteractiveServerTests::test_copy_array_with_double_form_normalizes_to_single_double_copy_ref tests/test_interactive_server.py::InteractiveServerTests::test_copy_array_without_double_markers_is_not_merged tests/test_interactive_server.py::InteractiveServerTests::test_payload_contains_diagnostics -q
```

Expected: failures because `parse_context` uses `utf-8`, `normalize_context` does not exist, `copy` is not converted, and diagnostics are missing.

- [ ] **Step 3: Implement context normalization and diagnostics**

Modify `skills/onion-image/scripts/interactive_server.py`:

```python
def normalize_context(context: dict[str, Any] | None) -> dict[str, Any]:
    ...

def parse_context(value: str | None) -> dict[str, Any]:
    ...
```

Call `normalize_context()` at the start of `build_config_payload()` and `OnionInteractionServer.__init__()`. Add helper functions for rules metadata and enabled placement counts, and include the result under `payload["diagnostics"]`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py -q
```

Expected: all interactive server tests pass.

### Task 2: Add Request ID Guard Tests

**Files:**
- Modify: `tests/test_interactive_server.py`

- [ ] **Step 1: Write failing test**

Add an HTTP-level test:

```python
def test_request_id_mismatch_returns_error_page(self):
    with tempfile.TemporaryDirectory() as tmp:
        httpd = self.server.OnionInteractionServer(
            ("127.0.0.1", 0),
            output_dir=Path(tmp),
            request_id="current-req",
            context={},
            platform_rules=None,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(Exception) as raised:
                request.urlopen(
                    f"http://127.0.0.1:{httpd.server_port}/image-config?request_id=old-req",
                    timeout=5,
                )
            body = raised.exception.read().decode("utf-8")
        finally:
            httpd.shutdown()
            thread.join(timeout=5)

    self.assertIn("旧配置页或旧 request", body)
    self.assertIn("current-req", body)
    self.assertIn("old-req", body)
    self.assertNotIn("__DATA_JSON__", body)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py::InteractiveServerTests::test_request_id_mismatch_returns_error_page -q
```

Expected: test fails because mismatched request ids currently render the config page.

- [ ] **Step 3: Implement request guard**

Add a `build_request_mismatch_html()` helper and update `OnionInteractionHandler.do_GET()` to return status `409` when the query request id differs from `self.server.request_id`.

- [ ] **Step 4: Run focused test**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py::InteractiveServerTests::test_request_id_mismatch_returns_error_page -q
```

Expected: pass.

### Task 3: Render Status, Diagnostics, and Placement Warnings

**Files:**
- Modify: `skills/onion-image/templates/image-config.html`
- Modify: `tests/test_interactive_server.py`

- [ ] **Step 1: Write template coverage test**

Extend `test_config_html_contains_submit_endpoint_and_font_rule()` to assert the rendered HTML includes:

```python
self.assertIn("status-strip", html)
self.assertIn("diagnostics-panel", html)
self.assertIn("placement-warning", html)
self.assertIn("参考图只用于风格/版式参考", html)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py::InteractiveServerTests::test_config_html_contains_submit_endpoint_and_font_rule -q
```

Expected: fail because these UI elements do not exist yet.

- [ ] **Step 3: Update template**

Add a compact status strip, closed-by-default diagnostics `<details>`, optional reference-image note, and a `renderPlacementWarning()` function. The warning should use `DATA.diagnostics.noPlacementExplanation` and update after category changes.

- [ ] **Step 4: Run focused test**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py::InteractiveServerTests::test_config_html_contains_submit_endpoint_and_font_rule -q
```

Expected: pass.

### Task 4: Fix Attachment Upload Command Preparation

**Files:**
- Modify: `shared/scripts/base_ops.py`
- Modify: `tests/test_base_scripts.py`

- [ ] **Step 1: Write failing command tests**

Import `base_ops.py` and add:

```python
def load_base_ops_module(self):
    spec = importlib.util.spec_from_file_location("base_ops", SCRIPTS_DIR / "base_ops.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_attachment_upload_command_omits_name(self):
    base_ops = self.load_base_ops_module()
    command, cwd = base_ops.prepare_command(
        "attachment_upload",
        {
            "base_token": "app",
            "table_id": "tbl",
            "record_id": "rec",
            "field_id": "fld",
            "file": "image.png",
            "name": "ignored.png",
        },
    )

    self.assertNotIn("--name", command)
    self.assertIsNone(cwd)

def test_attachment_upload_absolute_file_runs_from_parent_with_relative_file(self):
    base_ops = self.load_base_ops_module()
    with tempfile.TemporaryDirectory() as tmp:
        image = Path(tmp) / "image.png"
        image.write_bytes(b"fake")
        command, cwd = base_ops.prepare_command(
            "attachment_upload",
            {
                "base_token": "app",
                "table_id": "tbl",
                "record_id": "rec",
                "field_id": "fld",
                "file": str(image),
            },
        )

    self.assertEqual(cwd, str(image.parent))
    self.assertEqual(command[command.index("--file") + 1], "./image.png")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/test_base_scripts.py::BaseScriptTests::test_attachment_upload_command_omits_name tests/test_base_scripts.py::BaseScriptTests::test_attachment_upload_absolute_file_runs_from_parent_with_relative_file -q
```

Expected: fail because `prepare_command` does not exist and `--name` is still emitted.

- [ ] **Step 3: Implement command preparation**

Add `prepare_command(op_type, payload, dry_run=False) -> tuple[list[str], str | None]`, keep `build_command()` as a compatibility wrapper, and update `execute()` to pass `cwd=cwd` to `subprocess.run()`.

- [ ] **Step 4: Run focused base script tests**

Run:

```bash
python3 -m pytest tests/test_base_scripts.py -q
```

Expected: all base script tests pass.

### Task 5: Version Bump and Full Verification

**Files:**
- Modify: `.codex-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Bump plugin version**

Change every `1.1.0` plugin version field to `1.1.1`.

- [ ] **Step 2: Run focused tests**

Run:

```bash
python3 -m pytest tests/test_interactive_server.py tests/test_base_scripts.py -q
```

Expected: pass.

- [ ] **Step 3: Run full test suite**

Run:

```bash
python3 -m pytest -q
```

Expected: pass.

- [ ] **Step 4: Commit**

Run:

```bash
git status --short
git add docs/superpowers/plans/2026-05-22-image-config-guardrails.md tests/test_interactive_server.py tests/test_base_scripts.py skills/onion-image/scripts/interactive_server.py skills/onion-image/templates/image-config.html shared/scripts/base_ops.py .codex-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "fix: harden image config double-image workflow"
```

Expected: commit succeeds on branch `codex/image-config-guardrails`.

### Self-Review

- Spec coverage: context normalization, BOM parsing, status summary, diagnostics, request mismatch guard, no-placement warning, reference-image clarification, attachment upload compatibility, version bump, and tests all map to tasks above.
- Placeholder scan: no task uses unspecified TODO/TBD language.
- Type consistency: diagnostics keys use camelCase in the payload and template, matching existing frontend data style.
