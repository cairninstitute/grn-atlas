"""In-silico dsRNA / RNAi analysis (predicted gene silencing).

A dsRNA is diced into ~21 nt siRNAs that can silence any transcript sharing a
sufficiently long exact match (either strand). This module predicts, for a dsRNA:
  - on-target coverage of an intended gene,
  - off-target genes (other transcripts sharing >=k-nt matches), ranked,
  - a specificity score,
and, in design mode, the most specific window within a target transcript.

STRONGLY PREDICTED, NOT MEASURED: exact k-mer matching is a specificity heuristic.
Real RNAi knockdown also depends on dicing efficiency, delivery/SIGS uptake, target
accessibility, and (in plants) transitivity/amplification — none modelled here.
Everything is labelled "predicted silencing".

Pure functions (no FastAPI / no DB) so they are unit-testable in isolation.
"""
import gzip
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

_COMP = str.maketrans("ACGTacgt", "TGCAtgca")


MAX_DSRNA_LEN = 5000


def validate_dsrna(seq: str, k: int, max_len: int = MAX_DSRNA_LEN) -> str:
    """Sanitise + validate a pasted dsRNA (pure: raises ValueError, no HTTP coupling).
    Keeps letters, uppercases, requires A/C/G/T/N, bounds length."""
    s = "".join(seq.split()).upper()
    if not s:
        raise ValueError("Empty dsRNA sequence")
    bad = set(s) - set("ACGTN")
    if bad:
        raise ValueError(f"dsRNA has non-nucleotide characters: {''.join(sorted(bad))[:10]}")
    if len(s) < k:
        raise ValueError(f"dsRNA shorter than the siRNA size (k={k})")
    if len(s) > max_len:
        raise ValueError(f"dsRNA too long (max {max_len} bp)")
    return s


def revcomp(seq: str) -> str:
    return seq.translate(_COMP)[::-1]


def kmers(seq: str, k: int = 21):
    seq = seq.upper()
    for i in range(len(seq) - k + 1):
        w = seq[i:i + k]
        if "N" not in w:
            yield i, w


def query_kmers(dsrna: str, k: int = 21) -> set:
    """All k-mers of the dsRNA AND its reverse complement (both strands are diced)."""
    s = dsrna.upper()
    out = {w for _, w in kmers(s, k)}
    out |= {w for _, w in kmers(revcomp(s), k)}
    return out


def gene_of(header_token: str) -> str:
    return header_token.rsplit(".", 1)[0]


def load_transcripts(path: Path) -> Dict[str, str]:
    """gene_id -> concatenated transcript sequence(s) (isoforms joined by a k-blocker).
    Reads a (gzipped) FASTA whose headers start with a transcript id."""
    genes: Dict[str, List[str]] = defaultdict(list)
    opener = gzip.open if str(path).endswith(".gz") else open
    gid, buf = None, []
    with opener(path, "rt") as fh:
        for line in fh:
            if line.startswith(">"):
                if gid:
                    genes[gid].append("".join(buf))
                gid = gene_of(line[1:].split()[0])
                buf = []
            else:
                buf.append(line.strip())
        if gid:
            genes[gid].append("".join(buf))
    # join isoforms with a run of N so no k-mer spans two isoforms
    return {g: ("N" * 21).join(seqs).upper() for g, seqs in genes.items()}


