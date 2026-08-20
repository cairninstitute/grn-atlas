#!/usr/bin/env python3
"""Population-level statistical validation of the regulatory network.

Unlike gold-standard spot-checks, these tests assess ALL edges at once using
orthogonal data types. Each test produces a p-value or effect size that
characterizes the entire network, not individual edges.

Tests:
  1. Regulon GO coherence — do TF targets share function more than random?
  2. Permutation test — is the network's GO coherence significant vs shuffled?
  3. Cross-species consistency — do multi-evidence edges have higher quality?
  4. Expression coherence — do interaction edges predict coexpression?
  5. Motif enrichment — do inferred targets have TF motifs in promoters?

Usage:
    python backend/scripts/validate_network_statistics.py
"""
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH = DATA_DIR / "grn.sqlite3"

random.seed(42)


def load_go_sets(db, species):
    """Return {gene_id: set(go_ids)} for a species."""
    rows = db.execute(
        "SELECT ga.gene_id, ga.go_id FROM go_annotations ga "
        "JOIN genes g ON ga.gene_id = g.id WHERE g.species = ?",
        (species,)).fetchall()
    go = defaultdict(set)
    for gid, goid in rows:
        go[gid].add(goid)
    return dict(go)


def jaccard(set_a, set_b):
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def mean_pairwise_jaccard(gene_ids, go_sets, max_pairs=500):
    """Mean pairwise GO Jaccard among a set of genes (sampled if large)."""
    annotated = [g for g in gene_ids if g in go_sets]
    if len(annotated) < 2:
        return None
    pairs = []
    if len(annotated) <= 32:
        for i in range(len(annotated)):
            for j in range(i + 1, len(annotated)):
                pairs.append((annotated[i], annotated[j]))
    else:
        for _ in range(max_pairs):
            a, b = random.sample(annotated, 2)
            pairs.append((a, b))
    if not pairs:
        return None
    return sum(jaccard(go_sets[a], go_sets[b]) for a, b in pairs) / len(pairs)


# ---------------------------------------------------------------------------
# Test 1: Regulon-wide GO coherence
# ---------------------------------------------------------------------------
def test_regulon_coherence(db, species, go_sets):
    """For each TF with >=10 targets, compare target GO coherence to random."""
    all_genes = list(go_sets.keys())

    tf_targets = defaultdict(set)
    rows = db.execute(
        "SELECT i.source_id, i.target_id FROM interactions i "
        "JOIN genes g ON i.source_id = g.id WHERE g.species = ?",
        (species,)).fetchall()
    for src, tgt in rows:
        tf_targets[src].add(tgt)

    real_scores = []
    random_scores = []
    n_better = 0
    n_tested = 0

    for tf, targets in tf_targets.items():
        if len(targets) < 10:
            continue
        target_list = list(targets)
        real = mean_pairwise_jaccard(target_list, go_sets)
        if real is None:
            continue

        rand_samples = []
        for _ in range(10):
            rand_genes = random.sample(all_genes, min(len(target_list), len(all_genes)))
            r = mean_pairwise_jaccard(rand_genes, go_sets)
            if r is not None:
                rand_samples.append(r)

        if not rand_samples:
            continue

        rand_mean = sum(rand_samples) / len(rand_samples)
        real_scores.append(real)
        random_scores.append(rand_mean)
        n_tested += 1
        if real > rand_mean:
            n_better += 1

    overall_real = sum(real_scores) / len(real_scores) if real_scores else 0
    overall_rand = sum(random_scores) / len(random_scores) if random_scores else 0
    frac_better = n_better / n_tested if n_tested else 0

    return {
        "tfs_tested": n_tested,
        "mean_real_coherence": round(overall_real, 5),
        "mean_random_coherence": round(overall_rand, 5),
        "enrichment": round(overall_real / overall_rand, 2) if overall_rand > 0 else None,
        "fraction_tfs_above_random": round(frac_better, 3),
    }


