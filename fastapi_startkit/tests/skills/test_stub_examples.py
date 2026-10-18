from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

from fastapi_startkit.skills.registry import STUBS_BASE_PATH

ASYNC_MODEL_METHODS = {"create", "update", "find", "find_or_fail", "all", "get", "first"}
CODE_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)

STUB_FILES = sorted(Path(STUBS_BASE_PATH).rglob("SKILL.md"))


def python_blocks(path: Path) -> list[ast.Module]:
    return [ast.parse(block) for block in CODE_BLOCK.findall(path.read_text())]


def parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def is_model_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in ASYNC_MODEL_METHODS
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id[:1].isupper()
    )


def request_model_names(blocks: list[ast.Module]) -> set[str]:
    return {
        node.name
        for tree in blocks
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef)
        and any(isinstance(base, ast.Name) and base.id == "RequestModel" for base in node.bases)
    }


def is_depends(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Depends"


def test_stub_files_are_discovered():
    assert {path.parent.name for path in STUB_FILES} >= {"fastapi", "inertia", "database"}


@pytest.mark.parametrize("path", STUB_FILES, ids=lambda p: p.parent.name)
def test_framework_imports_resolve(path: Path):
    for tree in python_blocks(path):
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("fastapi_startkit"):
                module = importlib.import_module(node.module or "")
                for alias in node.names:
                    assert hasattr(module, alias.name), f"{node.module} has no {alias.name}"


@pytest.mark.parametrize("path", STUB_FILES, ids=lambda p: p.parent.name)
def test_async_model_calls_are_awaited_inside_async_functions(path: Path):
    for tree in python_blocks(path):
        parent_of = parents(tree)
        for node in ast.walk(tree):
            if not is_model_call(node):
                continue
            assert isinstance(parent_of.get(node), ast.Await), ast.unparse(node)
            scope = parent_of.get(node)
            while scope is not None and not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scope = parent_of.get(scope)
            assert not isinstance(scope, ast.FunctionDef), f"{scope.name} must be async"


@pytest.mark.parametrize("path", STUB_FILES, ids=lambda p: p.parent.name)
def test_request_model_parameters_use_depends(path: Path):
    blocks = python_blocks(path)
    form_models = request_model_names(blocks)
    for tree in blocks:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args.args
            defaults: list[ast.expr | None] = [None] * (len(args) - len(node.args.defaults)) + list(node.args.defaults)
            for arg, default in zip(args, defaults):
                if isinstance(arg.annotation, ast.Name) and arg.annotation.id in form_models:
                    assert is_depends(default), f"{node.name}({arg.arg}) needs Depends()"
