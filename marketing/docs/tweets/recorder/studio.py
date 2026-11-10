import json
import os
import random
import shutil
import signal
import socket
import subprocess
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

import workspace

ROOT = Path(__file__).resolve().parent
SERVER_DATA = ROOT / ".vscode-server"
RAW = ROOT / "raw"
SIZE = {"width": 1920, "height": 1080}
APP_PORT = 8100
APP_URL = f"http://127.0.0.1:{APP_PORT}"
WORDS_PER_SECOND = 2.6
BREATH = 0.35


@dataclass
class Take:
    name: str
    perform: Callable[["Studio"], None]
    prepare: Callable[[], None] = lambda: None
    open: str | None = None
    panel: float = 0.48
    browser: str | None = None
    background: list[str] = field(default_factory=list)
    ready: list[str] = field(default_factory=list)
    zoom: float = 1.5
    verify: list[str] = field(default_factory=list)


@dataclass
class Beat:
    offset: float
    seconds: float


class Studio:
    def __init__(self, page: Page, shots: Path, take: Take, beats: dict[str, Beat]):
        self.page = page
        self.shots = shots
        self.take = take
        self.beats = beats
        self.started = time.monotonic()
        self.cues: dict[str, float] = {}

    def now(self) -> float:
        return round(time.monotonic() - self.started, 2)

    def cue(self, name: str) -> None:
        self.cues.setdefault(name, self.now())

    def hold(self, name: str, extra: float = 0.0) -> None:
        beat = self.beats[name]
        until = self.cues[name] + beat.offset + beat.seconds + BREATH + extra
        time.sleep(max(0.0, until - self.now()))

    def say(self, name: str, extra: float = 0.0) -> None:
        self.cue(name)
        self.hold(name, extra)

    def wait(self, seconds: float) -> None:
        time.sleep(seconds)

    def shot(self, name: str) -> None:
        self.page.screenshot(path=str(self.shots / f"{self.take.name}-{name}.png"))

    def type(self, text: str, pace: float = 0.05) -> None:
        for char in text:
            if char == "\n":
                self.page.keyboard.press("Enter")
                time.sleep(pace * 3)
                continue
            self.page.keyboard.type(char)
            pause = random.uniform(pace * 0.5, pace * 1.6)
            if char in " (.":
                pause += pace * 0.6
            time.sleep(pause)

    def press(self, key: str, settle: float = 0.3) -> None:
        self.page.keyboard.press(key)
        time.sleep(settle)

    def command(self, text: str) -> None:
        self.press("F1", 0.4)
        self.page.keyboard.type(text)
        time.sleep(0.6)
        self.press("Enter", 0.6)

    def open(self, name: str) -> None:
        self.press("ControlOrMeta+p", 0.3)
        self.page.keyboard.type(name)
        time.sleep(0.6)
        self.press("Enter", 0.7)

    def line(self, number: int, end: bool = True) -> None:
        self.press("ControlOrMeta+p", 0.3)
        self.page.keyboard.type(f":{number}")
        time.sleep(0.4)
        self.press("Enter", 0.3)
        if end:
            self.press("End", 0.3)

    def bottom(self) -> None:
        self.line(99999)

    def save(self) -> None:
        self.press("ControlOrMeta+s", 0.4)

    def editor(self) -> None:
        self.press("ControlOrMeta+1", 0.3)

    def terminal(self, clear: bool = False) -> None:
        self.page.locator(".terminal-wrapper").first.click()
        time.sleep(0.3)
        if clear:
            self.press("ControlOrMeta+k", 0.4)

    def run(self, command: str, settle: float = 1.5, pace: float = 0.05) -> None:
        self.type(command, pace)
        time.sleep(0.3)
        self.press("Enter", settle)

    def until(self, check: Callable[[], bool], seconds: float = 120) -> None:
        deadline = time.time() + seconds
        while time.time() < deadline and not check():
            time.sleep(0.1)
        time.sleep(0.3)

    def pytest(self, command: str = "uv run pytest") -> None:
        report = workspace.WORKSPACE / ".pytest_cache" / "v" / "cache" / "nodeids"
        before = report.stat().st_mtime if report.exists() else 0
        self.run(command, settle=0)
        self.until(lambda: report.exists() and report.stat().st_mtime != before, 90)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_http(url: str, seconds: float = 240) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                if response.status < 500:
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"nothing answered on {url}")


def spawn(command: list[str] | str, log: Path, env: dict[str, str] | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        command,
        shell=isinstance(command, str),
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
        cwd=workspace.WORKSPACE,
        env=env or workspace.clean_env(),
        start_new_session=True,
    )


