---
name: grn-clonelab-restriction
description: "Calculate exact restriction sites and full-digest fragments for a linear or circular DNA molecule. Use for restriction maps and digest predictions; do not calculate fragment sizes in the language model."
compatibility: Requires the GRN Atlas backend virtualenv or a running Darwin server.
---

Use `scripts/run.py --sequence ACGT... --topology circular --enzymes EcoRI,BamHI`. Zero-cut circular molecules remain explicitly uncut. A digest pattern does not prove base-perfect sequence identity.
