import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, BrowserWindow, GradientText, CodeCard, SceneHeading, ScrollTerminal, TermBlock, useFadeIn, useRise } from "./components";
import prompts from "./installer-prompts.json";
import { theme } from "./theme";

const row: React.CSSProperties = { display: "flex", gap: 48, alignItems: "center" };

const Question: React.FC<{ text: string; delay: number }> = ({ text, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame: frame - delay, fps, config: { damping: 13 } });
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 20,
        padding: "22px 30px",
        borderRadius: 18,
        border: "2px solid rgba(251,191,36,0.45)",
        background: "rgba(251,191,36,0.08)",
        boxShadow: "0 0 30px rgba(251,191,36,0.12)",
        fontFamily: theme.display,
        fontSize: 40,
        fontWeight: 500,
        opacity: pop,
        transform: `translateX(${(1 - pop) * 60}px) scale(${0.9 + pop * 0.1})`,
      }}
    >
      <span style={{ fontFamily: theme.mono, fontWeight: 600, color: theme.number }}>?</span>
      {text}
    </div>
  );
};

const Questions: React.FC<{ items: string[]; delay: number; gap?: number }> = ({ items, delay, gap = 30 }) => (
  <div style={{ flex: 0.8, display: "flex", flexDirection: "column", gap: 26 }}>
    {items.map((text, index) => (
      <Question key={text} text={text} delay={delay + index * gap} />
    ))}
  </div>
);

const GROWTH = ["Logging", "Environment & .env", "Database", "Tests", "Frontend"];

export const FastapiContext: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const label = useRise(70);
  return (
    <Backdrop>
      <SceneHeading step="Python · FastAPI" title="FastAPI makes the first endpoint easy" caption="Async, typed and fast. One file gets you an API." />
      <div style={row}>
        <CodeCard
          file="main.py"
          style={{ flex: 1 }}
          fontSize={28}
          lines={[
            "from fastapi import FastAPI",
            "",
            "app = FastAPI()",
            "",
            "@app.get(\"/\")",
            "async def index():",
            "    return {\"message\": \"Hello World\"}",
          ]}
        />
        <div style={{ flex: 0.8, display: "flex", flexDirection: "column", gap: 22 }}>
          <div style={{ ...label, fontFamily: theme.display, fontSize: 44, fontWeight: 700 }}>Then the app grows:</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 16 }}>
            {GROWTH.map((item, index) => {
              const pop = spring({ frame: frame - 90 - index * 10, fps, config: { damping: 13 } });
              return (
                <div
                  key={item}
                  style={{
                    padding: "14px 26px",
                    borderRadius: 999,
                    border: "1.5px solid rgba(251,191,36,0.45)",
                    background: "rgba(251,191,36,0.08)",
                    fontFamily: theme.mono,
                    fontSize: 28,
                    opacity: pop,
                    transform: `translateY(${(1 - pop) * 24}px)`,
                  }}
                >
                  {item}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </Backdrop>
  );
};

export const PainLogging: React.FC = () => (
  <Backdrop>
    <SceneHeading step="Sound familiar? · Logging" title="A page of setup for one logger" caption="And it still can't post to Slack." />
    <div style={row}>
      <CodeCard
        file="app/logger.py"
        style={{ flex: 1.2 }}
        fontSize={21}
        perLine={3}
        lines={[
          "import logging",
          "",
          "logger = logging.getLogger(\"app\")",
          "logger.setLevel(logging.DEBUG)",
          "",
          "formatter = logging.Formatter(",
          "    \"%(asctime)s %(levelname)s %(name)s: %(message)s\")",
          "",
          "console = logging.StreamHandler()",
          "console.setLevel(logging.INFO)",
          "console.setFormatter(formatter)",
          "logger.addHandler(console)",
          "",
          "file = logging.FileHandler(\"storage/logs/app.log\")",
          "file.setFormatter(formatter)",
          "logger.addHandler(file)",
        ]}
      />
      <Questions delay={90} items={["Send errors to Slack?", "Add another channel?", "A new log file every day?"]} />
    </div>
  </Backdrop>
);

export const PainEnvironment: React.FC = () => (
  <Backdrop>
    <SceneHeading step="Sound familiar? · Environment" title="Where did my .env go?" caption="load_dotenv() in every entry point, and a separate setup for tests." />
    <div style={row}>
      <div style={{ flex: 1.2, display: "flex", flexDirection: "column", gap: 28 }}>
        <CodeCard
          file="app/settings.py"
          fontSize={22}
          lines={[
            "import os",
            "from dotenv import load_dotenv",
            "",
            "load_dotenv()",
            "",
            "DATABASE_URL = os.getenv(\"DATABASE_URL\")",
            "DEBUG = os.getenv(\"DEBUG\", \"false\") == \"true\"",
          ]}
        />
        <CodeCard
          file="tests/conftest.py"
          fontSize={22}
          delay={50}
          lines={[
            "import os",
            "from dotenv import load_dotenv",
            "",
            "load_dotenv(\".env.test\", override=True)",
            "os.environ[\"DEBUG\"] = \"true\"",
          ]}
        />
      </div>
      <Questions delay={100} items={["DATABASE_URL is None?", "load_dotenv() in every file?", "Which .env do tests read?"]} />
    </div>
  </Backdrop>
);

const STACK = ["Async ORM & migrations", "Artisan CLI", "Testing", "Vite + Inertia", "AI agents"];

export const IndieHacker: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const title = spring({ frame, fps, config: { damping: 14 } });
  const sub = useRise(30);
  return (
    <Backdrop>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", textAlign: "center" }}>
        <div style={{ fontFamily: theme.display, fontSize: 100, fontWeight: 700, letterSpacing: -3, lineHeight: 1.05, opacity: title, transform: `scale(${0.85 + title * 0.15})` }}>
          Are you an <GradientText>indie hacker</GradientText>?
        </div>
        <div style={{ ...sub, fontSize: 40, color: theme.muted, marginTop: 34, maxWidth: 1300 }}>
          You want full-stack batteries, without leaving FastAPI and Python.
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 18, marginTop: 56 }}>
          {STACK.map((item, index) => {
            const pop = spring({ frame: frame - 60 - index * 8, fps, config: { damping: 13 } });
            return (
              <div
                key={item}
                style={{
                  padding: "14px 26px",
                  borderRadius: 999,
                  border: "1.5px solid rgba(34,197,94,0.45)",
                  background: "rgba(34,197,94,0.08)",
                  fontFamily: theme.mono,
                  fontSize: 28,
                  opacity: pop,
                  transform: `translateY(${(1 - pop) * 24}px)`,
                }}
              >
                {item}
              </div>
            );
          })}
        </div>
      </div>
    </Backdrop>
  );
};

