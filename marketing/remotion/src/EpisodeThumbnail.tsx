import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { theme } from "./theme";

export type EpisodeThumbnailProps = { number: number; title: string; series: string; frame: string };

const Window: React.FC<{ frame: string }> = ({ frame }) => (
  <div
    style={{
      position: "absolute",
      left: 720,
      top: 170,
      width: 820,
      background: theme.panel,
      border: `2px solid ${theme.border}`,
      borderRadius: 16,
      overflow: "hidden",
      transform: "rotate(-3deg)",
      boxShadow: "0 30px 80px rgba(0,0,0,0.6), 0 0 80px rgba(47,129,247,0.18)",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "12px 18px", borderBottom: `2px solid ${theme.border}` }}>
      {["#f85149", "#d29922", "#3fb950"].map((color) => (
        <div key={color} style={{ width: 13, height: 13, borderRadius: 7, background: color }} />
      ))}
      <div style={{ marginLeft: 14, fontFamily: theme.mono, fontSize: 19, color: theme.muted }}>/projects/2/board</div>
    </div>
    <Img src={staticFile(frame)} style={{ display: "block", width: "100%" }} />
  </div>
);

export const EpisodeThumbnail: React.FC<EpisodeThumbnailProps> = ({ number, title, series, frame }) => {
  const words = title.split(" ");
  const lead = words.slice(0, -1).join(" ");
  const last = words[words.length - 1];
  return (
    <AbsoluteFill style={{ background: theme.bg, color: theme.text, fontFamily: theme.sans, overflow: "hidden" }}>
      <AbsoluteFill style={{ background: "radial-gradient(circle at 85% 30%, rgba(47,129,247,0.22) 0%, transparent 55%), radial-gradient(circle at 10% 95%, rgba(63,185,80,0.16) 0%, transparent 50%)" }} />
      <Window frame={frame} />
      <AbsoluteFill style={{ background: "linear-gradient(90deg, #0d1117 0%, #0d1117 52%, rgba(13,17,23,0.6) 60%, transparent 70%)" }} />
      <AbsoluteFill style={{ padding: "0 64px", justifyContent: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div style={{ fontFamily: theme.mono, fontSize: 40, fontWeight: 700, color: theme.bg, background: theme.green, borderRadius: 12, padding: "4px 18px" }}>
            EP {String(number).padStart(2, "0")}
          </div>
          <div style={{ fontFamily: theme.mono, fontSize: 30, color: theme.blue }}>{series}</div>
        </div>
        <div style={{ fontSize: 104, fontWeight: 800, letterSpacing: -4, lineHeight: 1, marginTop: 30, maxWidth: 700 }}>
          {lead}
          <br />
          <span style={{ color: theme.green }}>{last}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 40, fontFamily: theme.mono, fontSize: 28, color: theme.muted }}>
          <div style={{ width: 12, height: 12, borderRadius: 6, background: theme.green, boxShadow: `0 0 12px ${theme.green}` }} />
          FastAPI Startkit
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
