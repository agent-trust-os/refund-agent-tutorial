"""Read a ``.env`` file, if there is one, into the environment. Real environment variables win."""
from __future__ import annotations

import os
from pathlib import Path


def load_env(path: str = ".env") -> None:
    file = Path(path)
    if not file.is_file():
        return
    for line in file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        os.environ.setdefault(name.strip(), value.strip().strip("'\""))
