# 021 — Promo video built with Remotion

Date: 2026-10-18

## Problem

FastAPI Startkit has no short visual introduction. We need a 60–90 second, 1920x1080, 30fps MP4 with no voiceover that shows the framework's real APIs, and it must be possible to re-render it when those APIs change.

## Alternatives

- **Screen recording of a live editor and terminal.** It looks authentic, but it can't be reproduced, it is hard to edit, and it goes stale whenever the code changes.
- **A video editor timeline (Kdenlive, After Effects).** These produce binary project files that can't be reviewed in a PR and need a GUI to re-render.
- **Motion Canvas.** It is code-driven like Remotion, but it has a smaller ecosystem and its headless rendering is less mature.
- **Remotion (React).** Scenes are TSX components, timing is driven by frame numbers, and `npx remotion render` produces the MP4 headless with Remotion's bundled Chromium and ffmpeg.

## Decision

Use Remotion in a new top-level `promo-video/` directory that is not part of the uv workspace. One `Promo` composition chains nine scenes with `Series`. Scenes are built from three primitives:

- `Title`: animated headline and subtitle
- `CodeCard`: an editor window with a small built-in Python/JS highlighter, with lines revealed in order
- `Terminal`: a typed command followed by its output lines

Every code snippet and command is taken from the codebase:

- `Application(providers=[...])`
- `Provider.register`/`boot`
- `app.bind`/`app.make`
- `@dataclass` config fields using `env()`
- `Router.resource()`
- `Model` with `HasMany["..."]`/`BelongsTo["..."]` and `with_()`
- `uv run artisan db:make:model` and `db:migrate`, using the real output strings
- `Inertia.render`, the `vite()`/`inertia()` Jinja helpers and `fastapi-vite-plugin`

The video ends with a call to action pointing to https://fastapi-startkit.github.io and the GitHub repository.

## Implementation

- `promo-video/SCRIPT.md` holds the storyboard and the timing for each scene.
- `src/Root.tsx` registers the composition at 1920x1080 and 30fps.
- `src/scenes.tsx` holds the scene content.
- `src/components.tsx` holds the primitives and the highlighter.
- `npm run render` writes `out/promo.mp4`, which is committed. If it grows past 20MB, it is attached to the PR instead.

## Validation

- `ffprobe`, using the ffmpeg bundled with Remotion, confirms the duration, resolution and frame rate.
- Still frames from every scene are extracted and checked to make sure they aren't blank and that the text is legible.
