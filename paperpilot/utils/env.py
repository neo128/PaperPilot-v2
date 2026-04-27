from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def load_dotenv_if_present(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        # Strip surrounding quotes from value
        val = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def optional_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.environ.get(name, default)