export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({ frame, fps, config: { damping: 14 } });
  const sub = useRise(30);
  const underline = interpolate(frame, [20, 50], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Backdrop>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", textAlign: "center" }}>
        <div style={{ fontFamily: theme.mono, fontSize: 36, color: theme.accent, opacity: useFadeIn(0, 10), marginBottom: 24 }}>
          <span style={{ color: theme.muted }}>Introducing </span>fastapi-startkit
        </div>
        <div style={{ fontFamily: theme.display, fontSize: 110, fontWeight: 700, letterSpacing: -3, lineHeight: 1.05, transform: `scale(${0.8 + scale * 0.2})`, opacity: scale }}>
          Full-stack productivity
          <br />
          for <GradientText>FastAPI</GradientText>
        </div>
        <div style={{ height: 8, width: `${underline * 6}px`, background: theme.gradient, borderRadius: 4, marginTop: 30 }} />
        <div style={{ ...sub, fontSize: 40, color: theme.muted, marginTop: 36 }}>A modular, provider-driven framework for Python.</div>
      </div>
    </Backdrop>
  );
};

const INSTALL_COMMANDS = [
  ["macOS / Linux", '/bin/bash -c "$(curl -fsSL https://fastapi-startkit.github.io/install.sh)"'],
  ["Windows", 'powershell -ExecutionPolicy ByPass -c "irm https://fastapi-startkit.github.io/install.ps1 | iex"'],
  ["Existing uv", "uvx fastapi-startkit@latest init"],
];

