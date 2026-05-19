def storage_path(path: str = "") -> str:
    """Get the path to the storage directory."""
    from fastapi_startkit.application import app

    return app().storage_path(path)


def public_path(path: str = "") -> str:
    """Get the path to the public directory."""
    from fastapi_startkit.application import app

    return app().public_path(path)
