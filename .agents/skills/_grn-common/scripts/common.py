"""
Shared utilities for GRN Atlas agent skills.

Provides two execution modes:
  - Direct: import backend Python modules, query SQLite (no server needed)
  - HTTP:   call the running FastAPI server via requests
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_DIR = REPO_ROOT / "backend"
DB_PATH = Path(os.environ.get("GRN_DB", BACKEND_DIR / "data" / "grn.sqlite3"))


def add_common_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--http", metavar="URL", default=None,
        help="Base URL of a running GRN Atlas server (e.g. http://localhost:8000). "
             "If omitted, queries the SQLite database directly.",
    )


def http_get(base_url: str, path: str, params: dict | None = None):
    import requests
    r = requests.get(f"{base_url}{path}", params=params, timeout=30)
    if not r.ok:
        try:
            err = r.json()
        except Exception:
            err = {"error": r.text, "status_code": r.status_code}
        output(err)
        sys.exit(0)
    return r.json()


def http_post(base_url: str, path: str, payload: dict):
    import requests
    r = requests.post(f"{base_url}{path}", json=payload, timeout=60)
    if not r.ok:
        try:
            err = r.json()
        except Exception:
            err = {"error": r.text, "status_code": r.status_code}
        output(err)
        sys.exit(0)
    return r.json()


def init_db():
    sys.path.insert(0, str(BACKEND_DIR))
    os.environ.setdefault("GRN_DB", str(DB_PATH))
    from main import db  # noqa: F401
    return db


def run_async(coro):
    """Run an async endpoint function, converting HTTPException to JSON error output."""
    import asyncio
    try:
        return asyncio.run(coro)
    except Exception as e:
        if hasattr(e, "status_code") and hasattr(e, "detail"):
            output({"error": e.detail, "status_code": e.status_code})
            sys.exit(0)
        raise


def _serialize(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return obj.__dict__
    return str(obj)


def output(data):
    if hasattr(data, "model_dump"):
        data = data.model_dump()
    elif isinstance(data, dict):
        data = json.loads(json.dumps(data, default=_serialize))
    elif isinstance(data, list):
        data = json.loads(json.dumps(data, default=_serialize))
    print(json.dumps(data, indent=2, default=str))
