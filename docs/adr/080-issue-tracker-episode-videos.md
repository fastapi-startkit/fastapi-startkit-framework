# 080. Issue Tracker episode videos under `marketing/`

Date: 2026-11-10

## Problem

Episode 1 of the Issue Tracker video series ("What are we building?") existed only in an untracked local checkout. Its script lived in `docs/videos/001-what-are-we-building/`, and its recorder lived in `marketing/vscode-recordings/`. The thumbnail's Remotion source lived in a separate repository. Nothing was reviewable or reproducible from the framework repository. The episode folder was also about 23MB, mostly rendered video and voice clips.

## Alternatives

| Option | Why not |
|---|---|
| Keep the series in the repository's top-level `docs/videos/` | `docs/` holds framework decisions and the docs site; marketing material belongs under `marketing/` (as with the tweet videos in ADR 079) |
| Commit everything, including mp4 and wav | About 20MB per episode in a library repository; the final mp4 lives on YouTube |
| Git LFS | A new dependency for contributors, for files that are regenerated anyway |
| Wait for a Remotion `Episode` composition before adding `npm run video` | Blocks the episode on unbuilt work; the recorder already produces the final mp4 |
| **Commit sources only; give `npm run video` to the existing recorder; reuse the thumbnail project as `marketing/remotion/`** | Chosen |

## Design

- **Episode folder.** `marketing/docs/videos/001-what-are-we-building/` holds `episode.json`, `takes.py`, `narration/*.txt`, `recordings/*.cues.json`, the review frames, `thumbnail.png`, `thumbnail-frame.png` and a README.
- **Ignored.** `marketing/docs/videos/.gitignore` ignores `*.mp4`, `*.webm`, `narration/*.wav`, `__pycache__/` and `.DS_Store`. `marketing/vscode-recordings/.gitignore` ignores the VS Code server data, raw browser recordings, tag checkouts and shell history.
- **Recorder.** `marketing/vscode-recordings/` (`workspace.py`, `studio.py`, `record.py`, `narrate.py`, `voice.json`, `vscode-settings.json`, `shell/.zshrc`) is copied unchanged. It is the shared tooling for every episode.
- **npm entry point.** `marketing/remotion/` is a standalone npm project with exact pins: Remotion 4.0.533 and React 18.3.1.
  - `npm run video <episode dir> [take ...]` runs `uv run record.py` and then `uv run narrate.py` in `marketing/vscode-recordings/`.
  - `npm run thumbnail <episode dir>` renders the `EpisodeThumbnail` still.
  - Both resolve the folder against `INIT_CWD`, so `npm --prefix marketing/remotion run video marketing/docs/videos/001-what-are-we-building` works from the repository root.
- **Voice.** On a fresh checkout, `narrate.py` voices every beat once, because voices are cached by the `.txt` line beside each `.wav`. After that it only re-voices changed lines.
- **Tweet videos.** `marketing/docs/tweets/recorder/` (ADR 079, PR #370) is a modified copy of this recorder, tuned for `/tmp/startkit-demo`. It is left as it is, and folding it into `marketing/vscode-recordings/` is a follow-up.

## Implementation

- `marketing/docs/videos/README.md`, `marketing/docs/videos/.gitignore`, and `marketing/docs/videos/001-what-are-we-building/`.
- `marketing/vscode-recordings/`.
- `marketing/remotion/` (`package.json`, `package-lock.json`, `video.mjs`, `thumbnail.mjs`, `src/`, and the JetBrains Mono fallback fonts).

## Validation

- Run from the repository root, `npm --prefix marketing/remotion run thumbnail marketing/docs/videos/001-what-are-we-building` reproduces the committed `thumbnail.png` byte for byte.
- With the local takes and voice clips in place, `narrate.py` (the second half of `npm run video`) rebuilds the 157.5s episode without an API key. ffprobe shows H.264 1920x1080 and AAC 48kHz streams of equal length.
- `npm run video` with a missing folder fails in `record.py` on the missing `takes.py`. This shows that paths are resolved from the caller's directory.
- The committed files contain no home paths, usernames, emails or keys.
