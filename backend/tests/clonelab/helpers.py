def molecule(length: int, sites: dict[int, str]) -> str:
    bases = ["C"] * length
    for start, site in sites.items():
        bases[start:start + len(site)] = site
    return "".join(bases)


def diagnostic_hypotheses() -> list[dict]:
    return [
        {
            "hypothesis_id": "intended",
            "label": "Correct orientation",
            "sequence": molecule(1000, {100: "GAATTC", 300: "CTCGAG"}),
            "topology": "circular",
        },
        {
            "hypothesis_id": "reverse",
            "label": "Reverse orientation",
            "sequence": molecule(1000, {100: "GAATTC", 700: "CTCGAG"}),
            "topology": "circular",
        },
        {
            "hypothesis_id": "empty",
            "label": "Empty vector",
            "sequence": molecule(1000, {100: "GAATTC"}),
            "topology": "circular",
        },
    ]
