import React from "react";
import { theme } from "./theme";

const KEYWORDS = new Set([
  "from", "import", "class", "def", "async", "await", "return", "self", "lambda",
  "None", "True", "False", "export", "default", "const", "for", "in", "if",
]);

const TOKEN = /(#.*$|\/\/.*$)|("[^"]*"|'[^']*')|(@\w+)|(\{\{|\}\})|(\b\d+\b)|(\b[A-Za-z_]\w*\b)(?=\s*[(\[])|(\b[A-Za-z_]\w*\b)/g;

const colorFor = (match: RegExpExecArray): string => {
  const [, comment, str, decorator, jinja, num, call, word] = match;
  if (comment) return theme.comment;
  if (str) return theme.string;
  if (decorator) return theme.decorator;
  if (jinja) return theme.decorator;
  if (num) return theme.number;
  const ident = call ?? word;
  if (KEYWORDS.has(ident)) return theme.keyword;
  if (/^[A-Z]/.test(ident)) return theme.type;
  if (call) return theme.func;
  return theme.text;
};

export const HighlightedLine: React.FC<{ code: string }> = ({ code }) => {
  const parts: React.ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  TOKEN.lastIndex = 0;
  while ((match = TOKEN.exec(code)) !== null) {
    if (match.index > last) parts.push(code.slice(last, match.index));
    parts.push(
      <span key={match.index} style={{ color: colorFor(match) }}>
        {match[0]}
      </span>,
    );
    last = match.index + match[0].length;
  }
  if (last < code.length) parts.push(code.slice(last));
  return <>{parts.length ? parts : " "}</>;
};