const InstallCommand: React.FC<{ label: string; command: string; delay: number }> = ({ label, command, delay }) => {
  const rise = useRise(delay);
  return (
    <div style={{ ...rise, background: theme.panel, border: `2px solid ${theme.panelBorder}`, borderRadius: 18, padding: "22px 34px" }}>
      <div style={{ fontSize: 26, fontWeight: 700, color: theme.accent2, marginBottom: 10 }}>{label}</div>
      <div style={{ fontFamily: theme.mono, fontSize: 26, whiteSpace: "pre" }}>
        <span style={{ color: theme.accent }}>$ </span>
        {command}
      </div>
    </div>
  );
};

export const CreateProject: React.FC = () => (
  <Backdrop>
    <SceneHeading step="01 · Create a project" title="One command to start" caption="It installs uv if you don't have it, then runs the latest installer." />
    <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
      {INSTALL_COMMANDS.map(([label, command], index) => (
        <InstallCommand key={label} label={label} command={command} delay={20 + index * 14} />
      ))}
    </div>
  </Backdrop>
);

const CREATED_FILES = [
  ".env",
  ".env.example",
  ".gitignore",
  ".python-version",
  "README.md",
  "app/__init__.py",
  "app/http/__init__.py",
  "app/http/controllers/__init__.py",
  "app/http/controllers/home_controller.py",
  "artisan",
  "bootstrap/__init__.py",
  "bootstrap/application.py",
  "config/__init__.py",
  "config/app.py",
  "config/fastapi.py",
  "config/logging.py",
  "providers/__init__.py",
  "providers/fastapi_provider.py",
  "pyproject.toml",
  "routes/__init__.py",
  "routes/api.py",
  "storage/logs/.gitignore",
  "tests/__init__.py",
  "tests/test_application.py",
];

const INSTALLER: TermBlock[] = [
  { kind: "command", text: "uvx fastapi-startkit@latest init", at: 10 },
  { kind: "prompt", draws: prompts.directory, at: [40, 52, 56, 60, 64, 68, 72, 82] },
  { kind: "prompt", draws: prompts.services, at: [88, 110] },
  { kind: "prompt", draws: prompts.database, at: [116, 130, 142] },
  { kind: "prompt", draws: prompts.frontend, at: [148, 166] },
  {
    kind: "lines",
    at: 172,
    stagger: 3,
    lines: [{ text: "Destination: /Users/dev/my-app", color: theme.text }, { text: "Application: web; database: none; frontend: none", color: theme.text }],
  },
  { kind: "lines", at: 178, stagger: 1, lines: CREATED_FILES.map((name) => ({ text: `  create ${name}` })) },
  {
    kind: "lines",
    at: 206,
    stagger: 4,
    lines: [
      { text: "Dependency: fastapi-startkit[fastapi]==0.67.0", color: theme.text },
      { text: "Python dependencies: uv sync", color: theme.text },
    ],
  },
  { kind: "prompt", draws: prompts.confirm, at: [218, 238] },
  {
    kind: "lines",
    at: 244,
    stagger: 6,
    lines: [{ text: "Application files created." }, { text: "Next: cd /Users/dev/my-app" }, { text: "Installing Python dependencies..." }],
  },
  {
    kind: "lines",
    at: 276,
    stagger: 7,
    lines: [
      { text: "Your application is ready.", color: theme.accent },
      { text: "Run: uv run python artisan serve", color: theme.text },
    ],
  },
];

export const Installer: React.FC = () => (
  <Backdrop>
    <SceneHeading step="02 · Interactive installer" title="Start small: just the web app" caption="No database, no frontend. Add each one later when you need it." />
    <ScrollTerminal blocks={INSTALLER} rows={16} fontSize={26} />
  </Backdrop>
);