# ---------------------------------------------------------------------------
# Test 2: Permutation test
# ---------------------------------------------------------------------------
def test_permutation(db, species, go_sets, n_perms=100):
    """Shuffle TF-target assignments, compare GO coherence distribution."""
    rows = db.execute(
        "SELECT i.source_id, i.target_id FROM interactions i "
        "JOIN genes g ON i.source_id = g.id WHERE g.species = ?",
        (species,)).fetchall()

    edges = [(s, t) for s, t in rows]
    all_targets = list(set(t for _, t in edges))

    def network_coherence(edge_list):
        tf_targets = defaultdict(set)
        for s, t in edge_list:
            tf_targets[s].add(t)
        scores = []
        for tf, targets in tf_targets.items():
            if len(targets) < 10:
                continue
            sc = mean_pairwise_jaccard(list(targets)[:50], go_sets)
            if sc is not None:
                scores.append(sc)
        return sum(scores) / len(scores) if scores else 0

    real_score = network_coherence(edges)

    perm_scores = []
    for i in range(n_perms):
        shuffled_targets = all_targets[:]
        random.shuffle(shuffled_targets)
        target_map = {}
        for idx, (src, tgt) in enumerate(edges):
            target_map[(src, tgt)] = shuffled_targets[idx % len(shuffled_targets)]
        perm_edges = [(s, target_map[(s, t)]) for s, t in edges]
        perm_scores.append(network_coherence(perm_edges))

    n_above = sum(1 for ps in perm_scores if ps >= real_score)
    p_value = (n_above + 1) / (n_perms + 1)

    return {
        "real_coherence": round(real_score, 5),
        "mean_permuted": round(sum(perm_scores) / len(perm_scores), 5) if perm_scores else 0,
        "std_permuted": round((sum((x - sum(perm_scores)/len(perm_scores))**2 for x in perm_scores) / len(perm_scores))**0.5, 5) if perm_scores else 0,
        "p_value": round(p_value, 4),
        "n_permutations": n_perms,
        "effect_size_sigma": round(
            (real_score - sum(perm_scores)/len(perm_scores)) /
            max((sum((x - sum(perm_scores)/len(perm_scores))**2 for x in perm_scores) / len(perm_scores))**0.5, 1e-10),
            2) if perm_scores else None,
    }


# ---------------------------------------------------------------------------
# Test 3: Cross-species consistency (multi-evidence quality)
# ---------------------------------------------------------------------------
def test_multi_evidence(db, species, go_sets):
    """Compare GO overlap of multi-source vs single-source edges."""
    single = db.execute(
        "SELECT i.source_id, i.target_id FROM interactions i "
        "JOIN genes g ON i.source_id = g.id "
        "WHERE g.species = ? AND i.sources NOT LIKE '%,%' "
        "ORDER BY RANDOM() LIMIT 2000", (species,)).fetchall()
    multi = db.execute(
        "SELECT i.source_id, i.target_id FROM interactions i "
        "JOIN genes g ON i.source_id = g.id "
        "WHERE g.species = ? AND i.sources LIKE '%,%' "
        "ORDER BY RANDOM() LIMIT 2000", (species,)).fetchall()

    def edge_overlaps(edges):
        overlaps = []
        for s, t in edges:
            if s in go_sets and t in go_sets:
                overlaps.append(jaccard(go_sets[s], go_sets[t]))
        return overlaps

    s_ov = edge_overlaps(single)
    m_ov = edge_overlaps(multi)

    s_mean = sum(s_ov) / len(s_ov) if s_ov else 0
    m_mean = sum(m_ov) / len(m_ov) if m_ov else 0
    s_any = sum(1 for x in s_ov if x > 0) / len(s_ov) if s_ov else 0
    m_any = sum(1 for x in m_ov if x > 0) / len(m_ov) if m_ov else 0

    # Mann-Whitney U approximation (z-score)
    if s_ov and m_ov:
        combined = [(v, 'S') for v in s_ov] + [(v, 'M') for v in m_ov]
        combined.sort(key=lambda x: x[0])
        ranks = {}
        for i, (v, g) in enumerate(combined):
            ranks.setdefault(g, []).append(i + 1)
        n1, n2 = len(s_ov), len(m_ov)
        r_multi = sum(ranks.get('M', []))
        u_multi = r_multi - n2 * (n2 + 1) / 2
        mu = n1 * n2 / 2
        sigma = (n1 * n2 * (n1 + n2 + 1) / 12) ** 0.5
        z = (u_multi - mu) / sigma if sigma > 0 else 0
    else:
        z = 0

    return {
        "single_source_n": len(s_ov),
        "multi_source_n": len(m_ov),
        "single_mean_overlap": round(s_mean, 5),
        "multi_mean_overlap": round(m_mean, 5),
        "ratio": round(m_mean / s_mean, 3) if s_mean > 0 else None,
        "single_any_overlap": round(s_any, 3),
        "multi_any_overlap": round(m_any, 3),
        "mann_whitney_z": round(z, 2),
    }


