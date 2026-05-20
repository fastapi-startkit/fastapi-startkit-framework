from pathlib import Path

from fastapi_startkit.application import Application
from fastapi_startkit.masoniteorm import SQLiteConfig
from fastapi_startkit.masoniteorm.providers import DatabaseProvider

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "test.sqlite3"


def create_app() -> Application:
    return Application(
        base_path=BASE_DIR,
        providers=[
            (
                DatabaseProvider,
                {
                    "default": "sqlite",
                    "connections": {
                        "sqlite": SQLiteConfig(
                            driver="sqlite",
                            url=f"sqlite+aiosqlite:///{DB_PATH}",
                            options=None,
                        ),
                    },
                },
            ),
        ],
    )
