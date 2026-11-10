import json
import random
import shutil
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
APP_URL = "http://127.0.0.1:8000"
HIDE_QUICK_INPUT = """() => {
  const style = document.createElement('style')
  style.id = 'quiet'
  style.textContent = '.quick-input-widget { opacity: 0 !important }'
  document.head.appendChild(style)
}"""
SHOW_QUICK_INPUT = "() => document.getElementById('quiet')?.remove()"


@dataclass
class Take:
    name: str
    tag: str | None
    perform: Callable[["Studio"], None]
    folder: Path = workspace.WORKSPACE
    sidebar: bool = False
    maximized: bool = False
    teardown: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    setup: list[str] = field(default_factory=list)
    ready: list[str] = field(default_factory=list)
    open: str | None = None
    panel: float = 0.48
    server: bool = False
    browser: str | None = None
    zoom: float = 1.5
    verify_tag: str | None = None
    verify_files: list[str] = field(default_factory=list)


class Studio:
    def __init__(self, page: Page, shots: Path, take: Take, started: float):
        self.page = page
        self.shots = shots
        self.take = take
        self.started = started
        self.cues: dict[str, float] = {}

    def cue(self, name: str) -> None:
        self.cues.setdefault(name, round(time.monotonic() - self.started, 2))

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

    def quietly(self, keys: str, text: str) -> None:
        self.page.evaluate(HIDE_QUICK_INPUT)
        self.press(keys, 0.3)
        self.page.keyboard.type(text)
        time.sleep(0.4)
        self.press("Enter", 0.5)
        self.page.evaluate(SHOW_QUICK_INPUT)

    def command(self, text: str) -> None:
        self.quietly("F1", text)

    def open(self, name: str) -> None:
        self.press("ControlOrMeta+p", 0.3)
        self.page.keyboard.type(name)
        time.sleep(0.6)
        self.press("Enter", 0.7)

    def line(self, number: int, end: bool = True) -> None:
        self.quietly("ControlOrMeta+p", f":{number}")
        if end:
            self.press("End", 0.3)

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

    def click(self, selector: str, steps: int = 25) -> None:
        box = self.page.locator(selector).first.bounding_box()
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)
        time.sleep(0.25)
        self.page.mouse.down()
        time.sleep(0.08)
        self.page.mouse.up()
        time.sleep(0.4)

    def pytest(self, command: str = "uv run pytest") -> None:
        report = workspace.WORKSPACE / ".pytest_cache" / "v" / "cache" / "nodeids"
        before = report.stat().st_mtime if report.exists() else 0
        self.type(command, 0.06)
        time.sleep(0.3)
        self.page.keyboard.press("Enter")
        deadline = time.time() + 60
        while time.time() < deadline and (not report.exists() or report.stat().st_mtime == before):
            time.sleep(0.05)
        time.sleep(0.25)


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


def start_vscode(port: int, log: Path, folder: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [
            "code", "serve-web",
            "--host", "127.0.0.1",
            "--port", str(port),
            "--without-connection-token",
            "--accept-server-license-terms",
            "--disable-telemetry",
            "--server-data-dir", str(SERVER_DATA),
        ],
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
        cwd=folder,
        env={**workspace.clean_env(), "ZDOTDIR": str(ROOT / "shell")},
    )


def start_app(log: Path) -> subprocess.Popen:
    server = subprocess.Popen(
        ["uv", "run", "python", "artisan", "serve"],
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
        cwd=workspace.WORKSPACE,
        env=workspace.clean_env(),
    )
    wait_for_http(f"{APP_URL}/health", 120)
    return server


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
    if not studio.take.sidebar:
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
    if studio.take.maximized:
        studio.command("View: Toggle Maximized Panel")
        studio.terminal(clear=True)
    else:
        studio.command("View: Focus Active Editor Group")
    time.sleep(1)


CURSOR = """
addEventListener('DOMContentLoaded', () => {
  document.documentElement.style.zoom = '%s'
  const cursor = document.createElement('div')
  cursor.style.cssText = 'position:fixed;left:0;top:0;width:22px;height:22px;margin:-11px 0 0 -11px;border-radius:50%%;background:rgba(17,24,39,.35);border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.4);pointer-events:none;z-index:2147483647;transition:transform .12s'
  document.body.appendChild(cursor)
  const scale = parseFloat(document.documentElement.style.zoom) || 1
  addEventListener('mousemove', event => { cursor.style.left = event.clientX / scale + 'px'; cursor.style.top = event.clientY / scale + 'px' })
  addEventListener('mousedown', () => { cursor.style.transform = 'scale(.7)' })
  addEventListener('mouseup', () => { cursor.style.transform = '' })
})
"""


def prepare_browser(studio: Studio, url: str) -> None:
    page = studio.page
    page.goto(url)
    page.wait_for_load_state("networkidle")
    page.mouse.move(SIZE["width"] * 0.62, SIZE["height"] * 0.7)
    time.sleep(1)


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


def record(take: Take, recordings: Path) -> dict:
    recordings.mkdir(parents=True, exist_ok=True)
    shots = recordings / "frames"
    shots.mkdir(exist_ok=True)
    RAW.mkdir(exist_ok=True)
    if take.tag:
        workspace.checkout(take.tag)
    workspace.write(take.files)
    for command in take.setup:
        workspace.sh(command)
    processes = []
    try:
        if take.server or take.browser:
            processes.append(start_app(RAW / "app.log"))
        for command in take.ready:
            workspace.sh(command)
        if not take.browser:
            port = free_port()
            processes.append(start_vscode(port, RAW / "serve-web.log", take.folder))
            wait_for_http(f"http://127.0.0.1:{port}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(
                viewport=SIZE,
                device_scale_factor=1,
                color_scheme="light",
                record_video_dir=str(RAW),
                record_video_size=SIZE,
            )
            if take.browser:
                context.add_init_script(CURSOR % take.zoom)
            page = context.new_page()
            opened = time.monotonic()
            studio = Studio(page, shots, take, opened)
            try:
                if take.browser:
                    prepare_browser(studio, f"{APP_URL}{take.browser}")
                else:
                    prepare_vscode(studio, f"http://127.0.0.1:{port}/?folder={take.folder}")
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
        if take.verify_tag:
            changed = workspace.drift(take.verify_tag, take.verify_files)
            if changed:
                raise RuntimeError(f"{take.name}: typed code differs from {take.verify_tag}: {changed}")
        target = recordings / f"{take.name}.mp4"
        cut(video, start, end, target)
        (recordings / f"{take.name}.cues.json").write_text(json.dumps(studio.cues, indent=1) + "\n")
        video.unlink()
        return {"take": take.name, "seconds": round(end - start, 2), "cues": studio.cues}
    finally:
        for process in processes:
            process.terminate()
            process.wait()
        for command in take.teardown:
            subprocess.run(command, shell=True)
        shutil.rmtree(SERVER_DATA / "data" / "User" / "workspaceStorage", ignore_errors=True)
