# 001 — Installations video

## Source

- Thread: https://x.com/fastapistartkit/status/2118793752303305208
- Fetch result: 7 tweets, stored in `video/thread.json`. The live thread is the script source.
- Docs tweets the live thread does not cover: 002 (installer), 005 (Router / `resource`), 009 (AI agents).

## Takes

The 9 takes were recorded in VS Code (GitHub Dark Default, Dank Mono) against `/tmp/startkit-demo`:

| Take | Seconds | Checked during recording |
|---|---|---|
| intro | 25.7 | plain FastAPI `main.py`, then `artisan` lists commands |
| providers | 21.2 | fresh provider list (logging, FastAPI) |
| logging | 29.5 | `pytest` green |
| database | 35.6 | migration runs, `pytest` green |
| posts | 41.0 | `curl /posts` returns JSON |
| testing | 34.8 | `pytest` green |
| frontend | 25.9 | `pytest` green |
| hot-reload | 14.7 | edited heading reloads in the browser |
| install | 27.2 | installer finishes |

The narrated video (4:20) was previewed in Remotion and approved by the user.

## Narration

- Voice: `google/gemini-3.8-flash-tts` through OpenRouter, voice Charon, style sent as `instructions`.
- Levelling: -19 dB mean per clip, with a -1.5 dB peak limit.
- Status: all 24 clips voiced; `narration/leveled/` and `timeline.json` feed the Remotion preview.

## Output

- Target: `001-installations.mp4`. It is rendered locally and never committed.
- Commands, run from `marketing/docs/tweets/recorder`:
  - `uv run --script narrate.py ../001-installations/video voice`
  - `uv run --script record.py ../001-installations/video`
  - `uv run --script narrate.py ../001-installations/video timeline`
- Then, from `marketing/docs/tweets/remotion`:
  - `npm run preview ../001-installations/video` to watch in Remotion Studio
  - `npm run render ../001-installations/video` to write `video/001-installations.mp4`
