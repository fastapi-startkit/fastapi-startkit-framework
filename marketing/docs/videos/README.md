# Issue Tracker video series

One narrated screencast per lesson of the [Issue Tracker course](https://fastapi-startkit.github.io/tutorials/issue-tracker/), recorded in real VS Code against the real app.

The decision record is [ADR 080](../../../docs/adr/080-issue-tracker-episode-videos.md).

## Pipeline

- **Workspace.** Each take checks out a published tag of `fastapi-startkit/issue-tracker` into `/tmp/issue-tracker`. The neutral path keeps home directories off screen.
- **Editor.** `code serve-web` serves VS Code. Headless Chromium drives it through Playwright at 1920x1080 and records it. The look is in `marketing/vscode-recordings/vscode-settings.json`: the Github theme, Dank Mono 500, and italic keywords.
- **Takes.** `NNN-slug/takes.py` lists the takes. Each one names its tag, any off-camera setup, the file to open, and the on-screen steps.
- **Cues and narration.** Takes log cues as they happen. `episode.json` attaches one narration beat to each cue. `narrate.py` voices each beat, places it at its cue without overlaps, holds the last frame if the voice runs long, and joins the takes.
- **Voice.** `marketing/vscode-recordings/voice.json`: `gemini-3.8-flash-tts`, voice `Charon`. `narrate.py` calls it through OpenRouter when `OPEN_ROUTER_KEY` is set and through the Gemini API otherwise. Each beat is levelled to -19 dB mean and the mix is limited to -1.5 dB peak.
- **Thumbnail.** The `EpisodeThumbnail` Remotion still in `marketing/remotion/` renders `thumbnail.png` from `episode.json` and `thumbnail-frame.png`.

## Layout

```
marketing/docs/videos/NNN-<lesson-slug>/
  episode.json               script + manifest
  takes.py                   on-screen steps
  narration/*.txt            one line per beat (the .wav beside it is local only)
  recordings/*.cues.json     cue times per take (the .mp4 takes are local only)
  recordings/frames/         review stills
  thumbnail.png              YouTube thumbnail
  thumbnail-frame.png        episode frame behind the thumbnail title
  README.md
marketing/vscode-recordings/ workspace.py  studio.py  record.py  narrate.py  voice.json  vscode-settings.json  shell/
marketing/remotion/          video.mjs  thumbnail.mjs  src/ (EpisodeThumbnail)
```

Videos (`*.mp4`, `*.webm`) and voiced beats (`narration/*.wav`) are not committed. The final mp4 is uploaded to YouTube; a fresh checkout re-voices beats on its first render.

## Rendering

From the repository root, after `npm --prefix marketing/remotion install`:

```bash
npm --prefix marketing/remotion run video marketing/docs/videos/001-what-are-we-building           # record every take, voice, join
npm --prefix marketing/remotion run video marketing/docs/videos/001-what-are-we-building curl board # re-record only some takes
npm --prefix marketing/remotion run thumbnail marketing/docs/videos/001-what-are-we-building
```

`video` needs `uv`, `ffmpeg`, the `code` CLI, and `OPEN_ROUTER_KEY` or `GEMINI_API_KEY` in the environment or in `marketing/.env`.

## Validation

- `narrate.py` prints ffprobe output for the final mp4: an H.264 1920x1080 stream and an AAC stream with matching, non-zero durations.
- Review frames in `recordings/frames/` are checked against the lesson.

## Episodes

| # | Folder | Lesson | Tag on screen |
|---|---|---|---|
| 1 | `001-what-are-we-building` | 01 | `lesson-13` (finished app) |
