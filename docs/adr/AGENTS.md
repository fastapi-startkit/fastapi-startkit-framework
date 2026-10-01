---
title: Architectural Decision Records
description: Index of architectural decisions, their dates, and the reasons for each implementation.
---

Read this index first, then open the records relevant to the change. Before implementation, add or update an ADR explaining the problem, alternatives, decision, implementation, and validation. Keep this index current.

| Index | Date | Title | Abstract |
| --- | --- | --- | --- |
| [001](001-masonite-orm-aftercommit.md) | 2026-10-01 | ORM after-commit callbacks | Queue sync and async callbacks on the active database transaction, defer nested callbacks until the outer commit, and discard callbacks on rollback. |
