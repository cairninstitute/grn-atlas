import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
for p in (BACKEND, BACKEND / "scripts"):
    sys.path.insert(0, str(p))
