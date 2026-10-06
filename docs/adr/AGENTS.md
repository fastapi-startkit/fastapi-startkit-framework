---
title: Architectural Decision Records
description: This file contains the index of ADR along with the date with the implementation detail in abstract. So that agent can only read these index without need of reading the whole file.
---

| Index | Date | Title | Abstract (Explain how and why) |
|-------|------|-------|--------------------------------|
| [001](001-explicit-config-exports.md) | 2026-10-06 | Explicit re-export of AppConfig | `py.typed` makes implicit re-exports private, triggering basedpyright `reportPrivateImportUsage`; `config/__init__.py` now declares `__all__ = ["AppConfig"]`. |
| [002](002-handle-command-return-type.md) | 2026-10-06 | handle_command returns exit code | `handle_command` returned `None`, so artisan scripts needed an `isinstance` guard flagged by `reportUnnecessaryIsInstance`; `ConsoleApplication.handle` and `Application.handle_command` now return `int` and artisan calls `sys.exit(app.handle_command())`. |
| [003](003-typed-migration-schema.md) | 2026-10-06 | Typed Migration.schema and Blueprint params | `Migration.schema` was inferred as `None`, so `self.schema.create(...)` and chained `table.*` calls were unknown under basedpyright; `Migration` declares `schema: Schema`/`connection: str`, public `Blueprint` params and `Column.name` are annotated, and `foreign_id_for` now passes the resolved column to `foreign_uuid`. |
