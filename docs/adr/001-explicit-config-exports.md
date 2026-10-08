---
title: Explicit re-export of AppConfig from fastapi_startkit.config
date: 2026-10-06
---

## Why

The package ships `py.typed`. Type checkers treat names imported inside a `py.typed` package's `__init__.py` as private unless they are re-exported explicitly. `from fastapi_startkit.config import AppConfig` therefore raises basedpyright `reportPrivateImportUsage`, pushing consumers to import from `fastapi_startkit.config.app`, an implementation module.

## How

- `fastapi_startkit/config/__init__.py` re-exports `AppConfig` and declares `__all__ = ["AppConfig"]`. `AppConfig` is the only public class in the `config` package.
- `fastapi_startkit/__init__.py` already declares `__all__` for `Application`, `ConsoleApplication` and `Config`, so no change is needed there.
- No runtime behaviour or import graph changes.

## Verification

basedpyright on a scratch file importing `AppConfig` from `fastapi_startkit.config`, before and after; the existing pytest suite.
