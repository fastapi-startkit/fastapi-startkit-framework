# Draft: fastapi-startkit introduction thread

Status: DRAFT, not posted.

Follows the promo video (`promo-video/SCRIPT.md` on `task/promo-video`). Every code card is taken from a video scene and checked against the current framework imports.

Style: one idea per tweet, plain sentences, one emoji at the end, and a code card image under each tweet.

---

## 1/

Introducing fastapi-startkit: full-stack productivity for FastAPI 🚀

Start with a plain web app. Add a database, logging channels, tests, a Vite + Inertia frontend and AI agents when you need them, without leaving Python.

Media: promo video (`promo-video/out/promo.mp4`)

## 2/

One command creates a project. The installer asks what you're building and writes only what you picked ✨

Card:

```bash
uvx fastapi-startkit@latest init
```

## 3/

Everything is a provider. Bind services in `register()`, then resolve them in `boot()` once every provider has registered 📦

Card: `providers/app_provider.py`

```python
from fastapi_startkit.support import Provider

class AppProvider(Provider):
    def register(self) -> None:
        self.app.bind("billing", BillingService)

    def boot(self) -> None:
        billing = self.app.make("billing")
        billing.connect()
```

## 4/

Logging uses channels instead of handlers. Stack daily files, the terminal and Slack, then pick one per environment with `LOG_CHANNEL` 🪵

Card: `config/logging.py`

```python
@dataclass
class LoggingConfig(Config):
    default: str = env("LOG_CHANNEL", "stack")
    channels: dict = field(default_factory=lambda: {
        "stack": StackChannel(channels=["daily", "terminal", "slack"]),
        "daily": DailyChannel(path="storage/logs"),
        "terminal": TerminalChannel(level="info"),
        "slack": SlackChannel(
            channel="#alerts", token=env("SLACK_TOKEN"), level="error"),
    })
```

## 5/

`Router` wraps FastAPI's APIRouter and adds `resource()`. One line gives you all seven CRUD routes 🛣️

Card: `routes/web.py`

```python
from fastapi_startkit.fastapi import Router

guest = Router()
guest.get("/login", session.create)

auth = Router(dependencies=[Depends(auth)])
auth.resource("organizations", organizations_controller)
```

## 6/

Need a database? `artisan db:install` adds the provider for you. Models and migrations come from the CLI, and every query is async ⚡

Card: `app/Post.py` + `posts_controller.py`

```python
class Post(Model):
    id: int
    title: str
    body: str

class PostsController:
    async def index(self):
        posts = await Post.all()
        return posts.serialize()
```

## 7/

Under pytest, `.env.testing` loads on its own. `RefreshDatabase` migrates once and rolls back after every test 🧪

Card: `tests/test_posts.py`

```python
class TestPosts(HttpTestCase, RefreshDatabase):
    def get_application(self):
        from bootstrap.application import app
        return app

    async def test_lists_posts(self):
        await Post.create({"title": "Hello", "body": "From tests"})
        response = await self.get("/posts")
        response.assert_ok()
```

## 8/

Need a frontend? Add the Vite and Inertia providers and write React pages with hot reload. It's still FastAPI underneath 🎨

Card: `bootstrap/application.py`

```python
app = Application(
    providers=[
        (LogProvider, LoggingConfig),
        (FastapiProvider, FastAPIConfig),
        (DatabaseProvider, DatabaseConfig),
        (ViteProvider, ViteConfig),
        InertiaProvider,
    ],
)
```

## 9/

AI agents are classes too. Give them instructions, tools and a pydantic schema, and fake their responses in tests 🤖

Card: `app/agents/support_agent.py`

```python
@provider("openai")
class SupportAgent(Agent):
    def instructions(self) -> str:
        return "You answer questions about customer orders."

    def tools(self):
        return [order_status]

    def schema(self):
        return OrderStatus

with SupportAgent.fake(['{"order_id": 1042, "status": "shipped"}']):
    await SupportAgent().prompt("Where is it?")
```

## 10/

Build your next FastAPI app faster 💫

uvx fastapi-startkit@latest init

📖 https://fastapi-startkit.github.io
⭐ https://github.com/fastapi-startkit/fastapi-startkit-framework