# ---------------------------------------------------------------------------
# Test 4: Expression coherence
# ---------------------------------------------------------------------------
def test_expression_coherence(db, species, go_sets):
    """Check if interaction-table edges have higher coexpression (GRNBoost2
    importance) than random TF-gene pairs."""
    interaction_edges = db.execute(
        "SELECT i.source_id, i.target_id FROM interactions i "
        "JOIN genes g ON i.source_id = g.id WHERE g.species = ? "
        "ORDER BY RANDOM() LIMIT 5000", (species,)).fetchall()

    importances_real = []
    for src, tgt in interaction_edges:
        row = db.execute(
            "SELECT importance FROM inferred_edges WHERE source_id=? AND target_id=?",
            (src, tgt)).fetchone()
        if row:
            importances_real.append(row[0])

    tfs = list(set(s for s, _ in interaction_edges))
    genes = [r[0] for r in db.execute(
        "SELECT id FROM genes WHERE species=?", (species,)).fetchall()]
    importances_random = []
    attempts = 0
    while len(importances_random) < len(importances_real) and attempts < 50000:
        tf = random.choice(tfs)
        gene = random.choice(genes)
        if tf == gene:
            attempts += 1
            continue
        row = db.execute(
            "SELECT importance FROM inferred_edges WHERE source_id=? AND target_id=?",
            (tf, gene)).fetchone()
        if row:
            importances_random.append(row[0])
        attempts += 1

    real_mean = sum(importances_real) / len(importances_real) if importances_real else 0
    rand_mean = sum(importances_random) / len(importances_random) if importances_random else 0

    real_hit_rate = len(importances_real) / len(interaction_edges) if interaction_edges else 0
    rand_hit_rate = len(importances_random) / attempts if attempts else 0

    return {
        "interaction_edges_sampled": len(interaction_edges),
        "coexpressed_count": len(importances_real),
        "coexpression_rate": round(real_hit_rate, 4),
        "random_coexpression_rate": round(rand_hit_rate, 4),
        "coexpression_rate_ratio": round(real_hit_rate / rand_hit_rate, 2) if rand_hit_rate > 0 else None,
        "mean_importance_real": round(real_mean, 5),
        "mean_importance_random": round(rand_mean, 5),
        "importance_ratio": round(real_mean / rand_mean, 2) if rand_mean > 0 else None,
    }


