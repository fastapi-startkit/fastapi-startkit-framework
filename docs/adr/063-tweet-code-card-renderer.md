# 063 — Tweet code card renderer

Date: 2026-11-06

## Problem

Tweet threads in `docs/tweets/` need code card images in one consistent style: a dark code card on a blue background. Making them by hand in a screenshot tool drifts between cards and has to be redone whenever the code changes.

## Alternatives

- Screenshot tools (Carbon, ray.so): manual, and the result can't be rebuilt from source.
- HTML template + headless browser: pixel-perfect CSS, but it needs Playwright and a browser download.
- Pillow + Pygments script: two small pure-Python dependencies, deterministic output.

## Decision

`docs/tweets/render.py` is a PEP 723 script (`uv run docs/tweets/render.py <thread-dir>`). For every file in `<thread-dir>/cards/`, it picks a Pygments lexer from the file extension, colours the tokens and draws a 1600x900 PNG to `<thread-dir>/images/<stem>.png`.

The font size shrinks from 40px until the card fits the canvas. Code uses Dank Mono from the local font folders (`~/Library/Fonts`, `/Library/Fonts` or `TWEET_FONT_DIR`), with keywords and comments in its italic cut. Dank Mono is a paid font and is not committed. When it is missing, the script falls back to the bundled JetBrains Mono (OFL).

Each `NNN-thread.md` holds only the text to post and a link to its image.

## Validation

All cards in `docs/tweets/001-installations` were rendered and checked by eye.
