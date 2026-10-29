import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, CodeCard, SceneHeading, ScrollTerminal, TermBlock, useFadeIn, useRise } from "./components";
import prompts from "./installer-prompts.json";
import { theme } from "./theme";

const row: React.CSSProperties = { display: "flex", gap: 48, alignItems: "flex-start" };

export const Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scale = spring({ frame, fps, config: { damping: 14 } });
  const sub = useRise(30);
  const underline = interpolate(frame, [20, 50], [0, 100], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Backdrop>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", textAlign: "center" }}>
        <div style={{ fontFamily: theme.mono, fontSize: 36, color: theme.accent, opacity: useFadeIn(0, 10), marginBottom: 24 }}>fastapi-startkit</div>
        <div style={{ fontSize: 104, fontWeight: 900, lineHeight: 1.1, transform: `scale(${0.8 + scale * 0.2})`, opacity: scale }}>
          Laravel-style productivity
          <br />
          for <span style={{ color: theme.accent }}>FastAPI</span>
        </div>
        <div style={{ height: 8, width: `${underline * 6}px`, background: theme.accent, borderRadius: 4, marginTop: 30 }} />
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
  "config/database.py",
  "config/fastapi.py",
  "config/logging.py",
  "config/vite.py",
  "databases/__init__.py",
  "databases/migrations/.gitkeep",
  "databases/seeders/__init__.py",
  "databases/seeders/database_seeder.py",
  "package.json",
  "providers/__init__.py",
  "providers/fastapi_provider.py",
  "pyproject.toml",
  "resources/css/app.css",
  "resources/js/Pages/Home.tsx",
  "resources/js/app.tsx",
  "resources/templates/index.html",
  "routes/__init__.py",
  "routes/api.py",
  "storage/logs/.gitignore",
  "tests/__init__.py",
  "tests/test_application.py",
  "vite.config.ts",
];

const INSTALLER: TermBlock[] = [
  { kind: "command", text: "uvx fastapi-startkit@latest init", at: 10 },
  { kind: "prompt", draws: prompts.directory, at: [40, 52, 56, 60, 64, 68, 72, 82] },
  { kind: "prompt", draws: prompts.services, at: [88, 110] },
  { kind: "prompt", draws: prompts.database, at: [116, 138] },
  { kind: "prompt", draws: prompts.frontend, at: [144, 160, 176] },
  {
    kind: "lines",
    at: 182,
    stagger: 3,
    lines: [{ text: "Destination: /Users/dev/my-app", color: theme.text }, { text: "Application: web; database: sqlite; frontend: react", color: theme.text }],
  },
  { kind: "lines", at: 188, stagger: 1, lines: CREATED_FILES.map((name) => ({ text: `  create ${name}` })) },
  {
    kind: "lines",
    at: 226,
    stagger: 4,
    lines: [
      { text: "Dependency: fastapi-startkit[database,fastapi,inertia,sqlite,vite]==0.67.0", color: theme.text },
      { text: "Python dependencies: uv sync", color: theme.text },
      { text: "Frontend dependencies: npm install (run after generation; requires Node.js 22.12+)", color: theme.text },
    ],
  },
  { kind: "prompt", draws: prompts.confirm, at: [242, 262] },
  {
    kind: "lines",
    at: 268,
    stagger: 6,
    lines: [{ text: "Application files created." }, { text: "Next: cd /Users/dev/my-app" }, { text: "Installing Python dependencies..." }],
  },
  {
    kind: "lines",
    at: 300,
    stagger: 7,
    lines: [
      { text: "Your application is ready.", color: theme.accent },
      { text: "Run: uv run python artisan serve", color: theme.text },
      { text: "In another terminal: npm install && npm run dev (Node.js 22.12+).", color: theme.text },
      { text: "Migrate: uv run python artisan db:migrate", color: theme.text },
    ],
  },
];

