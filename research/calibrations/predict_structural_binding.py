#!/usr/bin/env python3
"""Predict TF-DNA structural binding via NVIDIA Boltz-2 NIM API.

Scores candidate regulatory edges by predicting whether a transcription factor
protein can physically bind the target gene's core promoter DNA.  Results are
stored as a separate evidence layer (predicted_structural) and are never
auto-promoted into observed interactions.

Usage:
  # Fetch sequences only (no Boltz-2 calls):
  python backend/scripts/predict_structural_binding.py --fetch-sequences-only --species arabidopsis

  # Dry run — show which edges would be predicted:
  python backend/scripts/predict_structural_binding.py --dry-run --species arabidopsis --tier cycle_closing

  # Predict cycle-closing candidates for Arabidopsis (max 50):
  python backend/scripts/predict_structural_binding.py --species arabidopsis --tier cycle_closing --max-edges 50

  # Predict across all species:
  python backend/scripts/predict_structural_binding.py --tier cycle_closing

Requires NVIDIA_NIM_API_KEY env var (free tier from build.nvidia.com).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "grn.sqlite3"

UA = {"User-Agent": "grn-atlas-build/1.0"}
BOLTZ_ENDPOINT = "https://health.api.nvidia.com/v1/biology/mit/boltz2/predict"
UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
ENSEMBL_SEQ = "https://rest.ensembl.org/sequence/region"

SPECIES_CONFIG = {
    "arabidopsis": {"taxon_id": 3702, "ensembl": "arabidopsis_thaliana"},
    "human":       {"taxon_id": 9606, "ensembl": "homo_sapiens"},
    "mouse":       {"taxon_id": 10090, "ensembl": "mus_musculus"},
    "tomato":      {"taxon_id": 4081, "ensembl": "solanum_lycopersicum"},
    "rice":        {"taxon_id": 39947, "ensembl": "oryza_sativa"},
    "potato":      {"taxon_id": 4113, "ensembl": "solanum_tuberosum"},
    "pepper":      {"taxon_id": 4072, "ensembl": "capsicum_annuum"},
    "petunia":     {"taxon_id": 4102, "ensembl": None},
}

CONFIDENCE_THRESHOLDS = {"likely": 0.7, "uncertain": 0.4}


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS protein_sequences (
            gene_id       TEXT NOT NULL,
            species       TEXT NOT NULL,
            uniprot_acc   TEXT,
            sequence      TEXT,
            sequence_len  INTEGER,
            fetch_status  TEXT NOT NULL DEFAULT 'pending',
            fetched_at    TEXT,
            PRIMARY KEY (gene_id, species)
        );
        CREATE INDEX IF NOT EXISTS idx_protseq_status
            ON protein_sequences(fetch_status);

        CREATE TABLE IF NOT EXISTS promoter_dna_sequences (
            gene_id       TEXT NOT NULL,
            species       TEXT NOT NULL,
            chromosome    TEXT,
            start         INTEGER,
            end           INTEGER,
            strand        INTEGER,
            sequence      TEXT,
            sequence_len  INTEGER,
            source        TEXT NOT NULL DEFAULT 'ensembl_rest',
            fetch_status  TEXT NOT NULL DEFAULT 'pending',
            fetched_at    TEXT,
            PRIMARY KEY (gene_id, species)
        );
        CREATE INDEX IF NOT EXISTS idx_dnaseq_status
            ON promoter_dna_sequences(fetch_status);

        CREATE TABLE IF NOT EXISTS structural_binding_predictions (
            species           TEXT NOT NULL,
            source_id         TEXT NOT NULL,
            target_id         TEXT NOT NULL,
            relation_type     TEXT NOT NULL,
            confidence_score  REAL,
            binding_class     TEXT NOT NULL,
            protein_length    INTEGER,
            dna_length        INTEGER,
            recycling_steps   INTEGER DEFAULT 3,
            sampling_steps    INTEGER DEFAULT 50,
            diffusion_samples INTEGER DEFAULT 1,
            raw_output        TEXT,
            error_message     TEXT,
            predicted_at      TEXT NOT NULL,
            model_version     TEXT DEFAULT 'boltz2-nim-v1',
            PRIMARY KEY (species, source_id, target_id, relation_type)
        );
        CREATE INDEX IF NOT EXISTS idx_sbp_species_class
            ON structural_binding_predictions(species, binding_class);
        CREATE INDEX IF NOT EXISTS idx_sbp_confidence
            ON structural_binding_predictions(confidence_score DESC);
    """)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(url: str, headers: dict | None = None, retries: int = 4,
              accept: str = "text/plain") -> str | None:
    hdrs = {**UA, "Accept": accept}
    if headers:
        hdrs.update(headers)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise
    return None


