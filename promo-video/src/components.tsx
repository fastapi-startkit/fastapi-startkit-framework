import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { HighlightedLine } from "./highlight";
import { theme } from "./theme";

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
        background: `radial-gradient(circle at 20% 15%, ${theme.bgAccent} 0%, ${theme.bg} 60%)`,
        fontFamily: theme.sans,
        color: theme.text,
      }}
    >
      <AbsoluteFill style={{ opacity: fadeOut, padding: "80px 120px" }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export const SceneHeading: React.FC<{ step: string; title: string; caption?: string }> = ({ step, title, caption }) => {
  const rise = useRise(0);
  const captionStyle = useRise(12);
  return (
    <div style={{ marginBottom: 44 }}>
      <div style={{ ...rise, fontSize: 28, fontWeight: 700, color: theme.accent, letterSpacing: 4, textTransform: "uppercase" }}>
        {step}
      </div>
      <div style={{ ...rise, fontSize: 68, fontWeight: 800, marginTop: 8 }}>{title}</div>
      {caption ? <div style={{ ...captionStyle, fontSize: 32, color: theme.muted, marginTop: 12 }}>{caption}</div> : null}
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
  style?: React.CSSProperties;
}> = ({ file, lines, delay = 10, perLine = 4, fontSize = 30, style }) => {
  const frame = useCurrentFrame();
  const appear = useRise(delay - 8);
  return (
    <WindowChrome title={file} style={{ ...appear, ...style }}>
      <div style={{ fontFamily: theme.mono, fontSize, lineHeight: 1.5, whiteSpace: "pre" }}>
        {lines.map((line, index) => {
          const opacity = interpolate(frame - delay - index * perLine, [0, 8], [0, 1], clamp);
          const shift = interpolate(opacity, [0, 1], [-16, 0]);
          return (
            <div key={index} style={{ opacity, transform: `translateX(${shift}px)` }}>
              <HighlightedLine code={line} />
            </div>
          );
        })}
      </div>
    </WindowChrome>
  );
};

export type TerminalStep = { command: string; output: { text: string; color?: string }[] };

export const Terminal: React.FC<{ steps: TerminalStep[]; delay?: number; charsPerFrame?: number; gap?: number; style?: React.CSSProperties }> = ({
  steps,
  delay = 10,
  charsPerFrame = 1.2,
  gap = 30,
  style,
}) => {
  const frame = useCurrentFrame();
  const appear = useRise(delay - 8);
  let cursor = delay;
  const rendered = steps.map((step, index) => {
    const start = cursor;
    const typingFrames = Math.ceil(step.command.length / charsPerFrame);
    const outputStart = start + typingFrames + 8;
    cursor = outputStart + step.output.length * 6 + gap;
    if (frame < start) return null;
    const typed = step.command.slice(0, Math.floor((frame - start) * charsPerFrame));
    const typing = typed.length < step.command.length;
    const blink = Math.floor(frame / 15) % 2 === 0;
    return (
      <div key={index} style={{ marginBottom: 18 }}>
        <div>
          <span style={{ color: theme.accent }}>$ </span>
          <span>{typed}</span>
          {typing || (index === steps.length - 1 && step.output.length === 0) ? (
            <span style={{ opacity: blink ? 1 : 0, color: theme.accent }}>▋</span>
          ) : null}
        </div>
        {step.output.map((line, lineIndex) => (
          <div key={lineIndex} style={{ opacity: interpolate(frame - outputStart - lineIndex * 6, [0, 6], [0, 1], clamp), color: line.color ?? theme.muted }}>
            {line.text}
          </div>
        ))}
      </div>
    );
  });
  return (
    <WindowChrome title="terminal" style={{ ...appear, ...style }}>
      <div style={{ fontFamily: theme.mono, fontSize: 34, lineHeight: 1.55, whiteSpace: "pre", minHeight: 120 }}>{rendered}</div>
    </WindowChrome>
  );
};

export const Pill: React.FC<{ label: string; delay: number; color?: string }> = ({ label, delay, color = theme.accent2 }) => {
  const rise = useRise(delay);
  return (
    <div
      style={{
        ...rise,
        fontFamily: theme.mono,
        fontSize: 28,
        padding: "12px 24px",
        borderRadius: 999,
        border: `2px solid ${color}`,
        color,
        background: "rgba(56,189,248,0.08)",
      }}
    >
      {label}
    </div>
  );
};
