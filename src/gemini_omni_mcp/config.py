"""Runtime configuration, workspace path resolution, and stderr logging."""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

# Single lock protecting ledger and local state updates across threads.
LEDGER_LOCK = threading.Lock()


def get_logger() -> logging.Logger:
    """Return the package logger configured strictly on stderr (stdout stays clean JSON-RPC)."""
    log = logging.getLogger("gemini-omni-mcp")
    if not log.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] [gemini-omni-mcp] %(levelname)s: %(message)s")
        )
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False
    return log


logger = get_logger()


def get_workspace_root() -> Path:
    """Resolve the active workspace directory from env vars or current working directory."""
    raw = (
        os.environ.get("GEMINI_OMNI_WORKSPACE")
        or os.environ.get("OMNI_WORKSPACE_DIR")
        or ""
    ).strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def get_ledger_path() -> Path:
    """Resolve the USD spend ledger JSON path."""
    raw = (os.environ.get("GEMINI_OMNI_LEDGER_PATH") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return get_workspace_root() / ".gemini-omni" / "usage_ledger.json"


def get_cache_dir() -> Path:
    """Return the workspace cache directory for implicit context prefix bundles."""
    return get_workspace_root() / ".gemini-omni" / "cache"


def is_3d_tools_enabled() -> bool:
    """Return True unless optional 3D/CAD tools are explicitly disabled via env var."""
    raw = os.environ.get("GEMINI_OMNI_ENABLE_3D_TOOLS", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def load_dotenv_if_present(override: bool = False) -> None:
    """Load `<workspace>/.env` if present without clobbering explicit MCP client env vars."""
    env_file = get_workspace_root() / ".env"
    if not env_file.is_file():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if not key:
                continue
            if override:
                os.environ[key] = val
            else:
                os.environ.setdefault(key, val)
    except Exception as exc:
        logger.warning("Failed to parse .env file at %s: %s", env_file, exc)


def resolve_path(p: str) -> Path:
    """Resolve a path relative to the active workspace root."""
    path_obj = Path(p).expanduser()
    if not path_obj.is_absolute():
        path_obj = get_workspace_root() / path_obj
    return path_obj.resolve()
