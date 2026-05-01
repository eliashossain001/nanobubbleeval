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
  - n<1K
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

## Annotation tiers

| Tier | Records | Annotators | Use |
|---|---:|---|---|
| **Gold-hard** (headline) | 40 | pre-specified blind dual-annotator protocol; v1.0 ships single-annotator-validated labels under that protocol; full dual annotation and IAA statistics planned for v1.1 | All headline metrics |
| **Gold-lite extension** | 460 (dev=50, test=410) | single-annotator | Robustness check only — not used for headline claims |

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

| Path | Purpose |
|---|---|
| `gold_hard/iaa_subset.csv` | 40-record gold-hard tier (first-annotator labels) |
| `predictions/regex-v1.csv` | B1 regex baseline predictions on gold-hard |
| `predictions/biobert-squadv2.csv` | B2 BioBERT-SQuADv2 predictions on gold-hard |
| `predictions/qwen25-7b-instruct.csv` | B3 Qwen2.5-7B-Instruct predictions on gold-hard |
| `metadata/croissant.json` | Croissant 1.1 dataset metadata |
| `metadata/extraction_schema.json` | 18-field schema specification |
| `metadata/data_quality_report.md` | Warehouse-level QC (deduplication, missing fields) |
| `splits/slice_summary.md` | Slice membership counts |
| `splits/leakage_report.md` | Disjointness audit across splits |

## Baselines

| Baseline | Macro Naive-F1 | Macro Acal-F1 [95% CI] | Num. match | A–E consistency |
|---|---:|---:|---:|---:|
| B1 Regex | 0.305 | 0.493 [0.434, 0.538] | 0.889 | 1.000 |
| B2 BioBERT-SQuADv2 | 0.378 | 0.545 [0.487, 0.588] | 0.727 | 1.000 |
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

The benchmark is versioned semantically. v1.0 ships the small-artifact
release (gold-hard tier, baseline predictions, Croissant metadata, schema
specification, slice and leakage reports). The 52,519-record warehouse
manifest, the 8,006-record high-precision core, the 460-record gold-lite
extension tier, the three task views (`structured`, `numerical`,
`evidence`), and the deterministic `splits.json` will be added in a
subsequent release. v1.1 will additionally finalise dual annotation on the
gold-hard tier, extend the gold-lite tier with open-access full-text records,
and add a same-family-larger ceiling baseline plus a retrieval-augmented
variant.

## Code

The accompanying Python package, pipeline scripts, and unit-test suite are
released at:

`https://github.com/eliashossain001/nanobubbleeval`

## License

The dataset is released under **CC BY-NC 4.0** (research use only). The
codebase is released under **MIT**.
