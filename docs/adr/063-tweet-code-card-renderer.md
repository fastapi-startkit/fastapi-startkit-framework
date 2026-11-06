# 063 — Tweet code card renderer

Date: 2026-11-06

## Problem

Tweet threads in `docs/tweets/` need code card images in one consistent style: a dark code card on a blue background. Making them by hand in a screenshot tool drifts between cards and has to be redone whenever the code changes.

## Alternatives

- Screenshot tools (Carbon, ray.so): manual, and the result can't be rebuilt from source.
- HTML template + headless browser: pixel-perfect CSS, but it needs Playwright and a browser download.
- Pillow + Pygments script: two small pure-Python dependencies, deterministic output.

## Decision

`docs/tweets/render.py` is a PEP 723 script (`uv run docs/tweets/render.py <thread-dir>`). Each card is a folder `<thread-dir>/cards/NNN/` holding the files as they appear in a project, e.g. `cards/003/providers/app_provider.py`. For every file, the script picks a Pygments lexer from the file extension, colours the tokens with Pygments' `github-dark` style and draws a 1600x900 PNG to `<thread-dir>/images/NNN.png`, or `NNN-1.png`, `NNN-2.png`, … when the folder holds several files. The card is a GitHub-dark window with close, minimise and zoom buttons, titled with the file's path relative to the card folder (`Terminal` for shell files), so the folder layout is the only place a file name is written. Pygments leaves method calls and shell commands as plain names, so the script colours a name followed by `(`, and the first word of each shell line, as functions, as GitHub does. It also draws module paths and the `.` in attribute access in the plain text colour. The background is a diagonal gradient between the brand oranges `#a13d17` and `#f27a4c`, with a white dot grid at low opacity. No logo is used: the repository has no fastapi-startkit logo, and the only SVG in the docs theme is another product's icon.

The font size shrinks from 40px until the card fits the canvas. Code uses Dank Mono from the local font folders (`~/Library/Fonts`, `/Library/Fonts` or `TWEET_FONT_DIR`), with keywords and comments in its italic cut. Dank Mono is a paid font and is not committed. When it is missing, the script falls back to the bundled JetBrains Mono (OFL).

Each `NNN-thread.md` holds only the text to post and a link to its image.

## Validation

All cards in `docs/tweets/001-installations` were rendered and checked by eye.
