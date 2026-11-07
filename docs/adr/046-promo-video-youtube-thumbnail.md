# 046 — Promo video YouTube thumbnail

Date: 2026-10-29

## Problem

The promo video (ADRs 043–045) is going on YouTube, which needs a custom thumbnail. A frame grabbed from the video doesn't work: each scene's text is sized for a full-screen 1080p view, so it can't be read at thumbnail size, and no single frame shows both the product name and what the product does.

## Alternatives

- **Export a frame from the Hook scene.** There's nothing new to build, but the subtitle and the underline are too small to read at 320px wide, and nothing says what the framework includes.
- **Design it in an image editor.** This is flexible, but it can't be reviewed in a PR, and it drifts from the video's fonts and colours.
- **A Remotion `Still` composition in the same project.** It reuses the theme, fonts, `Ambient` background and `CodeCard`, so it matches the video, and one command re-renders it.

## Decision

- `src/Thumbnail.tsx` is registered as a `Still` with id `Thumbnail`, at 1280x720. That is YouTube's recommended size (16:9, under 2 MB).
- Left side: a `fastapi-startkit` pill, then the headline "Full-stack" / "FastAPI" (the second line uses the gradient), sized to read at small widths. Under it are chips for what the video shows: ORM, Logging, Testing, Vite + Inertia, AI agents.
- Right side: a slightly rotated `bootstrap/application.py` card with the provider list from the Frontend scene. The Vite and Inertia lines are highlighted. It shows the "everything is a provider" idea, and its code is real.
- `npm run thumbnail` writes `out/thumbnail.png`. That file is tracked next to `out/promo.mp4`.

## Validation

- `npx tsc --noEmit` passes.
- `out/thumbnail.png` is 1280x720 and under 2 MB. The headline is still readable when the image is scaled down to 320x180.