def start_vscode(port: int) -> subprocess.Popen:
    return spawn(
        [
            "code", "serve-web",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--without-connection-token",
            "--accept-server-license-terms",
            "--disable-telemetry",
            "--server-data-dir", str(SERVER_DATA),
        ],
        RAW / "serve-web.log",
        {**workspace.clean_env(), "ZDOTDIR": str(ROOT / "shell")},
    )


def start_app() -> subprocess.Popen:
    server = spawn(["uv", "run", "python", "artisan", "serve", "--port", str(APP_PORT)], RAW / "app.log")
    wait_for_http(f"{APP_URL}/health", 120)
    return server


def stop(process: subprocess.Popen) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    try:
        process.wait(10)
    except subprocess.TimeoutExpired:
        process.kill()


def trust(page: Page) -> None:
    for label in ("Yes, I trust the authors", "Trust Folder & Continue", "Trust"):
        button = page.get_by_role("button", name=label, exact=True)
        if button.count():
            button.first.click()
            time.sleep(1.5)
            return


def prepare_vscode(studio: Studio, url: str) -> None:
    page = studio.page
    page.goto(url)
    page.wait_for_selector(".monaco-workbench", timeout=120_000)
    time.sleep(4)
    trust(page)
    if studio.take.open:
        studio.open(studio.take.open)
    studio.command("View: Close Primary Side Bar")
    studio.command("Notifications: Clear All Notifications")
    studio.command("Terminal: Create New Terminal")
    time.sleep(1)
    trust(page)
    time.sleep(2)
    sash = page.locator(".part.panel").first.bounding_box()
    page.mouse.move(SIZE["width"] / 2, sash["y"] - 2)
    page.mouse.down()
    page.mouse.move(SIZE["width"] / 2, SIZE["height"] * studio.take.panel, steps=10)
    page.mouse.up()
    time.sleep(0.5)
    studio.terminal(clear=True)
    studio.command("View: Focus Active Editor Group")
    time.sleep(1)


def prepare_browser(studio: Studio, url: str) -> None:
    page = studio.page
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.evaluate(f"document.documentElement.style.zoom = '{studio.take.zoom}'")
    time.sleep(1.5)


def cut(video: Path, start: float, end: float, target: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start:.2f}", "-to", f"{end:.2f}", "-i", str(video),
            "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
            "-movflags", "+faststart", str(target),
        ],
        check=True,
    )


def beats_for(take: str, episode: dict, narration: Path) -> dict[str, Beat]:
    beats = {}
    for entry in next(item for item in episode["takes"] if item["name"] == take)["beats"]:
        timing = narration / f"{take}-{entry['cue']}.json"
        seconds = json.loads(timing.read_text())["seconds"] if timing.exists() else len(entry["say"].split()) / WORDS_PER_SECOND
        beats[entry["cue"]] = Beat(entry.get("offset", 0.0), seconds)
    return beats


def record(take: Take, folder: Path, episode: dict) -> dict:
    recordings = folder / "recordings"
    shots = recordings / "frames"
    shots.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(exist_ok=True)
    workspace.reset()
    take.prepare()
    processes = []
    try:
        for index, command in enumerate(take.background):
            processes.append(spawn(command, RAW / f"background-{index}.log"))
        for url in take.ready:
            wait_for_http(url, 120)
        if take.browser:
            processes.append(start_app())
        else:
            port = free_port()
            processes.append(start_vscode(port))
            wait_for_http(f"http://127.0.0.1:{port}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport=SIZE,
                device_scale_factor=1,
                color_scheme="dark",
                record_video_dir=str(RAW),
                record_video_size=SIZE,
            )
            page = context.new_page()
            opened = time.monotonic()
            studio = Studio(page, shots, take, beats_for(take.name, episode, folder / "narration"))
            try:
                if take.browser:
                    prepare_browser(studio, f"{APP_URL}{take.browser}")
                else:
                    prepare_vscode(studio, f"http://127.0.0.1:{port}/?folder={workspace.WORKSPACE}")
                start = time.monotonic() - opened
                studio.started = time.monotonic()
                take.perform(studio)
            except Exception:
                page.screenshot(path=str(shots / f"{take.name}-error.png"))
                raise
            end = time.monotonic() - opened
            video = Path(page.video.path())
            context.close()
            browser.close()
        for command in take.verify:
            workspace.sh(command)
        target = recordings / f"{take.name}.mp4"
        cut(video, start, end, target)
        (recordings / f"{take.name}.cues.json").write_text(json.dumps(studio.cues, indent=1) + "\n")
        video.unlink()
        return {"take": take.name, "seconds": round(end - start, 2), "cues": studio.cues}
    finally:
        for process in processes:
            stop(process)
        shutil.rmtree(SERVER_DATA / "data" / "User" / "workspaceStorage", ignore_errors=True)
