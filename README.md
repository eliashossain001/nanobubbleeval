<div align="center">

# NanoBubbleEval

**An evidence-grounded benchmark for schema extraction, numerical grounding,
and evidence attribution in the nanobubble and nanocarrier literature.**

NeurIPS 2026 Datasets & Benchmarks Track

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-78%20passing-brightgreen.svg)](#tests)

</div>

---

## What this is

Scientific information extraction in the nanobubble and nanocarrier literature
jointly stresses three failure modes that existing benchmarks evaluate only in
isolation:

1. **Schema-fill hallucination** — emitting a value when the source is silent.
2. **Numerical grounding under unit normalisation** — drifting between nm and µm,
   hours and days, percent and fraction.
3. **Verbatim evidence attribution** — citing a span that genuinely contains
   the answer.

NanoBubbleEval operationalises these as **three structured tasks over a shared
record set**, evaluated with abstention-calibrated F1, tolerance-bounded
numerical match (after canonical-unit conversion), and an answer–evidence
consistency rate.

## Benchmark at a glance

| Layer | Records | Release | Notes |
|---|---:|:---:|---|
| Deduplicated warehouse | 51,566 | **v1.0** | OpenAlex (50,022) + PubMed (1,544); harvest framework also wires Europe PMC, CrossRef, Semantic Scholar, ClinicalTrials.gov v2 |
| High-precision nanobubble core | 8,006 | v1.1 | A1 (3,577) + A2 (4,429); regenerable from the released pipeline scripts |
| Benchmark candidate pool | 1,000 | v1.1 | Balanced sample over the high-precision core |
| Gold pool | 500 | v1.1 | Gold-hard tier ∪ 460-record gold-lite extension tier |
| Gold-hard tier (headline evaluation) | 40 | **v1.0** | Stratified by `nb_label` × `document_type` |
| Gold-lite extension tier | 460 | v1.1 | dev=50, test=410; single-annotator robustness check |
| Headline schema fields | 6 | **v1.0** | size, zeta_potential, stability, payload, loading_efficiency, release_profile |

The evaluation protocol defines three task views over the gold-hard tier
(structured extraction, numerical grounding, evidence attribution); standalone
task-view CSV files are scheduled for v1.1.

### v1.0 release contents

The dataset bundle (under [`dataset_release/`](dataset_release/)) ships:

- `warehouse/master_inventory.csv` — 51,566-record deduplicated warehouse manifest (post-recovery, 2026-05 snapshot)
- `gold_hard/iaa_subset.csv` — 40-record gold-hard tier with first-annotator labels
- `predictions/{regex-v1,biobert-squadv2,qwen25-7b-instruct}.csv` — three reference baselines
- `splits/{slice_summary,leakage_report}.md` — slice membership and leakage audit
- `metadata/{croissant.json,extraction_schema.json,data_quality_report.md}` — Croissant 1.1 metadata + 18-field schema
- `verification/{gold_hard_*.csv,summary.json,abstract_mismatches.txt}` — Branch B recovery audit logs (X/Y/Z = 14 verbatim / 19 normalised / 7 source-side revisions; 40/40 contained)

The 8,006-record high-precision core, the 500-record gold pool, the 460-record
gold-lite tier, the three task-view CSVs, and the deterministic `splits.json`
are scheduled for v1.1 and are regenerable end-to-end from the included
pipeline scripts.

The dataset will be released publicly at the camera-ready stage; an
anonymised mirror is provided to reviewers.

## Install

```bash
# clone from the anonymised release URL provided to reviewers
cd nanobubbleeval
pip install -e .                # core: pandas, numpy, scikit-learn
pip install -e .[baselines]     # adds transformers, torch (B2/B3)
pip install -e .[dev]           # adds pytest, ruff, mypy
```

## Quickstart — CLI

The package installs a single `nanoeval` console script with four subcommands.
The fastest way to evaluate against the v1.0 release is to score baseline
predictions against the bundled gold-hard tier:

```bash
# Score a (gold, prediction) pair on the headline metrics (v1.0)
nanoeval evaluate \
    --gold dataset_release/gold_hard/iaa_subset.csv \
    --pred dataset_release/predictions/qwen25-7b-instruct.csv \
    --out  results/metrics/qwen25_7b.csv
```

The remaining subcommands rely on the v1.1-scheduled gold pool
(`data/gold/gold_annotation_set_v3.csv`) and are kept here for the v1.1
workflow:

```bash
# 1. Sample a stratified IAA subset (40 records, seed=42)
nanoeval build-iaa-subset \
    --gold data/gold/gold_annotation_set_v3.csv \
    --out  annotation/packet \
    --n 40 --seed 42

# 2. Build dev/test splits + 5-slice tagging
nanoeval build-splits \
    --gold     data/gold/gold_annotation_set_v3.csv \
    --iaa-keys annotation/packet/iaa_subset_keys.csv \
    --out      data/splits

# 3. Compute IAA between two annotators
nanoeval reconcile \
    --a annotation/received/iaa_subset_A.csv \
    --b annotation/received/iaa_subset_B.csv \
    --out annotation/gold_hard
```

Numbered wrapper scripts under [`scripts/`](scripts/) carry the same calls
with canonical paths pre-baked, so `python3 scripts/01_build_iaa_subset.py`
works without any flags once the v1.1 gold pool ships.

## Quickstart — Python API

```python
from nanobubbleval import (
    AnnotationFrame, Evaluator, Reconciler, SplitBuilder,
    HEADLINE_FIELDS, NUMERIC_FIELDS, UnitNormalizer,
    Baseline, FieldPrediction, RegexBaseline,
    paths,                            # ProjectPaths singleton
)

# 1. Run a baseline on the IAA subset
input_frame = AnnotationFrame.from_csv(paths.iaa_subset)
predictions  = RegexBaseline().predict_frame(input_frame)
predictions.to_csv(paths.predictions_for("regex-v1"))

# 2. Evaluate against gold
gold = AnnotationFrame.from_csv(paths.gold_hard)
pred = AnnotationFrame.from_csv(paths.predictions_for("regex-v1"))
table = Evaluator().evaluate(gold, pred, fields=HEADLINE_FIELDS)
print(table[table["field"] == "MACRO"][["naive_f1", "acal_f1", "num_match"]])

# 3. Compute IAA between two annotators
report = Reconciler().run(annotator_a, annotator_b, label_a="A", label_b="B")
report.write(paths.iaa_gold_hard)

# 4. Add a new baseline (subclass the ABC, get predict_frame for free)
class MyBaseline(Baseline):
    name = "my-baseline-v1"
    def predict_record(self, record_id, abstract):
        return {f: FieldPrediction.nr() for f in HEADLINE_FIELDS}
```

## Headline metrics

| Metric | What it measures |
|---|---|
| `naive_f1` | F1 over the EMIT class only (correct emit vs missed / wrong value) |
| `nr_f1` | F1 over the NR class (correctly emitted `NOT_REPORTED`) |
| `acal_f1` | Macro mean of (`naive_f1`, `nr_f1`) — abstention-calibrated headline |
| `num_match` | Tolerance-bounded numeric match after canonical-unit conversion |
| `unit_accuracy` | Canonical-unit equality among emit-emit pairs |
| `span_iou` | Character-set IoU of evidence quotes among emit-emit pairs |
| `ae_consistency` | Frac. of non-NR predictions whose value substring is in the cited quote |

The `Naive-F1` minus `Acal-F1` gap is the v1.0 schema-fill-hallucination
signature: a model that fabricates values where the source is silent has a
high naive score and a low calibrated score.

## Architecture

The package follows a three-layer architecture for testability and reuse:

| Layer | Modules | Role |
|---|---|---|
| **Domain** | `schema.py`, `frames.py`, `baselines/base.py` (`FieldPrediction`) | Value objects and typed wrappers; no I/O, no side effects |
| **Application** | `evaluator.py`, `reconciliation.py`, `splits.py`, `baselines/*.py` | Use-case services and strategy classes; pure functions of domain inputs |
| **Infrastructure** | `paths.py`, `cli.py` | Path resolution, argument parsing, logging |

Adding a new baseline is one new file under `baselines/`: subclass `Baseline`,
set `name`, implement `predict_record`. The default `predict_frame` and the
I/O machinery come for free from the abstract class.

Adding a new metric is one method on `Evaluator` plus one column in
`FieldMetrics`. The match logic itself lives in `MatchPolicy` and can be
swapped via constructor injection without touching `Evaluator`.

## Repository layout

```
nanobubbleeval/
├── src/nanobubbleval/      # importable Python package (clean layered)
│   ├── schema.py           # FieldSpec, UnitNormalizer
│   ├── frames.py           # AnnotationFrame, FieldCell
│   ├── evaluator.py        # Evaluator, FieldMetrics, MatchPolicy
│   ├── reconciliation.py   # Reconciler, ReconciliationReport
│   ├── splits.py           # SplitBuilder, StratifiedSampler, SplitConfig
│   ├── baselines/          # Strategy pattern: Baseline ABC + concretes
│   │   ├── base.py         # Baseline (ABC), FieldPrediction
│   │   ├── regex_baseline.py
│   │   ├── encoder_baseline.py
│   │   └── llm_baseline.py
│   ├── harvest/            # Multi-source harvest + dedup framework
│   ├── paths.py            # ProjectPaths singleton
│   └── cli.py              # nanoeval CLI (argparse subcommands)
├── tests/                  # 78 unit tests
├── scripts/                # Numbered pipeline wrappers (01–05)
│   ├── legacy_harvest/     # Stage A: multi-source harvest
│   └── verification/       # Branch B recovery + HF push + figure build
├── data/                   # Lifecycle-staged datasets (large files .gitignored)
│   ├── raw/                #   warehouse manifest
│   ├── curated/            #   high-precision core (v1.1)
│   ├── gold/               #   gold pool (v1.1)
│   ├── tasks/              #   three task views (v1.1)
│   └── splits/             #   splits.json (v1.1) + slice/leakage (v1.0)
├── annotation/             # Annotation packet, received, gold-hard
├── verification/           # Gold-hard recovery audit logs (40/40 containment)
├── dataset_release/        # Release bundle (gold-hard, predictions,
│                           # splits, metadata, README; warehouse 75 MB local)
├── baselines/              # Baseline run outputs (regex, encoder, llm)
├── results/                # Experiment outputs (metrics, slices, errors)
├── paper/                  # LaTeX submission (main.tex, checklist.tex, ref.bib)
├── docs/                   # Corpus statistics and characterisation
├── configs/                # Schema specification
└── archive/                # Frozen artefacts (legacy reports)
```

## Reproducibility

All build steps are seeded (`seed=42`). The dev/test split is deterministic;
IAA subset stratification quotas are fixed in
[`src/nanobubbleval/cli.py`](src/nanobubbleval/cli.py).

```bash
# regenerate everything from a clean checkout:
python3 scripts/01_build_iaa_subset.py
python3 scripts/02_build_splits.py
python3 scripts/verification/run_recovery.py --write-warehouse   # rebuilds the v1.0 warehouse from the May 2026 re-harvest
pytest -q                              # 78/78 tests pass
```

## Provenance and gold-hard recovery (Branch B)

The original 2026-03 warehouse from which the 40-record gold-hard tier was
sampled was destroyed in a project-deletion incident. The released v1.0
warehouse is a 2026-05 re-harvest re-anchored to the gold-hard records by
direct identifier lookup against the source APIs. The full audit trail lives
in [`verification/`](verification/) and ships in the release bundle under
the same path:

- 26 of 40 gold-hard records were already present in the May 2026 re-harvest;
  14 were missing and were re-fetched by canonical DOI (PubMed E-utilities +
  OpenAlex `/works/doi:`) and merged in under the original gold-hard
  `record_id`.
- After deduplication (DOI → PMID/PMCID → normalised title → URL), all 40/40
  gold-hard records resolve into the released warehouse.
- Abstract cross-check between source-API text today and annotation-time
  text: 14 verbatim / 19 Unicode-normalised / 7 source-side editorial
  revisions (e.g., PubMed structured-abstract section labels added
  post-annotation). See
  [`verification/summary.json`](verification/summary.json) for the
  machine-readable summary and
  [`verification/abstract_mismatches.txt`](verification/abstract_mismatches.txt)
  for the seven Z-bucket records.

The recovery pipeline is fully scripted under
[`scripts/verification/`](scripts/verification/) and rerunnable from a clean
checkout.

## Tests

```bash
pytest tests/ -v
```

Covers the unit normaliser, evaluator, reconciler, `ProjectPaths`, the
`Baseline` abstract class, the regex / encoder / LLM baselines, the harvest
framework, and the annotation pipeline (78 tests total).

## Environment variables

NanoBubbleEval has minimal external configuration. The only required
variable for the LLM baseline is `HF_TOKEN`; copy `.env.example` to `.env`
and fill in your value:

```bash
cp .env.example .env
# edit .env to add HF_TOKEN
```

`.env` is gitignored. See [`.env.example`](.env.example) for the full list
of supported variables.

## Citation

```bibtex
@misc{nanobubbleeval2026,
  title  = {NanoBubbleEval: An Evidence-Grounded Benchmark for Schema Extraction,
            Numerical Grounding, and Evidence Attribution in the Nanobubble
            and Nanocarrier Literature},
  author = {Anonymous Authors},
  year   = {2026},
  note   = {NeurIPS 2026 Datasets and Benchmarks Track (under review)}
}
```

The bibtex stanza will be updated with the verified URL and final author
list after the camera-ready deadline.

## License

Released under the [MIT License](LICENSE). The dataset itself is licensed for
research use under terms detailed in the paper's *Limitations and Ethics*
section.
