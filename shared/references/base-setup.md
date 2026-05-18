# Base Setup and Schema Check

This plugin expects one shared Feishu Base as the central database. Core production skills must not create or mutate schema during normal direction/copy/image generation.

## Preferred Team Setup

Use the maintained shared Base:

- Base URL: `https://guanghe.feishu.cn/base/WIoGb0ksnaREvJsPtQCcW8Lsnfg`
- Tables: `directions`, `copies`, `image_groups`, `feedbacks`
- Table ids are stored in `.env.template` and `shared/base_schema.md`.

For team members:

1. Run `lark-cli auth login` with their own Feishu account.
2. Make sure the account is an editable collaborator on the Base.
3. Copy `.env.template` to `~/.onion-ad/.env`.
4. Fill only `LAOZHANG_API_KEY` unless the maintainer changed the Base.

This mode preserves `创建人` correctly because all writes use `--as user`.

## Schema Check

When `onion-help` is asked to check setup or the user provides a Base link, validate:

1. `+base-get` succeeds with `identity=user`.
2. `+table-list` includes exactly the four required business tables.
3. Each table has the expected field names and compatible field types from `shared/base_schema.md`.
4. System fields (`创建人`, `创建时间`, `最后更新时间`) exist and are not treated as writable fields.
5. `image_groups` has attachment fields `图1`, `图2`, `图3`, and `风格参考图_用户上传`.

If the check fails, report missing tables/fields. Do not create schema silently.

## Empty Base Bootstrap

If a maintainer gives an empty Base:

1. Create the four tables first: `directions`, `copies`, `image_groups`, `feedbacks`.
2. Create fields serially, not in parallel.
3. Create link fields after target tables exist:
   - `copies.关联方向` -> `directions`
   - `image_groups.关联方向` -> `directions`
   - `image_groups.关联文案` -> `copies`
   - `image_groups.父图组` -> `image_groups`
4. Create attachment fields only for `image_groups`: `图1`, `图2`, `图3`, `风格参考图_用户上传`.
5. After creation, write the resulting table ids into `.env.template` and ask users to sync their local `~/.onion-ad/.env`.

Use `lark-base` references for exact `+table-create` and `+field-create` payloads. Treat schema creation as setup/admin work, not as a normal skill side effect.

## Why Not Auto-Create in Core Skills

Automatic schema creation during generation is risky:

- It can create duplicate tables when a user points at the wrong Base.
- It can hide permission problems that should be fixed directly.
- Link fields require stable target table ids, so partial creation leaves confusing broken state.
- Normal generation should stay fast and predictable.

The right place is `onion-help` setup diagnostics plus an explicit maintainer-approved bootstrap step.
