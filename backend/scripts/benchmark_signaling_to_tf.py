from __future__ import annotations

from validation_common import benchmark_payload, case_result, client, find_non_tf_to_tf_edges, save_benchmark


def main() -> None:
    cases = []

    pairs = client.post("/api/v1/signaling/ligand-receptor", json={"species": "human", "top": 10}).json()
    pair_count = len(pairs.get("pairs", []))
    direct_pair_count = len([p for p in pairs.get("pairs", []) if p.get("evidence_mode") == "direct_edge"])
    fallback_pair_count = len([p for p in pairs.get("pairs", []) if p.get("evidence_mode") == "shared_pathway_fallback"])
    cases.append(
        case_result(
            "ligand_receptor_pair_listing",
            "Ligand/receptor-style pair listing in human",
            "pass" if pair_count > 0 else "partial",
            metrics={
                "reported_pairs": pair_count,
                "direct_pairs": direct_pair_count,
                "fallback_pairs": fallback_pair_count,
                "db_non_tf_to_tf_edges": len(find_non_tf_to_tf_edges('human')),
            },
            notes=["A zero result currently indicates sparse biological content in this layer, not an HTTP failure."],
        )
    )

    trace = client.post("/api/v1/signaling/to-tf", json={"species": "human", "receptor_gene": "TP53"})
    trace_json = trace.json()
    cases.append(
        case_result(
            "signaling_trace_surface",
            "Signaling-to-TF trace surface executes",
            "pass" if trace.status_code == 200 else "fail",
            metrics={
                "status_code": trace.status_code,
                "direct_tf_targets": len(trace_json.get("direct_tf_targets", [])),
                "secondary_tfs": len(trace_json.get("secondary_tfs", [])),
                "cascade_depth": trace_json.get("cascade_depth"),
            },
            notes=["TP53 is used here as a surface-level smoke case; it is not a true receptor benchmark."],
        )
    )

    payload = benchmark_payload(
        "benchmark_signaling_to_tf",
        "PR4",
        "Validate signaling-to-TF workflow availability while separating direct-edge coverage from fallback coverage.",
        cases,
        notes=["This benchmark is explicit about current direct-content sparsity. It is designed to harden reporting until richer signaling sources are ingested."],
    )
    out = save_benchmark("benchmark_signaling_to_tf", payload)
    print(out)


if __name__ == "__main__":
    main()
