# 045 — Promo video provider-first flow

Date: 2026-10-29

## Problem

The promo video (ADRs 043 and 044) installs everything up front: the installer picks SQLite and React, and "Run it" starts both `artisan serve` and `npm run dev`. That hides the framework's main idea, which is that features are providers you add when you need them. A first run with no frontend also shouldn't need Node.js at all. The video also opens on the product name, before it shows the viewer a problem worth solving.

## Alternatives

- **Keep the full install and explain providers in one scene.** This is the shortest change, but viewers only hear the provider idea instead of seeing it.
- **Start with the smallest app and add features through their providers.** The installer answers None for the database and frontend. Each later scene adds one provider, using the real command where one exists. The video gets longer, but each step stands on its own.

## Decision

- The installer prompts were re-recorded with `Prompter(color=False, width=64)`. The database prompt moves from the SQLite default up to None. The frontend prompt keeps None. The created files, the summary (`Application: web; database: none; frontend: none`) and the dependency line (`fastapi-startkit[fastapi]==0.67.0`) come from a real `init --app web --database none --frontend none` run.
- "03 · Run it" has one terminal running `artisan serve`. The browser shows the raw JSON from `/`. There is no `npm run dev`.
- "04 · Application" shows the generated bootstrap with only `LogProvider` and `FastapiProvider`.
- New scenes, all captured from a real session in the generated app:
  - "06 · Add a database": `db:install`, then `uv add "fastapi-startkit[database,sqlite]"`. The bootstrap is shown with `DatabaseProvider` appended after `FastapiProvider`, and the new lines are highlighted.
  - "07 · Model & migration": `db:make:model Post --migration`, the edited migration and model, then `db:migrate`.
  - "08 · Query it": a `PostsController` that awaits `Post.all()`, the `/posts` route, and a browser showing the real JSON response.
- These replace the old ORM and Artisan scenes.
- "11 · Frontend" replaces the Cache scene and comes right after Testing, so the steps go Testing, Frontend, then "12 · AI agents". It adds `ViteProvider` and `InertiaProvider` to the bootstrap, then runs `npm run dev` and shows the browser rendering the React Home page. There is no frontend install command, so the scene shows the providers being registered, using the bootstrap that `init --frontend react` generates.
- A context scene opens the video. "Python · FastAPI" shows the familiar hello-world `main.py`, then "Then the app grows:" with chips for logging, environment, database, tests and frontend. Viewers who haven't used FastAPI learn what it is before the problems start.
- Three problem scenes follow it, before the hook. Each one shows the plain-Python way, then asks the questions the framework answers:
  - "Sound familiar? · Logging": a stdlib `logging` setup with a formatter, a `StreamHandler` and a `FileHandler`. The questions: Slack, another channel, a file per day. These map to the framework's `slack`, `stack` and `daily` channels. Trimming old log files was left out, because `DailyChannel` has no retention setting.
  - "Sound familiar? · Environment": `load_dotenv()` and `os.getenv` in `settings.py`, plus a `conftest.py` that loads `.env.test` by hand. The questions: a variable that is `None`, `load_dotenv()` in every file, and which `.env` tests read. These map to `env()` in config dataclasses and the automatic `.env.testing` under pytest.
  - "Are you an indie hacker?": the full stack without leaving FastAPI and Python, with chips for the features the video goes on to show.
- The hook now reads "Introducing fastapi-startkit". The footer brand line stays hidden until the hook ends, so it never gives away the name early. The progress bar runs from the first frame.
- Two scenes answer the problem slides, using code from the logging and FastAPI testing docs that was run in the demo app:
  - "05 · Logging" (after Application): `config/logging.py` stacks the daily, terminal and slack channels. `app/orders.py` logs with `Logger`, and `tail -f` shows the real daily-file lines. The Slack driver still looks up channels with Slack's retired `channels.list` API, so error logs to Slack fail. That fix is being handled separately, and the scene shows only the config and the file output.
  - "10 · Testing" (after Query it): `.env.testing` plus an `HttpTestCase` + `RefreshDatabase` test for `/posts`, and the real `pytest -v` output. The run uses `-p no:warnings` because pytest-asyncio prints deprecation warnings for the framework test case's fixtures.
  - The later steps are renumbered 06–12.
- `CodeCard` gains a `highlight` prop for marking lines that were added.
- The Cache scene is removed, and so is the Cache chip on the indie-hacker slide (Testing takes its place). The video is now 18 scenes and 155s.
- The music stays at 120 BPM and uses one palette throughout: saw pads, an FM electric-piano arpeggio, a sine bass and synthesized drums. The intro (up to the drop at 36s) plays the arpeggio in eighths with a sustained bass. From the problem slides on, a light half-time beat joins. The arpeggio, kick and clap feel slower than the main part, and the intro plays about 3 dB quieter. During the hook, the beat drops out, and a band-passed noise riser and a clap roll (up to sixteenths) build. The chord order is counted back from the drop, so the intro ends on G and resolves to Am at the drop. The full groove starts there, with the same arpeggio in sixteenths. `generate.py` takes the drop time as a third argument. An earlier 75 BPM intro with a square-wave pluck was rejected because it sounded slow and boring and didn't match the main part.

## Validation

- `npx tsc --noEmit` passes.
- Stills from every new or changed scene show the full terminal command and the highlighted lines, and no card overlaps another.
- `npm run render` produces `out/promo.mp4` with H.264 video and AAC audio, and its duration is 155s.

## Regenerating the music

```bash
cd promo-video
uv run --no-project --with numpy --with scipy python music/generate.py /tmp/music.wav 155 36
ffmpeg -y -i /tmp/music.wav -codec:a libmp3lame -b:a 192k public/music.mp3
```