def _http_post_json(url: str, payload: dict, headers: dict | None = None,
                    retries: int = 3, timeout: int = 120) -> dict | None:
    hdrs = {**UA, "Content-Type": "application/json", "Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code == 400:
                body = e.read().decode("utf-8", "replace")
                return {"error": body, "status_code": 400}
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            body = e.read().decode("utf-8", "replace")
            return {"error": body, "status_code": e.code}
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            return {"error": "timeout", "status_code": 0}
    return None


# ---------------------------------------------------------------------------
# Candidate edge selection
# ---------------------------------------------------------------------------

def select_candidate_edges(conn: sqlite3.Connection, species: str | None,
                           tier: str, max_edges: int) -> list[dict]:
    species_clause = "AND rci.species = ?" if species else ""
    params_base: list = [species] if species else []

    edges: list[dict] = []

    if tier in ("cycle_closing", "all"):
        sql = f"""
            SELECT rci.species, rci.source_id, rci.target_id, rci.relation_type,
                   rci.impact_score, rci.closes_cycle
            FROM regulatory_candidate_impacts rci
            JOIN genes g ON g.id = rci.source_id AND g.is_tf = 1
            WHERE rci.closes_cycle = 1 {species_clause}
              AND NOT EXISTS (
                SELECT 1 FROM structural_binding_predictions sbp
                WHERE sbp.species = rci.species
                  AND sbp.source_id = rci.source_id
                  AND sbp.target_id = rci.target_id
                  AND sbp.relation_type = rci.relation_type
              )
            ORDER BY rci.impact_score DESC
            LIMIT ?
        """
        remaining = max_edges - len(edges)
        if remaining > 0:
            for row in conn.execute(sql, params_base + [remaining]):
                edges.append({
                    "species": row[0], "source_id": row[1], "target_id": row[2],
                    "relation_type": row[3], "impact_score": row[4],
                    "priority": "cycle_closing",
                })

    if tier in ("supported", "all") and len(edges) < max_edges:
        sql = f"""
            SELECT rec.species, rec.source_id, rec.target_id, rec.relation_type,
                   rec.confidence
            FROM regulatory_edge_candidates rec
            JOIN genes g ON g.id = rec.source_id AND g.is_tf = 1
            WHERE rec.evidence_tier = 'supported'
              {"AND rec.species = ?" if species else ""}
              AND NOT EXISTS (
                SELECT 1 FROM structural_binding_predictions sbp
                WHERE sbp.species = rec.species
                  AND sbp.source_id = rec.source_id
                  AND sbp.target_id = rec.target_id
                  AND sbp.relation_type = rec.relation_type
              )
            ORDER BY rec.confidence DESC
            LIMIT ?
        """
        remaining = max_edges - len(edges)
        if remaining > 0:
            for row in conn.execute(sql, params_base + [remaining]):
                edges.append({
                    "species": row[0], "source_id": row[1], "target_id": row[2],
                    "relation_type": row[3], "confidence": row[4],
                    "priority": "supported",
                })

    return edges


# ---------------------------------------------------------------------------
# Protein sequence fetching
# ---------------------------------------------------------------------------

def _parse_fasta_sequence(fasta_text: str) -> tuple[str | None, str]:
    lines = fasta_text.strip().split("\n")
    if not lines or not lines[0].startswith(">"):
        return None, ""
    header = lines[0]
    acc_match = re.search(r"\|([A-Z0-9]+)\|", header)
    acc = acc_match.group(1) if acc_match else None
    seq = "".join(l.strip() for l in lines[1:] if not l.startswith(">"))
    return acc, seq


def fetch_protein_sequence(gene_id: str, symbol: str, species: str,
                           conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT sequence, fetch_status FROM protein_sequences WHERE gene_id=? AND species=?",
        (gene_id, species),
    ).fetchone()
    if row:
        if row[1] == "found":
            return row[0]
        if row[1] == "not_found":
            return None
        # error status -> retry

    cfg = SPECIES_CONFIG.get(species, {})
    taxon = cfg.get("taxon_id")
    if not taxon:
        return None

    query_terms = [
        f"gene:{symbol} AND taxonomy_id:{taxon}",
        f"gene:{gene_id} AND taxonomy_id:{taxon}",
    ]

    fasta = ""
    for q in query_terms:
        for reviewed_suffix in (" AND reviewed:true", ""):
            full_q = q + reviewed_suffix
            url = f"{UNIPROT_SEARCH}?query={urllib.parse.quote(full_q)}&format=fasta&size=1"
            result = _http_get(url)
            if result and result.strip() and result.strip().startswith(">"):
                fasta = result
                break
        if fasta:
            break

    now = datetime.now(timezone.utc).isoformat()
    if fasta:
        acc, seq = _parse_fasta_sequence(fasta)
        conn.execute(
            "INSERT OR REPLACE INTO protein_sequences "
            "(gene_id, species, uniprot_acc, sequence, sequence_len, fetch_status, fetched_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (gene_id, species, acc, seq, len(seq), "found", now),
        )
        conn.commit()
        return seq

    conn.execute(
        "INSERT OR REPLACE INTO protein_sequences "
        "(gene_id, species, fetch_status, fetched_at) VALUES (?,?,?,?)",
        (gene_id, species, "not_found", now),
    )
    conn.commit()
    return None


# ---------------------------------------------------------------------------
# Promoter DNA sequence fetching
# ---------------------------------------------------------------------------

def _normalize_chrom(chrom: str, species: str) -> str:
    if species == "potato":
        m = re.search(r"ch(\d+)$", chrom)
        if m:
            return m.group(1)
    if species == "arabidopsis":
        if chrom in ("C", "Mt"):
            return chrom
    if species == "pepper":
        m = re.search(r"scaffold(\d+)$", chrom)
        if m:
            return chrom
    return chrom


def _promoter_window(start: int, end: int, strand: int,
                     dna_window: int) -> tuple[int, int]:
    half_up = int(dna_window * 0.75)
    half_down = dna_window - half_up
    if strand >= 0:
        tss = start
        return max(1, tss - half_up), tss + half_down
    else:
        tss = end
        return max(1, tss - half_down), tss + half_up


def fetch_promoter_dna(gene_id: str, species: str, conn: sqlite3.Connection,
                       dna_window: int = 200) -> str | None:
    row = conn.execute(
        "SELECT sequence, fetch_status, sequence_len FROM promoter_dna_sequences WHERE gene_id=? AND species=?",
        (gene_id, species),
    ).fetchone()
    if row:
        if row[1] == "found" and row[2] and abs(row[2] - dna_window) < 50:
            return row[0]
        if row[1] == "not_found" and row[2] is None:
            return None

    cfg = SPECIES_CONFIG.get(species, {})
    ensembl_species = cfg.get("ensembl")
    if not ensembl_species:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO promoter_dna_sequences "
            "(gene_id, species, source, fetch_status, fetched_at) VALUES (?,?,?,?,?)",
            (gene_id, species, "no_ensembl", "not_found", now),
        )
        conn.commit()
        return None

    loc = conn.execute(
        "SELECT chromosome, start, end, strand FROM gene_locations WHERE gene_id=? AND species=?",
        (gene_id, species),
    ).fetchone()
    if not loc:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO promoter_dna_sequences "
            "(gene_id, species, source, fetch_status, fetched_at) VALUES (?,?,?,?,?)",
            (gene_id, species, "no_location", "not_found", now),
        )
        conn.commit()
        return None

    chrom, g_start, g_end, strand = loc
    p_start, p_end = _promoter_window(g_start, g_end, strand, dna_window)
    norm_chrom = _normalize_chrom(chrom, species)
    strand_val = 1 if strand >= 0 else -1

    region = f"{norm_chrom}:{p_start}..{p_end}:{strand_val}"
    url = f"{ENSEMBL_SEQ}/{ensembl_species}/{region}?content-type=text/plain"

    seq = _http_get(url)
    now = datetime.now(timezone.utc).isoformat()

    if seq and seq.strip() and not seq.strip().startswith("{"):
        clean = seq.strip().upper()
        conn.execute(
            "INSERT OR REPLACE INTO promoter_dna_sequences "
            "(gene_id, species, chromosome, start, end, strand, sequence, "
            "sequence_len, source, fetch_status, fetched_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (gene_id, species, chrom, p_start, p_end, strand, clean,
             len(clean), "ensembl_rest", "found", now),
        )
        conn.commit()
        return clean

    conn.execute(
        "INSERT OR REPLACE INTO promoter_dna_sequences "
        "(gene_id, species, chromosome, start, end, strand, source, fetch_status, fetched_at) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (gene_id, species, chrom, p_start, p_end, strand, "ensembl_rest", "not_found", now),
    )
    conn.commit()
    return None