export const Providers: React.FC = () => (
  <Backdrop>
    <SceneHeading step="04 · Application" title="Everything is a provider" caption="Logging and FastAPI are providers. Every provider registers, then every provider boots." />
    <div style={row}>
      <CodeCard
        file="bootstrap/application.py"
        style={{ flex: 1.15 }}
        fontSize={23}
        lines={[
          "from fastapi_startkit import Application",
          "from fastapi_startkit.logging import LogProvider",
          "from providers.fastapi_provider import FastapiProvider",
          "",
          "app = Application(",
          "    base_path=Path(__file__).resolve().parent.parent,",
          "    config=AppConfig,",
          "    providers=[",
          "        (LogProvider, LoggingConfig),",
          "        (FastapiProvider, FastAPIConfig),",
          "    ],",
          ")",
        ]}
      />
      <CodeCard
        file="providers/app_provider.py"
        style={{ flex: 1 }}
        fontSize={23}
        delay={70}
        lines={[
          "from fastapi_startkit.support import Provider",
          "",
          "class AppProvider(Provider):",
          "    def register(self) -> None:",
          "        self.app.bind(\"billing\", BillingService)",
          "",
          "    def boot(self) -> None:",
          "        billing = self.app.make(\"billing\")",
          "        billing.connect()",
        ]}
      />
    </div>
  </Backdrop>
);

const ACTIONS = [
  ["GET", "/organizations", "index"],
  ["GET", "/organizations/create", "create"],
  ["POST", "/organizations", "store"],
  ["GET", "/organizations/{organization}", "show"],
  ["GET", "/organizations/{organization}/edit", "edit"],
  ["PUT", "/organizations/{organization}", "update"],
  ["DELETE", "/organizations/{organization}", "destroy"],
];

const RouteRow: React.FC<{ method: string; path: string; action: string; delay: number }> = ({ method, path, action, delay }) => {
  const rise = useRise(delay);
  return (
    <div style={{ ...rise, display: "flex", fontFamily: theme.mono, fontSize: 22, lineHeight: 1.75 }}>
      <span style={{ width: 110, color: theme.number }}>{method}</span>
      <span style={{ flex: 1 }}>{path}</span>
      <span style={{ color: theme.accent }}>{action}</span>
    </div>
  );
};

export const Routing: React.FC = () => (
  <Backdrop>
    <SceneHeading step="06 · Routing" title="CRUD routes in one line" caption="Router wraps APIRouter and adds resource()." />
    <div style={row}>
      <CodeCard
        file="routes/web.py"
        style={{ flex: 1.2 }}
        fontSize={22}
        lines={[
          "from fastapi_startkit.fastapi import Router",
          "",
          "guest = Router()",
          "guest.get(\"/login\", session.create)",
          "",
          "auth = Router(dependencies=[Depends(auth)])",
          "auth.resource(\"organizations\", organizations_controller)",
        ]}
      />
      <div style={{ flex: 1, background: theme.panel, border: `2px solid ${theme.panelBorder}`, borderRadius: 18, padding: "26px 34px" }}>
        {ACTIONS.map(([method, path, action], index) => (
          <RouteRow key={action} method={method} path={path} action={action} delay={50 + index * 9} />
        ))}
      </div>
    </div>
  </Backdrop>
);

const DB_INSTALL: TermBlock[] = [
  { kind: "command", text: "uv run python artisan db:install", at: 10 },
  {
    kind: "lines",
    at: 40,
    stagger: 4,
    lines: [
      { text: "Created config/database.py", color: theme.accent },
      { text: "Registered DatabaseProvider in bootstrap/application.py", color: theme.accent },
      { text: "" },
      { text: "Next steps:", color: theme.text },
      { text: '  Install the database extra: uv add "fastapi-startkit[database,sqlite]"' },
      { text: "  Add to .env:" },
      { text: "    DB_CONNECTION=sqlite", color: theme.number },
      { text: "    DB_DATABASE=databases/database.sqlite", color: theme.number },
      { text: "  Create the migrations directory: mkdir -p databases/migrations" },
      { text: "  Create a migration: uv run python artisan db:make:migration create_users_table" },
      { text: "  Run migrations: uv run python artisan db:migrate" },
      { text: "" },
    ],
  },
  { kind: "command", text: 'uv add "fastapi-startkit[database,sqlite]"', at: 150 },
  {
    kind: "lines",
    at: 186,
    stagger: 4,
    lines: [
      { text: "Resolved 83 packages in 230ms" },
      { text: "Installed 4 packages in 41ms" },
      { text: " + aiosqlite==0.22.1", color: theme.accent },
      { text: " + faker==40.44.0", color: theme.accent },
      { text: " + greenlet==3.5.6", color: theme.accent },
      { text: " + sqlalchemy==2.1.6", color: theme.accent },
    ],
  },
];

