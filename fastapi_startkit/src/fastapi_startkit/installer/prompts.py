from __future__ import annotations

import os
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol, TextIO

try:
    import termios
    import tty
except ImportError:
    termios = None
    tty = None

CYAN = "36"
GRAY = "90"
YELLOW = "33"
INVERSE = "7"
UP = {"\x1b[A", "\x1bOA", "k"}
DOWN = {"\x1b[B", "\x1bOB", "j"}
ENTER = {"\r", "\n"}
SPACE = {" "}
BACKSPACE = {"\x7f", "\x08"}
WIDTH = 64

Segment = tuple[str, str]


@dataclass(frozen=True)
class Choice:
    value: str
    label: str
    hint: str = ""


class Painter:
    def __init__(self, color: bool):
        self.color = color

    def __call__(self, text: str, code: str) -> str:
        if self.color and code and text:
            return f"\x1b[{code}m{text}\x1b[0m"
        return text


def fit(segments: Sequence[Segment], width: int) -> list[Segment]:
    fitted: list[Segment] = []
    remaining = width
    for text, code in segments:
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[: remaining - 1] + "…"
        fitted.append((text, code))
        remaining -= len(text)
    return fitted


def box(
    title: str,
    rows: Sequence[Sequence[Segment]],
    paint: Painter,
    width: int,
    footer: str = "",
    accent: str = CYAN,
    footer_style: str = GRAY,
) -> list[str]:
    inner = width - 4
    head = fit([(f" {title} ", accent)], width - 2)[0][0]
    foot = fit([(f" {footer} ", footer_style)], width - 2)[0][0] if footer else ""
    lines = [paint("┌", GRAY) + paint(head, accent) + paint("─" * (width - 2 - len(head)) + "┐", GRAY)]
    for row in rows:
        segments = fit(row, inner)
        visible = sum(len(text) for text, _ in segments)
        content = "".join(paint(text, code) for text, code in segments)
        lines.append(paint("│", GRAY) + " " + content + " " * (inner - visible) + " " + paint("│", GRAY))
    lines.append(paint("└" + "─" * (width - 2 - len(foot)), GRAY) + paint(foot, footer_style) + paint("┘", GRAY))
    return lines


def split_keys(data: str) -> list[str]:
    keys: list[str] = []
    index = 0
    while index < len(data):
        end = index + 1
        if data.startswith("\x1b[", index):
            end = index + 2
            while end < len(data) and not "@" <= data[end] <= "~":
                end += 1
            end = min(end + 1, len(data))
        elif data.startswith("\x1bO", index):
            end = min(index + 3, len(data))
        keys.append(data[index:end])
        index = end
    return keys


class Screen(Protocol):
    def __enter__(self) -> Screen: ...

    def __exit__(self, *exc: object) -> None: ...

    def read(self) -> str: ...

    def draw(self, lines: Sequence[str]) -> None: ...


class Terminal:
    def __init__(self, input: TextIO, output: TextIO):
        self.input = input
        self.output = output
        self.height = 0
        self.saved: Any = None
        self.pending: list[str] = []

    @staticmethod
    def supported(input: Any, output: Any) -> bool:
        return termios is not None and input is not None and input.isatty() and output.isatty()

    def __enter__(self) -> Terminal:
        assert termios is not None and tty is not None
        descriptor = self.input.fileno()
        self.saved = termios.tcgetattr(descriptor)
        tty.setcbreak(descriptor)
        self.height = 0
        self.output.write("\x1b[?25l")
        return self

    def __exit__(self, *exc: object) -> None:
        assert termios is not None
        termios.tcsetattr(self.input.fileno(), termios.TCSADRAIN, self.saved)
        self.output.write("\x1b[?25h")
        self.output.flush()

    def read(self) -> str:
        while not self.pending:
            self.pending = split_keys(os.read(self.input.fileno(), 1024).decode(errors="ignore"))
        return self.pending.pop(0)

    def draw(self, lines: Sequence[str]) -> None:
        if self.height:
            self.output.write(f"\x1b[{self.height}F\x1b[J")
        self.output.write("\n".join(lines) + "\n")
        self.output.flush()
        self.height = len(lines)