# ---------------------------------------------------------------------------
# Boltz-2 NIM API
# ---------------------------------------------------------------------------

def load_api_key() -> str | None:
    key = os.environ.get("NVIDIA_NIM_API_KEY")
    if key:
        return key
    secrets_path = Path.home() / ".secrets.env"
    if secrets_path.exists():
        for line in secrets_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            line = line.removeprefix("export").strip()
            if line.startswith("NVIDIA_NIM_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
            if line.startswith("NVIDIA_NIM_API_KEY "):
                return line.split(None, 1)[1].strip().strip("'\"")
    return None


def call_boltz2(protein_seq: str, dna_seq: str, api_key: str,
                recycling_steps: int = 3, sampling_steps: int = 50,
                diffusion_samples: int = 1) -> dict:
    payload = {
        "polymers": [
            {"id": "A", "molecule_type": "protein", "sequence": protein_seq},
            {"id": "B", "molecule_type": "dna", "sequence": dna_seq},
        ],
        "recycling_steps": recycling_steps,
        "sampling_steps": sampling_steps,
        "diffusion_samples": diffusion_samples,
        "output_format": "mmcif",
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    return _http_post_json(BOLTZ_ENDPOINT, payload, headers=headers, timeout=300)


def classify_binding(confidence: float | None) -> str:
    if confidence is None:
        return "error"
    if confidence >= CONFIDENCE_THRESHOLDS["likely"]:
        return "likely"
    if confidence >= CONFIDENCE_THRESHOLDS["uncertain"]:
        return "uncertain"
    return "unlikely"


# ---------------------------------------------------------------------------
# Edge processing
# ---------------------------------------------------------------------------

def process_edge(edge: dict, conn: sqlite3.Connection, api_key: str,
                 dna_window: int, recycling_steps: int, sampling_steps: int,
                 diffusion_samples: int) -> dict:
    species = edge["species"]
    source_id = edge["source_id"]
    target_id = edge["target_id"]
    relation_type = edge["relation_type"]

    src_row = conn.execute(
        "SELECT symbol FROM genes WHERE id = ?", (source_id,)
    ).fetchone()
    symbol = src_row[0] if src_row else source_id

    protein_seq = fetch_protein_sequence(source_id, symbol, species, conn)
    if not protein_seq:
        return _store_prediction(conn, edge, None, "no_sequence", None, None,
                                 error_message="protein sequence not found")

    dna_seq = fetch_promoter_dna(target_id, species, conn, dna_window)
    if not dna_seq:
        return _store_prediction(conn, edge, None, "no_sequence",
                                 len(protein_seq), None,
                                 error_message="promoter DNA not found")

    result = call_boltz2(protein_seq, dna_seq, api_key,
                         recycling_steps, sampling_steps, diffusion_samples)

    if not result or "error" in result:
        err_msg = str(result.get("error", "unknown")) if result else "no response"
        return _store_prediction(conn, edge, None, "error",
                                 len(protein_seq), len(dna_seq),
                                 error_message=err_msg[:1000])

    scores = result.get("confidence_scores", [])
    confidence = scores[0] if scores else None
    binding_class = classify_binding(confidence)

    raw_output = json.dumps({
        "confidence_scores": scores,
        "num_structures": len(result.get("structures", [])),
    })

    return _store_prediction(conn, edge, confidence, binding_class,
                             len(protein_seq), len(dna_seq),
                             raw_output=raw_output)


def _store_prediction(conn: sqlite3.Connection, edge: dict,
                      confidence: float | None, binding_class: str,
                      protein_len: int | None, dna_len: int | None,
                      raw_output: str | None = None,
                      error_message: str | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO structural_binding_predictions "
        "(species, source_id, target_id, relation_type, confidence_score, "
        "binding_class, protein_length, dna_length, raw_output, "
        "error_message, predicted_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (edge["species"], edge["source_id"], edge["target_id"],
         edge["relation_type"], confidence, binding_class,
         protein_len, dna_len, raw_output, error_message, now),
    )
    conn.commit()
    return {
        "species": edge["species"],
        "source_id": edge["source_id"],
        "target_id": edge["target_id"],
        "relation_type": edge["relation_type"],
        "confidence_score": confidence,
        "binding_class": binding_class,
        "error": error_message,
    }


# ---------------------------------------------------------------------------
# Batch sequence pre-fetching
# ---------------------------------------------------------------------------

def prefetch_sequences(edges: list[dict], conn: sqlite3.Connection,
                       dna_window: int) -> dict:
    tf_ids = {}
    target_ids = set()
    for e in edges:
        src = e["source_id"]
        sp = e["species"]
        if (src, sp) not in tf_ids:
            row = conn.execute("SELECT symbol FROM genes WHERE id=?", (src,)).fetchone()
            tf_ids[(src, sp)] = row[0] if row else src
        target_ids.add((e["target_id"], sp))

    stats = {"protein_found": 0, "protein_not_found": 0,
             "dna_found": 0, "dna_not_found": 0}

    print(f"Fetching protein sequences for {len(tf_ids)} TFs...", flush=True)
    for (gene_id, species), symbol in tf_ids.items():
        seq = fetch_protein_sequence(gene_id, symbol, species, conn)
        if seq:
            stats["protein_found"] += 1
        else:
            stats["protein_not_found"] += 1
        time.sleep(0.5)

    print(f"Fetching promoter DNA for {len(target_ids)} targets...", flush=True)
    for gene_id, species in target_ids:
        seq = fetch_promoter_dna(gene_id, species, conn, dna_window)
        if seq:
            stats["dna_found"] += 1
        else:
            stats["dna_not_found"] += 1
        time.sleep(0.1)

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Predict TF-DNA structural binding via Boltz-2 NIM")
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--species", default=None,
                        help="Restrict to one species (default: all)")
    parser.add_argument("--tier", default="cycle_closing",
                        choices=["cycle_closing", "supported", "all"])
    parser.add_argument("--max-edges", type=int, default=500)
    parser.add_argument("--dna-window", type=int, default=200,
                        help="Promoter DNA window size in bp (default: 200)")
    parser.add_argument("--recycling-steps", type=int, default=3)
    parser.add_argument("--sampling-steps", type=int, default=50)
    parser.add_argument("--diffusion-samples", type=int, default=1)
    parser.add_argument("--rate-limit", type=float, default=1.0,
                        help="Seconds between Boltz-2 API calls (default: 1.0)")
    parser.add_argument("--fetch-sequences-only", action="store_true",
                        help="Only fetch and cache sequences, skip Boltz-2")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show selected edges without fetching or predicting")
    args = parser.parse_args()

    conn = sqlite3.connect(str(args.db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    ensure_tables(conn)

    edges = select_candidate_edges(conn, args.species, args.tier, args.max_edges)
    print(f"Selected {len(edges)} candidate edges "
          f"(species={args.species or 'all'}, tier={args.tier})", flush=True)

    if args.dry_run:
        print(json.dumps({"mode": "dry_run", "edges": edges[:20],
                           "total": len(edges)}, indent=2))
        conn.close()
        return 0

    seq_stats = prefetch_sequences(edges, conn, args.dna_window)
    print(json.dumps({"sequence_fetch": seq_stats}, indent=2), flush=True)

    if args.fetch_sequences_only:
        conn.close()
        return 0

    api_key = load_api_key()
    if not api_key:
        print("ERROR: NVIDIA_NIM_API_KEY not set. "
              "Get a free key at https://build.nvidia.com", flush=True)
        conn.close()
        return 1

    results = {"predicted": 0, "no_sequence": 0, "error": 0,
               "likely": 0, "uncertain": 0, "unlikely": 0}

    for i, edge in enumerate(edges):
        print(f"[{i+1}/{len(edges)}] {edge['source_id']} -> {edge['target_id']} "
              f"({edge['species']})...", end=" ", flush=True)

        result = process_edge(edge, conn, api_key, args.dna_window,
                              args.recycling_steps, args.sampling_steps,
                              args.diffusion_samples)

        bc = result["binding_class"]
        if bc == "no_sequence":
            results["no_sequence"] += 1
        elif bc == "error":
            results["error"] += 1
        else:
            results["predicted"] += 1
            results[bc] += 1

        score_str = f"{result['confidence_score']:.3f}" if result["confidence_score"] else "n/a"
        print(f"{bc} (confidence={score_str})", flush=True)

        if bc not in ("no_sequence", "error") and i < len(edges) - 1:
            time.sleep(args.rate_limit)

    print(json.dumps({"summary": results}, indent=2))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
