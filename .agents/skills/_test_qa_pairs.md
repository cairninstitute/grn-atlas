# GRN Atlas Skills — Test Q&A Pairs with Ground Truth

174 tests across 15 skills, all answers verified against direct SQLite queries.

## grn-gene-search (12 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--query TP53 --species human --limit 5` | First=TP53, human, is_tf=true, id=TP53 | PASS |
| 2 | `--query MYB --species arabidopsis --limit 3` | All arabidopsis, ≤3 results | PASS |
| 3 | `--query ZZZZNOTAREAL_GENE_XYZ --species human` | Empty list | PASS |
| 4 | `--query BRCA --species human` | Finds BRCA1 and BRCA2 | PASS |
| 5 | `--query apoptosis --species human --limit 5` | Finds BAX (name match) | PASS |
| 6 | `--query MYC --species human --limit 1` | Exactly 1 result, symbol=MYC | PASS |
| 7 | `--query HY5 --species arabidopsis` | Finds HY5 with id=AT5G11260 | PASS |
| 8 | `--query AN1 --species tomato` | Finds AN1, all tomato | PASS |
| 9 | `--query ABF --species arabidopsis --limit 50` | Finds ABF1 and ABF2 | PASS |
| 10 | `--query BCL2` (no species) | Finds BCL2, is_tf=false | PASS |
| 11 | `--query STAT3 --species human` | STAT3, is_tf=true, protein_coding | PASS |
| 12 | `--query NFKB1 --species mouse` | Returns list (may be empty) | PASS |

## grn-gene-info (11 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--gene-id TP53` | id=TP53, human, tf=true, "tumor" in name | PASS |
| 2 | `--symbol ABF1 --species arabidopsis` | id=AT1G49720, symbol=ABF1 | PASS |
| 3 | `--gene-id FAKEGENE999` | None/error/not found | PASS |
| 4 | `--gene-id MYC` | MYC, tf=true, protein_coding | PASS |
| 5 | `--gene-id BCL2` | BCL2, tf=false | PASS |
| 6 | `--gene-id BAX` | tf=false, human | PASS |
| 7 | `--symbol HY5 --species arabidopsis` | id=AT5G11260, tf=true | PASS |
| 8 | `--gene-id AT5G11260` | symbol=HY5, arabidopsis | PASS |
| 9 | `--gene-id NFKB1` | NFKB1, tf=true | PASS |
| 10 | `--gene-id MDM2` | tf=true, human | PASS |
| 11 | `--symbol PIF4 --species arabidopsis` | id=AT2G43010, tf=true | PASS |

## grn-network (12 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--gene-id TP53` (both) | 31 regulators, 106 targets, BAX in targets, SIRT1 in regulators | PASS |
| 2 | `--gene-id TP53 --direction regulators` | 31 regulators, 0 targets | PASS |
| 3 | `--gene-id TP53 --direction targets` | 0 regulators, 106 targets | PASS |
| 4 | `--gene-id TP53 --min-confidence 0.7` | 9 regulators, 22 targets | PASS |
| 5 | `--gene-id AT1G49720 --direction targets` | 1458 targets | PASS |
| 6 | `--gene-id AT1G49720 --direction regulators` | 2 regulators | PASS |
| 7 | `--gene-id MYC` | 45 reg, 69 tgt, STAT3 in regulators | PASS |
| 8 | `--gene-id AT5G11260` (HY5) | 32 reg, 231 tgt, PIF4 in regulators | PASS |
| 9 | `--gene-id NFKB1` | 22 reg, 176 tgt | PASS |
| 10 | `--gene-id E2F1` | 20 reg, 94 tgt | PASS |
| 11 | `--gene-id FAKEGENE` | Error/empty | PASS |
| 12 | `--gene-id AT5G13930` | 10 reg, 0 tgt (no targets) | PASS |

