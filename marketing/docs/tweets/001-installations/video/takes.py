import workspace
from studio import APP_PORT, APP_URL, Studio, Take

VITE_PORT = 5199

BILLING = """class BillingService:
    def connect(self) -> None:
        self.connected = True
"""

PROVIDER_IMPORTS = """from fastapi_startkit.support import Provider

from app.services.billing import BillingService


"""

PROVIDER_REGISTER = """class AppProvider(Provider):
    def register(self) -> None:
        self.app.bind("billing", BillingService)

"""

PROVIDER_BOOT = """    def boot(self) -> None:
        billing = self.app.make("billing")
        billing.connect()
"""

LOGGING_HEAD = """from dataclasses import dataclass, field

from fastapi_startkit.environment import env
from fastapi_startkit.logging.config import (
    DailyChannel,
    LoggingConfig as BaseLoggingConfig,
    SlackChannel,
    StackChannel,
    TerminalChannel,
)


@dataclass
class LoggingConfig(BaseLoggingConfig):
    channels: dict = field(default_factory=lambda: {
"""

LOGGING_CHANNELS = """        "stack": StackChannel(channels=["daily", "terminal", "slack"]),
        "daily": DailyChannel(path="storage/logs"),
        "terminal": TerminalChannel(),
        "slack": SlackChannel(channel="#alerts", token=env("SLACK_TOKEN"), level="error"),
"""

LOGGING_TAIL = "    })\n"

MIGRATION_COLUMNS = """
            table.string("title")
            table.text("body")"""

MODEL_FIELDS = """id: int
    title: str
    body: str"""

CONTROLLER_IMPORTS = "from app.models.Post import Post\n\n\n"

CONTROLLER = """class PostsController:
    async def index(self):
        posts = await Post.all()
        return posts.serialize()
"""

ROUTE_IMPORT = "\nfrom app.http.controllers.posts_controller import PostsController"
ROUTE = '\nrouter.get("/posts", PostsController().index)'

ENV_TESTING = """DB_CONNECTION=sqlite
DB_DATABASE=databases/testing.sqlite
"""

TEST_IMPORTS = """from app.models.Post import Post
from fastapi_startkit.fastapi.testing import HttpTestCase
from fastapi_startkit.masoniteorm.testing import RefreshDatabase


"""

TEST = """class TestPosts(HttpTestCase, RefreshDatabase):
    def get_application(self):
        from bootstrap.application import app

        return app

    async def test_lists_posts(self):
        await Post.create({"title": "Hello", "body": "World"})

        response = await self.get("/posts")

        response.assert_ok()
"""

FRONTEND_IMPORTS = """
from fastapi_startkit.inertia import InertiaProvider
from fastapi_startkit.vite import ViteProvider
from config.vite import ViteConfig"""

FRONTEND_PROVIDERS = """
        (ViteProvider, ViteConfig),
        InertiaProvider,"""

FRONTEND_FILES = [
    "package.json",
    "vite.config.ts",
    "resources",
    "config/vite.py",
    "app/http/controllers/home_controller.py",
]

HEADING = "Welcome to FastAPI Startkit"
NEW_HEADING = "Hello from the startkit demo"


def number(path: str, text: str) -> int:
    return next(index for index, line in enumerate(workspace.read(path).splitlines(), start=1) if text in line)


def last_import(path: str) -> int:
    return max(index for index, line in enumerate(workspace.read(path).splitlines(), start=1) if line.startswith(("from ", "import ")))


def insert_after(path: str, anchor: str, text: str) -> None:
    lines = workspace.read(path).splitlines(keepends=True)
    at = number(path, anchor)
    lines.insert(at, text.lstrip("\n") + "\n")
    workspace.write({path: "".join(lines)})


def insert_after_imports(path: str, text: str) -> None:
    lines = workspace.read(path).splitlines(keepends=True)
    lines.insert(last_import(path), text.lstrip("\n") + "\n")
    workspace.write({path: "".join(lines)})


def append_env(line: str) -> None:
    text = workspace.read(".env")
    workspace.write({".env": text + ("" if text.endswith("\n") else "\n") + line + "\n"})


