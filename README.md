<div align="center">

# NanoBubbleEval

**An evidence-grounded benchmark for schema extraction, numerical grounding,
and evidence attribution in the nanobubble and nanocarrier literature.**

NeurIPS 2026 Datasets & Benchmarks Track

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-53%20passing-brightgreen.svg)](#tests)

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

| Layer | Records | Notes |
|---|---:|---|
| Deduplicated warehouse | 52,519 | Six public scholarly APIs |
| High-precision nanobubble core | 8,006 | A1 (3,577) + A2 (4,429) |
| Gold pool | 500 | dev = 50, test = 450 |
| IAA subset (dual-annotator) | 40 | Pinned to test split |
| Headline schema fields | 6 | size, zeta_potential, stability, payload, loading_efficiency, release_profile |

The same 500-record gold pool is reprojected into three task views: structured
extraction, numerical grounding, and evidence attribution.

## Install

```bash
git clone https://github.com/eliashossain001/nanobubbleeval.git
cd nanobubbleeval
pip install -e .                # core: pandas, numpy, scikit-learn
pip install -e .[baselines]     # adds transformers, torch (B2/B3)
pip install -e .[dev]           # adds pytest, ruff, mypy
```

## Quickstart — CLI

The package installs a single `nanoeval` console script with four subcommands:

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
    --a annotation/received/iaa_subset_elias.csv \
    --b annotation/received/iaa_subset_collab.csv \
    --out annotation/gold_hard

# 4. Score a (gold, prediction) pair on the headline metrics
nanoeval evaluate \
    --gold annotation/gold_hard/gold_hard.csv \
    --pred baselines/llm/qwen25_7b_predictions.csv \
    --out  results/metrics/qwen25_7b.csv
```

Numbered wrapper scripts under [`scripts/`](scripts/) carry the same calls
with canonical paths pre-baked, so `python3 scripts/01_build_iaa_subset.py`
works without any flags.

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
report = Reconciler().run(annotator_a, annotator_b, label_a="elias", label_b="collab")
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
│   │   └── regex_baseline.py
│   ├── paths.py            # ProjectPaths singleton
│   └── cli.py              # nanoeval CLI (argparse subcommands)
├── tests/                  # 53 unit tests
├── scripts/                # Numbered pipeline wrappers (01–04)
├── data/                   # Lifecycle-staged datasets
│   ├── raw/                #   warehouse manifest
│   ├── curated/            #   high-precision core, candidate pools
│   ├── gold/               #   gold pool
│   ├── tasks/              #   three task views
│   └── splits/             #   splits.json + slice & leakage reports
├── annotation/             # Annotation packet, received, gold-hard
├── baselines/              # Baseline run outputs (regex, encoder, llm)
├── results/                # Experiment outputs (metrics, slices, errors)
├── paper/                  # LaTeX submission (main.tex, ref.bib)
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
pytest -q                              # 53/53 tests pass
```

## Tests

```bash
pytest tests/ -v
```

Covers the unit normaliser (28 cases), evaluator (5 cases), reconciler (4
cases), `ProjectPaths` (6 cases), and the `Baseline` abstract class (10
cases) with shared fixtures defining a six-record gold set, a near-perfect
extractor, and a never-abstain hallucinator.

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
