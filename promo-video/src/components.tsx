import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { HighlightedLine } from "./highlight";
import { FPS, theme } from "./theme";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const useFadeIn = (delay = 0, duration = 15) => {
  const frame = useCurrentFrame();
  return interpolate(frame - delay, [0, duration], [0, 1], clamp);
};

export const useRise = (delay = 0) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = spring({ frame: frame - delay, fps, config: { damping: 200 } });
  return { opacity: progress, transform: `translateY(${(1 - progress) * 40}px)` };
};

export const Backdrop: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const fadeOut = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], clamp);
  return (
    <AbsoluteFill
      style={{
        fontFamily: theme.sans,
        fontVariantLigatures: "none",
        color: theme.text,
      }}
    >
      <AbsoluteFill style={{ opacity: fadeOut, padding: "70px 120px 100px", justifyContent: "center" }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

const Orb: React.FC<{ color: string; x: number; y: number; size: number; speed: number; phase: number }> = ({ color, x, y, size, speed, phase }) => {
  const seconds = useCurrentFrame() / FPS;
  return (
    <div
      style={{
        position: "absolute",
        left: `${x + Math.sin(seconds * speed + phase) * 7}%`,
        top: `${y + Math.cos(seconds * speed * 0.8 + phase) * 7}%`,
        width: size,
        height: size,
        marginLeft: -size / 2,
        marginTop: -size / 2,
        borderRadius: "50%",
        background: `radial-gradient(circle, ${color} 0%, transparent 68%)`,
      }}
    />
  );
};

export const Ambient: React.FC = () => {
  const frame = useCurrentFrame();
  const drift = (frame / FPS) * 6;
  return (
    <AbsoluteFill style={{ background: theme.bg, overflow: "hidden" }}>
      <Orb color="rgba(34,197,94,0.26)" x={12} y={8} size={1200} speed={0.11} phase={0} />
      <Orb color="rgba(56,189,248,0.24)" x={88} y={85} size={1300} speed={0.09} phase={2} />
      <Orb color="rgba(192,132,252,0.18)" x={78} y={12} size={950} speed={0.13} phase={4} />
      <AbsoluteFill
        style={{
          backgroundImage: "linear-gradient(rgba(255,255,255,0.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.045) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          backgroundPosition: `${drift}px ${drift}px`,
          maskImage: "radial-gradient(ellipse at 50% 45%, black 25%, transparent 78%)",
          WebkitMaskImage: "radial-gradient(ellipse at 50% 45%, black 25%, transparent 78%)",
        }}
      />
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 50%, transparent 55%, rgba(2,4,12,0.6) 100%)" }} />
    </AbsoluteFill>
  );
};

export const Footer: React.FC<{ totalFrames: number; hideBefore: number; hideAfter: number }> = ({ totalFrames, hideBefore, hideAfter }) => {
  const frame = useCurrentFrame();
  const visible = interpolate(frame, [hideBefore - 10, hideBefore + 10, hideAfter - 10, hideAfter + 10], [0, 1, 1, 0], clamp);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          left: 120,
          right: 120,
          bottom: 30,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontFamily: theme.mono,
          fontSize: 20,
          color: theme.muted,
          opacity: visible * 0.85,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 10, height: 10, borderRadius: 5, background: theme.accent, boxShadow: `0 0 12px ${theme.accent}` }} />
          fastapi-startkit
        </div>
        <div>fastapi-startkit.github.io</div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          bottom: 0,
          height: 4,
          width: `${(frame / totalFrames) * 100}%`,
          background: `linear-gradient(90deg, ${theme.accent}, ${theme.accent2})`,
          boxShadow: `0 0 14px ${theme.accent2}`,
        }}
      />
    </AbsoluteFill>
  );
};

export const GradientText: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span style={{ background: theme.gradient, WebkitBackgroundClip: "text", backgroundClip: "text", color: "transparent" }}>{children}</span>
);