## grn-pathfinding (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--source TP53 --target BAX --max-depth 1` | Direct path, 2 genes, conf=0.95 | PASS |
| 2 | `--source TP53 --target TERT --max-depth 1` | Direct path exists | PASS |
| 3 | `--source TP53 --target TERT --max-depth 2` | ≥2 paths (direct + via MYC) | PASS |
| 4 | `--source TP53 --target BAX --max-depth 2` | ≥2 paths, direct first | PASS |
| 5 | `--source TP53 --target ZZZZFAKE` | Graceful error (no paths) | PASS |
| 6 | `--source TP53 --target E2F1 --max-depth 1` | Path with repression | PASS |
| 7 | `--source E2F1 --target TP53 --max-depth 1` | Path with activation | PASS |
| 8 | `--source MYC --target CDKN1A --max-depth 1` | Path, conf=0.95 | PASS |
| 9 | `--source NFKB1 --target MYC --max-depth 1` | Path, conf=0.7 | PASS |
| 10 | `--source TP53 --target BAX --min-confidence 0.9` | Only high-conf paths | PASS |

## grn-enrichment (16 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | GO: TP53,BAX,BCL2,CDKN1A,MDM2 | Non-empty enriched terms | PASS |
| 2 | pathway: same 5 genes | Non-empty results | PASS |
| 3 | trait: same 5 genes | Non-empty results | PASS |
| 4 | motif: AT1G49720,AT1G45249,AT4G34000 | Returns results | PASS |
| 5 | GO: 6 human TFs | Non-empty | PASS |
| 6 | pathway: 6 human TFs | Non-empty | PASS |
| 7 | trait: 6 human TFs | Returns results | PASS |
| 8 | GO: arabidopsis light TFs | Returns results | PASS |
| 9 | GO: nonexistent genes | Graceful error | PASS |
| 10 | GO: single gene TP53 | Returns results | PASS |
| 11 | motif: arabidopsis light TFs | Returns results | PASS |
| 12 | pathway: arabidopsis light TFs | Returns results | PASS |
| 13 | **GO content**: apoptotic process & p53 terms present, q<0.05, study_count≥2 | PASS |
| 14 | **Pathway content**: TP53 network & DNA damage response found, study_count=5, q<0.05 | PASS |
| 15 | **Trait content**: results have trait, p_value, study_count fields | PASS |
| 16 | **GO sort order**: results sorted ascending by p_value | PASS |

## grn-expression (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--gene-id AT1G49720` (ABF1) | Has expression data (arabidopsis) | PASS |
| 2 | `--gene-id AT5G11260` (HY5) | Has expression data | PASS |
| 3 | `--gene-id AT2G43010` (PIF4) | Has expression data | PASS |
| 4 | `--gene-id TP53` (human) | Graceful (no human expression file) | PASS |
| 5 | `--gene-id FAKEGENE` | Graceful error | PASS |
| 6 | `--gene-id AT1G45249` (ABF2) | Has data | PASS |
| 7 | `--gene-id AT3G24650` (ABI3) | Has data | PASS |
| 8 | `--gene-id AT2G36270` (ABI5) | Has data | PASS |
| 9 | `--gene-id AT3G20770` (EIN3) | Has data | PASS |
| 10 | `--gene-id Solyc02g071730.2` (tomato AG) | Has data (tomato expression exists) | PASS |

## grn-coexpression (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--gene-id AT1G49720 --top 5` | Returns partners | PASS |
| 2 | `--gene-id AT5G11260 --top 10` (HY5) | Returns results | PASS |
| 3 | `--gene-id AT2G43010 --top 5` (PIF4) | Returns results | PASS |
| 4 | `--gene-id AT1G49720 --top 3 --min-r 0.8` | High-correlation only | PASS |
| 5 | `--gene-id AT1G49720 --top 20` | Returns results | PASS |
| 6 | `--gene-id TP53 --top 5` (no human expr) | Graceful | PASS |
| 7 | `--gene-id FAKEGENE --top 5` | Graceful | PASS |
| 8 | `--gene-id AT1G45249 --top 5` (ABF2) | Returns results | PASS |
| 9 | `--gene-id AT3G20770 --top 5` (EIN3) | Returns results | PASS |
| 10 | `--gene-id Solyc02g071730.2 --top 5` (tomato) | Returns results | PASS |

