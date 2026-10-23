---
name: grn-clonelab-diagnostic
description: "Rank single- and double-enzyme diagnostic digests against explicit molecular hypotheses using resolvable gel signatures and information gain."
compatibility: Requires the GRN Atlas backend virtualenv or a running Darwin server.
---

Use `scripts/run.py --hypotheses '<JSON array>' --enzymes EcoRI,BamHI,HindIII`. Report `no_unique_digest` and unresolved groups exactly. Distinguish insert detection, orientation discrimination, and sequence confirmation as separate claims.
