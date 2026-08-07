"""
Shared utilities for GRN Atlas agent skills.

Provides two execution modes:
  - Direct: import backend Python modules, query SQLite (no server needed)
  - HTTP:   call the running FastAPI server via urllib (no extra dependency)
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
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


def _http_json(method: str, base_url: str, path: str, payload: dict | None = None,
               params: dict | None = None, timeout: int = 30):
    url = f"{base_url}{path}"
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(body)
        except Exception:
            err = {"error": body, "status_code": e.code}
        output(err)
        sys.exit(0)


def http_get(base_url: str, path: str, params: dict | None = None):
    return _http_json("GET", base_url, path, params=params, timeout=30)


def http_post(base_url: str, path: str, payload: dict):
    return _http_json("POST", base_url, path, payload=payload, timeout=60)


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
