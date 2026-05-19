# render.py Interface Contract

`skills/onion-image/scripts/render.py` is the single-job renderer. It renders one PNG per call.

`skills/onion-image/scripts/batch_render.py` is the batch orchestration entrypoint for paid multi-image work. It reads a manifest, runs `render.py` as subprocesses, respects single/double/triple dependencies, skips already-rendered outputs on resume, and writes `image-render-result.json`.

Do not hand-roll concurrent shell loops in the agent. 并发单位是 render job，不是套数：单图 1 套约等于 1 个 job；双图 1 套至少 2 个 job，图2依赖图1；三图 1 套至少 3 个 job，图2/图3依赖图1。

## Inputs

Required:

- `--prompt`: complete image prompt.
- `--size`: explicit gpt-image-2 size from the selected placement's `render_size`, such as `1568x672`.
- `--output`: absolute or cwd-relative PNG path.

Optional:

- `--aspect-ratio`: legacy route for `1:1`, `3:2`, `16:9`, or `9:16`; use only when no placement is selected.
- `--quality`: `low`, `medium`, or `high`; default `medium`.
- `--reference <path>`: repeatable local reference image path.
- `--input-json <path>`: JSON with `prompt`, `size` or `aspect_ratio`, `quality`, and `reference_images`. Prefer object entries with `label` / `role` / `asset_id` / `path` when more than one reference image is used.
- `--api-base`: defaults to `LAOZHANG_API_BASE` or LaoZhang default.
- `--retries`: default 3.
- `--validate-only`: validate prompt, size, output, and reference paths without paid API call.

Environment:

- `LAOZHANG_API_KEY` is required only for paid rendering, not for `--validate-only`; before a paid render, check that it exists and is not a placeholder so the run does not fail after prompts are prepared.
- `.env` is auto-loaded from `~/.onion-ad/.env`, cwd `.env`, and the skill directory.
- LaoZhang `GPTImage2 Enterprise / gpt-image-2` is planned as `3000 RPM / API key` and `100 concurrent requests / API key`; this plugin uses local concurrency only, not a team-wide lock.
- `ONION_IMAGE_CONCURRENCY` defaults to `6`.
- `ONION_IMAGE_FALLBACK_CONCURRENCY` defaults to `3`.

## Output

On success, stdout is JSON:

```json
{
  "valid": true,
  "filepath": "<output-dir>/set1_img1.png",
  "size_label": "1568x672",
  "size": "1568x672",
  "aspect_ratio": "custom",
  "model": "gpt-image-2",
  "quality": "medium",
  "endpoint": "/images/edits",
  "reference_images_resolved": []
}
```

Use `filepath` as the source of truth for downstream chain steps.

## Exit Codes

| Code | Meaning | Handling |
|---|---|---|
| 0 | Success or validate-only success | Continue |
| 1 | Local validation error | Fix prompt, size, output path, or reference path |
| 2 | Missing/invalid API key | Ask user to fix environment |
| 3 | Network/API failure after retries | Retry later or queue task manually |
| 4 | API rejection or moderation block | Rewrite prompt to safer language |
| 130 | Interrupted | Stop cleanly |

## Reference Rules

When more than one reference is used, prompt and input JSON must agree:

```json
"reference_images": [
  {"label": "参考图1", "role": "品牌 Logo 参考图", "asset_id": "logo.onion.standard.001", "path": "assets/logos/onion-logo-standard-001.png"},
  {"label": "参考图2", "role": "豆包正常版角色参考图", "asset_id": "ip.doubao.junior.standard.001", "path": "assets/ip-roles/doubao/doubao-junior-standard-001.png"}
]
```

The prompt must mention explicitly labeled references. `--validate-only` rejects missing labels, duplicate labels, missing files, invalid sizes, and invalid ratios before any paid call.

Single/base image:

- Pass full visual references: Logo, IP, style, font if selected.
- Reference order must match prompt wording.

Branch image:

- Pass only the base PNG unless the user explicitly changes a visual asset.
- Do not pass Logo/IP/style/font again by default; they should already be fused into the base PNG.

## Chain Rules

### Single

For `imageForm=单图`, each set has one independent render call.

Different single-image sets may render concurrently after their prompts pass validation.

### Double

For `imageForm=双图`:

1. Render `setN_img1.png` with full references.
2. Validate the file exists.
3. Render `setN_img2.png` with `setN_img1.png` as the reference.

Do not render image 1 and image 2 concurrently.

### Triple

For `imageForm=三图`:

1. Render `setN_img1.png` with full references.
2. Validate the file exists.
3. Render `setN_img2.png` and `setN_img3.png` using only `setN_img1.png` as reference.

Image 2 and image 3 may run concurrently after image 1 exists.

Different sets are independent and may render concurrently within the selected batch. Keep each set's internal chain order intact.

## Batch Rendering

For 11-50 set requests, prompt authoring follows `shared/recipes/batch-prompting.md`; rendering follows this file.

Recommended execution shape:

- author prompts in batches of 5-10 sets;
- run `--validate-only` for all planned images in the batch;
- render independent sets concurrently with a conservative cap;
- for double/triple sets, render each set's base first, then render its branches after the base file exists;
- keep partial successes and do not rerender existing PNGs on resume.

Use `batch_render.py` after prompts and references have passed validation:

```bash
python3 skills/onion-image/scripts/batch_render.py \
  --manifest <output-dir>/image-render-manifest.json \
  --output <output-dir>/image-render-result.json
```

Manifest shape:

```json
{
  "request_id": "img-20260519-xxx",
  "jobs": [
    {
      "job_id": "set1-img1",
      "set_id": "set1",
      "slot": 1,
      "image_form": "single",
      "prompt": "完整生图提示词",
      "size": "1568x672",
      "quality": "low",
      "output": "/tmp/onion-ad/<request_id>/renders/set1-img1.png",
      "references": [],
      "depends_on": []
    }
  ]
}
```

Dependency rules:

- Single: `depends_on=[]`.
- Double: `setN-img2.depends_on=["setN-img1"]`.
- Triple: `setN-img2` and `setN-img3` both depend on `setN-img1`; branches can run concurrently after base exists.

Failure handling:

- Default local concurrency is 6.
- On `429 / rate limit / timeout / 5xx`, the current failed jobs retry once at fallback concurrency 3.
- Failed sets stay in `failed_sets`; completed sets remain available for selection.
- Existing non-empty output files are skipped on resume.

## Validation Before Paid Calls

Before paid rendering, run the exact planned prompt/size/reference/output combination with `--validate-only`. A valid result proves:

- prompt is non-empty;
- `render_size` is syntactically valid;
- output path is writable enough to resolve;
- all reference paths exist;
- asset references resolve from plugin root or skill root.

## Failure Handling

- Base image failure invalidates that set; do not render branches.
- Branch failure affects only that branch; keep the base for inspection.
- Moderation failure means rewrite prompt language, usually by softening emotion and removing risky promises.
- Missing reference path means fix asset selection before retrying.
