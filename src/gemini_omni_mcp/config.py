"""Runtime configuration, workspace path resolution, and stderr logging."""

from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path
from typing import Iterable, Optional, Union

# Single lock protecting ledger and local state updates across threads.
LEDGER_LOCK = threading.Lock()

ALL_TOOLSETS: tuple[str, ...] = ("core", "swarm", "research", "3d")


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


def is_outside_workspace_allowed() -> bool:
    """Return True only when the user explicitly opts into reading/writing outside workspace."""
    raw = os.environ.get("GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE", "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def is_custom_render_cmd_allowed() -> bool:
    """Return True only when custom shell render_command execution is explicitly enabled."""
    raw = os.environ.get("GEMINI_OMNI_ALLOW_CUSTOM_RENDER_CMD", "false").strip().lower()
    return raw in ("1", "true", "yes", "on")


def get_enabled_toolsets(
    explicit: Optional[Union[str, Iterable[str]]] = None,
) -> set[str]:
    """Parse enabled toolsets from explicit argument, GEMINI_OMNI_TOOLSETS, or legacy flags."""
    if explicit is not None:
        if isinstance(explicit, str):
            tokens = [t.strip().lower() for t in explicit.split(",") if t.strip()]
        else:
            tokens = [str(t).strip().lower() for t in explicit if str(t).strip()]
    else:
        raw_env = (os.environ.get("GEMINI_OMNI_TOOLSETS") or "").strip()
        tokens = [t.strip().lower() for t in raw_env.split(",") if t.strip()]

    if not tokens:
        enabled = {"core"}
        legacy_3d = os.environ.get("GEMINI_OMNI_ENABLE_3D_TOOLS", "false").strip().lower()
        if legacy_3d in ("1", "true", "yes", "on"):
            enabled.add("3d")
        return enabled

    valid = set(ALL_TOOLSETS) | {"all"}
    unknown = [t for t in tokens if t not in valid]
    if unknown:
        raise ValueError(
            f"Unknown toolset(s): {', '.join(unknown)}. "
            f"Valid options: {', '.join(ALL_TOOLSETS)}, all."
        )

    if "all" in tokens:
        return set(ALL_TOOLSETS)
    return set(tokens)


def is_3d_tools_enabled() -> bool:
    """Return True when the optional `3d` toolset is enabled."""
    return "3d" in get_enabled_toolsets()


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


def resolve_path(
    p: str,
    *,
    allow_outside_workspace: Optional[bool] = None,
) -> Path:
    """Resolve a path relative to the active workspace root, blocking traversal by default."""
    workspace = get_workspace_root()
    path_obj = Path(p).expanduser()
    if not path_obj.is_absolute():
        path_obj = workspace / path_obj
    resolved = path_obj.resolve()

    outside_ok = (
        is_outside_workspace_allowed()
        if allow_outside_workspace is None
        else allow_outside_workspace
    )
    if not outside_ok and not resolved.is_relative_to(workspace):
        raise PermissionError(
            f"Access blocked: '{resolved}' is outside workspace '{workspace}'. "
            "Set GEMINI_OMNI_ALLOW_OUTSIDE_WORKSPACE=true or pass --allow-outside-workspace to allow external paths."
        )
    return resolved
