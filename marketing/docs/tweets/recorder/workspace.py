import os
import shutil
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path("/tmp/startkit-demo")
STARTKIT = "fastapi-startkit==0.75.2"
CACHE = ROOT / "cache" / STARTKIT
KEEP = {".venv", "node_modules"}
TEMPLATES = {
    "web": ["--app", "web", "--database", "none", "--frontend", "none"],
    "react": ["--app", "web", "--database", "sqlite", "--frontend", "react"],
}


def clean_env() -> dict[str, str]:
    return {**{name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}, "PYTHONDONTWRITEBYTECODE": "1"}


def sh(command: str) -> None:
    subprocess.run(command, shell=True, cwd=WORKSPACE, check=True, env=clean_env())


def template(name: str) -> Path:
    target = CACHE / name / WORKSPACE.name
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["uvx", STARTKIT, "init", WORKSPACE.name, *TEMPLATES[name], "-n", "--no-deps"],
        cwd=target.parent, check=True, env=clean_env(),
    )
    return target


def reset() -> None:
    WORKSPACE.mkdir(exist_ok=True)
    for entry in WORKSPACE.iterdir():
        if entry.name in KEEP:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    shutil.copytree(template("web"), WORKSPACE, dirs_exist_ok=True)
    (WORKSPACE / ".vscode").mkdir(exist_ok=True)
    shutil.copy(ROOT / "vscode-settings.json", WORKSPACE / ".vscode" / "settings.json")


def adopt(name: str, paths: list[str]) -> None:
    source = template(name)
    for path in paths:
        origin = source / path
        if origin.is_dir():
            shutil.copytree(origin, WORKSPACE / path, dirs_exist_ok=True)
        else:
            (WORKSPACE / path).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(origin, WORKSPACE / path)


def write(files: dict[str, str]) -> None:
    for name, content in files.items():
        path = WORKSPACE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def read(name: str) -> str:
    return (WORKSPACE / name).read_text()


def answers(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            return response.status < 500
    except OSError:
        return False