export const SceneHeading: React.FC<{ step: string; title: string; caption?: string }> = ({ step, title, caption }) => {
  const rise = useRise(0);
  const captionStyle = useRise(12);
  const [number, label] = step.split(" · ");
  return (
    <div style={{ marginBottom: 44 }}>
      <div
        style={{
          ...rise,
          display: "inline-flex",
          alignItems: "center",
          gap: 14,
          padding: "8px 18px",
          borderRadius: 999,
          border: `1.5px solid rgba(34,197,94,0.45)`,
          background: "rgba(34,197,94,0.08)",
          boxShadow: "0 0 24px rgba(34,197,94,0.18)",
          fontFamily: theme.mono,
          fontSize: 22,
          fontWeight: 600,
          letterSpacing: 2,
          textTransform: "uppercase",
        }}
      >
        <span style={{ color: theme.accent }}>{number}</span>
        <span style={{ width: 1.5, height: 20, background: "rgba(34,197,94,0.45)" }} />
        <span style={{ color: theme.text }}>{label}</span>
      </div>
      <div style={{ ...rise, fontFamily: theme.display, fontSize: 72, fontWeight: 700, letterSpacing: -2, lineHeight: 1.05, marginTop: 22 }}>{title}</div>
      {caption ? <div style={{ ...captionStyle, fontSize: 30, color: theme.muted, marginTop: 14 }}>{caption}</div> : null}
    </div>
  );
};

const WindowChrome: React.FC<{ title: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ title, children, style }) => (
  <div
    style={{
      background: theme.panel,
      border: `2px solid ${theme.panelBorder}`,
      borderRadius: 18,
      boxShadow: "0 30px 80px rgba(0,0,0,0.45)",
      overflow: "hidden",
      minWidth: 0,
      ...style,
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "16px 22px", borderBottom: `2px solid ${theme.panelBorder}` }}>
      {["#f87171", "#fbbf24", "#4ade80"].map((color) => (
        <div key={color} style={{ width: 16, height: 16, borderRadius: 8, background: color }} />
      ))}
      <div style={{ marginLeft: 16, fontFamily: theme.mono, fontSize: 24, color: theme.muted }}>{title}</div>
    </div>
    <div style={{ padding: "26px 34px" }}>{children}</div>
  </div>
);

export const CodeCard: React.FC<{
  file: string;
  lines: string[];
  delay?: number;
  perLine?: number;
  fontSize?: number;
  highlight?: number[];
  style?: React.CSSProperties;
}> = ({ file, lines, delay = 10, perLine = 4, fontSize = 30, highlight = [], style }) => {
  const frame = useCurrentFrame();
  const appear = useRise(delay - 8);
  return (
    <WindowChrome title={file} style={{ ...appear, ...style }}>
      <div style={{ fontFamily: theme.mono, fontSize, lineHeight: 1.5, whiteSpace: "pre" }}>
        {lines.map((line, index) => {
          const opacity = interpolate(frame - delay - index * perLine, [0, 8], [0, 1], clamp);
          const shift = interpolate(opacity, [0, 1], [-16, 0]);
          return (
            <div
              key={index}
              style={{
                opacity,
                transform: `translateX(${shift}px)`,
                margin: "0 -34px",
                padding: "0 31px",
                borderLeft: `3px solid ${highlight.includes(index) ? theme.accent : "transparent"}`,
                background: highlight.includes(index) ? "rgba(34,197,94,0.13)" : undefined,
              }}
            >
              <HighlightedLine code={line} />
            </div>
          );
        })}
      </div>
    </WindowChrome>
  );
};