export const AddDatabase: React.FC = () => (
  <Backdrop>
    <SceneHeading step="07 · Add a database" title="One command adds a provider" caption="db:install publishes config/database.py and registers DatabaseProvider for you." />
    <div style={{ ...row, gap: 32 }}>
      <ScrollTerminal blocks={DB_INSTALL} rows={18} fontSize={17} style={{ width: 900, flexShrink: 0 }} />
      <CodeCard
        file="bootstrap/application.py"
        style={{ flex: 1 }}
        fontSize={18}
        delay={60}
        perLine={2}
        highlight={[3, 4, 12]}
        lines={[
          "from fastapi_startkit import Application",
          "from fastapi_startkit.logging import LogProvider",
          "from providers.fastapi_provider import FastapiProvider",
          "from fastapi_startkit.masoniteorm import DatabaseProvider",
          "from config.database import DatabaseConfig",
          "",
          "app = Application(",
          "    base_path=Path(__file__).resolve().parent.parent,",
          "    config=AppConfig,",
          "    providers=[",
          "        (LogProvider, LoggingConfig),",
          "        (FastapiProvider, FastAPIConfig),",
          "        (DatabaseProvider, DatabaseConfig),",
          "    ],",
          ")",
        ]}
      />
    </div>
  </Backdrop>
);

const MIGRATION = "2026_10_29_124741_create_posts_table";

const MAKE_MODEL: TermBlock[] = [
  { kind: "command", text: "uv run python artisan db:make:model Post --migration", at: 10 },
  {
    kind: "lines",
    at: 52,
    stagger: 6,
    lines: [
      { text: "Model created: app/Post.py", color: theme.accent },
      { text: `Migration file created: databases/migrations/${MIGRATION}.py`, color: theme.accent },
      { text: "" },
    ],
  },
  { kind: "command", text: "uv run python artisan db:migrate", at: 250 },
  {
    kind: "lines",
    at: 280,
    stagger: 8,
    lines: [
      { text: `Migrating: ${MIGRATION}`, color: theme.number },
      { text: `Migrated: ${MIGRATION} (0.00s)`, color: theme.accent },
    ],
  },
];

export const ModelAndMigration: React.FC = () => (
  <Backdrop>
    <SceneHeading step="08 · Model & migration" title="Add a model, migrate, done" caption="db:make:model --migration writes both files. db:migrate creates the table." />
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <ScrollTerminal blocks={MAKE_MODEL} rows={7} fontSize={18} />
      <div style={row}>
        <CodeCard
          file="databases/migrations/…_create_posts_table.py"
          style={{ flex: 1.3 }}
          fontSize={18}
          delay={80}
          highlight={[4, 5]}
          lines={[
            "class CreatePostsTable(Migration):",
            "    async def up(self):",
            "        async with await self.schema.create(\"posts\") as table:",
            "            table.increments(\"id\")",
            "            table.string(\"title\")",
            "            table.text(\"body\")",
            "            table.timestamps()",
            "",
            "    async def down(self):",
            "        await self.schema.drop(\"posts\")",
          ]}
        />
        <CodeCard
          file="app/Post.py"
          style={{ flex: 1 }}
          fontSize={18}
          delay={160}
          highlight={[3, 4, 5]}
          lines={["from fastapi_startkit.masoniteorm.models import Model", "", "class Post(Model):", "    id: int", "    title: str", "    body: str"]}
        />
      </div>
    </div>
  </Backdrop>
);

