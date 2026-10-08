---
title: handle_command returns the exit code
date: 2026-10-06
---

## Why

`Application.handle_command` and `ConsoleApplication.handle` discarded the result of `run()`, so they were inferred as returning `None`. The `artisan` entrypoints worked around it with `isinstance(status, int)`, which basedpyright reports as `reportUnnecessaryIsInstance`, and exit codes were lost.

## How

- `ConsoleApplication.handle` returns `self.run()` and is annotated `-> int`.
- `Application.handle_command` returns that value and is annotated `-> int`.
- Every `example/*/artisan` becomes `sys.exit(app.handle_command())`.

## Verification

basedpyright on an artisan script; the existing pytest suite.
