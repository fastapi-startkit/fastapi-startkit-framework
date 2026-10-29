# 043 — Promo video built with Remotion

Date: 2026-10-29

## Problem

FastAPI Startkit has no short visual introduction. We need a 60–95 second MP4 at 1920x1080 and 30fps, with no voiceover. It should show the framework's real APIs and real command output, and it must be easy to re-render whenever those change. The first cut showed `uv add fastapi-startkit` and `db:make:model`. The actual onboarding path is now `uvx fastapi-startkit@latest init` (or the curl/PowerShell installers) followed by `uv run python artisan db:install`. The cache module and AI agents are also missing from the video.

## Alternatives

- **Screen recording of a live editor and terminal.** It looks authentic, but it can't be reproduced, it's hard to edit, and it goes stale whenever the installer changes.
- **A video editor timeline (Kdenlive, After Effects).** The project files are binary, can't be reviewed in a PR, and need a GUI to re-render.
- **Motion Canvas.** It is code-driven like Remotion, but it has a smaller ecosystem and less mature headless rendering.
- **Remotion (React).** Scenes are TSX components, timing is set by frame numbers, and `npx remotion render` produces the MP4 headless.

## Decision

Use Remotion in a top-level `promo-video/` directory that sits outside the uv workspace. One `Promo` composition chains eleven scenes (93s) with `Series`:

1. Hook
2. Create a project
3. Interactive installer
4. Application
5. Routing
6. Database
7. Console
8. Cache
9. AI agents
10. Frontend
11. Call to action

Scenes are built from three primitives:

- `SceneHeading`: step label, title and caption.
- `CodeCard`: an editor window with a small Python/TS/Jinja highlighter. Lines are revealed in order.
- `ScrollTerminal`: a terminal made of timed blocks (typed commands, output lines, and prompt redraws). It shows only the last N rows, so long output scrolls like a real terminal.

Nothing on screen is invented:

- **Install commands** come from the docs site: `install.sh`, `install.ps1` and `uvx fastapi-startkit@latest init`.
- **Installer prompt boxes** in `src/installer-prompts.json` are recorded by driving the real `installer.prompts.Prompter` (`color=False, width=64`) through a scripted screen and keys. Each redraw is one frame of the prompt.
- **Installer plan and summary lines** are copied from a dry run of `fastapi-startkit init` that picks the web service, SQLite and React.
- **`bootstrap/application.py` and `HomeController`** are the installer-generated files.
- **Console output** is the real `db:install`, `db:make:migration` and `db:migrate` output.
- **Cache and AI snippets** were executed against the package. The AI snippet runs with `SupportAgent.fake`.

`Application(env=...)` is not shown because it is not part of the generated bootstrap.

## Implementation

- `promo-video/SCRIPT.md`: storyboard, per-scene timing and sources.
- `src/Promo.tsx`: the scene list with durations in seconds.
- `src/Root.tsx`: registers the composition at 1920x1080 and 30fps.
- `src/scenes.tsx`: scene content.
- `src/components.tsx`: primitives, with ligatures disabled so `==`, `&&` and `...` render literally.
- `src/highlight.tsx`: the highlighter.
- `npm run render -- --concurrency=4` writes `out/promo.mp4`, which is committed.

## Validation

- `npx tsc -p .` passes.
- `ffprobe` reports h264, 1920x1080, 30fps and 93s.
- `ffmpeg blackdetect` reports no black segments apart from the scene fade-outs.
- A still from every scene is checked for overflow and legibility.