export const BrowserWindow: React.FC<{ url: string; delay?: number; loadAt: number; children: React.ReactNode; style?: React.CSSProperties }> = ({
  url,
  delay = 0,
  loadAt,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const appear = useRise(delay);
  const typed = url.slice(0, Math.max(0, Math.floor((frame - delay - 10) * 1.2)));
  const progress = interpolate(frame, [loadAt - 14, loadAt], [0, 100], clamp);
  const page = interpolate(frame, [loadAt, loadAt + 10], [0, 1], clamp);
  return (
    <div
      style={{
        ...appear,
        display: "flex",
        flexDirection: "column",
        background: theme.panel,
        border: `2px solid ${theme.panelBorder}`,
        borderRadius: 18,
        boxShadow: "0 30px 80px rgba(0,0,0,0.45)",
        overflow: "hidden",
        minWidth: 0,
        ...style,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 22px" }}>
        {["#f87171", "#fbbf24", "#4ade80"].map((color) => (
          <div key={color} style={{ width: 16, height: 16, borderRadius: 8, background: color }} />
        ))}
        <div
          style={{
            marginLeft: 20,
            flex: 1,
            background: theme.bg,
            borderRadius: 10,
            padding: "8px 18px",
            fontFamily: theme.mono,
            fontSize: 22,
            color: theme.text,
          }}
        >
          <span style={{ color: theme.muted }}>⌂ </span>
          {typed}
        </div>
      </div>
      <div style={{ height: 4, width: `${progress}%`, background: theme.accent2, opacity: 1 - page }} />
      <div style={{ flex: 1, background: "#ffffff", color: "#0f172a", opacity: page }}>{children}</div>
    </div>
  );
};

export type TermLine ={ text: string; color?: string };

export type TermBlock =
  | { kind: "command"; text: string; at: number }
  | { kind: "lines"; lines: TermLine[]; at: number; stagger?: number }
  | { kind: "prompt"; draws: string[][]; at: number[] };

const BOX_LINE = /^([┌└│])(.*)([┐┘│])$/;

const BoxLine: React.FC<{ text: string }> = ({ text }) => {
  const match = BOX_LINE.exec(text);
  if (!match) return <>{text}</>;
  const [, left, body, right] = match;
  const border = { color: theme.boxBorder };
  if (left === "┌") {
    const [, title = body, rule = ""] = /^( [^─]+ )(─*)$/.exec(body) ?? [];
    return (
      <>
        <span style={border}>{left}</span>
        <span style={{ color: theme.accent2 }}>{title}</span>
        <span style={border}>{rule + right}</span>
      </>
    );
  }
  if (left === "└") {
    const [, rule = body, footer = ""] = /^(─*)(.*)$/.exec(body) ?? [];
    return (
      <>
        <span style={border}>{left + rule}</span>
        <span style={{ color: theme.muted }}>{footer}</span>
        <span style={border}>{right}</span>
      </>
    );
  }
  const active = body.startsWith(" › ");
  const inactive = body.startsWith("   ");
  return (
    <>
      <span style={border}>{left}</span>
      <span style={{ color: active ? theme.accent2 : inactive ? theme.muted : theme.text }}>{body}</span>
      <span style={border}>{right}</span>
    </>
  );
};

export const ScrollTerminal: React.FC<{
  blocks: TermBlock[];
  title?: string;
  rows: number;
  fontSize?: number;
  charsPerFrame?: number;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ blocks, title = "terminal", rows, fontSize = 26, charsPerFrame = 1.4, delay = 2, style }) => {
  const frame = useCurrentFrame();
  const appear = useRise(delay);
  const blink = Math.floor(frame / 15) % 2 === 0;
  const lines: React.ReactNode[] = [];
  blocks.forEach((block, blockIndex) => {
    if (block.kind === "command") {
      if (frame < block.at) return;
      const typed = block.text.slice(0, Math.floor((frame - block.at) * charsPerFrame));
      lines.push(
        <div key={blockIndex}>
          <span style={{ color: theme.accent }}>$ </span>
          {typed}
          {typed.length < block.text.length ? <span style={{ opacity: blink ? 1 : 0, color: theme.accent }}>▋</span> : null}
        </div>,
      );
    } else if (block.kind === "lines") {
      block.lines.forEach((line, lineIndex) => {
        const start = block.at + lineIndex * (block.stagger ?? 5);
        if (frame < start) return;
        lines.push(
          <div key={`${blockIndex}-${lineIndex}`} style={{ color: line.color ?? theme.muted, opacity: interpolate(frame - start, [0, 4], [0, 1], clamp) }}>
            {line.text || " "}
          </div>,
        );
      });
    } else {
      const step = block.at.filter((at) => frame >= at).length - 1;
      if (step < 0) return;
      block.draws[step].forEach((text, lineIndex) => {
        lines.push(
          <div key={`${blockIndex}-${lineIndex}`}>
            <BoxLine text={text} />
          </div>,
        );
      });
    }
  });
  const lineHeight = Math.round(fontSize * 1.25);
  return (
    <WindowChrome title={title} style={{ ...appear, ...style }}>
      <div
        style={{
          fontFamily: theme.mono,
          fontSize,
          lineHeight: `${lineHeight}px`,
          whiteSpace: "pre",
          height: rows * lineHeight,
          overflow: "hidden",
        }}
      >
        {lines.slice(-rows)}
      </div>
    </WindowChrome>
  );
};