export const Installer: React.FC = () => (
  <Backdrop>
    <SceneHeading step="02 · Interactive installer" title="Pick your stack, get a running app" caption="Services, database and frontend. Files and dependencies in one go." />
    <ScrollTerminal blocks={INSTALLER} rows={16} fontSize={26} />
  </Backdrop>
);

export const Providers: React.FC = () => (
  <Backdrop>
    <SceneHeading step="03 · Application" title="Provider-driven, with a service container" caption="Two-phase boot: every provider registers, then every provider boots." />
    <div style={row}>
      <CodeCard
        file="bootstrap/application.py"
        style={{ flex: 1.15 }}
        fontSize={23}
        lines={[
          "from fastapi_startkit import Application",
          "",
          "app = Application(",
          "    base_path=Path(__file__).resolve().parent.parent,",
          "    config=AppConfig,",
          "    providers=[",
          "        (LogProvider, LoggingConfig),",
          "        (DatabaseProvider, DatabaseConfig),",
          "        (FastapiProvider, FastAPIConfig),",
          "        (ViteProvider, ViteConfig),",
          "        InertiaProvider,",
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
          "        inertia = self.app.make(\"inertia\")",
          "        inertia.share(\"app_name\", \"Demo\")",
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
    <SceneHeading step="04 · Routing" title="CRUD routes in one line" caption="Router wraps APIRouter and adds resource()." />
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

export const Orm: React.FC = () => (
  <Backdrop>
    <SceneHeading step="05 · Database" title="An async ORM with relationships" caption="Async-first and built on SQLAlchemy. Every query is awaited." />
    <div style={row}>
      <CodeCard
        file="app/models/Organization.py"
        style={{ flex: 1.3 }}
        fontSize={24}
        lines={[
          "from fastapi_startkit.masoniteorm.models import Model",
          "from fastapi_startkit.masoniteorm.relationships import (",
          "    BelongsTo, HasMany,",
          ")",
          "",
          "class Organization(Model):",
          "    contacts = HasMany[\"Contact\"](",
          "        local_key=\"id\", foreign_key=\"organization_id\")",
          "",
          "class Contact(Model):",
          "    organization = BelongsTo[\"Organization\"](",
          "        local_key=\"organization_id\", foreign_key=\"id\")",
        ]}
      />
      <CodeCard
        file="organizations_controller.py"
        style={{ flex: 1 }}
        fontSize={24}
        delay={80}
        lines={[
          "organizations = await (",
          "    Organization.with_(\"contacts\")",
          "    .where(\"city\", \"Kathmandu\")",
          "    .get()",
          ")",
          "",
          "page = await Organization.query().paginate(",
          "    page=1, per_page=10)",
        ]}
      />
    </div>
  </Backdrop>
);

const MIGRATION = "2026_10_29_013122_create_users_table";

const CONSOLE: TermBlock[] = [
  { kind: "command", text: "uv run python artisan db:install", at: 10 },
  {
    kind: "lines",
    at: 42,
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
  { kind: "command", text: "uv run python artisan db:make:migration create_users_table", at: 130 },
  {
    kind: "lines",
    at: 180,
    lines: [{ text: `Migration file created: databases/migrations/${MIGRATION}.py`, color: theme.accent }, { text: "" }],
  },
  { kind: "command", text: "uv run python artisan db:migrate", at: 205 },
  {
    kind: "lines",
    at: 236,
    stagger: 8,
    lines: [
      { text: `Migrating: ${MIGRATION}`, color: theme.number },
      { text: `Migrated: ${MIGRATION} (0.00s)`, color: theme.accent },
    ],
  },
];

export const Artisan: React.FC = () => (
  <Backdrop>
    <SceneHeading step="06 · Console" title="Add a database with db:install" caption="Artisan publishes the config, registers the provider and prints the next steps." />
    <ScrollTerminal blocks={CONSOLE} rows={16} fontSize={26} />
  </Backdrop>
);

export const Caching: React.FC = () => (
  <Backdrop>
    <SceneHeading step="07 · Cache" title="Remember, lock and tag" caption="Array, file, database and Redis stores behind one Cache facade." />
    <div style={row}>
      <CodeCard
        file="config/cache.py"
        style={{ flex: 1 }}
        fontSize={22}
        lines={[
          "from dataclasses import dataclass",
          "from fastapi_startkit.configuration import Config",
          "from fastapi_startkit.environment import env",
          "",
          "@dataclass",
          "class CacheConfig(Config):",
          "    default: str = env(\"CACHE_CONNECTION\", \"database\")",
          "    prefix: str = env(\"CACHE_PREFIX\", \"cache\")",
        ]}
      />
      <CodeCard
        file="dashboard_controller.py"
        style={{ flex: 1 }}
        fontSize={22}
        delay={60}
        lines={[
          "from fastapi_startkit.facades import Cache",
          "",
          "stats = await Cache.remember(",
          "    \"dashboard.stats\", 600, load_stats)",
          "",
          "async with Cache.lock(\"reports:nightly\", 30):",
          "    await build_report()",
          "",
          "await Cache.tags(\"users\").put(\"user:1\", user, 3600)",
          "await Cache.tags(\"users\").flush()",
        ]}
      />
    </div>
  </Backdrop>
);

export const Agents: React.FC = () => (
  <Backdrop>
    <SceneHeading step="08 · AI agents" title="Agents are classes" caption="Instructions, tools and provider settings in one place, with fakes for tests." />
    <div style={row}>
      <CodeCard
        file="app/agents/support_agent.py"
        style={{ flex: 1.25 }}
        fontSize={22}
        lines={[
          "from fastapi_startkit.ai import Agent, max_steps, provider",
          "",
          "@provider(\"openai\")",
          "@max_steps(5)",
          "class SupportAgent(Agent):",
          "    def instructions(self) -> str:",
          "        return \"You answer questions about customer orders.\"",
          "",
          "    def tools(self):",
          "        return [order_status]",
        ]}
      />
      <CodeCard
        file="orders_controller.py"
        style={{ flex: 1 }}
        fontSize={22}
        delay={70}
        lines={[
          "from fastapi_startkit.ai import state",
          "",
          "response = await SupportAgent().prompt(",
          "    \"Where is order #1042?\")",
          "state.text(response)",
          "",
          "with SupportAgent.fake([\"It shipped today.\"]):",
          "    await SupportAgent().prompt(\"Where is it?\")",
        ]}
      />
    </div>
  </Backdrop>
);

export const Frontend: React.FC = () => (
  <Backdrop>
    <SceneHeading step="09 · Frontend" title="Inertia + Vite, out of the box" caption="Return React or Vue pages straight from your controllers." />
    <div style={row}>
      <CodeCard
        file="app/http/controllers/home_controller.py"
        style={{ flex: 1.1 }}
        fontSize={21}
        lines={[
          "from fastapi_startkit.inertia import Inertia",
          "from fastapi_startkit.inertia.inertia import InertiaResponse",
          "",
          "class HomeController:",
          "    async def index(self) -> InertiaResponse:",
          "        return Inertia.render(\"Home\")",
        ]}
      />
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 28 }}>
        <CodeCard
          file="resources/templates/index.html"
          fontSize={21}
          delay={60}
          lines={["<head>", "    {{ vite_react_refresh() }}", "    {{ vite('resources/js/app.tsx') }}", "    {{ inertia_head(page) }}", "</head>", "<body>{{ inertia(page) }}</body>"]}
        />
        <CodeCard
          file="vite.config.ts"
          fontSize={21}
          delay={95}
          lines={["import fastapi from 'fastapi-vite-plugin'", "", "plugins: [", "    fastapi({", "        input: 'resources/js/app.tsx',", "        refresh: true,", "    }),", "    react(),", "]"]}
        />
      </div>
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
        <div style={{ fontSize: 92, fontWeight: 900, transform: `scale(${0.85 + pop * 0.15})`, opacity: pop }}>
          Build your next <span style={{ color: theme.accent }}>FastAPI</span> app faster.
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