const JsonPage: React.FC<{ body: string }> = ({ body }) => (
  <div style={{ padding: "22px 26px", fontFamily: theme.mono, fontSize: 22, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>{body}</div>
);

const POSTS_JSON =
  '[{"id":1,"title":"Hello, world","body":"Our first post.","created_at":"2026-10-29 19:50:43.942766","updated_at":"2026-10-29 19:50:43.942802"}]';

export const QueryIt: React.FC = () => (
  <Backdrop>
    <SceneHeading step="09 · Query it" title="Await the model, return JSON" caption="Controllers await the async ORM. FastAPI serializes the result." />
    <div style={row}>
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 28 }}>
        <CodeCard
          file="app/http/controllers/posts_controller.py"
          fontSize={18}
          lines={["from app.Post import Post", "", "class PostsController:", "    async def index(self):", "        posts = await Post.all()", "        return posts.serialize()"]}
        />
        <CodeCard
          file="routes/api.py"
          fontSize={18}
          delay={60}
          highlight={[0, 2, 5]}
          lines={[
            "from app.http.controllers.posts_controller import PostsController",
            "",
            "posts = PostsController()",
            "router.get(\"/\", controller.index, response_model=None)",
            "router.get(\"/health\", controller.health)",
            "router.get(\"/posts\", posts.index)",
          ]}
        />
      </div>
      <BrowserWindow url="127.0.0.1:8000/posts" delay={120} loadAt={165} style={{ flex: 1, height: 560 }}>
        <JsonPage body={POSTS_JSON} />
      </BrowserWindow>
    </div>
  </Backdrop>
);

export const Agents: React.FC = () => (
  <Backdrop>
    <SceneHeading step="12 · AI agents" title="Agents are classes" caption="Instructions, tools and typed structured output in one class, with fakes for tests." />
    <div style={row}>
      <CodeCard
        file="app/agents/support_agent.py"
        style={{ flex: 1.15 }}
        fontSize={22}
        perLine={3}
        lines={[
          "from pydantic import BaseModel",
          "from fastapi_startkit.ai import Agent, provider",
          "",
          "class OrderStatus(BaseModel):",
          "    order_id: int",
          "    status: str",
          "",
          "@provider(\"openai\")",
          "class SupportAgent(Agent):",
          "    def instructions(self) -> str:",
          "        return \"You answer questions about customer orders.\"",
          "",
          "    def tools(self):",
          "        return [order_status]",
          "",
          "    def schema(self):",
          "        return OrderStatus",
        ]}
      />
      <CodeCard
        file="orders_controller.py"
        style={{ flex: 1 }}
        fontSize={22}
        delay={80}
        lines={[
          "response = await SupportAgent().prompt(",
          "    \"Where is order #1042?\")",
          "order = response[\"structured_response\"]",
          "print(order.order_id, order.status)",
          "",
          "with SupportAgent.fake([",
          "    '{\"order_id\": 1042, \"status\": \"shipped\"}',",
          "]):",
          "    await SupportAgent().prompt(\"Where is it?\")",
        ]}
      />
    </div>
  </Backdrop>
);

const VITE: TermBlock[] = [
  { kind: "command", text: "npm run dev", at: 70 },
  {
    kind: "lines",
    at: 94,
    stagger: 4,
    lines: [
      { text: "  VITE v8.0.10  ready in 542 ms", color: theme.accent },
      { text: "" },
      { text: "  ➜  Local:   http://localhost:5173/", color: theme.text },
      { text: "  ➜  Network: use --host to expose" },
      { text: "" },
      { text: "  FASTAPI  plugin v0.0.3", color: theme.type },
      { text: "" },
      { text: "  ➜  APP_URL: http://127.0.0.1:8000", color: theme.text },
    ],
  },
];

const HomePage: React.FC = () => (
  <div style={{ maxWidth: 768, margin: "70px auto 0", padding: "0 48px", fontFamily: theme.sans }}>
    <div style={{ fontSize: 38, fontWeight: 600, letterSpacing: -0.6 }}>Welcome to FastAPI Startkit</div>
    <div style={{ fontSize: 22, marginTop: 20 }}>Your React application is ready.</div>
    <div style={{ fontSize: 22, marginTop: 28, color: "#047857" }}>Explore the API</div>
  </div>
);

