# TBD Log — `nano/paper/main.tex` v0.1

Every TBD in the draft, what fills it, and which experiment we run to fill it.
This is the work-list for D1–D3.

## Numbers / placeholders to replace

| # | Where | What it says | What fills it | Owner | Day |
|---|---|---|---|---|---|
| 1 | Abstract | "We benchmark a regex floor..." | Final result phrasing once tables filled | me | D3 |
| 2 | Contributions item 4 | Baseline table reference | Filled Tab. `headline_results` | me | D3 |
| 3 | Contributions item 4 | $\kappa$ on IAA | IAA reconciliation script output | me | D2 |
| 4 | §3 Task — "average fields-per-record" | Mean of present fields per gold record | Compute on 40 IAA + 60 self-annotated | me | D2 |
| 5 | §6 Validity — IAA $\kappa$, span IoU, unit-norm match | Per-field IAA agreement | Reconciliation script on D2 | me | D2 |
| 6 | §9 Tab. `headline_results` | All cells (3 baselines × 4 metrics) | B1, B2, B3 runs on test | me | D2–D3 |
| 7 | §9.2 slice tables | Acal-F1 per slice per baseline | Re-score outputs by slice | me | D3 |
| 8 | §9.2 narrative | Slice gap commentary | Read off slice tables | me | D3 |
| 9 | §9.3 Tab. `iaa_summary` | Per-field $\kappa$, IoU, num-match | Reconciliation script + double-annotation | me | D2 |
| 10 | §9.3 narrative | Per-field $\kappa$ + ambiguity comment | Read off Tab. `iaa_summary` | me | D2 |
| 11 | §10 Error taxonomy count | 25 hand-inspected errors | Manual error pass on B3 outputs | me | D3 |
| 12 | §11 Conclusion 1-line takeaway | Headline takeaway sentence | Read off `headline_results` | me | D3 |
| 13 | App. A pipeline details | Full harvest spec | Copy from `report.tex` + `query_families.md` | me | D3 |
| 14 | App. B schema specification | Full 18-field schema | Copy from `extraction_schema.json` | me | D3 |
| 15 | App. C annotation guideline | Full guideline | Expand from `annotator_packet/instructions.md` | me | D3 |
| 16 | App. D extended results | Year/source slices, error examples | After main table runs | me | D3 |

## Experiments needed (in order)

### D1 (Fri May 1) — Annotation + B1
1. Receive collaborator IAA subset back (end of day).
2. Self-annotate the same 40 IAA records (blind, parallel work — start in AM).
3. Annotate 20 additional gold records (gold-lite tier).
4. Build B1 regex baseline (`baselines/regex_baseline.py`).
5. Smoke-test B1 on dev (50 records), iterate patterns.

### D2 (Sat May 2) — IAA + B3 + more annotation
1. Run reconciliation script: my labels vs. collaborator labels → IAA $\kappa$, span IoU, unit-norm match per field.
2. Adjudicate disagreements → produce `gold_hard.csv` (40 records, adjudicated).
3. Annotate 15 more gold-lite records (~75 total gold).
4. Build B3 LLM baseline (Qwen2.5-7B via HF, schema-constrained prompt, JSON repair).
5. Smoke-test B3 on dev (50 records), iterate prompt.
6. (stretch) Build B2 PubMedBERT QA-span baseline.

### D3 (Sun May 3) — Run, score, write, polish
1. Run B1, B3 (and B2 if built) on test (450 records — but only ~75 have gold; report on the 75-record gold-anchored subset).
2. Compute all metrics (`metrics.py`): Naive-F1, Acal-F1, num-match, span IoU, A-E consistency.
3. Generate slice tables and narrative paragraphs.
4. Hand-inspect ~25 B3 errors, classify into the 5 error categories.
5. Fill all TBDs in `main.tex`.
6. Polish abstract, intro, conclusion.

### D4 (Mon May 4) — Submit abstract + incorporate feedback
1. Polish abstract; submit by deadline.
2. Read professor feedback (if returned); apply.

### D5–D6 — Polish full paper, datasheet, checklist, submit.

## Risk register

| Risk | Mitigation |
|---|---|
| Collaborator slips past Friday EOD | I have my own annotations; report single-annotator on test, dual-annotator only on IAA subset |
| HF Inference API rate-limits B3 | Run B3 locally on the GPU; same prompt, same model |
| Fewer than 75 gold-pool records by D3 | Headline reports on whatever count we have; declare it explicitly |
| B2 doesn't run cleanly | Drop to two baselines (B1, B3); not a paper-killer |
| Numerical-match metric needs unit canonicaliser bugs | Restrict numerical-match table to fields where unit set is closed (size, zeta, loading_efficiency) |
