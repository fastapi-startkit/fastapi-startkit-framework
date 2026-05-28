# config/logging.py
DEFAULT = "stack"

CHANNELS = {
    "daily": {"driver": "daily", "level": "debug", "path": "storage/logs"},
    "terminal": {
        "driver": "terminal",
        "level": "info",
    },
    "stack": {"driver": "stack", "channels": ["daily", "terminal"]},
}
