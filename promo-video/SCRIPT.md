# FastAPI Startkit — Promo Script

Format: 1920x1080, 30fps, about 82s, no voiceover. On-screen text, code cards and terminals only.

| # | Scene | Time | On screen |
|---|---|---|---|
| 1 | Hook | 0:00–0:06 | Headline "Laravel-style productivity for FastAPI". Subtitle "A modular, provider-driven framework for Python." |
| 2 | Install | 0:06–0:12 | Terminal: `uv add fastapi-startkit`. Caption: "One package. Optional extras: [fastapi] [database] [vite]." |
| 3 | Providers & container | 0:12–0:23 | Code card `bootstrap/application.py`: `Application(base_path=..., providers=[LogProvider, (DatabaseProvider, DatabaseConfig), FastAPIProvider, ViteProvider, InertiaProvider])`, then a `Provider` with `register()` binding into the container and `boot()` resolving with `self.app.make(...)`. Caption: "Two-phase boot: register, then boot." |
| 4 | Config | 0:23–0:32 | Code card `config/redis.py`: `@dataclass class RedisConfig` with `host: str = env("REDIS_HOST", "localhost")` and `port: int = env("REDIS_PORT", 6379)`. Then `Config.get("redis.host")`. Caption: ".env + .env.{APP_ENV}, typed dataclasses." |
| 5 | Router | 0:32–0:42 | Code card `routes/web.py`: `guest = Router()` and `auth = Router(dependencies=[Depends(auth)])`, with `auth.resource("organizations", organizations_controller)`. A route list fans out: index, create, store, show, edit, update, destroy. |
| 6 | Async ORM | 0:42–0:53 | Code card `app/Organization.py`: `class Organization(Model)` with `contacts = HasMany["Contact"](...)`, plus `Contact.organization = BelongsTo["Organization"](...)`, then `await Organization.with_("contacts").where("city", "Kathmandu").get()`. Caption: "Async-first ORM on SQLAlchemy." |
| 7 | Artisan CLI | 0:53–1:03 | Terminal: `uv run artisan db:make:model Post` prints `Model created: app/Post.py`. Then `uv run artisan db:migrate` prints `Migrating:` and `Migrated:` lines. |
| 8 | Inertia + Vite | 1:03–1:14 | Split view. Left: a controller returning `Inertia.render("Organizations/Index", {...})`. Right: the template with `{{ vite('resources/js/app.tsx') }}` and `{{ inertia(page) }}`, and `vite.config.js` using `fastapi-vite-plugin`. Caption: "React/Vue pages, no API boilerplate." |
| 9 | CTA | 1:14–1:22 | "Build your next FastAPI app faster." Links: `fastapi-startkit.github.io` and `github.com/fastapi-startkit/fastapi-startkit-framework`. Also `uv add fastapi-startkit`. |

All snippets come from `example/inertia-pingcrm-app`, `AGENTS.md`, the masoniteorm command sources and the ORM test fixtures.

## Render

```bash
cd promo-video
npm install
npm run render
```