def sync() -> None:
    workspace.sh("uv sync -q")


def stage_providers() -> None:
    workspace.write({
        "app/services/__init__.py": "",
        "app/services/billing.py": BILLING,
        "providers/app_provider.py": PROVIDER_IMPORTS + PROVIDER_REGISTER + PROVIDER_BOOT,
    })
    insert_after_imports("bootstrap/application.py", "from providers.app_provider import AppProvider")
    insert_after("bootstrap/application.py", "(FastapiProvider, FastAPIConfig),", "        AppProvider,")


def stage_logging() -> None:
    workspace.write({"config/logging.py": LOGGING_HEAD + LOGGING_CHANNELS + LOGGING_TAIL})
    append_env("LOG_CHANNEL=terminal")


def stage_database() -> None:
    workspace.sh("uv run python artisan db:install")
    workspace.sh('uv add -q "fastapi-startkit[database,sqlite]"')
    workspace.sh("uv run python artisan db:make:model Post --migration")
    migration = next((workspace.WORKSPACE / "databases" / "migrations").glob("*_create_posts_table.py"))
    name = str(migration.relative_to(workspace.WORKSPACE))
    insert_after(name, 'table.increments("id")', MIGRATION_COLUMNS.strip("\n"))
    workspace.sh("uv run python artisan db:migrate")


def stage_posts() -> None:
    model = "app/models/Post.py"
    workspace.write({
        model: workspace.read(model).replace("pass", MODEL_FIELDS),
        "app/http/controllers/posts_controller.py": CONTROLLER_IMPORTS + CONTROLLER,
    })
    insert_after_imports("routes/api.py", ROUTE_IMPORT)
    workspace.write({"routes/api.py": workspace.read("routes/api.py").rstrip("\n") + ROUTE + "\n"})


def stage_testing() -> None:
    workspace.write({".env.testing": ENV_TESTING, "tests/test_posts.py": TEST_IMPORTS + TEST})


def stage_frontend() -> None:
    workspace.adopt("react", FRONTEND_FILES)
    workspace.sh('uv add -q "fastapi-startkit[inertia,vite]"')
    workspace.sh("npm install --silent")
    insert_after_imports("bootstrap/application.py", FRONTEND_IMPORTS)
    insert_after("bootstrap/application.py", "AppProvider,", FRONTEND_PROVIDERS.strip("\n"))


def build(*stages) -> None:
    sync()
    for stage in stages:
        stage()


def prepare_intro() -> None:
    build(stage_providers, stage_logging, stage_database, stage_posts, stage_testing, stage_frontend)


def intro(studio: Studio) -> None:
    studio.line(number("bootstrap/application.py", "providers=["), end=False)
    studio.say("joy")
    studio.cue("wired")
    studio.terminal()
    studio.run("uv run python artisan", settle=1.5)
    studio.shot("artisan")
    studio.hold("wired")


def prepare_providers() -> None:
    build()
    workspace.write({
        "app/services/__init__.py": "",
        "app/services/billing.py": BILLING,
        "providers/app_provider.py": PROVIDER_IMPORTS,
    })


def providers(studio: Studio) -> None:
    path = "bootstrap/application.py"
    studio.line(number(path, "(FastapiProvider, FastAPIConfig),"))
    studio.say("everything")
    studio.open("providers/app_provider.py")
    studio.bottom()
    studio.cue("register")
    studio.type(PROVIDER_REGISTER, 0.045)
    studio.hold("register")
    studio.cue("boot")
    studio.type(PROVIDER_BOOT, 0.045)
    studio.save()
    studio.shot("provider")
    studio.hold("boot")
    studio.open(path)
    studio.cue("add")
    studio.line(last_import(path))
    studio.type("\nfrom providers.app_provider import AppProvider", 0.04)
    studio.save()
    studio.line(number(path, "(FastapiProvider, FastAPIConfig),"))
    studio.type("\n        AppProvider,", 0.05)
    studio.save()
    studio.shot("bootstrap")
    studio.hold("add", 0.8)


def prepare_logging() -> None:
    build(stage_providers)
    workspace.write({"config/logging.py": LOGGING_HEAD + LOGGING_TAIL})


