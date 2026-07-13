# Onboarding a new species (e.g. Dahlia)

This runbook makes adding a species turnkey. It is the concrete path we're preparing for
the **Dahlia** collaboration (Alex/Zach — incoming genome + RNA-seq + ~400-cultivar GWAS;
see the `grn-atlas-dahlia-collaboration` memory). Every added layer follows the project
rule: **predicted/inferred data is labelled distinct from measured** (see the honesty memory).

Central config: `backend/scripts/species_config.py` — add one entry per species
(assembly, reference URLs, `id_style`). A `dahlia` placeholder is already stubbed there.

Check readiness / progress any time: `GET /api/v1/species` shows the per-species layer
matrix (network / orthologs / binding / expression / pathways / traits); empty layers are
the remaining onboarding steps.

## Steps (each independent; do what the available data supports)

1. **Genes + genome/annotation.** Load gene models (id, symbol, description, coords) from
   the release's GFF into `genes` + `gene_locations`. Set the assembly tag.

2. **Sequence context + predicted TF binding** (needs genome FASTA + GFF). All
   config-driven off `species_config.py` — no per-species scripts:
   - windows: `python backend/scripts/fetch_seqctx.py <species>` (PLAZA-identity pattern;
     tomato's SGN ITAG lift-over is the one special case in `fetch_tomato_seqctx.py`).
   - load: `python backend/scripts/load_seqctx.py <species>` (crosswalk + windows).
   - scan: `python backend/scripts/motif_scan.py <species> <genome.fa>` (JASPAR-plant PWMs,
     `tf_motif_map_<species>.json` if present else symbol match) → `motif_hits` (`tier=JASPAR_scan`);
     then `load_seqctx.py <species>` again to load motifs + hits.
   - Register the assembly in `_ASSEMBLY_OF` (backend/main.py) → motif enrichment +
     sequence-context export light up.

3. **Expression + co-expression** (needs a CDS FASTA + a curated SRA panel):
   - build a kallisto index from the CDS (`tools/kallisto/kallisto index`); curate a tissue
     panel in the species' `expr_panel` (aim for contrast; prefer same-study to limit batch).
   - `EXPR_SUBSAMPLE=3000000 python backend/scripts/fetch_expression.py <species>` →
     `expression_<species>.json.gz`.
   - No backend change: `expression.get_matrix(species)` + the `/expression` and
     `/coexpression` endpoints auto-select by gene species.

4. **Orthologs** (enables cross-species conservation + Arabidopsis-network projection):
   load ortholog pairs (OMA/PLAZA BHIF, or genus phylogeny/bait-capture for Dahlia) into
   `orthologs`. Projecting the Arabidopsis network onto the new species yields
   `Inferred:Arabidopsis` edges (labelled inferred).

5. **Pathways** (optional): if the species is in Plant Reactome, extend `fetch_pathways.py`
   `SPECIES`; else project via orthologs.

6. **Traits / GWAS** (species-agnostic, ready now): produce a TSV with `gene_id` + `trait`
   (+ optional `pmid`, `source`) and run:
   ```
   python backend/scripts/ingest_trait_table.py dahlia zach_gwas.tsv --source "Dahlia GWAS (Zach 20XX)"
   ```
   Gene ids must match atlas ids for the species; non-matching rows are skipped and
   reported. `/trait_enrichment` then works for that species automatically.

7. **dsRNA / RNAi silencing** (needs a transcript store): drop the species' CDS/transcript
   FASTA at `backend/data/transcripts_<species>.fasta.gz` (headers start with a transcript
   id). `POST /api/v1/dsrna` then works for that species — analyze a dsRNA (on-/off-target)
   or design the most specific window for a target gene; `silenced_genes` feeds `/perturb`.
   For polyploids (e.g. Dahlia) this is the key specificity check: include all homeolog
   transcripts so off-target/homeolog coverage is visible.

## Dahlia specifics (fill in when data lands)
- Genome/annotation: from the G3 paper / NCBI BioProject (bioRxiv link pending from Alex).
- Expression: the paper's RNA-seq on SRA → step 3.
- GWAS: Zach's ~400 low-pass cultivar runs → gene-mapped trait table → step 6.
- Phylogeny: genus bait-capture (~1000 CompCos genes) → orthology context (step 4).
- Prioritise the **anthocyanin/floral-pigmentation** pathway (the shared scientific interest).
