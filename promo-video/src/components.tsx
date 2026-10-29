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
        fontVariantLigatures: "none",
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

export type TermLine = { text: string; color?: string };

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
  rows: number;
  fontSize?: number;
  charsPerFrame?: number;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ blocks, rows, fontSize = 26, charsPerFrame = 1.4, delay = 2, style }) => {
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
    <WindowChrome title="terminal" style={{ ...appear, ...style }}>
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