def logging(studio: Studio) -> None:
    path = "config/logging.py"
    studio.say("channels")
    studio.line(number(path, "default_factory"))
    studio.cue("stack")
    studio.type("\n" + LOGGING_CHANNELS.rstrip("\n"), 0.035)
    studio.save()
    studio.shot("channels")
    studio.hold("stack")
    studio.open(".env")
    studio.bottom()
    studio.cue("env")
    studio.type("LOG_CHANNEL=terminal", 0.06)
    studio.save()
    studio.hold("env", 0.8)


def prepare_database() -> None:
    build(stage_providers, stage_logging)


def database(studio: Studio) -> None:
    studio.terminal(clear=True)
    studio.cue("install")
    studio.run("uv run python artisan db:install", settle=1.2)
    studio.shot("install")
    studio.hold("install")
    studio.press("ControlOrMeta+k", 0.3)
    studio.cue("extra")
    pyproject = workspace.WORKSPACE / "uv.lock"
    before = pyproject.stat().st_mtime
    studio.run('uv add "fastapi-startkit[database,sqlite]"', settle=0.5)
    studio.until(lambda: pyproject.stat().st_mtime != before, 60)
    studio.wait(1)
    studio.hold("extra")
    studio.press("ControlOrMeta+k", 0.3)
    studio.cue("model")
    studio.run("uv run python artisan db:make:model Post --migration", settle=1.5)
    studio.shot("model")
    studio.hold("model")
    studio.cue("migrate")
    studio.open("create_posts_table")
    migration = next((workspace.WORKSPACE / "databases" / "migrations").glob("*_create_posts_table.py"))
    studio.line(number(str(migration.relative_to(workspace.WORKSPACE)), 'table.increments("id")'))
    studio.type(MIGRATION_COLUMNS, 0.045)
    studio.save()
    studio.terminal(clear=True)
    studio.run("uv run python artisan db:migrate", settle=1.5)
    studio.shot("migrate")
    studio.hold("migrate", 0.8)


def prepare_posts() -> None:
    build(stage_providers, stage_logging, stage_database)
    workspace.write({"app/http/controllers/posts_controller.py": CONTROLLER_IMPORTS})
    workspace.sh("""sqlite3 database.sqlite "insert into posts (title, body, created_at, updated_at) values ('Hello', 'From the startkit demo', datetime('now'), datetime('now'))" """)


def posts(studio: Studio) -> None:
    model = "app/models/Post.py"
    studio.line(number(model, "pass"))
    studio.press("Home", 0.2)
    studio.press("Shift+End", 0.3)
    studio.cue("fields")
    studio.type(MODEL_FIELDS, 0.06)
    studio.save()
    studio.hold("fields")
    studio.open("posts_controller.py")
    studio.bottom()
    studio.cue("async")
    studio.type(CONTROLLER, 0.045)
    studio.save()
    studio.shot("controller")
    studio.hold("async")
    path = "routes/api.py"
    studio.open(path)
    studio.cue("route")
    studio.line(last_import(path))
    studio.type(ROUTE_IMPORT, 0.035)
    studio.bottom()
    studio.type(ROUTE.lstrip("\n"), 0.045)
    studio.save()
    studio.terminal(clear=True)
    studio.run(f"uv run python artisan serve --port {APP_PORT}", settle=0)
    studio.until(lambda: workspace.answers(f"{APP_URL}/health"), 30)
    studio.command("Terminal: Split Terminal")
    studio.wait(1)
    studio.run(f"curl -sS 127.0.0.1:{APP_PORT}/posts", settle=1.2)
    studio.shot("curl")
    studio.hold("route", 1.2)


def prepare_testing() -> None:
    build(stage_providers, stage_logging, stage_database, stage_posts)
    workspace.write({".env.testing": "", "tests/test_posts.py": TEST_IMPORTS})


