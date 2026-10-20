# 023 — Interactive project scaffolding

Date: 2026-10-19

Status: Proposed; reconciles the onboarding flow with [PR #288](https://github.com/fastapi-startkit/fastapi-startkit-framework/pull/288).

## Problem

Creating an application currently requires users to assemble project initialization, dependencies, and starter files. The proposed onboarding should ask what they are building and generate a matching application.

## Alternatives

- Document a sequence of manual setup commands.
- Implement all scaffolding and prompts in platform-specific shell scripts.
- Provide a Python scaffolding CLI with an optional shell bootstrap for machines without uv.
- Reuse PR #288's standalone Cleo installer, bundled templates, and plan/writer separation, extending its entry flow to create a project before dependencies are installed.

## Decision

Specify a Python scaffolding CLI with one interactive wizard shared by uvx and a future hosted bootstrap. Keep the bootstrap responsible for locating or installing uv and launching the CLI. Offer web, worker, and combined applications, with frontend selection only for web applications.

This record proposes the flow in `docs/fdr/001-project-scafolding.md`. The CLI, template distribution, hosted endpoint, and release automation remain future implementation work. PR #288 also contains only an ADR; it does not implement an installer.

## Relationship to PR #288

Reuse its bare Cleo application, `string.Template` stubs shipped in the wheel, pure generation plan, writer, database selection, and command/packaging tests. The CLI must work without constructing a framework `Application`.

The original PR #288 design called its command `install`, defaults to the current directory, and supports adding files to existing applications. This onboarding proposal keeps `init [directory]` as the new-project command and asks for a destination when omitted. Both commands can share the planner and templates if the existing-project workflow is retained. The `install` name and its feature-addition semantics must be reconciled in that PR before implementation; they are not silently aliases for new-project creation.

The frontend prompt here selects None, React, or Vue; React/Vue imply Inertia + Vite. The original PR #288 design instead selected none/vite/inertia. Its implementation should translate the selected frontend into integrations internally, with a plain Vite option considered separately.

This record replaces the original `022-interactive-install-command.md` with ADR 023 to avoid the ADR 022 number reserved for promo background music in the local promo branch. The starter `application/` exists in that local checkout but is absent from this PR branch; reconcile its availability during integration rather than assuming it is universally missing.

## Implementation design

Expose a proposed `fastapi-startkit init [directory]` command through a package console entry point. Use `uvx fastapi-startkit init [directory]` in onboarding examples because the package and executable share the same name. Resolve the destination before generating files, validate all selections, select templates compatible with the installer release, install only the selected dependencies, and print commands appropriate to the generated application. Support explicit flags for automation without requiring terminal input.

Use `application/` as the baseline and the queue and Inertia examples as references. Generated applications must work outside the monorepo. Keep scaffolding outside core application lifecycle and container abstractions. The shell bootstrap must preserve terminal input for prompts and invoke a versioned installer release.

Bundle the normalized templates under `fastapi_startkit/installer/stubs/`. Separate CLI options, a pure `build_plan`, and a writer. Include an optional database choice (none/sqlite/postgres/mysql, default sqlite). Show files, extras, and dependency commands before writing, and support `--dry-run` and `--no-deps`. Initialize standalone project metadata before running `uv add` for selected extras. Leave frontend dependency installation to the printed next steps, as PR #288 proposes.

Queue support remains gated behind the separate queue ADR and implementation described in PR #288. Do not offer worker/both choices until the queue extra, provider, lifecycle management, and worker command are available; reject explicit worker requests with an actionable error before writing. The queue example alone does not establish that framework support exists.

For `init`, refuse nonempty destinations. If `install` is retained for existing projects, specify its merge behavior separately: preserve existing environment values and user-owned bootstrap code, show create/skip/overwrite actions, and require explicit overwrite authorization. Adding a feature must account for required provider registration before claiming it is usable.

Consider making `application/` reproducible from the shipped templates after comparing its existing files. A drift check should compare deterministic scaffold content, with environment-specific files and lockfile generation handled explicitly.

## Validation plan

For this documentation change, check the proposal against package metadata, starter files, and existing examples, then run `git diff --check`.

Before shipping an implementation, exercise every supported application/frontend combination in temporary directories outside the workspace. Verify generated imports, dependency synchronization, HTTP startup for web applications, worker startup against a test broker, frontend builds, paths containing spaces, noninteractive flags, existing-directory protection, and failure recovery. Validate the bootstrap on macOS and Linux, including machines without uv or Python, before publishing its endpoint.

Follow PR #288's test layers: planner matrix, Cleo `CommandTester`, writer preservation, generated-project smoke checks, and a built-wheel check that confirms both the console script and stubs are present. Cover database choices, queue gating, dry runs, skipped dependency installation, and any retained existing-project workflow.
