---
license: cc-by-nc-4.0
task_categories:
  - question-answering
  - text-classification
language:
  - en
tags:
  - scientific-information-extraction
  - schema-constrained-extraction
  - numerical-grounding
  - evidence-attribution
  - abstention-calibrated-f1
  - cite-hallucination
  - benchmark
  - nanobubble
  - nanocarrier
  - biomedical-nlp
size_categories:
  - 10K<n<100K
pretty_name: NanoBubbleEval v1.0
configs:
  - config_name: gold_hard
    data_files:
      - split: test
        path: gold_hard/iaa_subset.csv
  - config_name: predictions
    data_files:
      - split: regex
        path: predictions/regex-v1.csv
      - split: encoder
        path: predictions/biobert-squadv2.csv
      - split: llm
        path: predictions/qwen25-7b-instruct.csv
  - config_name: warehouse
    data_files:
      - split: full
        path: warehouse/master_inventory.csv
---

# NanoBubbleEval v1.0

**An evidence-grounded benchmark for schema extraction, numerical grounding,
and evidence attribution in the nanobubble and nanocarrier literature.**

## Summary

NanoBubbleEval operationalises three failure modes of scientific information
extraction as decomposed evaluation tasks over a shared record set:

1. **Schema-fill hallucination** — emitting a value when the source is silent.
2. **Numerical grounding under unit normalisation** — drifting between nm
   and µm, hours and days, percent and fraction.
3. **Verbatim evidence attribution** — citing a span that genuinely contains
   the answer.

The benchmark contributes:
- a **18-field normalised schema** with an explicit `NOT_REPORTED` convention
  scored under **abstention-calibrated F1**,
- a **tolerance-bounded numerical match** metric over canonicalised units that
  disentangles unit drift from value drift, and
- an **answer–evidence consistency rate** that detects cite-hallucination —
  predictions that emit a correct value paired with an unsupported span.

## v1.0 release at a glance

- **Final warehouse size:** 51,566 deduplicated records (post-recovery, 2026-05 snapshot).
- **Gold-hard tier containment:** 40/40 records resolve into the released warehouse.
- **Provenance branch:** **B** — original 2026-03 warehouse unrecovered;
  May 2026 re-harvest merged with direct-identifier re-fetches for the 14
  records the query-based re-harvest did not return.
- **Abstract cross-check (X / Y / Z):**
  - **X = 14** records: source-API abstract is byte-identical to the annotation-time abstract.
  - **Y = 19** records: differ only after Unicode/whitespace normalisation (mojibake repair, NFKC, whitespace collapse).
  - **Z = 7** records: source-side editorial revisions or mismatches (e.g., PubMed structured-abstract section labels added post-annotation).
  - 14 + 19 + 7 = 40.

The full audit log lives in [`verification/`](./verification) and is
machine-readable via [`verification/summary.json`](./verification/summary.json).

## Annotation tiers

| Tier | Records | Annotators | Use | Status |
|---|---:|---|---|---|
| **Gold-hard** (headline) | 40 | pre-specified blind dual-annotator protocol; v1.0 ships single-annotator-validated labels under that protocol; full dual annotation and IAA statistics planned for v1.1 | All headline metrics | **v1.0** |
| **Gold-lite extension** | 460 (dev=50, test=410) | single-annotator | Internal robustness check; not used for any reported claim | **v1.1 (scheduled)** |

## Schema

Six **headline** fields (numerical: `size`, `zeta_potential`, `stability`,
`loading_efficiency`; text: `payload`, `release_profile`) and twelve
**provisional** fields (`bubble_type`, `material_identity`,
`application_category`, `generation_method`, `characterization_method`,
`medium_environment`, `outcome_claim`, `evidence_span`, `ambiguity_flag`,
plus three additional unit slots).

Numerical headline fields carry a canonical unit (size: nm; zeta potential:
mV; stability: h; loading efficiency: %) and a unit-synonym table.
Out-of-vocabulary unit strings are flagged but never silently coerced.

## Files in this release

### v1.0 (shipped here)

| Path | Purpose |
|---|---|
| `warehouse/master_inventory.csv` | 51,566-record deduplicated warehouse manifest (2026-05 snapshot, post-recovery) |
| `gold_hard/iaa_subset.csv` | 40-record gold-hard tier with first-annotator labels |
| `predictions/regex-v1.csv` | B1 regex baseline predictions on gold-hard |
| `predictions/biobert-squadv2.csv` | B2 BioBERT-SQuAD-v2 predictions on gold-hard |
| `predictions/qwen25-7b-instruct.csv` | B3 Qwen2.5-7B-Instruct predictions on gold-hard |
| `verification/gold_hard_identifier_parse.csv` | DOI candidates parsed from each gold-hard `record_id` |
| `verification/gold_hard_containment_before_merge.csv` | Per-record match status against the May 2026 re-harvest (26/40 matched) |
| `verification/gold_hard_refetch_log.csv` | Source API + DOI candidate that resolved each of the 14 missing records |
| `verification/gold_hard_abstract_crosscheck.csv` | Per-record abstract cross-check (verbatim / normalised / source-side revision) |
| `verification/gold_hard_containment_after_merge.csv` | Post-merge containment confirming all 40 gold-hard records resolve into the released warehouse |
| `verification/summary.json` | Machine-readable summary of all recovery counts |
| `verification/abstract_mismatches.txt` | First 120 chars of each Z-bucket mismatch for manual review |
| `metadata/croissant.json` | Croissant 1.1 dataset metadata |
| `metadata/extraction_schema.json` | 18-field schema specification |
| `metadata/data_quality_report.md` | Warehouse-level QC (deduplication, missing fields) |
| `splits/slice_summary.md` | Slice membership counts |
| `splits/leakage_report.md` | Disjointness audit across splits |

