#!/usr/bin/env python3
"""Return a compact overview of the atlas and its supported workflows."""
import json


def main():
    data = {
        "atlas_name": "GRN Atlas",
        "supported_species": [
            "human",
            "mouse",
            "arabidopsis",
            "tomato",
            "petunia",
        ],
        "capability_examples": [
            "gene search",
            "network neighborhood",
            "pathfinding",
            "subgraph extraction",
            "enrichment",
            "perturbation",
            "orthology",
            "conservation",
            "regulon analysis",
            "RNAi planning",
            "evidence synthesis",
            "study packet generation",
        ],
        "workflow_examples": [
            "grn-gene-search -> grn-network -> grn-enrichment",
            "grn-gene-info -> grn-orthology -> grn-conservation",
            "grn-dataset-import -> grn-user-gene-set-analysis",
            "grn-research-brief -> grn-validation-plan -> grn-study-packet",
        ],
        "skills_documented": 58,
    }
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
