from __future__ import annotations

import json

from validation_common import (
    CORPUS_DIR,
    benchmark_payload,
    case_result,
    client,
    find_pathway_by_name,
    pathway_members,
    rank_of,
    save_benchmark,
    top_symbols,
)


def main() -> None:
    cases = []
    corpus = json.loads((CORPUS_DIR / "activity_cases.json").read_text())
    for case in corpus.get("pathway_activity_cases", []):
        resp = client.post("/api/v1/activity/pathway", json={"gene_values": case["gene_values"], "species": case["species"], "top": 15})
        data = resp.json()
        rank = rank_of(
            data.get("pathways", []),
            lambda r, kws=case["expected_keywords"]: any(kw.lower() in (r.get("pathway_name") or "").lower() for kw in kws),
        )
        cases.append(
            case_result(
                case["case_id"],
                f"Pathway recovery for {case['case_id']}",
                "pass" if rank and rank <= case.get("top_threshold", 10) else "partial",
                metrics={"expected_rank": rank, "top_pathways": top_symbols(data.get("pathways", []), limit=8)},
                notes=["Curated pathway-activity case from the validation corpus."],
            )
        )

    pathway = find_pathway_by_name("p53 transcriptional gene network") or find_pathway_by_name("PI3K-Akt")
    if pathway:
        members = pathway_members(pathway["pathway_id"], limit=12)
        gene_values = {gene_id: 2.0 for gene_id in members}
        resp = client.post("/api/v1/activity/pathway", json={"gene_values": gene_values, "species": "human", "top": 10})
        data = resp.json()
        rank = rank_of(
            data.get("pathways", []),
            lambda r, pw=pathway["pathway_id"]: r.get("pathway_id") == pw
            or "p53" in (r.get("pathway_name") or "").lower()
            or "dna damage" in (r.get("pathway_name") or "").lower(),
        )
        cases.append(
            case_result(
                "synthetic_member_enrichment",
                "Synthetic pathway member enrichment recovery",
                "pass" if rank and rank <= 5 else "partial",
                metrics={"pathway_name": pathway["name"], "pathway_rank": rank, "top_pathways": top_symbols(data.get("pathways", []))},
                details={"pathway_id": pathway["pathway_id"], "seeded_members": len(members)},
                notes=["This is a self-consistency benchmark using atlas pathway members."],
            )
        )

    payload = benchmark_payload(
        "benchmark_pathway_activity",
        "M2",
        "Validate pathway activity scoring on expanded literal signatures and a synthetic member-enrichment case.",
        cases,
        notes=["Literal pathway cases come from the validation corpus."],
    )
    out = save_benchmark("benchmark_pathway_activity", payload)
    print(out)


if __name__ == "__main__":
    main()
