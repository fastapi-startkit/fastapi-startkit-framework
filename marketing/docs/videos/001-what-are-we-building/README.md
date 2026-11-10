# 001 · What are we building?

Lesson: [01 · What are we building?](https://fastapi-startkit.github.io/tutorials/issue-tracker/01-what-are-we-building)
App state: tag `lesson-13` of `fastapi-startkit/issue-tracker` (the finished app), checked out at `/tmp/issue-tracker`.

No code is typed in this lesson. The episode opens with what the series builds, its stack and the test-first approach, then shows the finished app and the three ideas the course rests on.

| Take | On screen | Lesson section |
|---|---|---|
| `welcome` | The seeded APP board on `/projects/2/board` (no WEB cards, so the `curl` take's WEB-2 stays new), the cursor following the narration, while the series, the domain, the stack (FastAPI, async ORM, Vue through Inertia) and test-first are introduced | Issue Tracker |
| `curl` | The lesson's `curl` creates `WEB-2` against a live server (users, projects and `WEB-1` are seeded off camera) | Issue Tracker |
| `board` | `/projects/1/board`: add an issue, move it to In Progress, show only the allowed next steps | Issue Tracker, The workflow |
| `ideas` | `bootstrap/application.py` providers, `config/issues.py`, `uv run python artisan`, the four migrations | Three ideas, The data |

## Files

| Path | What |
|---|---|
| `episode.json` | Script and manifest: takes in order, each beat's cue, offset and narration line |
| `takes.py` | What each take does on screen, its tag and its off-camera setup |
| `recordings/<take>.cues.json` | Seconds into the take at which each cue happened |
| `recordings/frames/` | Stills captured during recording, for review |
| `narration/<take>-NN.txt` | The line each narration beat is voiced from |
| `thumbnail.png` | YouTube thumbnail, 1280x720 |
| `thumbnail-frame.png` | Mobile app board at 0:03 of the episode, cropped to 1320x560, behind the thumbnail title |

Local only (gitignored): `001-what-are-we-building.mp4`, the final episode (1920x1080 30fps H.264 + AAC 48kHz, 157.5s); `recordings/<take>.mp4` and `recordings/<take>.narrated.mp4`; and `narration/<take>-NN.wav`.

## Render

From the repository root, after `npm --prefix marketing/remotion install`:

```bash
npm --prefix marketing/remotion run video marketing/docs/videos/001-what-are-we-building             # all takes, or name some: ... curl board
npm --prefix marketing/remotion run thumbnail marketing/docs/videos/001-what-are-we-building
```

`video` runs `record.py` then `narrate.py` from `marketing/vscode-recordings/`. `narrate.py` only calls the voice API for beats whose `.wav` is missing or whose line changed. It needs `OPEN_ROUTER_KEY` or `GEMINI_API_KEY` in the environment or in `marketing/.env`.