## grn-perturbation (14 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--gene-id TP53 --action ko` | Has downstream effects | PASS |
| 2 | `--gene-id TP53 --action oe` | Has effects | PASS |
| 3 | `--gene-id MYC --action ko` | Has effects | PASS |
| 4 | `--gene-id NFKB1 --action ko` (176 tgt) | Has effects | PASS |
| 5 | `--gene-id E2F1 --action oe` | Has effects | PASS |
| 6 | `--gene-id AT5G11260 --action ko` (HY5) | Has effects | PASS |
| 7 | `--gene-id AT1G49720 --action ko` (ABF1, 1458 tgt) | Has effects | PASS |
| 8 | `--gene-id TP53 --action ko --depth 2` | Has effects | PASS |
| 9 | `--gene-id TP53 --action ko --min-confidence 0.9` | Has effects | PASS |
| 10 | `--gene-id BAX --action ko` (non-TF, 0 targets) | Returns data (empty effects OK) | PASS |
| 11 | **Multi: `--gene-ids TP53:ko,MYC:oe`** | Has effects, 2 interventions listed | PASS |
| 12 | **Multi: `--gene-ids TP53:ko,E2F1:ko`** | Has effects | PASS |
| 13 | **Multi: `--gene-ids NFKB1:ko,STAT3:ko,MYC:ko`** | Has effects, 3 interventions | PASS |
| 14 | **Multi: `--gene-ids TP53:oe,MYC:ko`** (opposing) | Has effects | PASS |

## grn-dsrna (15 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--target-gene AT1G49720 --species arabidopsis` | Designs dsRNA for ABF1 | PASS |
| 2 | `--sequence ATGCATGC...48nt --species arabidopsis` | Analyzes off-targets | PASS |
| 3 | `--target-gene AT5G11260 --species arabidopsis` (HY5) | Designs dsRNA | PASS |
| 4 | `--target-gene AT2G43010 --species arabidopsis` (PIF4) | Designs dsRNA | PASS |
| 5 | `--sequence ATGATG...48nt --species arabidopsis --k 19` | k=19 analysis | PASS |
| 6 | `--target-gene AT3G20770 --species arabidopsis` (EIN3) | Designs dsRNA | PASS |
| 7 | GC-rich sequence, arabidopsis | Analyzes | PASS |
| 8 | `--target-gene AT1G49720 --k 25` | k=25 design | PASS |
| 9 | `--target-gene Solyc09g065100.1 --species tomato` (AN1) | Designs/error | PASS |
| 10 | AT-rich sequence, tomato | Analyzes | PASS |
| 11 | **`--target-gene TP53 --species human`** | available=false, "no transcript" in note | PASS |
| 12 | **`--target-gene MOUSE05861 --species mouse`** | available=false | PASS |
| 13 | **Design content**: mode=design, has sequence/start/end, specificity 0-1, on_target matches | PASS |
| 14 | **Analyze content**: mode=analyze, k=21, has n_sirnas, off_target_gene_count | PASS |
| 15 | **Nonexistent gene in valid species**: graceful error | PASS |

## grn-orthology (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | `--gene-id TP53` (default species) | human found=true, has regulators | PASS |
| 2 | `--gene-id TP53 --species mouse` | Has mouse entry | PASS |
| 3 | `--gene-id TP53 --species human,mouse` | Has both | PASS |
| 4 | `--gene-id MYC` | human found=true | PASS |
| 5 | `--gene-id AT5G11260` (HY5) | Returns data | PASS |
| 6 | `--gene-id AT5G11260 --species tomato` | Has tomato | PASS |
| 7 | `--gene-id E2F1` | Returns data | PASS |
| 8 | `--gene-id NFKB1 --species mouse` | Has mouse | PASS |
| 9 | `--gene-id FAKEGENE` | Graceful error | PASS |
| 10 | `--gene-id BRCA1 --species mouse` | Has mouse | PASS |

