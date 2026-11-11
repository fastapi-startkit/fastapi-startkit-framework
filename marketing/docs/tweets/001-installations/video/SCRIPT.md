# Build your next FastAPI app faster

Script for the screencast of https://x.com/fastapistartkit/status/2118793752303305208. Each take is recorded in VS Code from `/tmp/startkit-demo`.

## Tweet 1

> FastAPI is a joy for building APIs quickly. But it deliberately leaves the rest of your app up to you: environments, config, logging, database, CLI commands, storage, queues, cache, Redis…
>
> fastapi-startkit wires it all together, so you can focus on your product 🚀

**Take `intro`** opens on a hand-wired plain FastAPI `main.py`, then the fresh Startkit app.

- `joy`: FastAPI is a joy for building APIs quickly. But it deliberately leaves the rest of your app up to you. Environments, config, logging, a database, CLI commands, storage, queues, cache, Redis.
- `wired`: FastAPI Startkit wires all of that together, so you can focus on your product. Here's a fresh app. Let's see how it fits.

## Tweet 2

> Everything is a provider. Bind services in `register()`, then resolve them in `boot()` once every provider has registered 📦

**Take `providers`**

- `everything`: FastAPI Startkit is all about providers. Logging is a provider. FastAPI itself is a provider. Every feature plugs in the same way.
- `lifecycle`: Each one registers its services, then boots once everything is ready. Add a provider to this list, and your app picks it up.

## Tweet 3

> Logging uses channels instead of handlers. Stack daily files, the terminal and Slack, then pick one per environment with `LOG_CHANNEL`

**Take `logging`**

- `channels`: Logging uses channels instead of handlers.
- `stack`: A stack fans out to other channels. Daily files, the terminal, and Slack, but only for errors.
- `env`: Then you pick one per environment with LOG CHANNEL. On my laptop, the terminal is plenty.

## Tweet 4

> Need a database? `artisan db:install` adds the provider for you. Models and migrations come from the CLI, and every query is async ⚡

**Take `database`**

- `install`: Need a database? artisan D B install publishes the config, and adds the provider for you.
- `extra`: Add the database extra, and that's the setup done.
- `model`: Models and migrations come straight from the CLI.
- `migrate`: Give posts a title and a body, then migrate.

**Take `posts`**

- `fields`: The model describes the same fields.
- `async`: And every query is async. Await Post all, serialize it, and that's an endpoint.
- `route`: One route, and we're live.

## Tweet 5

> Under pytest, `.env.testing` loads on its own. `RefreshDatabase` migrates once and rolls back after every test

**Take `testing`**

- `env`: Under pytest, dot env dot testing loads on its own, so tests get their own database.
- `refresh`: RefreshDatabase migrates once, and rolls back after every test. Create a post, get the list, and check it's OK.
- `green`: Run pytest, and we're green.

## Tweet 6

> Need a frontend? Add the Vite and Inertia providers and write React pages with hot reload. It's still FastAPI underneath

**Take `frontend`**

- `providers`: Need a frontend? Add the Vite and Inertia providers.
- `vite`: Vite runs with the FastAPI plugin, React, and Tailwind. Your pages are plain React components.

**Take `hot-reload`**

- `page`: Here's the page, served by FastAPI and rendered with Inertia.
- `reload`: Change it, save, and it hot reloads. No refresh. And it's still FastAPI underneath.

## Tweet 7

> Build your next FastAPI app faster 💫
>
> uvx fastapi-startkit@latest init
>
> 📖 https://fastapi-startkit.github.io
> ⭐ https://github.com/fastapi-startkit/fastapi-startkit-framework

**Take `install`**

- `faster`: So, build your next FastAPI app faster. One command. uvx fastapi-startkit at latest, init.
- `choose`: Pick your services, a database, and a frontend.
- `ready`: And it's ready. The docs and the GitHub repo are linked below. Happy building.
