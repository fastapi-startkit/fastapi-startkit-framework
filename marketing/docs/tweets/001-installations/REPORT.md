# 001 — Installations video

## Source

- Thread: https://x.com/fastapistartkit/status/2118793752303305208
- Fetch result: 7 tweets, stored in `video/thread.json`. The live thread is the script source.
- Docs tweets the live thread does not cover: 002 (installer), 005 (Router / `resource`), 009 (AI agents).

## Takes

The 9 takes were recorded in VS Code (GitHub Dark Default, Dank Mono) against `/tmp/startkit-demo`:

| Take | Seconds | Checked during recording |
|---|---|---|
| intro | 27.9 | app boots |
| providers | 36.1 | `pytest` green |
| logging | 27.5 | `pytest` green |
| database | 30.4 | migration runs, `pytest` green |
| posts | 40.2 | `curl /posts` returns JSON |
| testing | 32.2 | `pytest` green |
| frontend | 22.8 | `pytest` green |
| hot-reload | 11.5 | edited heading reloads in the browser |
| install | 24.1 | installer finishes |

A silent preview (all takes joined, 4:13) was sent to the user. Approval is pending.

## Narration

- Voice: `google/gemini-3.8-flash-tts` through OpenRouter, voice Charon, style sent as `instructions`.
- Levelling: -19 dB mean per clip, with a -1.5 dB peak limit.
- Status: 3 of 25 clips were voiced before the Gemini daily quota ran out. The remaining clips will be voiced through OpenRouter.

## Output

- Target: `001-installations.mp4`. It is rendered locally and never committed.
- Commands, run from `marketing/docs/tweets/recorder`:
  - `uv run --script narrate.py ../001-installations/video voice`
  - `uv run --script record.py ../001-installations/video`
  - `uv run --script narrate.py ../001-installations/video` (prints ffprobe)
