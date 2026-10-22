import ast
from collections.abc import Sequence
from importlib.resources import files
from pathlib import Path
from string import Template

from cleo.helpers import option

from fastapi_startkit.console.command import Command
from fastapi_startkit.installer.plan import DRIVER_CLASSES

CONFIG_PATH = "config/database.py"
BOOTSTRAP_PATH = "bootstrap/application.py"
PROVIDER = "(DatabaseProvider, DatabaseConfig)"
IMPORTS = {
    "DatabaseProvider": "from fastapi_startkit.masoniteorm import DatabaseProvider",
    "DatabaseConfig": "from config.database import DatabaseConfig",
}

Insert = tuple[int, str]


class DatabaseInstallCommand(Command):
    name = "database:install"
    description = "Publish config/database.py and register DatabaseProvider in bootstrap/application.py."

    options = [
        option(
            "driver",
            "d",
            description=f"Database driver: {', '.join(DRIVER_CLASSES)}.",
            flag=False,
            default="sqlite",
        ),
        option("force", "f", description=f"Overwrite an existing {CONFIG_PATH}."),
    ]

    def handle(self) -> int:
        driver = self.option("driver")
        if driver not in DRIVER_CLASSES:
            self.line_error(f"<error>Unsupported driver '{driver}'. Use one of: {', '.join(DRIVER_CLASSES)}.</error>")
            return 1

        base_path = Path(self.container.base_path)
        self.write_config(base_path / CONFIG_PATH, driver)
        return self.register_provider(base_path / BOOTSTRAP_PATH)

    def write_config(self, path: Path, driver: str) -> None:
        if path.exists() and not self.option("force"):
            self.line(f"<comment>{CONFIG_PATH} already exists, skipped. Use --force to overwrite it.</comment>")
            return

        stub = files("fastapi_startkit.installer").joinpath("stubs/database/config.py.stub").read_text(encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(Template(stub).substitute(driver=driver, driver_class=DRIVER_CLASSES[driver]), encoding="utf-8")
        self.line(f"Created <info>{CONFIG_PATH}</info>")

    def register_provider(self, path: Path) -> int:
        source = path.read_text(encoding="utf-8") if path.exists() else None
        updated = register_database_provider(source) if source is not None else None

        if updated is None:
            self.line_error(f"<error>Could not find Application(providers=[...]) in {BOOTSTRAP_PATH}.</error>")
            self.line_error("Register the provider manually:")
            for statement in IMPORTS.values():
                self.line_error(f"  {statement}")
            self.line_error(f"  providers=[..., {PROVIDER}]")
            return 1

        if updated == source:
            self.line(f"<comment>DatabaseProvider is already registered in {BOOTSTRAP_PATH}.</comment>")
            return 0

        path.write_text(updated, encoding="utf-8")
        self.line(f"Registered <info>DatabaseProvider</info> in <info>{BOOTSTRAP_PATH}</info>")
        return 0


def register_database_provider(source: str) -> str | None:
    tree = ast.parse(source)
    call = find_application_call(tree)
    if call is None:
        return None

    lines = source.splitlines(keepends=True)
    keyword = next((keyword for keyword in call.keywords if keyword.arg == "providers"), None)

    if keyword is None:
        inserts = append_item(source, lines, call, [*call.args, *call.keywords], f"providers=[{PROVIDER}]")
    elif not isinstance(keyword.value, ast.List):
        return None
    elif any(isinstance(node, ast.Name) and node.id == "DatabaseProvider" for node in ast.walk(keyword.value)):
        return source
    else:
        inserts = append_item(source, lines, keyword.value, keyword.value.elts, PROVIDER)

    inserts.extend(import_inserts(tree, lines))
    for position, text in sorted(inserts, key=lambda insert: insert[0], reverse=True):
        source = source[:position] + text + source[position:]
    return source


def find_application_call(tree: ast.Module) -> ast.Call | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (isinstance(func, ast.Name) and func.id == "Application") or (
            isinstance(func, ast.Attribute) and func.attr == "Application"
        ):
            return node
    return None


def append_item(
    source: str, lines: list[str], node: ast.expr, items: Sequence[ast.expr | ast.keyword], text: str
) -> list[Insert]:
    assert node.end_lineno is not None and node.end_col_offset is not None
    close = offset(lines, node.end_lineno, node.end_col_offset - 1)
    if not items:
        return [(close, text)]

    last = max(items, key=lambda item: (item.end_lineno or 0, item.end_col_offset or 0))
    assert last.end_lineno is not None and last.end_col_offset is not None
    end = offset(lines, last.end_lineno, last.end_col_offset)
    has_comma = source[end:close].lstrip().startswith(",")

    if last.end_lineno == node.end_lineno:
        return [(close, (" " if has_comma else ", ") + text)]

    line = lines[last.end_lineno - 1]
    line_end = offset(lines, last.end_lineno, 0) + len(line.rstrip("\r\n"))
    indent = line[: len(line) - len(line.lstrip())]
    inserts = [(line_end, f"\n{indent}{text},")]
    if not has_comma:
        inserts.append((end, ","))
    return inserts


def import_inserts(tree: ast.Module, lines: list[str]) -> list[Insert]:
    imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    imported = {alias.asname or alias.name for node in imports for alias in node.names}
    missing = [statement for name, statement in IMPORTS.items() if name not in imported]
    if not missing:
        return []
    if not imports:
        return [(0, "\n".join(missing) + "\n\n")]

    last = imports[-1].end_lineno
    assert last is not None
    return [(offset(lines, last, 0) + len(lines[last - 1].rstrip("\r\n")), "\n" + "\n".join(missing))]


def offset(lines: list[str], lineno: int, col: int) -> int:
    return sum(len(line) for line in lines[: lineno - 1]) + len(lines[lineno - 1].encode()[:col].decode())
