"""
Worker entrypoint — exposes `broker` for the Taskiq CLI.

Run with:
    uv run python -m taskiq worker worker:broker tasks.example_task

Or via artisan:
    uv run artisan queue:work
    uv run artisan queue:work --workers 4
"""

from bootstrap.application import app

broker = app.make("broker")
