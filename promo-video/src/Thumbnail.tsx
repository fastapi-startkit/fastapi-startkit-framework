import React from "react";
import { AbsoluteFill } from "remotion";
import { Ambient, CodeCard, GradientText } from "./components";
import { theme } from "./theme";

const FEATURES = ["Async ORM", "Logging", "Testing", "Vite + Inertia", "AI agents"];

const PROVIDERS = [
  "app = Application(",
  "    providers=[",
  "        (LogProvider, LoggingConfig),",
  "        (FastapiProvider, FastAPIConfig),",
  "        (DatabaseProvider, DatabaseConfig),",
  "        (ViteProvider, ViteConfig),",
  "        InertiaProvider,",
  "    ],",
  ")",
];

export const Thumbnail: React.FC = () => (
  <AbsoluteFill>
    <Ambient />
    <AbsoluteFill style={{ fontFamily: theme.sans, fontVariantLigatures: "none", color: theme.text, padding: "0 64px", flexDirection: "row", alignItems: "center", gap: 40 }}>
      <div style={{ flex: "0 0 540px" }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 12, fontFamily: theme.mono, fontSize: 28, fontWeight: 600, color: theme.accent, border: `2px solid rgba(34,197,94,0.45)`, background: "rgba(34,197,94,0.1)", borderRadius: 40, padding: "8px 22px", boxShadow: "0 0 24px rgba(34,197,94,0.25)" }}>
          <div style={{ width: 12, height: 12, borderRadius: 6, background: theme.accent, boxShadow: `0 0 12px ${theme.accent}` }} />
          fastapi-startkit
        </div>
        <div style={{ fontFamily: theme.display, fontSize: 106, fontWeight: 700, letterSpacing: -4, whiteSpace: "nowrap", lineHeight: 0.95, marginTop: 28 }}>
          Full-stack
          <br />
          <GradientText>FastAPI</GradientText>
        </div>
        <div style={{ height: 8, width: 300, background: theme.gradient, borderRadius: 4, marginTop: 26 }} />
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 30 }}>
          {FEATURES.map((feature) => (
            <div key={feature} style={{ fontSize: 26, fontWeight: 600, background: theme.panel, border: `2px solid ${theme.panelBorder}`, borderRadius: 14, padding: "8px 18px" }}>
              {feature}
            </div>
          ))}
        </div>
      </div>
      <CodeCard
        file="bootstrap/application.py"
        lines={PROVIDERS}
        delay={-200}
        fontSize={19}
        highlight={[5, 6]}
        style={{ flex: 1, transform: "rotate(-3deg)", boxShadow: "0 30px 80px rgba(0,0,0,0.55), 0 0 60px rgba(56,189,248,0.15)" }}
      />
    </AbsoluteFill>
  </AbsoluteFill>
);
