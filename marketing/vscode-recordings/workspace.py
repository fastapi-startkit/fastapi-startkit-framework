import io
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKSPACE = Path("/tmp/issue-tracker")
TAGS = ROOT / "tags"
REPO = "fastapi-startkit/issue-tracker"
KEEP = {".venv", "node_modules"}


def fetch(tag: str) -> Path:
    target = TAGS / tag
    if target.exists():
        return target
    archive = subprocess.run(["gh", "api", f"repos/{REPO}/tarball/{tag}"], capture_output=True, check=True).stdout
    staging = TAGS / f".{tag}"
    shutil.rmtree(staging, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            _, _, inner = member.name.partition("/")
            if not inner:
                continue
            member.name = inner
            tar.extract(member, staging, filter="data")
    staging.rename(target)
    return target


def clean_env() -> dict[str, str]:
    return {**{name: value for name, value in os.environ.items() if name != "VIRTUAL_ENV"}, "PYTHONDONTWRITEBYTECODE": "1"}


def sh(command: str) -> None:
    WORKSPACE.mkdir(exist_ok=True)
    subprocess.run(command, shell=True, cwd=WORKSPACE, check=True, env=clean_env())


def checkout(tag: str) -> None:
    source = fetch(tag)
    WORKSPACE.mkdir(exist_ok=True)
    for entry in WORKSPACE.iterdir():
        if entry.name in KEEP:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()
    shutil.copytree(source, WORKSPACE, dirs_exist_ok=True)
    (WORKSPACE / ".vscode").mkdir(exist_ok=True)
    shutil.copy(ROOT / "vscode-settings.json", WORKSPACE / ".vscode" / "settings.json")
    shutil.copy(WORKSPACE / ".env.example", WORKSPACE / ".env")


def write(files: dict[str, str]) -> None:
    for name, content in files.items():
        path = WORKSPACE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def drift(tag: str, files: list[str]) -> list[str]:
    source = fetch(tag)
    return [name for name in files if (WORKSPACE / name).read_text() != (source / name).read_text()]