def scan(dsrna: str, transcripts: Dict[str, str], k: int = 21,
         target_gene: Optional[str] = None) -> dict:
    """Predict silencing of `dsrna` across the transcriptome.

    Returns on-target sites (if target_gene given), ranked off-target genes, and a
    specificity score = on_target_sites / (on_target_sites + total_offtarget_sites).
    A 'site' is one k-mer position in a gene matching a dsRNA k-mer (either strand).
    """
    qk = query_kmers(dsrna, k)
    NB = 40  # bins for the per-transcript hit-density map
    per_gene = {}
    for gid, seq in transcripts.items():
        L = len(seq)
        span = max(1, L - k + 1)
        n, bins = 0, None
        for i, w in kmers(seq, k):
            if w in qk:
                n += 1
                if bins is None:
                    bins = [0] * NB
                bins[min(NB - 1, i * NB // span)] += 1
        if n:
            per_gene[gid] = {"sites": n, "length": L, "profile": bins}

    on = per_gene.get(target_gene, {}).get("sites", 0) if target_gene else 0
    offs = [{"gene_id": g, "sites": d["sites"], "length": d["length"], "profile": d["profile"]}
            for g, d in per_gene.items() if g != target_gene]
    offs.sort(key=lambda d: d["sites"], reverse=True)
    off_total = sum(o["sites"] for o in offs)
    denom = on + off_total
    specificity = round(on / denom, 4) if denom else 0.0
    return {
        "k": k,
        "dsrna_length": len(dsrna),
        "n_sirnas": len(qk),
        "on_target_gene": target_gene,
        "on_target_sites": on,
        "off_target_gene_count": len(offs),
        "off_target_total_sites": off_total,
        "off_targets": offs,
        "specificity": specificity,
        "silenced_genes": ([target_gene] if on else []) + [o["gene_id"] for o in offs],
    }


def design(target_gene: str, transcripts: Dict[str, str], k: int = 21,
           window: int = 250, step: int = 25) -> dict:
    """Pick the most specific dsRNA window within a target transcript: the window
    whose k-mers hit the fewest OTHER genes. Returns the window sequence + its
    off-target profile."""
    tseq = transcripts.get(target_gene)
    if not tseq or len(tseq) < k:
        return {"error": f"no transcript for {target_gene}"}
    # first, the target's own k-mers, and which other genes each one appears in
    tk = {w: i for i, w in kmers(tseq, k)}
    off_by_kmer: Dict[str, set] = {w: set() for w in tk}
    for gid, seq in transcripts.items():
        if gid == target_gene:
            continue
        for _, w in kmers(seq, k):
            if w in off_by_kmer:
                off_by_kmer[w].add(gid)
    # slide a window over the target; score = number of distinct off-target genes hit
    best = None
    L = len(tseq)
    win = min(window, L)
    for start in range(0, max(1, L - win + 1), step):
        sub = tseq[start:start + win]
        hit = set()
        for _, w in kmers(sub, k):
            hit |= off_by_kmer.get(w, set())
        if best is None or len(hit) < best["off_target_gene_count"]:
            best = {"start": start, "end": start + win, "sequence": sub,
                    "off_target_gene_count": len(hit),
                    "off_target_genes": sorted(hit)[:50]}
    best["target_gene"] = target_gene
    best["window"] = win
    best["transcript_length"] = L
    # off-target density along the transcript (how many other genes each k-mer hits),
    # binned for a compact map that shows WHY the chosen window is clean.
    n_bins = 120
    bins = [0] * n_bins
    span = max(1, L - k + 1)
    for i, w in kmers(tseq, k):
        b = min(n_bins - 1, i * n_bins // span)
        c = len(off_by_kmer.get(w, ()))
        if c > bins[b]:
            bins[b] = c
    best["offtarget_profile"] = bins
    best["note"] = "Predicted most-specific window (fewest off-target genes); verify with scan()."
    return best


def screen(target_genes: List[str], transcripts: Dict[str, str], k: int = 21,
           window: int = 250, step: int = 25) -> List[dict]:
    """Batch dsRNA-designability screen for a gene set (e.g. a whole pathway) in ONE
    transcriptome pass. For each target gene, find its most-specific window and report
    how many other genes it would hit — so you can pick the cleanest RNAi target(s).

    Ranks genes by designability (fewest off-targets in the best window first).
    """
    targets = [g for g in dict.fromkeys(target_genes) if g in transcripts]
    # union of all target k-mers -> which target(s) each belongs to (for reference)
    tk_by_gene = {g: {w: i for i, w in kmers(transcripts[g], k)} for g in targets}
    union = set()
    for m in tk_by_gene.values():
        union |= set(m)
    # single pass: for each union k-mer, which genes contain it
    genes_with: Dict[str, set] = {w: set() for w in union}
    for gid, seq in transcripts.items():
        for _, w in kmers(seq, k):
            s = genes_with.get(w)
            if s is not None:
                s.add(gid)

    out = []
    for g in targets:
        tseq = transcripts[g]
        # off-target genes per k-mer of this target
        off_by_pos = [(i, genes_with.get(w, set()) - {g}) for i, w in kmers(tseq, k)]
        best = None
        L = len(tseq)
        win = min(window, L)
        for start in range(0, max(1, L - win + 1), step):
            hit = set()
            for i, off in off_by_pos:
                if start <= i < start + win:
                    hit |= off
            if best is None or len(hit) < best:
                best = len(hit)
        # also whole-transcript off-target burden
        all_off = set()
        for _, off in off_by_pos:
            all_off |= off
        out.append({"gene_id": g, "best_window_off_targets": best if best is not None else 0,
                    "transcript_off_targets": len(all_off),
                    "designable": (best == 0)})
    out.sort(key=lambda d: (d["best_window_off_targets"], d["transcript_off_targets"]))
    return out


_cache: Dict[str, Optional[Dict[str, str]]] = {}


def get_transcripts(species: str, data_dir: Path) -> Optional[Dict[str, str]]:
    if species not in _cache:
        path = data_dir / f"transcripts_{species}.fasta.gz"
        _cache[species] = load_transcripts(path) if path.exists() else None
    return _cache[species]