class Prompter:
    def __init__(self, screen: Screen, color: bool | None = None, width: int | None = None):
        self.screen = screen
        self.paint = Painter("NO_COLOR" not in os.environ if color is None else color)
        self.width = width or min(WIDTH, shutil.get_terminal_size().columns - 1)

    def text(self, title: str, default: str) -> str:
        value = ""
        with self.screen as screen:
            while True:
                caret = (" ", INVERSE) if self.paint.color else ("_", "")
                row = [(value, ""), caret] if value else [caret, (default, GRAY)]
                screen.draw(box(title, [row], self.paint, self.width))
                key = screen.read()
                if key in ENTER:
                    break
                if key in BACKSPACE:
                    value = value[:-1]
                elif key.isprintable():
                    value += key
            answer = value or default
            screen.draw(self.submitted(title, answer))
        return answer

    def select(self, title: str, choices: Sequence[Choice], default: str) -> str:
        cursor = [choice.value for choice in choices].index(default)
        with self.screen as screen:
            while True:
                rows = [
                    self.row(choice, index == cursor, "●" if index == cursor else "○", choices)
                    for index, choice in enumerate(choices)
                ]
                screen.draw(box(title, rows, self.paint, self.width))
                key = screen.read()
                if key in ENTER:
                    break
                cursor = self.move(cursor, key, len(choices))
            screen.draw(self.submitted(title, choices[cursor].label))
        return choices[cursor].value

    def multiselect(self, title: str, choices: Sequence[Choice], defaults: Sequence[str]) -> list[str]:
        cursor = 0
        selected = set(defaults)
        footer, footer_style = "space to toggle, enter to confirm", GRAY
        with self.screen as screen:
            while True:
                rows = [
                    self.row(choice, index == cursor, "◼" if choice.value in selected else "◻", choices)
                    for index, choice in enumerate(choices)
                ]
                screen.draw(box(title, rows, self.paint, self.width, footer=footer, footer_style=footer_style))
                key = screen.read()
                if key in ENTER:
                    if selected:
                        break
                    footer, footer_style = "select at least one option", YELLOW
                elif key in SPACE:
                    selected ^= {choices[cursor].value}
                else:
                    cursor = self.move(cursor, key, len(choices))
            answer = [choice for choice in choices if choice.value in selected]
            screen.draw(self.submitted(title, ", ".join(choice.label for choice in answer)))
        return [choice.value for choice in answer]

    def confirm(self, title: str, default: bool = True) -> bool:
        choices = [Choice("yes", "Yes"), Choice("no", "No")]
        return self.select(title, choices, "yes" if default else "no") == "yes"

    def row(self, choice: Choice, active: bool, mark: str, choices: Sequence[Choice]) -> list[Segment]:
        width = max(len(other.label) for other in choices)
        segments: list[Segment] = [
            ("› " if active else "  ", CYAN),
            (mark, CYAN if active else GRAY),
            (f" {choice.label:<{width}}", "" if active else GRAY),
        ]
        if choice.hint:
            segments.append((f"  {choice.hint}", GRAY))
        return segments

    def submitted(self, title: str, answer: str) -> list[str]:
        return box(title, [[(answer, "")]], self.paint, self.width, accent=GRAY)

    @staticmethod
    def move(cursor: int, key: str, count: int) -> int:
        if key in UP:
            return (cursor - 1) % count
        if key in DOWN:
            return (cursor + 1) % count
        return cursor


class ClassicPrompts:
    def __init__(self, command: Any):
        self.command = command

    def text(self, title: str, default: str) -> str:
        return self.command.ask(title, default=default)

    def select(self, title: str, choices: Sequence[Choice], default: str) -> str:
        labels = self.labels(choices)
        index = [choice.value for choice in choices].index(default)
        picked = self.command.choice(title, list(labels), default=index, attempts=3)
        return labels[picked]

    def multiselect(self, title: str, choices: Sequence[Choice], defaults: Sequence[str]) -> list[str]:
        labels = self.labels(choices)
        indexes = ",".join(str(index) for index, choice in enumerate(choices) if choice.value in defaults)
        picked = self.command.choice(
            f"{title} (comma-separated)", list(labels), default=indexes, attempts=3, multiple=True
        )
        chosen = {labels[label] for label in picked}
        return [choice.value for choice in choices if choice.value in chosen]

    def confirm(self, title: str, default: bool = True) -> bool:
        return self.command.confirm(title, default=default)

    @staticmethod
    def labels(choices: Sequence[Choice]) -> dict[str, str]:
        width = max(len(choice.label) for choice in choices)
        return {f"{choice.label:<{width}}  {choice.hint}".rstrip(): choice.value for choice in choices}