export const Frontend: React.FC = () => (
  <Backdrop>
    <SceneHeading step="11 · Frontend" title="Add Vite + Inertia when you need them" caption="Two more providers, then npm run dev serves React pages with hot reload." />
    <div style={row}>
      <CodeCard
        file="bootstrap/application.py"
        style={{ flex: 1 }}
        fontSize={19}
        perLine={3}
        highlight={[0, 1, 2, 9, 10]}
        lines={[
          "from fastapi_startkit.inertia import InertiaProvider",
          "from fastapi_startkit.vite import ViteProvider",
          "from config.vite import ViteConfig",
          "",
          "app = Application(",
          "    providers=[",
          "        (LogProvider, LoggingConfig),",
          "        (FastapiProvider, FastAPIConfig),",
          "        (DatabaseProvider, DatabaseConfig),",
          "        (ViteProvider, ViteConfig),",
          "        InertiaProvider,",
          "    ],",
          ")",
        ]}
      />
      <div style={{ flex: 1, minWidth: 0, position: "relative", height: 600 }}>
        <ScrollTerminal blocks={VITE} title="my-app — npm run dev" rows={9} fontSize={18} delay={50} />
        <BrowserWindow url="127.0.0.1:8000" delay={150} loadAt={200} style={{ position: "absolute", left: 60, right: 0, top: 300, bottom: -10 }}>
          <HomePage />
        </BrowserWindow>
      </div>
    </div>
  </Backdrop>
);

const SERVE: TermBlock[] = [
  { kind: "command", text: "uv run python artisan serve", at: 10 },
  {
    kind: "lines",
    at: 34,
    stagger: 5,
    lines: [
      { text: "Starting Uvicorn server on 127.0.0.1:8000 [bootstrap.application:app]...", color: theme.accent },
      { text: "INFO:     Will watch for changes in these directories: ['/Users/dev/my-app']" },
      { text: "INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)" },
      { text: "INFO:     Started reloader process [48213] using WatchFiles" },
      { text: "INFO:     Started server process [48215]" },
      { text: "INFO:     Waiting for application startup." },
      { text: "INFO:     Application startup complete." },
    ],
  },
  { kind: "lines", at: 132, lines: [{ text: 'INFO:     127.0.0.1:52344 - "GET / HTTP/1.1" 200 OK', color: theme.text }] },
];

export const RunInBrowser: React.FC = () => (
  <Backdrop>
    <SceneHeading step="03 · Run it" title="Serve it and open the browser" caption="artisan serve starts Uvicorn with reload. No database or Node.js needed yet." />
    <div style={{ position: "relative", height: 560 }}>
      <ScrollTerminal blocks={SERVE} rows={10} fontSize={20} />
      <BrowserWindow url="127.0.0.1:8000" delay={80} loadAt={130} style={{ position: "absolute", left: "48%", right: 0, top: 120, bottom: -20 }}>
        <JsonPage body={'{"message":"Welcome to FastAPI Startkit"}'} />
      </BrowserWindow>
    </div>
  </Backdrop>
);

export const CallToAction: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 12 } });
  const links = useRise(20);
  const install = useRise(35);
  return (
    <Backdrop>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", textAlign: "center" }}>
        <div style={{ fontFamily: theme.display, fontSize: 96, fontWeight: 700, letterSpacing: -2.5, transform: `scale(${0.85 + pop * 0.15})`, opacity: pop }}>
          Build your next <GradientText>FastAPI</GradientText> app faster.
        </div>
        <div
          style={{
            ...install,
            marginTop: 56,
            fontFamily: theme.mono,
            fontSize: 44,
            padding: "18px 40px",
            borderRadius: 14,
            background: theme.panel,
            border: `2px solid ${theme.accent}`,
          }}
        >
          <span style={{ color: theme.accent }}>$ </span>uvx fastapi-startkit@latest init
        </div>
        <div style={{ ...links, marginTop: 56, display: "flex", flexDirection: "column", gap: 20, fontFamily: theme.mono, fontSize: 38 }}>
          <div>
            <span style={{ color: theme.muted }}>Docs  </span>
            <span style={{ color: theme.accent2 }}>fastapi-startkit.github.io</span>
          </div>
          <div>
            <span style={{ color: theme.muted }}>Code  </span>
            <span style={{ color: theme.accent2 }}>github.com/fastapi-startkit/fastapi-startkit-framework</span>
          </div>
        </div>
      </div>
    </Backdrop>
  );
};

