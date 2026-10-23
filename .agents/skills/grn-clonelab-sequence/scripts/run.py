#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_grn-common" / "scripts"))
from clonelab_common import run
run("sequence")