### v1.1 (scheduled, regenerable from the released pipeline scripts)

| Path | Purpose |
|---|---|
| `data/curated/nanobubble_core_high_precision.csv` | 8,006-record A1+A2 high-precision core |
| `data/gold/gold_annotation_set_v3.csv` | 500-record gold pool (gold-hard ∪ 460-record gold-lite) |
| `data/tasks/` | Three task-view CSV files (structured, numerical, evidence) |
| `data/splits/splits.json` | Deterministic dev/test split file |

## Provenance and recovery audit

The original 2026-03 warehouse from which the gold-hard tier was sampled
was destroyed in a project-deletion incident. Local recovery was exhausted
(filesystem, git history, and HuggingFace dataset history were all checked).
Rather than ship a warehouse from which the evaluation tier could not be
derived, we re-anchored the warehouse to the gold-hard records by direct
identifier lookup against the source APIs:

- **26 / 40** records were already present in the May 2026 query-based
  re-harvest (matched by DOI or normalised title).
- **14 / 40** records were missing from the re-harvest. For each missing
  record, the canonical source-API identifier encoded in the gold-hard
  `record_id` (12 PubMed DOIs, 27 OpenAlex DOIs, 1 Europe PMC DOI across
  the full tier) was used to re-fetch metadata directly via PubMed
  E-utilities (`idconv` → `efetch`), OpenAlex `/works/doi:`, or EuropePMC
  search-by-DOI. All 14 re-fetches succeeded.
- After deduplication (DOI → PMID/PMCID → normalised title → URL), the
  released warehouse contains **51,566** records and is a strict superset
  of the gold-hard tier by `record_id` (40/40 resolve directly via the
  containment audit in `verification/gold_hard_containment_after_merge.csv`).
- Annotation-time abstracts from the gold-hard file are preserved verbatim
  in the warehouse for the 14 re-fetched rows; baseline predictions remain
  exactly reproducible from the released warehouse.

The full identifier-anchored recovery pipeline lives in the GitHub repo at
[`scripts/verification/`](https://github.com/eliashossain001/nanobubbleeval/tree/main/scripts/verification)
and is rerunnable end-to-end from a clean checkout.

## Baselines

| Baseline | Macro Naive-F1 | Macro Acal-F1 [95% CI] | Num. match | A–E consistency |
|---|---:|---:|---:|---:|
| B1 Regex | 0.305 | 0.493 [0.434, 0.538] | 0.889 | 1.000 |
| B2 BioBERT-SQuAD-v2 | 0.378 | 0.545 [0.487, 0.588] | 0.727 | 1.000 |
| B3 Qwen2.5-7B-Instruct | **0.724** | **0.758 [0.700, 0.810]** | **1.000** | 0.939 |

Bootstrap 95% CIs computed by record-level resampling with replacement
(`n_boot=1000`, seed=42).

## Headline finding

On the gold-hard tier, B3 dominates B2 by 21.3 points and B1 by 26.5 points
of macro Acal-F1, with non-overlapping CIs across all three baselines. Unit
accuracy is 1.000 across all three baselines, indicating that the bottleneck
is *which* property to extract rather than how to canonicalise its unit.
B3's macro Acal-F1 falls from 0.786 on original-research abstracts to 0.449
on review-paper abstracts — a 33.7-point drop, more than twice the
corresponding drop for B1 (12.6 points) or B2 (15.6 points), suggesting the
LLM is more sensitive to review-paper paraphrase than the simpler baselines.

## Versioning

The benchmark is versioned semantically. **v1.0** ships the post-recovery
deduplicated warehouse manifest, the 40-record gold-hard tier, the three
baseline-prediction files, the gold-hard recovery audit logs
(`verification/`), the Croissant 1.1 metadata, the schema specification,
and the slice and leakage reports. **v1.1** will add the 8,006-record
high-precision core, the 500-record gold pool, the 460-record gold-lite
extension tier, the three task-view CSVs, the deterministic `splits.json`,
finalised dual annotation on the gold-hard tier, an open-access full-text
gold subset under the same schema, and a same-family-larger ceiling
baseline plus a retrieval-augmented variant. Items in the v1.1 list are
regenerable end-to-end from the released pipeline scripts; we did not ship
them in v1.0 to keep the release scope strictly to what has been audited
and validated.

## Code

The accompanying Python package, pipeline scripts, and unit-test suite are
released at:

`https://github.com/eliashossain001/nanobubbleeval`

## License

The dataset is released under **CC BY-NC 4.0** (research use only). The
codebase is released under **MIT**.
