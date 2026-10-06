---
title: Architectural Decision Records
description: This file contains the index of ADR along with the date with the implementation detail in abstract. So that agent can only read these index without need of reading the whole file.
---

| Index | Date | Title | Abstract (Explain how and why) |
|-------|------|-------|--------------------------------|
| [001](001-explicit-config-exports.md) | 2026-10-06 | Explicit re-export of AppConfig | `py.typed` makes implicit re-exports private, triggering basedpyright `reportPrivateImportUsage`; `config/__init__.py` now declares `__all__ = ["AppConfig"]`. |
| [002](002-handle-command-return-type.md) | 2026-10-06 | handle_command returns exit code | `handle_command` returned `None`, so artisan scripts needed an `isinstance` guard flagged by `reportUnnecessaryIsInstance`; `ConsoleApplication.handle` and `Application.handle_command` now return `int` and artisan calls `sys.exit(app.handle_command())`. |
