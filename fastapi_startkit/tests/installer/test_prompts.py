import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

import pytest

from fastapi_startkit.installer.prompts import Choice, Painter, Prompter, box, split_keys

UP, DOWN, ENTER, SPACE, BACKSPACE = "\x1b[A", "\x1b[B", "\r", " ", "\x7f"
DATABASES = [Choice("none", "None"), Choice("sqlite", "SQLite", "File-based"), Choice("postgres", "PostgreSQL")]
SERVICES = [Choice("web", "Web", "HTTP server"), Choice("worker", "Worker", "Background jobs")]
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class ScriptedScreen:
    def __init__(self, *keys: str):
        self.keys = list(keys)
        self.frames: list[list[str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def read(self) -> str:
        return self.keys.pop(0)

    def draw(self, lines):
        self.frames.append(list(lines))


def prompter(*keys: str) -> tuple[Prompter, ScriptedScreen]:
    screen = ScriptedScreen(*keys)
    return Prompter(screen, color=False, width=48), screen


def test_select_moves_and_wraps():
    prompts, _ = prompter(UP, UP, DOWN, "k", ENTER)
    assert prompts.select("Which database?", DATABASES, "sqlite") == "postgres"


def test_select_highlights_cursor_and_collapses_to_answer():
    prompts, screen = prompter(DOWN, ENTER)
    prompts.select("Which database?", DATABASES, "none")
    assert "│ › ● SQLite      File-based" in screen.frames[1][2]
    assert "○ None" in screen.frames[1][1]
    assert screen.frames[-1] == [
        "┌ Which database? ─────────────────────────────┐",
        "│ SQLite                                       │",
        "└──────────────────────────────────────────────┘",
    ]


def test_multiselect_toggles_and_requires_one_option():
    prompts, screen = prompter(SPACE, ENTER, DOWN, SPACE, ENTER)
    assert prompts.multiselect("Which services?", SERVICES, ["web"]) == ["worker"]
    assert "select at least one option" in screen.frames[2][-1]
    assert "Worker" in screen.frames[-1][1]


def test_multiselect_returns_choices_in_declared_order():
    prompts, screen = prompter(DOWN, SPACE, ENTER)
    assert prompts.multiselect("Which services?", SERVICES, ["web"]) == ["web", "worker"]
    assert "Web, Worker" in screen.frames[-1][1]


def test_text_edits_and_falls_back_to_default():
    prompts, _ = prompter("a", "p", "px", BACKSPACE, ENTER)
    assert prompts.text("Where?", "example-project") == "app"
    prompts, screen = prompter(UP, ENTER)
    assert prompts.text("Where?", "example-project") == "example-project"
    assert "example-project" in screen.frames[0][1]


def test_confirm_maps_choice_to_bool():
    assert prompter(ENTER)[0].confirm("Create?") is True
    assert prompter(DOWN, ENTER)[0].confirm("Create?") is False


def test_split_keys_separates_buffered_input():
    assert split_keys("\x1b[B \r") == [DOWN, SPACE, ENTER]
    assert split_keys("ab\x1bOA\x1b") == ["a", "b", "\x1bOA", "\x1b"]


def test_box_pads_by_visible_width_and_truncates():
    lines = box("Title", [[("a" * 80, "36")]], Painter(True), 20)
    assert {len(ANSI.sub("", line)) for line in lines} == {20}
    assert ANSI.sub("", lines[1]).endswith("… │")
    assert "\x1b[36m" in lines[1]
    assert "\x1b[" not in "".join(box("Title", [[("a", "36")]], Painter(False), 20))


@pytest.mark.skipif(sys.platform == "win32", reason="pseudo-terminals are Unix only")
def test_init_runs_interactive_prompts_in_a_terminal(tmp_path: Path):
    import pty

    destination = tmp_path / "project"
    leader, follower = pty.openpty()
    process = subprocess.Popen(
        [sys.executable, "-m", "fastapi_startkit.installer.cli", "init", str(destination), "--dry-run"],
        stdin=follower,
        stdout=follower,
        stderr=follower,
        env={**os.environ, "NO_COLOR": "1", "COLUMNS": "80"},
    )
    os.close(follower)
    output = b""

    def wait_for(text: str) -> None:
        nonlocal output
        deadline = time.monotonic() + 30
        while text.encode() not in output:
            assert time.monotonic() < deadline, output.decode(errors="ignore")
            if select.select([leader], [], [], 0.1)[0]:
                output += os.read(leader, 4096)

    for prompt, keys in (
        ("Which services", [DOWN, SPACE, ENTER]),
        ("Which database", [DOWN, ENTER]),
        ("Which frontend", [DOWN, DOWN, ENTER]),
    ):
        wait_for(prompt)
        for key in keys:
            os.write(leader, key.encode())
    wait_for("Application: both; database: postgres; frontend: vue")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if select.select([leader], [], [], 0.1)[0]:
            try:
                chunk = os.read(leader, 4096)
            except OSError:
                break
            if not chunk:
                break
            output += chunk
        elif process.poll() is not None:
            break
    os.close(leader)
    assert process.wait(timeout=30) == 0
    assert not destination.exists()
