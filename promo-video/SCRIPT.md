# FastAPI Startkit — Promo Script

Format: 1920x1080, 30fps, 93s, no voiceover. Only on-screen text, code cards and terminals.

| # | Scene | Time | On screen |
|---|---|---|---|
| 1 | Hook | 0:00–0:05 | Headline "Laravel-style productivity for FastAPI". Subtitle "A modular, provider-driven framework for Python." |
| 2 | 01 · Create a project | 0:05–0:11 | Three install cards. macOS / Linux: `/bin/bash -c "$(curl -fsSL https://fastapi-startkit.github.io/install.sh)"`. Windows: `powershell -ExecutionPolicy ByPass -c "irm https://fastapi-startkit.github.io/install.ps1 \| iex"`. With uv: `uvx fastapi-startkit@latest init`. |
| 3 | 02 · Interactive installer | 0:11–0:24 | Terminal running `uvx fastapi-startkit@latest init`. The real boxed prompts (`src/installer-prompts.json`) answer `my-app`, the Web service, SQLite and React. Then the plan (`create ...` lines, `Dependency: fastapi-startkit[database,fastapi,inertia,sqlite,vite]==0.67.0`), the confirm prompt and the closing "Your application is ready." / `uv run python artisan serve` lines. |
| 4 | 03 · Application | 0:24–0:33 | `bootstrap/application.py` exactly as the installer generates it: `Application(base_path=..., config=AppConfig, providers=[(LogProvider, LoggingConfig), (DatabaseProvider, DatabaseConfig), (FastapiProvider, FastAPIConfig), (ViteProvider, ViteConfig), InertiaProvider])`. Next to it, an `AppProvider(Provider)` with `register()` binding into the container and `boot()` calling `self.app.make("inertia").share(...)`. |
| 5 | 04 · Routing | 0:33–0:41 | `routes/web.py`: `guest = Router()`, `auth = Router(dependencies=[Depends(auth)])`, `auth.resource("organizations", organizations_controller)`. The seven resource routes fan out using `{organization}` parameters. |
| 6 | 05 · Database | 0:41–0:50 | `app/models/Organization.py` with `HasMany["Contact"]` / `BelongsTo["Organization"]`, and a controller calling `with_("contacts").where(...).get()` and `query().paginate(page=1, per_page=10)`. |
| 7 | 06 · Console | 0:50–1:02 | Terminal: `uv run python artisan db:install` with its real output (`Created config/database.py`, `Registered DatabaseProvider in bootstrap/application.py`, next steps). Then `db:make:migration create_users_table` ("Migration file created: ...") and `db:migrate` ("Migrating:" / "Migrated: ... (0.00s)"). |
| 8 | 07 · Cache | 1:02–1:11 | `config/cache.py` `CacheConfig(Config)` dataclass, plus `Cache.remember`, `async with Cache.lock(...)` and `Cache.tags("users").put/flush`. |
| 9 | 08 · AI agents | 1:11–1:19 | `SupportAgent(Agent)` with `@provider("openai")`, `instructions()`, `tools()` and `schema()` returning a pydantic `OrderStatus`. Usage: `await SupportAgent().prompt(...)`, `response["structured_response"]` and `with SupportAgent.fake(['{"order_id": 1042, "status": "shipped"}'])`. |
| 10 | 09 · Frontend | 1:19–1:27 | The generated `HomeController` returning `Inertia.render("Home")`, `resources/templates/index.html` (`vite_react_refresh`, `vite`, `inertia_head`, `inertia`) and `vite.config.ts` with `fastapi-vite-plugin`. |
| 11 | CTA | 1:27–1:33 | "Build your next FastAPI app faster." `uvx fastapi-startkit@latest init`, `fastapi-startkit.github.io` and `github.com/fastapi-startkit/fastapi-startkit-framework`. |

Sources:

- Installer output and generated files: `fastapi-startkit init` (dry run) and the installer stubs.
- Prompt boxes: recorded from `installer.prompts.Prompter` with `color=False, width=64`.
- `db:install` next steps: `console/install_command.py` and the database install command.
- Migration lines: the masoniteorm migration commands.
- Cache and AI snippets: executed against the package (the AI snippet runs against the fake).

## Render

```bash
cd promo-video
npm install
npm run render -- --concurrency=4
```
