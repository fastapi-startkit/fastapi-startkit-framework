# /// script
# requires-python = ">=3.12"
# dependencies = ["playwright>=1.55"]
# ///
import importlib.util
import json
import sys
from pathlib import Path

import studio


def load_takes(folder: Path) -> list[studio.Take]:
    spec = importlib.util.spec_from_file_location("takes", folder / "takes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TAKES


def main(folder: Path, names: list[str]) -> None:
    takes = [take for take in load_takes(folder) if not names or take.name in names]
    for take in takes:
        print(json.dumps(studio.record(take, folder / "recordings")))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve(), sys.argv[2:])
