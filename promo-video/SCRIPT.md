# FastAPI Startkit — Promo Script

Format: 1920x1080, 30fps, 155s, no voiceover. On-screen text, code cards, terminals and a browser window, over an original synthesized soundtrack (120 BPM, a half-time intro that builds to a drop at 0:36) (`music/generate.py` → `public/music.mp3`).

| # | Scene | Time | On screen |
|---|---|---|---|
| 1 | Python · FastAPI | 0:00–0:07 | "FastAPI makes the first endpoint easy" / "Async, typed and fast. One file gets you an API." A hello-world `main.py`, then "Then the app grows:" with chips: Logging, Environment & .env, Database, Tests, Frontend. |
| 2 | Sound familiar? · Logging | 0:07–0:16 | "A page of setup for one logger" / "And it still can't post to Slack." A stdlib `logging` setup in `app/logger.py` (formatter, `StreamHandler`, `FileHandler`), then three question chips: "Send errors to Slack?", "Add another channel?", "A new log file every day?" |
| 3 | Sound familiar? · Environment | 0:16–0:25 | "Where did my .env go?" `app/settings.py` with `load_dotenv()` and `os.getenv`, `tests/conftest.py` loading `.env.test` by hand. Questions: "DATABASE_URL is None?", "load_dotenv() in every file?", "Which .env do tests read?" |
| 4 | Indie hacker | 0:25–0:31 | "Are you an indie hacker?" / "You want full-stack batteries, without leaving FastAPI and Python." Chips: Async ORM & migrations, Artisan CLI, Testing, Vite + Inertia, AI agents. |
| 5 | Hook | 0:31–0:36 | "Introducing fastapi-startkit", then the headline "Full-stack productivity for FastAPI". Subtitle "A modular, provider-driven framework for Python." |
| 6 | 01 · Create a project | 0:36–0:42 | Three install cards. macOS / Linux: `/bin/bash -c "$(curl -fsSL https://fastapi-startkit.github.io/install.sh)"`. Windows: `powershell -ExecutionPolicy ByPass -c "irm https://fastapi-startkit.github.io/install.ps1 \| iex"`. With uv: `uvx fastapi-startkit@latest init`. |
| 7 | 02 · Interactive installer | 0:42–0:54 | "Start small: just the web app". Terminal running `uvx fastapi-startkit@latest init`. The real boxed prompts (`src/installer-prompts.json`) answer `my-app` and the Web service, move from the SQLite default up to None for the database, and keep None for the frontend. Then `Application: web; database: none; frontend: none`, the 24 `create ...` lines, `Dependency: fastapi-startkit[fastapi]==0.67.0`, the confirm prompt, "Your application is ready." and `Run: uv run python artisan serve`. |
| 8 | 03 · Run it | 0:54–1:02 | One terminal: `uv run python artisan serve` with `Starting Uvicorn server on 127.0.0.1:8000 [bootstrap.application:app]...` and the Uvicorn reload-mode startup lines. A browser window loads `127.0.0.1:8000` and shows the raw JSON `{"message":"Welcome to FastAPI Startkit"}`; the terminal logs `"GET / HTTP/1.1" 200 OK`. No `npm run dev`, because there is no frontend yet. |
| 9 | 04 · Application | 1:02–1:11 | "Everything is a provider". The generated `bootstrap/application.py` with only `(LogProvider, LoggingConfig)` and `(FastapiProvider, FastAPIConfig)`. Next to it, an `AppProvider(Provider)` with `register()` binding `billing` into the container and `boot()` resolving it. |
| 10 | 05 · Logging | 1:11–1:20 | "Channels, not handlers". `config/logging.py` with `stack` → daily, terminal and slack, plus a `slack` channel (`#alerts`, `SLACK_TOKEN`, `level="error"`). `app/orders.py` calls `Logger.info` and `Logger.error`; `tail -f storage/logs/2026-10-29.log` shows both lines with file and line number. |
| 11 | 06 · Routing | 1:20–1:28 | `routes/web.py`: `guest = Router()`, `auth = Router(dependencies=[Depends(auth)])`, `auth.resource("organizations", organizations_controller)`. The seven resource routes fan out using `{organization}` parameters. |
| 12 | 07 · Add a database | 1:28–1:40 | "One command adds a provider". Terminal: `uv run python artisan db:install` with its real output and next steps, then `uv add "fastapi-startkit[database,sqlite]"` with uv's resolve/install lines (`+ aiosqlite`, `+ faker`, `+ greenlet`, `+ sqlalchemy`). Beside it, `bootstrap/application.py` after the command, with the two new imports and `(DatabaseProvider, DatabaseConfig)` highlighted. |
| 13 | 08 · Model & migration | 1:40–1:52 | Terminal: `uv run python artisan db:make:model Post --migration` ("Model created: app/Post.py", "Migration file created: ..._create_posts_table.py"), then `db:migrate` ("Migrating:" / "Migrated: ... (0.00s)"). Cards: the generated migration with `table.string("title")` and `table.text("body")` added, and `app/Post.py` with the columns declared as annotated fields (`id: int`, `title: str`, `body: str`), as in the models docs. |
| 14 | 09 · Query it | 1:52–2:02 | `PostsController.index` returning `(await Post.all()).serialize()`, the `/posts` route in `routes/api.py`, and a browser at `127.0.0.1:8000/posts` showing the real JSON row. |
| 15 | 10 · Testing | 2:02–2:11 | "Tests get their own .env". `.env.testing` (`DB_DATABASE=databases/testing.sqlite`, `LOG_CHANNEL=terminal`) and `tests/test_posts.py` using `HttpTestCase` + `RefreshDatabase`; `uv run pytest -v -p no:warnings` shows both tests passing. |
| 16 | 11 · Frontend | 2:11–2:21 | "Add Vite + Inertia when you need them". `bootstrap/application.py` with the React installer's `InertiaProvider`, `ViteProvider` and `ViteConfig` imports and `(ViteProvider, ViteConfig)`, `InertiaProvider` highlighted after the existing providers. `npm run dev` with real Vite 8 + `fastapi-vite-plugin` output, and a browser rendering the React `Home.tsx` stub. |
| 17 | 12 · AI agents | 2:21–2:29 | `SupportAgent(Agent)` with `@provider("openai")`, `instructions()`, `tools()` and `schema()` returning a pydantic `OrderStatus`. Usage: `await SupportAgent().prompt(...)`, `response["structured_response"]` and `with SupportAgent.fake(['{"order_id": 1042, "status": "shipped"}'])`. |
| 18 | CTA | 2:29–2:35 | "Build your next FastAPI app faster." `uvx fastapi-startkit@latest init`, `fastapi-startkit.github.io` and `github.com/fastapi-startkit/fastapi-startkit-framework`. |

Sources:

- Installer output and generated files: a real `fastapi-startkit init --app web --database none --frontend none` run.
- Run it, Logging, Add a database, Model & migration, Query it and Testing: a real session in that generated app (`artisan serve`, `db:install`, `uv add`, `db:make:model Post --migration`, `db:migrate`, `curl /` and `/posts`).
- Frontend providers: the `bootstrap/application.py` that `init --frontend react` generates.
- Prompt boxes: recorded from `installer.prompts.Prompter` with `color=False, width=64`.
- `db:install` next steps: `console/install_command.py` and the database install command.
- Migration lines: the masoniteorm migration commands.
- AI snippet: executed against the package's fake.

## Render

```bash
cd promo-video
npm install
npm run render -- --concurrency=4
npm run thumbnail
```

`npm run thumbnail` writes the 1280x720 YouTube thumbnail to `out/thumbnail.png`.
