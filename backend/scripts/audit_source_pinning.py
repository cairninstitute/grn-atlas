#!/usr/bin/env python3
"""5B step 1: how much of source_import_runs is actually pinned?

The schema already carries source_url and sha256. start_import_run accepts a
sha256 and has a dedicated path for callers that pass None. This counts which
callers do, so the work is sized before anything is written.

Read-only.

    backend/venv/bin/python backend/scripts/audit_source_pinning.py
"""
import re
import sqlite3
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend/data/grn.sqlite3"


def main():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT source_name, source_version, source_url, sha256, status, fetched_at "
        "FROM source_import_runs ORDER BY source_name, import_run_id").fetchall()
    print("=" * 78)
    print(f"source_import_runs: {len(rows)} rows\n")
    print(f"  {'source':22} {'version':22} {'sha':5} {'url':5} status")
    pinned = urled = 0
    for name, ver, url, sha, status, _ in rows:
        has_sha = bool(sha and sha.strip())
        # NOT NULL columns can still hold a placeholder rather than a real URL.
        has_url = bool(url and url.strip() and url.strip().lower() not in
                       ("", "-", "n/a", "none", "unknown", "local"))
        pinned += has_sha
        urled += has_url
        print(f"  {name[:22]:22} {str(ver)[:22]:22} "
              f"{'yes' if has_sha else 'NO':5} {'yes' if has_url else 'NO':5} {status}")
    print(f"\n  with sha256:     {pinned}/{len(rows)}")
    print(f"  with a real url: {urled}/{len(rows)}")
    conn.close()

    print("-" * 78)
    # Fetchers do not call start_import_run directly; replace_source_evidence
    # calls it for them. An earlier version of this audit grepped the inner
    # name and found only itself.
    print("callers of replace_source_evidence (where a hash must be threaded):")
    me = Path(__file__).resolve()
    seen = {}
    for fn in ("replace_source_evidence", "start_import_run"):
        hits = subprocess.run(["grep", "-rn", fn, "--include=*.py", str(ROOT)],
                              capture_output=True, text=True).stdout
        for line in hits.splitlines():
            try:
                path, lineno, body = line.split(":", 2)
            except ValueError:
                continue
            if Path(path).resolve() == me or f"def {fn}" in body:
                continue
            rel = str(Path(path).relative_to(ROOT))
            seen.setdefault(rel, set()).add(fn)
    if not seen:
        print("  (none)")
    for rel, fns in sorted(seen.items()):
        text = (ROOT / rel).read_text(errors="ignore")
        hashes = "hashlib" in text or "sha256" in text
        print(f"  {'computes a hash' if hashes else 'no hash in file':16} "
              f"{rel:46} [{', '.join(sorted(fns))}]")
    print("=" * 78)


if __name__ == "__main__":
    main()