# ---------------------------------------------------------------------------
# Test 5: Motif enrichment in inferred targets
# ---------------------------------------------------------------------------
def test_motif_enrichment(db, species):
    """Check if Arabidopsis orthologs of inferred targets have TF binding
    motifs more often than orthologs of non-targets.

    Motif scans are Arabidopsis-only, so we map species genes back to their
    Arabidopsis orthologs and check motif hits there."""
    ath_tf_motifs = defaultdict(set)
    for tf, mid in db.execute("SELECT tf_gene_id, motif_id FROM motifs"):
        ath_tf_motifs[tf].add(mid)

    omap = {}
    if (DATA_DIR / "ortholog_map_plaza.json").exists():
        omap = json.loads((DATA_DIR / "ortholog_map_plaza.json").read_text())

    sp_to_ath = defaultdict(set)
    for ath_gene, sp_map in omap.items():
        for sp_gene in sp_map.get(species, []):
            sp_to_ath[sp_gene].add(ath_gene)

    genes_with_hits = defaultdict(set)
    for row in db.execute("SELECT ext_gene_id, motif_id FROM motif_hits"):
        genes_with_hits[row[0]].add(row[1])

    results = []
    for ath_tf, motif_ids in ath_tf_motifs.items():
        sp_tfs = omap.get(ath_tf, {}).get(species, [])
        if not sp_tfs:
            continue

        for sp_tf in sp_tfs:
            targets = [r[0] for r in db.execute(
                "SELECT target_id FROM interactions WHERE source_id=?",
                (sp_tf,)).fetchall()]
            if len(targets) < 5:
                continue

            all_genes = [r[0] for r in db.execute(
                "SELECT id FROM genes WHERE species=? AND id != ?",
                (species, sp_tf)).fetchall()]
            non_targets = random.sample(all_genes, min(len(targets), len(all_genes)))

            def motif_rate(gene_list):
                hits = 0
                checked = 0
                for gid in gene_list:
                    ath_orthologs = sp_to_ath.get(gid, set())
                    if not ath_orthologs:
                        continue
                    checked += 1
                    for ath_g in ath_orthologs:
                        if genes_with_hits.get(ath_g, set()) & motif_ids:
                            hits += 1
                            break
                return hits, checked

            t_hits, t_checked = motif_rate(targets)
            n_hits, n_checked = motif_rate(non_targets)

            if t_checked >= 5 and n_checked >= 5:
                t_rate = t_hits / t_checked
                n_rate = n_hits / n_checked
                results.append({
                    "tf": sp_tf,
                    "ath_tf": ath_tf,
                    "n_targets": t_checked,
                    "target_motif_rate": t_rate,
                    "nontarget_motif_rate": n_rate,
                    "enrichment": t_rate / n_rate if n_rate > 0 else None,
                })

    if not results:
        return {"tfs_tested": 0, "note": "no TFs with both motifs and inferred targets"}

    enrichments = [r["enrichment"] for r in results if r["enrichment"] is not None]
    target_rates = [r["target_motif_rate"] for r in results]
    nontarget_rates = [r["nontarget_motif_rate"] for r in results]
    n_enriched = sum(1 for e in enrichments if e > 1.0)

    return {
        "tfs_tested": len(results),
        "mean_target_motif_rate": round(sum(target_rates) / len(target_rates), 4),
        "mean_nontarget_motif_rate": round(sum(nontarget_rates) / len(nontarget_rates), 4),
        "mean_enrichment": round(sum(enrichments) / len(enrichments), 2) if enrichments else None,
        "median_enrichment": round(sorted(enrichments)[len(enrichments)//2], 2) if enrichments else None,
        "fraction_enriched": round(n_enriched / len(enrichments), 3) if enrichments else None,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    db = sqlite3.connect(DB_PATH)

    species_with_interactions = [r[0] for r in db.execute(
        "SELECT g.species, COUNT(*) c FROM interactions i "
        "JOIN genes g ON i.source_id=g.id GROUP BY g.species HAVING c > 0 "
        "ORDER BY c DESC").fetchall()]
    all_reports = {}

    for species in species_with_interactions:
        print(f"\n{'='*70}")
        print(f"  {species.upper()} POPULATION-LEVEL VALIDATION")
        print(f"{'='*70}")

        go_sets = load_go_sets(db, species)
        print(f"\nGO coverage: {len(go_sets)} genes with annotations")

        print("\n--- Test 1: Regulon-wide GO Coherence ---")
        r1 = test_regulon_coherence(db, species, go_sets)
        print(f"  TFs tested: {r1['tfs_tested']}")
        print(f"  Mean real coherence: {r1['mean_real_coherence']}")
        print(f"  Mean random coherence: {r1['mean_random_coherence']}")
        print(f"  Enrichment: {r1['enrichment']}x")
        print(f"  Fraction of TFs above random: {r1['fraction_tfs_above_random']}")

        print("\n--- Test 2: Permutation Test (network-wide significance) ---")
        r2 = test_permutation(db, species, go_sets, n_perms=100)
        print(f"  Real coherence: {r2['real_coherence']}")
        print(f"  Permuted mean ± std: {r2['mean_permuted']} ± {r2['std_permuted']}")
        print(f"  Effect size: {r2['effect_size_sigma']} sigma")
        print(f"  p-value: {r2['p_value']}")

        print("\n--- Test 3: Multi-evidence vs Single-source Quality ---")
        r3 = test_multi_evidence(db, species, go_sets)
        print(f"  Single-source (n={r3['single_source_n']}): mean overlap={r3['single_mean_overlap']}")
        print(f"  Multi-source  (n={r3['multi_source_n']}): mean overlap={r3['multi_mean_overlap']}")
        print(f"  Ratio: {r3['ratio']}x")
        print(f"  Mann-Whitney z: {r3['mann_whitney_z']}")

        print("\n--- Test 4: Expression Coherence ---")
        r4 = test_expression_coherence(db, species, go_sets)
        print(f"  Interaction edges coexpressed: {r4['coexpression_rate']:.1%}")
        print(f"  Random pairs coexpressed: {r4['random_coexpression_rate']:.1%}")
        print(f"  Rate ratio: {r4['coexpression_rate_ratio']}x")
        print(f"  Mean importance (real): {r4['mean_importance_real']}")
        print(f"  Mean importance (random): {r4['mean_importance_random']}")
        print(f"  Importance ratio: {r4['importance_ratio']}x")

        print("\n--- Test 5: Motif Enrichment in Inferred Targets ---")
        r5 = test_motif_enrichment(db, species)
        print(f"  TFs tested: {r5['tfs_tested']}")
        if r5['tfs_tested'] > 0:
            print(f"  Target motif rate: {r5['mean_target_motif_rate']:.1%}")
            print(f"  Non-target motif rate: {r5['mean_nontarget_motif_rate']:.1%}")
            print(f"  Mean enrichment: {r5['mean_enrichment']}x")
            print(f"  Median enrichment: {r5['median_enrichment']}x")
            print(f"  Fraction of TFs enriched: {r5['fraction_enriched']}")

        report = {
            "species": species,
            "go_coverage": len(go_sets),
            "regulon_coherence": r1,
            "permutation_test": r2,
            "multi_evidence": r3,
            "expression_coherence": r4,
            "motif_enrichment": r5,
        }
        out_path = DATA_DIR / f"network_stats_{species}.json"
        out_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {out_path}")
        all_reports[species] = report

    # Write combined markdown report
    md = ["# GRN Atlas — Population-Level Network Validation\n"]
    md.append("Statistical validation across all regulatory edges, not just gold-standard spot-checks.\n")
    md.append("Each test uses an orthogonal data type to assess whether the inferred network\n")
    md.append("captures real biological signal.\n")

    # Summary table
    md.append("\n## Summary\n")
    md.append("| Species | Edges | GO genes | Coherence (σ) | Multi-ev. z | Motif enrichment |")
    md.append("\n|---------|------:|--------:|-------------:|----------:|----------------:|")
    for sp, r in all_reports.items():
        n_edges = db.execute(
            "SELECT COUNT(*) FROM interactions i JOIN genes g ON i.source_id=g.id WHERE g.species=?",
            (sp,)).fetchone()[0]
        sigma = r["permutation_test"]["effect_size_sigma"] or "—"
        mw_z = r["multi_evidence"]["mann_whitney_z"]
        motif = f'{r["motif_enrichment"].get("mean_enrichment", "—")}x' if r["motif_enrichment"]["tfs_tested"] > 0 else "—"
        md.append(f"\n| {sp} | {n_edges:,} | {r['go_coverage']:,} | {sigma} | {mw_z} | {motif} |")

    for sp, r in all_reports.items():
        md.append(f"\n\n## {sp.capitalize()}\n")

        md.append(f"\n### Test 1 — Regulon-wide GO Coherence\n")
        r1 = r["regulon_coherence"]
        md.append(f"For each TF with ≥10 targets, measure pairwise GO term overlap among targets\n")
        md.append(f"vs. size-matched random gene sets.\n\n")
        md.append(f"- **TFs tested:** {r1['tfs_tested']}\n")
        md.append(f"- **Mean real coherence:** {r1['mean_real_coherence']}\n")
        md.append(f"- **Mean random coherence:** {r1['mean_random_coherence']}\n")
        md.append(f"- **Enrichment:** {r1['enrichment']}×\n")
        md.append(f"- **Fraction of TFs above random:** {r1['fraction_tfs_above_random']}\n")

        md.append(f"\n### Test 2 — Permutation Test\n")
        r2 = r["permutation_test"]
        md.append(f"Shuffle all TF→target assignments 100 times, recompute network-wide coherence.\n\n")
        md.append(f"- **Real coherence:** {r2['real_coherence']}\n")
        md.append(f"- **Permuted mean ± std:** {r2['mean_permuted']} ± {r2['std_permuted']}\n")
        md.append(f"- **Effect size:** {r2['effect_size_sigma']} σ\n")
        md.append(f"- **p-value:** {r2['p_value']}\n")

        md.append(f"\n### Test 3 — Multi-evidence vs Single-source\n")
        r3 = r["multi_evidence"]
        md.append(f"Compare GO overlap of edges supported by 2+ independent sources vs. single-source.\n\n")
        md.append(f"- **Single-source** (n={r3['single_source_n']}): mean overlap = {r3['single_mean_overlap']}\n")
        md.append(f"- **Multi-source** (n={r3['multi_source_n']}): mean overlap = {r3['multi_mean_overlap']}\n")
        md.append(f"- **Ratio:** {r3['ratio']}×\n")
        md.append(f"- **Mann-Whitney z:** {r3['mann_whitney_z']}\n")

        md.append(f"\n### Test 4 — Expression Coherence\n")
        r4 = r["expression_coherence"]
        md.append(f"Check whether interaction-table edges appear in GRNBoost2/GENIE3 coexpression\n")
        md.append(f"more often than random TF-gene pairs.\n\n")
        md.append(f"- **Interaction edges coexpressed:** {r4['coexpression_rate']:.1%}\n")
        md.append(f"- **Random pairs coexpressed:** {r4['random_coexpression_rate']:.1%}\n")
        md.append(f"- **Rate ratio:** {r4['coexpression_rate_ratio']}×\n")
        md.append(f"- **Mean importance (real):** {r4['mean_importance_real']}\n")
        md.append(f"- **Mean importance (random):** {r4['mean_importance_random']}\n")

        md.append(f"\n### Test 5 — Motif Enrichment in Inferred Targets\n")
        r5 = r["motif_enrichment"]
        md.append(f"For TFs with known binding motifs, check whether Arabidopsis orthologs of\n")
        md.append(f"inferred targets have TF motif hits in promoters vs. non-targets.\n\n")
        md.append(f"- **TFs tested:** {r5['tfs_tested']}\n")
        if r5["tfs_tested"] > 0:
            md.append(f"- **Target motif rate:** {r5['mean_target_motif_rate']:.1%}\n")
            md.append(f"- **Non-target motif rate:** {r5['mean_nontarget_motif_rate']:.1%}\n")
            md.append(f"- **Mean enrichment:** {r5['mean_enrichment']}×\n")
            md.append(f"- **Median enrichment:** {r5['median_enrichment']}×\n")
            md.append(f"- **Fraction of TFs enriched:** {r5['fraction_enriched']}\n")
        else:
            md.append(f"- {r5.get('note', 'No data available')}\n")

    md.append("\n\n---\n*Generated by `validate_network_statistics.py`*\n")
    md_path = DATA_DIR / "network_validation_report.md"
    md_path.write_text("".join(md))
    print(f"\nCombined report: {md_path}")

    db.close()


if __name__ == "__main__":
    main()
