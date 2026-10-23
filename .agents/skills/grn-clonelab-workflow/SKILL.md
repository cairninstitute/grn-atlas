---
name: grn-clonelab-workflow
description: "Run the complete deterministic vector-plus-insert diagnostic workflow: construct alternatives, digest optimization, predicted gel, provenance, and verification boundaries."
compatibility: Requires the GRN Atlas backend virtualenv or a running Darwin server.
---

Use `scripts/run.py --vector ACGT... --insert TGCA... --insertion-start 100 --enzymes EcoRI,BamHI,HindIII`. Use after biological target selection. Darwin evidence motivates the target but does not validate construct function.
