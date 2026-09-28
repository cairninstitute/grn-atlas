import importlib
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (BACKEND, BACKEND / "scripts"):
    sys.path.insert(0, str(p))


def pytest_runtest_setup(item):
    """Undo module fixtures that reload ``main`` against a temporary database.

    Several API test modules set ``GRN_DB`` and reload the singleton backend for
    a small fixture database. Their module teardown clears the environment
    variable but historically left the imported backend module attached to the
    closed fixture connection, contaminating later integration tests.
    """
    if os.environ.get("GRN_DB"):
        return

    main = sys.modules.get("main")
    if main is None:
        return

    expected = BACKEND / "data" / "grn.sqlite3"
    if Path(main.DB_PATH) != expected:
        importlib.reload(main)
