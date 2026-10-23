---
name: grn-clonelab-interpret
description: "Compare manually measured gel bands with predicted molecular outcomes and retain every compatible hypothesis."
compatibility: Requires the GRN Atlas backend virtualenv or a running Darwin server.
---

Use `scripts/run.py --observed '[800,200]' --predictions '{"intended":[800,200],"empty":[1000]}'`. Report missing and unexpected bands. Compatibility is evidence, not proof of exact molecular identity.