## grn-conservation (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | 5 human genes -> mouse | Returns conservation data | PASS |
| 2 | 3 TFs -> mouse | Returns data | PASS |
| 3 | arabidopsis HY5,PIF4 -> tomato | Returns data | PASS |
| 4 | ABF1 -> tomato | Returns data | PASS |
| 5 | ABF1 -> petunia | Returns data | PASS |
| 6 | single gene TP53 -> mouse | Returns data | PASS |
| 7 | 3 TFs -> mouse (NFKB1,STAT3,BRCA1) | Returns data | PASS |
| 8 | 4 arabidopsis TFs -> tomato | Returns data | PASS |
| 9 | nonexistent genes -> mouse | Graceful | PASS |
| 10 | HY5 -> petunia | Returns data | PASS |

## grn-subgraph (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | TP53,BAX,BCL2,CDKN1A,MDM2 | Has edges (TP53 regulates all 4) | PASS |
| 2 | TP53,MYC,E2F1,NFKB1 | Has edges (7 known interactions) | PASS |
| 3 | TP53,MYC | Has edges | PASS |
| 4 | BAX,BCL2 (non-TFs) | Returns data (no edges expected) | PASS |
| 5 | HY5,PIF4,PIL5 (arabidopsis) | Returns data | PASS |
| 6 | 8 genes large set | Has edges | PASS |
| 7 | nonexistent genes | Graceful | PASS |
| 8 | single gene | Returns data | PASS |
| 9 | STAT3,MYC (known edge) | Has edges | PASS |
| 10 | TP53,E2F1 (bidirectional) | ≥2 edges | PASS |

## grn-export (14 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | TP53,BAX,BCL2 JSON | Returns edge data | PASS |
| 2 | TP53,BAX,BCL2 TSV | Returns tab-separated text | PASS |
| 3 | single gene JSON | Returns data | PASS |
| 4 | 5 TFs JSON | Returns data | PASS |
| 5 | arabidopsis genes JSON | Returns data | PASS |
| 6 | arabidopsis genes TSV | Returns tab-separated text | PASS |
| 7 | MYC,CDKN1A JSON | Returns data | PASS |
| 8 | nonexistent gene JSON | Graceful | PASS |
| 9 | non-TF gene (BAX) JSON | Returns data | PASS |
| 10 | BRCA1,BRCA2 JSON | Returns data | PASS |
| 11 | **JSON content**: edges have source/target_gene_id, regulation_type, confidence; TP53->BAX present; stats.edges matches | PASS |
| 12 | **JSON coordinates**: source_chromosome, target_start, promoter windows present | PASS |
| 13 | **TSV content (human)**: starts with "# GRN Atlas", has tab header, has data rows, TP53 & BAX present | PASS |
| 14 | **TSV content (arabidopsis)**: has comment header, ≥7 lines, AT5G11260 present | PASS |

## grn-provenance (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | basic manifest | has atlas_version, sources, methods, TRRUST | PASS |
| 2 | sources have DOIs | All sources have doi or url | PASS |
| 3 | methods documented | promoter_window, enrichment methods present | PASS |
| 4 | version is string | atlas_version is string type | PASS |
| 5 | has timestamp | generated field present | PASS |
| 6 | motif_scan method | In methods dict | PASS |
| 7 | inferred_edges method | In methods dict | PASS |
| 8 | has JASPAR source | JASPAR in sources | PASS |
| 9 | coordinate_systems method | In methods dict | PASS |
| 10 | regulator_identification method | In methods dict | PASS |

## grn-species (10 tests)

| # | Query | Ground Truth | Grade |
|---|---|---|---|
| 1 | returns all species | ≥5 species | PASS |
| 2 | has human | human in output | PASS |
| 3 | has arabidopsis | arabidopsis in output | PASS |
| 4 | has tomato | tomato in output | PASS |
| 5 | has petunia | petunia in output | PASS |
| 6 | has mouse | mouse in output | PASS |
| 7 | capability fields | expression/motif/trait keywords present | PASS |
| 8 | consistent results | Non-null on re-run | PASS |
| 9 | no empty species names | All species named | PASS |
| 10 | gene counts present | Gene-related data in output | PASS |