const LOG_TAIL: TermBlock[] = [
  { kind: "command", text: "tail -f storage/logs/2026-10-29.log", at: 120 },
  {
    kind: "lines",
    at: 160,
    stagger: 14,
    lines: [
      { text: "2026-10-29 20:11:29 - INFO - /Users/dev/my-app/app/orders.py:5 - Order 1042 placed" },
      { text: "2026-10-29 20:11:29 - ERROR - /Users/dev/my-app/app/orders.py:6 - Payment failed for order 1042", color: "#f87171" },
    ],
  },
];

export const Logging: React.FC = () => (
  <Backdrop>
    <SceneHeading step="05 · Logging" title="Channels, not handlers" caption="Stack daily files, the terminal and Slack. Pick one per environment with LOG_CHANNEL." />
    <div style={{ display: "flex", flexDirection: "column", gap: 26 }}>
      <div style={row}>
        <CodeCard
          file="config/logging.py"
          style={{ flex: 1.45 }}
          fontSize={18}
          perLine={3}
          highlight={[4, 8]}
          lines={[
            "@dataclass",
            "class LoggingConfig(Config):",
            "    default: str = env(\"LOG_CHANNEL\", \"stack\")",
            "    channels: dict = field(default_factory=lambda: {",
            "        \"stack\": StackChannel(channels=[\"daily\", \"terminal\", \"slack\"]),",
            "        \"daily\": DailyChannel(path=\"storage/logs\"),",
            "        \"terminal\": TerminalChannel(level=\"info\"),",
            "        \"slack\": SlackChannel(",
            "            channel=\"#alerts\", token=env(\"SLACK_TOKEN\"), level=\"error\"),",
            "    })",
          ]}
        />
        <CodeCard
          file="app/orders.py"
          style={{ flex: 1 }}
          fontSize={18}
          delay={60}
          lines={[
            "from fastapi_startkit.logging import Logger",
            "",
            "def place_order(order_id: int):",
            "    Logger.info(f\"Order {order_id} placed\")",
            "    Logger.error(f\"Payment failed for order {order_id}\")",
          ]}
        />
      </div>
      <ScrollTerminal blocks={LOG_TAIL} rows={3} fontSize={18} delay={100} />
    </div>
  </Backdrop>
);

const PYTEST: TermBlock[] = [
  { kind: "command", text: "uv run pytest -v -p no:warnings", at: 110 },
  {
    kind: "lines",
    at: 150,
    stagger: 12,
    lines: [
      { text: "collecting ... collected 2 items" },
      { text: "" },
      { text: "tests/test_application.py::TestApplication::test_health PASSED  [ 50%]", color: theme.accent },
      { text: "tests/test_posts.py::TestPosts::test_lists_posts PASSED         [100%]", color: theme.accent },
      { text: "" },
      { text: "=================== 2 passed in 0.52s ===================", color: theme.accent },
    ],
  },
];

export const Testing: React.FC = () => (
  <Backdrop>
    <SceneHeading step="10 · Testing" title="Tests get their own .env" caption="Under pytest, .env.testing loads on top of .env. RefreshDatabase migrates once and rolls back each test." />
    <div style={row}>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 24 }}>
        <CodeCard file=".env.testing" fontSize={19} lines={["DB_DATABASE=databases/testing.sqlite", "LOG_CHANNEL=terminal"]} />
        <CodeCard
          file="tests/test_posts.py"
          fontSize={18}
          delay={40}
          perLine={3}
          highlight={[4]}
          lines={[
            "from app.Post import Post",
            "from fastapi_startkit.fastapi.testing import HttpTestCase",
            "from fastapi_startkit.masoniteorm.testing import RefreshDatabase",
            "",
            "class TestPosts(HttpTestCase, RefreshDatabase):",
            "    def get_application(self):",
            "        from bootstrap.application import app",
            "        return app",
            "",
            "    async def test_lists_posts(self):",
            "        await Post.create({\"title\": \"Hello\", \"body\": \"From tests\"})",
            "        response = await self.get(\"/posts\")",
            "        response.assert_ok()",
            "        assert response.json()[0][\"title\"] == \"Hello\"",
          ]}
        />
      </div>
      <ScrollTerminal blocks={PYTEST} rows={9} fontSize={17} delay={90} style={{ flex: 0.95 }} />
    </div>
  </Backdrop>
);
