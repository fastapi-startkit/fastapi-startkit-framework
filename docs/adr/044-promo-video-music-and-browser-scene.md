# 044 — Promo video soundtrack and "Run it" browser scene

Date: 2026-10-29

## Problem

The promo video (ADR 043) is silent, and it never shows the generated application running. Viewers see code and terminals but not the result in a browser.

## Alternatives

- **A royalty-free track from a library (Pixabay, YouTube Audio Library, Free Music Archive).** These sound good, but every library has its own license terms and attribution rules, the file can't be reviewed in a PR, and the track length doesn't match the scene cuts.
- **A procedurally synthesized track checked in with its generator.** It is original, so there is nothing to license or attribute. It can be regenerated at any length and timed to the scenes. The trade-off is a simpler sound than a produced track.
- **A screen recording of the browser.** It doesn't match the rest of the video's style and goes stale when the Home page stub changes.
- **A browser window drawn in TSX.** It uses the same chrome and theme as the terminal and code cards, and it renders the Home page from the React installer stub.

## Decision

- `promo-video/music/generate.py` synthesizes an original 120 BPM A-minor track (Am–F–C–G) with numpy and scipy. Layers: a detuned saw pad, a sixteenth-note pluck arpeggio with echo, an eighth-note bass, and kick/clap/hat drums with kick sidechain ducking on the pad and bass. It has an intro of two bars without drums (the hook), a breakdown in bars 24–25, double-time hats from bar 26, and a three-bar outro on a held Am chord under the CTA. The output is encoded to `promo-video/public/music.mp3`.
- `Promo` plays the track with `Html5Audio` at volume 0.55. The volume fades in over the first second and out over the last two.
- A new `RunInBrowser` scene ("03 · Run it", 11s) is inserted right after the interactive installer, so the app the installer just generated is shown running before the tour of its code; the later steps are renumbered 04–10. Two stacked terminals run the two dev processes the installer tells you to start. The first types `uv run python artisan serve` and prints the serve command's `Starting Uvicorn server on 127.0.0.1:8000 [bootstrap.application:app]...` line, followed by uvicorn's reload-mode startup lines. The second types `npm run dev` and prints Vite 8's banner plus the `fastapi-vite-plugin` block (`FASTAPI  plugin v0.0.3`, `APP_URL: http://127.0.0.1:8000`), captured from a real run in `example/inertia-pingcrm-app` with the port and `APP_URL` set to the generated app's defaults. `ScrollTerminal` gains an optional `title`. A `BrowserWindow` component then slides in over the right side of both: it types `127.0.0.1:8000`, shows a loading bar, and renders the `Home.tsx` stub ("Welcome to FastAPI Startkit" / "Your React application is ready." / "Explore the API" in emerald-700). The terminal then logs `"GET / HTTP/1.1" 200 OK`.
- The per-scene radial gradient in `Backdrop` is replaced by one `Ambient` layer under the `Series`. It has three slowly drifting glow orbs (green, sky, purple), a 64px grid that drifts and fades out toward the edges, and a vignette. Because it lives at composition level, it flows across scene cuts instead of restarting. A `Footer` overlay shows the brand and the docs URL plus a gradient progress bar for the whole video. It is hidden during the hook and the CTA, which already show the brand. `Backdrop` now only lays out and fades out each scene's content.
- Typography: headlines use Space Grotesk 700 with tight tracking, body and captions use Inter, and code and terminals use JetBrains Mono. Space Grotesk and Inter come from `@remotion/google-fonts`. JetBrains Mono is bundled in `public/fonts/` (OFL, license alongside) because the Google subset lacks the box-drawing, `●`/`○`/`›` and `➜` glyphs the installer prompts and Vite output need. With fallback glyphs those lines came out misaligned. Step labels became mono pills with a green glow, and the "FastAPI" accents in the hook and CTA use a green-to-sky gradient.
- `Backdrop` centers each scene's content vertically, and two-column rows center the shorter card against the taller one. Every panel has a fixed height, so centering never shifts content while lines animate in.
- The video is now 104s.

## Validation

- `npx tsc --noEmit` passes.
- Stills 90 and 170 frames into the scene show the terminal before the browser appears and the loaded Home page with the request log line.
- A spectrogram of `music.mp3` shows the intro, breakdown and outro at the planned times. The peak level is −2.3 dBFS.
- `npm run render` produces `out/promo.mp4` with an AAC audio stream, and its duration is 104s.

## Regenerating the music

```bash
cd promo-video
uv run --no-project --with numpy --with scipy python music/generate.py /tmp/music.wav 104
ffmpeg -y -i /tmp/music.wav -codec:a libmp3lame -b:a 192k public/music.mp3
```

Pass the new total length in seconds whenever scenes change.
