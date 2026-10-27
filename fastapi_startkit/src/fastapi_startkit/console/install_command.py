import ast
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib.resources.abc import Traversable
from os import PathLike
from pathlib import Path
from typing import ClassVar, Self, cast

from cleo.helpers import option
from cleo.io.inputs.option import Option

from fastapi_startkit.console.command import Command

BOOTSTRAP_PATH = "bootstrap/application.py"

Insert = tuple[int, str]
Stub = str | PathLike[str] | Traversable


def dotted_path(reference: type | str) -> str:
    return reference if isinstance(reference, str) else f"{reference.__module__}.{reference.__qualname__}"


@dataclass(frozen=True)
class ProviderEntry:
    provider: str
    config: str | None = None

    @classmethod
    def of(cls, provider: type | str, config: type | str | None = None) -> "ProviderEntry":
        return cls(dotted_path(provider), dotted_path(config) if config is not None else None)

    @property
    def name(self) -> str:
        return self.provider.rpartition(".")[2]

    @property
    def entry(self) -> str:
        if self.config is None:
            return self.name
        return f"({self.name}, {self.config.rpartition('.')[2]})"

    @property
    def imports(self) -> dict[str, str]:
        references = [self.provider] if self.config is None else [self.provider, self.config]
        return {name: module for module, _, name in (reference.rpartition(".") for reference in references)}


class RegistrationError(Exception):
    pass


class InstallCommand(Command):
    stubs: ClassVar[tuple[tuple[Stub, str], ...]] = ()
    providers: ClassVar[tuple[ProviderEntry, ...]] = ()

    options: ClassVar[list[Option]] = [option("force", "f", description="Overwrite files that already exist.")]

    @classmethod
    def register(cls, name: str, description: str = "") -> type[Self]:
        return cls.extend(name=name, description=description)

    @classmethod
    def copy(cls, stub: Stub, destination: str) -> type[Self]:
        return cls.extend(stubs=(*cls.stubs, (stub, destination)))

    @classmethod
    def add_provider(cls, provider: type | str, config: type | str | None = None) -> type[Self]:
        return cls.extend(providers=(*cls.providers, ProviderEntry.of(provider, config)))

    @classmethod
    def extend(cls, **attributes: object) -> type[Self]:
        return cast(type[Self], type(cls.__name__, (cls,), attributes))

    def handle(self) -> int:
        return self.publish() or self.register_providers()

    def publish(self) -> int:
        for stub, destination in self.stubs:
            source = stub if isinstance(stub, Traversable) else Path(stub)
            self.publish_file(destination, source.read_text(encoding="utf-8"))
        return 0

    @property
    def base_path(self) -> Path:
        return Path(self.container.base_path)

    def publish_file(self, relative_path: str, content: str) -> None:
        path = self.base_path / relative_path
        if path.exists() and not self.option("force"):
            self.line(f"<comment>{relative_path} already exists, skipped. Use --force to overwrite it.</comment>")
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self.line(f"Created <info>{relative_path}</info>")

    def register_providers(self) -> int:
        return max((self.register_provider(provider) for provider in self.providers), default=0)

    def register_provider(self, provider: ProviderEntry) -> int:
        path = self.base_path / BOOTSTRAP_PATH
        try:
            if not path.exists():
                raise RegistrationError(f"{BOOTSTRAP_PATH} does not exist.")
            source = path.read_text(encoding="utf-8")
            updated = register_provider(source, provider.name, provider.entry, provider.imports)
        except RegistrationError as error:
            self.line_error(f"<error>Could not edit {BOOTSTRAP_PATH}: {error}</error>")
            self.line_error(f"Register {provider.name} manually:")
            for name, module in provider.imports.items():
                self.line_error(f"  {import_statement(name, module)}")
            self.line_error(f"  providers=[..., {provider.entry}]")
            return 1

        if updated == source:
            self.line(f"<comment>{provider.name} is already registered in {BOOTSTRAP_PATH}.</comment>")
            return 0

        path.write_text(updated, encoding="utf-8")
        self.line(f"Registered <info>{provider.name}</info> in <info>{BOOTSTRAP_PATH}</info>")
        return 0


def register_provider(source: str, provider: str, entry: str, imports: Mapping[str, str]) -> str:
    tree = ast.parse(source)
    call = find_application_call(tree)
    if call is None:
        raise RegistrationError("Could not find an Application(...) call.")

    providers = providers_argument(call)
    if providers is not None and is_registered(providers, provider):
        return source

    lines = source.splitlines(keepends=True)
    if providers is None:
        inserts = append_item(source, lines, call, [*call.args, *call.keywords], f"providers=[{entry}]")
    else:
        inserts = append_item(source, lines, providers, providers.elts, entry)

    inserts.extend(import_inserts(tree, lines, imports))
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


def providers_argument(call: ast.Call) -> ast.List | None:
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        raise RegistrationError("Application(...) is called with *args.")

    keyword = next((keyword for keyword in call.keywords if keyword.arg == "providers"), None)
    value = keyword.value if keyword is not None else call.args[2] if len(call.args) > 2 else None
    if value is not None and not isinstance(value, ast.List):
        raise RegistrationError("providers is not a list literal.")
    return value


def is_registered(providers: ast.List, provider: str) -> bool:
    return any(
        (isinstance(node, ast.Name) and node.id == provider)
        or (isinstance(node, ast.Attribute) and node.attr == provider)
        for node in ast.walk(providers)
    )


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


def import_inserts(tree: ast.Module, lines: list[str], imports: Mapping[str, str]) -> list[Insert]:
    existing = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
    bound = bound_names(existing)
    for name, module in imports.items():
        if name in bound and not same_object(bound[name], f"{module}.{name}"):
            raise RegistrationError(f"{name} is already imported as {bound[name]}, not {module}.{name}.")

    missing = [import_statement(name, module) for name, module in imports.items() if name not in bound]
    if not missing:
        return []
    if not existing:
        return [(0, "\n".join(missing) + "\n\n")]

    last = existing[-1].end_lineno
    assert last is not None
    return [(offset(lines, last, 0) + len(lines[last - 1].rstrip("\r\n")), "\n" + "\n".join(missing))]


def bound_names(imports: list[ast.Import | ast.ImportFrom]) -> dict[str, str]:
    bound: dict[str, str] = {}
    for node in imports:
        for alias in node.names:
            if isinstance(node, ast.Import):
                bound[alias.asname or alias.name.partition(".")[0]] = alias.name
            else:
                bound[alias.asname or alias.name] = f"{'.' * node.level}{node.module or ''}.{alias.name}"
    return bound


def same_object(reference: str, expected: str) -> bool:
    if reference == expected:
        return True
    resolved = [resolve(path) for path in (reference, expected)]
    return resolved[0] is not None and resolved[0] is resolved[1]


def resolve(reference: str) -> object | None:
    module, _, name = reference.rpartition(".")
    return getattr(sys.modules.get(module), name, None)


def import_statement(name: str, module: str) -> str:
    return f"from {module} import {name}"


def offset(lines: list[str], lineno: int, col: int) -> int:
    return sum(len(line) for line in lines[: lineno - 1]) + len(lines[lineno - 1].encode()[:col].decode())