def testing(studio: Studio) -> None:
    studio.open(".env.testing")
    studio.cue("env")
    studio.type(ENV_TESTING.rstrip("\n"), 0.05)
    studio.save()
    studio.hold("env")
    studio.open("test_posts.py")
    studio.bottom()
    studio.cue("refresh")
    studio.type(TEST, 0.035)
    studio.save()
    studio.shot("test")
    studio.hold("refresh")
    studio.terminal(clear=True)
    studio.cue("green")
    studio.pytest()
    studio.shot("green")
    studio.hold("green", 1.0)


def prepare_frontend() -> None:
    build(stage_providers, stage_logging, stage_database, stage_posts, stage_testing)
    workspace.adopt("react", FRONTEND_FILES)
    workspace.sh('uv add -q "fastapi-startkit[inertia,vite]"')
    workspace.sh("npm install --silent")


def frontend(studio: Studio) -> None:
    path = "bootstrap/application.py"
    studio.line(last_import(path))
    studio.cue("providers")
    studio.type(FRONTEND_IMPORTS, 0.035)
    studio.save()
    studio.line(number(path, "AppProvider,"))
    studio.type(FRONTEND_PROVIDERS, 0.045)
    studio.save()
    studio.shot("bootstrap")
    studio.hold("providers")
    studio.open("vite.config.ts")
    studio.cue("vite")
    studio.wait(4)
    studio.open("Home.tsx")
    studio.shot("home")
    studio.hold("vite", 0.8)


def prepare_hot_reload() -> None:
    build(stage_providers, stage_logging, stage_database, stage_posts, stage_testing, stage_frontend)
    workspace.write({".env": workspace.read(".env").replace("127.0.0.1:8000", f"127.0.0.1:{APP_PORT}")})


def hot_reload(studio: Studio) -> None:
    page = "resources/js/Pages/Home.tsx"
    studio.say("page")
    studio.cue("reload")
    studio.wait(2.2)
    workspace.write({page: workspace.read(page).replace(HEADING, NEW_HEADING)})
    studio.page.get_by_text(NEW_HEADING).wait_for(timeout=10_000)
    studio.shot("reloaded")
    studio.hold("reload", 1.0)


def prepare_install() -> None:
    build()


def install(studio: Studio) -> None:
    studio.command("View: Toggle Maximized Panel")
    studio.terminal(clear=True)
    studio.cue("faster")
    studio.run("uvx fastapi-startkit@latest init my-app", settle=2.5, pace=0.06)
    studio.hold("faster")
    studio.cue("choose")
    studio.press("Enter", 1.4)
    studio.press("Enter", 1.4)
    studio.press("ArrowDown", 0.8)
    studio.press("Enter", 2.2)
    studio.press("Enter", 0.5)
    lock = workspace.WORKSPACE / "my-app" / "uv.lock"
    studio.until(lock.exists, 120)
    studio.wait(1.5)
    studio.shot("ready")
    studio.hold("choose")
    studio.say("ready", 1.2)


TAKES = [
    Take(name="intro", perform=intro, prepare=prepare_intro, open="bootstrap/application.py", panel=0.55),
    Take(name="providers", perform=providers, prepare=prepare_providers, open="bootstrap/application.py", panel=0.86, verify=["uv run pytest -q"]),
    Take(name="logging", perform=logging, prepare=prepare_logging, open="config/logging.py", panel=0.86, verify=["uv run pytest -q"]),
    Take(name="database", perform=database, prepare=prepare_database, open="bootstrap/application.py", panel=0.4, verify=["uv run pytest -q"]),
    Take(
        name="posts", perform=posts, prepare=prepare_posts, open="app/models/Post.py", panel=0.6,
    ),
    Take(name="testing", perform=testing, prepare=prepare_testing, open="tests/test_application.py", panel=0.6, verify=["uv run pytest -q"]),
    Take(name="frontend", perform=frontend, prepare=prepare_frontend, open="bootstrap/application.py", panel=0.86, verify=["uv run pytest -q"]),
    Take(
        name="hot-reload", perform=hot_reload, prepare=prepare_hot_reload, browser="/", zoom=1.6,
        background=[f"npx vite --host 127.0.0.1 --port {VITE_PORT} --strictPort"], ready=[f"http://127.0.0.1:{VITE_PORT}/@vite/client"],
    ),
    Take(name="install", perform=install, prepare=prepare_install, panel=0.5),
]
