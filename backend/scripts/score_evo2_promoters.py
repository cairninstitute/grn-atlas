#!/usr/bin/env python3
"""Score promoter DNA sequences using Evo2 via NVIDIA NIM API.

Uses the Evo2-40B DNA foundation model to compute per-nucleotide log-likelihoods
for promoter sequences. High-likelihood promoters are more likely to be functional
regulatory regions. This provides a quality filter for regulatory evidence —
edges involving low-quality promoter regions can be down-weighted.

From prior calibration: Evo2 distinguishes plant promoters from intergenic DNA
at AUC=0.889 — strong enough to be a useful quality filter.

Requires NVIDIA_NIM_API_KEY env var (same free-tier key as Boltz-2).

Usage:
    python backend/scripts/score_evo2_promoters.py --species arabidopsis
    python backend/scripts/score_evo2_promoters.py --species all --max-sequences 500
    python backend/scripts/score_evo2_promoters.py --species arabidopsis --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

EVO2_ENDPOINT = "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/loglikelihood"
EVO2_GENERATE_ENDPOINT = "https://health.api.nvidia.com/v1/biology/arc/evo2-40b/generate"
REQUEST_DELAY = 1.0


def get_api_key() -> str | None:
    key = os.environ.get("NVIDIA_NIM_API_KEY")
    if key:
        return key
    secrets = Path.home() / ".secrets.env"
    if secrets.exists():
        for line in secrets.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if line.startswith("NVIDIA_NIM_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def score_sequence(sequence: str, api_key: str) -> dict:
    """Score a DNA sequence using Evo2 log-likelihood endpoint."""
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "sequence": sequence,
        "num_tokens": 1,
        "top_k": 1,
        "temperature": 1.0,
        "enable_sampled_probs": True,
    }).encode()

    req = urllib.request.Request(
        EVO2_GENERATE_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "nvcf-poll-seconds": "120",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
            probs = result.get("sampled_probs", [])
            mean_prob = float(np.mean(probs)) if probs else 0.0
            return {
                "status": "scored",
                "mean_prob": round(mean_prob, 6),
                "sequence_length": len(sequence),
                "raw": result,
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"status": "error", "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


def score_sequence_loglikelihood(sequence: str, api_key: str) -> dict:
    """Score using character-level log-likelihood from the generate endpoint.

    Approach: submit the sequence as a "prompt" and request 0 new tokens
    with enable_logits=true. The logits on the input tokens give us
    per-position log-likelihoods.
    """
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "sequence": sequence,
        "num_tokens": 1,
        "top_k": 1,
        "temperature": 1.0,
        "enable_logits": True,
    }).encode()

    req = urllib.request.Request(
        EVO2_GENERATE_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "nvcf-poll-seconds": "120",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
            logits = result.get("logits", [])
            if logits and isinstance(logits[0], list):
                max_logits = [max(row) for row in logits]
                mean_logit = float(np.mean(max_logits))
            elif logits:
                mean_logit = float(np.mean(logits))
            else:
                mean_logit = 0.0

            quality_score = 1.0 / (1.0 + np.exp(-mean_logit * 0.1))

            return {
                "status": "scored",
                "mean_logit": round(mean_logit, 4),
                "quality_score": round(float(quality_score), 4),
                "sequence_length": len(sequence),
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return {"status": "error", "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}


def get_promoter_sequences(
    conn: sqlite3.Connection, species: str, max_sequences: int
) -> list[dict]:
    """Get promoter DNA sequences from the database."""
    rows = conn.execute(
        "SELECT gene_id, sequence, sequence_len FROM promoter_dna_sequences "
        "WHERE species = ? AND fetch_status = 'found' AND sequence_len >= 50 "
        "ORDER BY gene_id LIMIT ?",
        (species, max_sequences),
    ).fetchall()
    return [{"gene_id": r[0], "sequence": r[1], "length": r[2]} for r in rows]


def get_already_scored(conn: sqlite3.Connection, species: str) -> set[str]:
    has_table = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='evo2_promoter_scores'"
    ).fetchone()[0]
    if not has_table:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT gene_id FROM evo2_promoter_scores WHERE species = ?", (species,)
    ).fetchall()}


def store_scores(
    conn: sqlite3.Connection, species: str,
    scores: list[dict], dry_run: bool = False,
) -> int:
    if dry_run or not scores:
        return 0

    conn.execute("""
        CREATE TABLE IF NOT EXISTS evo2_promoter_scores (
            gene_id         TEXT NOT NULL,
            species         TEXT NOT NULL,
            quality_score   REAL NOT NULL,
            mean_logit      REAL,
            sequence_length INTEGER NOT NULL,
            model_version   TEXT NOT NULL DEFAULT 'evo2-40b',
            scored_at       TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (gene_id, species)
        )
    """)

    conn.executemany(
        "INSERT OR REPLACE INTO evo2_promoter_scores "
        "(gene_id, species, quality_score, mean_logit, sequence_length) "
        "VALUES (?, ?, ?, ?, ?)",
        [(s["gene_id"], species, s["quality_score"], s.get("mean_logit"),
          s["sequence_length"]) for s in scores],
    )
    conn.commit()
    return len(scores)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--species", required=True,
                        help="Species to score (or 'all' for all with promoter sequences)")
    parser.add_argument("--max-sequences", type=int, default=500)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY)
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("ERROR: NVIDIA_NIM_API_KEY not set. "
              "Get a free key at https://build.nvidia.com")
        return 1

    conn = sqlite3.connect(str(args.db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")

    has_promoters = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
        "AND name='promoter_dna_sequences'"
    ).fetchone()[0]
    if not has_promoters:
        print("ERROR: No promoter_dna_sequences table. "
              "Run predict_structural_binding.py --fetch-sequences-only first.")
        conn.close()
        return 1

    if args.species == "all":
        species_list = [r[0] for r in conn.execute(
            "SELECT DISTINCT species FROM promoter_dna_sequences "
            "WHERE fetch_status = 'found'"
        ).fetchall()]
    else:
        species_list = [args.species]

    summary = {}
    for species in species_list:
        print(f"\n{'='*60}")
        print(f"Scoring promoters for {species}")
        print(f"{'='*60}")

        already = get_already_scored(conn, species)
        promoters = get_promoter_sequences(conn, species, args.max_sequences)
        todo = [p for p in promoters if p["gene_id"] not in already]

        print(f"  Available: {len(promoters)}, already scored: {len(already)}, "
              f"to score: {len(todo)}")

        if not todo:
            print("  Nothing to do.")
            summary[species] = {"skipped": True, "already_scored": len(already)}
            continue

        scored = []
        errors = 0
        for i, promoter in enumerate(todo):
            result = score_sequence_loglikelihood(
                promoter["sequence"], api_key)

            if result["status"] == "scored":
                scored.append({
                    "gene_id": promoter["gene_id"],
                    "quality_score": result["quality_score"],
                    "mean_logit": result.get("mean_logit"),
                    "sequence_length": promoter["length"],
                })
            else:
                errors += 1
                if errors <= 3:
                    print(f"  Error for {promoter['gene_id']}: {result.get('error', 'unknown')}")
                if errors >= 10:
                    print(f"  Too many errors ({errors}), stopping.")
                    break

            if (i + 1) % 25 == 0:
                print(f"  Scored {i + 1}/{len(todo)} "
                      f"({len(scored)} OK, {errors} errors)", flush=True)

            time.sleep(args.delay)

        n_stored = store_scores(conn, species, scored, dry_run=args.dry_run)
        prefix = "[DRY RUN] " if args.dry_run else ""

        if scored:
            qs = [s["quality_score"] for s in scored]
            print(f"\n{prefix}Results for {species}:")
            print(f"  Scored: {len(scored)}, errors: {errors}")
            print(f"  Quality score range: {min(qs):.4f} - {max(qs):.4f}")
            print(f"  Quality score mean: {np.mean(qs):.4f}")
            if not args.dry_run:
                print(f"  Stored: {n_stored}")

        summary[species] = {
            "scored": len(scored),
            "errors": errors,
            "stored": n_stored,
            "quality_mean": round(float(np.mean([s["quality_score"] for s in scored])), 4) if scored else None,
        }

    conn.close()
    print(f"\n{json.dumps(summary, indent=2)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
