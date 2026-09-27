"""Benchmarks for Application boot and provider register/boot (task #1045).

Deselected by default (see `addopts` in pyproject.toml); run explicitly with:

    uv run pytest -m benchmark tests/fastapi/benchmarks/test_application_boot_benchmark.py
"""

import pytest
from fastapi import FastAPI

from fastapi_startkit.application import Application
from fastapi_startkit.container.container import Container
from fastapi_startkit.fastapi.providers.fastapi_provider import FastAPIProvider


@pytest.fixture(autouse=True)
def restore_container_instance():
    """Application() replaces the global Container singleton; restore it after each round."""
    original = Container._instance
    yield
    Container._instance = original


@pytest.mark.benchmark(group="application-boot")
class TestApplicationBootBenchmarks:
    def test_boot_default_providers(self, benchmark, tmp_path):
        """Full Application() init: environment resolution, config, default providers register+boot."""
        benchmark(Application, base_path=tmp_path, env="testing")

    def test_boot_with_fastapi_provider(self, benchmark, tmp_path):
        """Same as above, plus FastAPIProvider register+boot (FastAPI instance, exception handlers, command)."""
        benchmark(Application, base_path=tmp_path, env="testing", providers=[FastAPIProvider])

    def test_boot_raw_fastapi_baseline(self, benchmark):
        """Raw FastAPI() instantiation — the floor that Application's boot overhead is measured against."""
        benchmark(FastAPI)
