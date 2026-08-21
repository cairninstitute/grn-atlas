from __future__ import annotations

from validation_common import (
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

    literal = {
        "TP53": 3.0,
        "MDM2": -2.0,
        "CDKN1A": 2.5,
        "BAX": 1.8,
        "BCL2": -1.5,
        "GADD45A": 2.1,
    }
    resp = client.post("/api/v1/activity/pathway", json={"gene_values": literal, "species": "human", "top": 15})
    data = resp.json()
    rank = rank_of(
        data.get("pathways", []),
        lambda r: "p53" in (r.get("pathway_name") or "").lower() or "dna damage" in (r.get("pathway_name") or "").lower(),
    )
    cases.append(
        case_result(
            "human_p53_signature",
            "Human p53 / DNA damage pathway recovery",
            "pass" if rank and rank <= 10 else "fail",
            metrics={"expected_rank": rank, "top_pathways": top_symbols(data.get("pathways", []), limit=8)},
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
        "Validate pathway activity scoring on a literal DNA-damage signature and a synthetic member-enrichment case.",
        cases,
        notes=["The literal p53 case is the stronger biological check in this script."],
    )
    out = save_benchmark("benchmark_pathway_activity", payload)
    print(out)


if __name__ == "__main__":
    main()
