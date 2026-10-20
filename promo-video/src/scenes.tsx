import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, CodeCard, Pill, SceneHeading, Terminal, useFadeIn, useRise } from "./components";
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

export const Install: React.FC = () => (
  <Backdrop>
    <SceneHeading step="01 · Install" title="One command to start" caption="Optional extras for the pieces you need." />
    <Terminal
      steps={[{ command: "uv add fastapi-startkit", output: [{ text: " + fastapi-startkit==0.66.0", color: theme.accent }] }]}
      style={{ width: 1200 }}
    />
    <div style={{ display: "flex", gap: 24, marginTop: 48 }}>
      <Pill label="fastapi-startkit[fastapi]" delay={60} />
      <Pill label="fastapi-startkit[database]" delay={68} />
      <Pill label="fastapi-startkit[vite]" delay={76} />
    </div>
  </Backdrop>
);

export const Providers: React.FC = () => (
  <Backdrop>
    <SceneHeading step="02 · Application" title="Provider-driven, with a service container" caption="Two-phase boot: every provider registers, then every provider boots." />
    <div style={row}>
      <CodeCard
        file="bootstrap/application.py"
        style={{ flex: 1 }}
        fontSize={27}
        lines={[
          "from fastapi_startkit import Application",
          "",
          "app = Application(",
          "    base_path=str(Path.cwd()),",
          "    providers=[",
          "        LogProvider,",
          "        (DatabaseProvider, DatabaseConfig),",
          "        FastAPIProvider,",
          "        ViteProvider,",
          "        InertiaProvider,",
          "    ],",
          ")",
        ]}
      />
      <CodeCard
        file="providers/app_provider.py"
        style={{ flex: 1 }}
        fontSize={27}
        delay={70}
        lines={[
          "class AppProvider(Provider):",
          "    def register(self) -> None:",
          "        self.app.bind(\"templates\", templates)",
          "",
          "    def boot(self) -> None:",
          "        inertia = self.app.make(\"inertia\")",
          "        inertia.share(\"app_name\", \"Demo\")",
        ]}
      />
    </div>
  </Backdrop>
);

export const Configuration: React.FC = () => (
  <Backdrop>
    <SceneHeading step="03 · Configuration" title="Typed config from the environment" caption=".env is loaded first, then .env.{APP_ENV} is merged on top." />
    <div style={row}>
      <CodeCard
        file="config/redis.py"
        style={{ flex: 1 }}
        fontSize={26}
        lines={[
          "from dataclasses import dataclass",
          "from fastapi_startkit.environment import env",
          "",
          "@dataclass",
          "class RedisConfig:",
          "    host: str = env(\"REDIS_HOST\", \"localhost\")",
          "    port: int = env(\"REDIS_PORT\", 6379)",
        ]}
      />
      <CodeCard
        file="anywhere.py"
        style={{ flex: 1 }}
        fontSize={26}
        delay={60}
        lines={[
          "from fastapi_startkit.facades import Config",
          "",
          "Config.get(\"redis.host\")",
          "# 'localhost'",
        ]}
      />
    </div>
  </Backdrop>
);

const ACTIONS = [
  ["GET", "/organizations", "index"],
  ["GET", "/organizations/create", "create"],
  ["POST", "/organizations", "store"],
  ["GET", "/organizations/{id}", "show"],
  ["GET", "/organizations/{id}/edit", "edit"],
  ["PUT", "/organizations/{id}", "update"],
  ["DELETE", "/organizations/{id}", "destroy"],
];

const RouteRow: React.FC<{ method: string; path: string; action: string; delay: number }> = ({ method, path, action, delay }) => {
  const rise = useRise(delay);
  return (
    <div style={{ ...rise, display: "flex", fontFamily: theme.mono, fontSize: 27, lineHeight: 1.75 }}>
      <span style={{ width: 130, color: theme.number }}>{method}</span>
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
        style={{ flex: 1.3 }}
        fontSize={25}
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
        file="app/Organization.py"
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

export const Artisan: React.FC = () => (
  <Backdrop>
    <SceneHeading step="06 · Console" title="An artisan CLI built on Cleo" caption="Models, migrations, seeders and more, all from the terminal." />
    <Terminal
      charsPerFrame={1.6}
      steps={[
        { command: "uv run artisan db:make:model Post", output: [{ text: "Model created: app/Post.py", color: theme.accent }] },
        {
          command: "uv run artisan db:migrate",
          output: [
            { text: "Migrating: 2026_04_26_110113_create_users", color: theme.number },
            { text: "Migrated:  2026_04_26_110113_create_users (0.01s)", color: theme.accent },
            { text: "Migrating: 2026_04_27_145006_create_posts_table", color: theme.number },
            { text: "Migrated:  2026_04_27_145006_create_posts_table (0.01s)", color: theme.accent },
          ],
        },
      ]}
    />
  </Backdrop>
);

export const Frontend: React.FC = () => (
  <Backdrop>
    <SceneHeading step="07 · Frontend" title="Inertia + Vite, out of the box" caption="Return React or Vue pages straight from your controllers." />
    <div style={row}>
      <CodeCard
        file="organizations_controller.py"
        style={{ flex: 1.2 }}
        fontSize={24}
        lines={[
          "from fastapi_startkit.inertia import Inertia",
          "",
          "async def index():",
          "    paginator = await Organization.query().paginate()",
          "    return Inertia.render(\"Organizations/Index\", {",
          "        \"data\": [o.name for o in paginator.result],",
          "    })",
        ]}
      />
      <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 28 }}>
        <CodeCard
          file="templates/app.html"
          fontSize={24}
          delay={60}
          lines={["<head>", "  {{ vite('resources/js/app.tsx') }}", "</head>", "<body>{{ inertia(page) }}</body>"]}
        />
        <CodeCard
          file="vite.config.js"
          fontSize={24}
          delay={95}
          lines={["import fastapi from \"fastapi-vite-plugin\"", "", "plugins: [", "  fastapi({ input: 'resources/js/app.tsx' }),", "]"]}
        />
      </div>
    </div>
  </Backdrop>
);

export const CallToAction: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({ frame, fps, config: { damping: 12 } });
  const links = useRise(25);
  const install = useRise(45);
  return (
    <Backdrop>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", height: "100%", textAlign: "center" }}>
        <div style={{ fontSize: 92, fontWeight: 900, transform: `scale(${0.85 + pop * 0.15})`, opacity: pop }}>
          Build your next <span style={{ color: theme.accent }}>FastAPI</span> app faster.
        </div>
        <div style={{ ...links, marginTop: 56, display: "flex", flexDirection: "column", gap: 20, fontFamily: theme.mono, fontSize: 40 }}>
          <div>
            <span style={{ color: theme.muted }}>Docs  </span>
            <span style={{ color: theme.accent2 }}>fastapi-startkit.github.io</span>
          </div>
          <div>
            <span style={{ color: theme.muted }}>Code  </span>
            <span style={{ color: theme.accent2 }}>github.com/fastapi-startkit/fastapi-startkit-framework</span>
          </div>
        </div>
        <div
          style={{
            ...install,
            marginTop: 56,
            fontFamily: theme.mono,
            fontSize: 40,
            padding: "18px 40px",
            borderRadius: 14,
            background: theme.panel,
            border: `2px solid ${theme.accent}`,
          }}
        >
          <span style={{ color: theme.accent }}>$ </span>uv add fastapi-startkit
        </div>
      </div>
    </Backdrop>
  );
};
