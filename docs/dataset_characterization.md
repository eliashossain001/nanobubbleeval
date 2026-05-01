# Dataset Characterization

## Warehouse vs Benchmark

| Split | Records | Abstracts | Abstract % | Nanobubble-like | Nanoparticle-like | Tier A | Tier B | Tier C |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Warehouse | 52519 | 38035 | 72.4% | 3250 | 46776 | 9033 | 8450 | 35036 |
| Benchmark 500 | 500 | 500 | 100.0% | 236 | 251 | 261 | 96 | 143 |
| Benchmark 1000 | 1000 | 999 | 99.9% | 484 | 471 | 523 | 196 | 281 |

## Core Subset

| Core label | Count | Precision proxy |
| --- | --- | --- |
| A1 | 3577 | 90.9% |
| A2 | 4429 | adjacent ultrasound/gas-carrier |

## Source Distribution

| Source API | Count |
| --- | --- |
| OpenAlex | 40836 |
| PubMed | 9404 |
| EuropePMC | 1391 |
| CrossRef | 548 |
| SemanticScholar | 250 |
| curated_seed | 80 |
| ClinicalTrials.gov | 10 |

## Document Type Distribution

| Document type | Count |
| --- | --- |
| original | 41817 |
| review | 10692 |
| clinical_trial | 10 |

## Year Distribution

| Year bin | Warehouse | Benchmark 1000 |
| --- | --- | --- |
| <=2010 | 8127 | 33 |
| 2011-2014 | 6519 | 74 |
| 2015-2018 | 9453 | 148 |
| 2019-2021 | 9479 | 210 |
| 2022-2024 | 9227 | 273 |
| 2025+ | 9696 | 262 |
| NOT_REPORTED | 18 | 0 |

## Venue Distribution

| Venue | Count |
| --- | --- |
| Pharmaceutics | 35 |
| NOT_REPORTED | 27 |
| International Journal of Nanomedicine | 22 |
| International journal of nanomedicine | 18 |
| Theranostics | 14 |
| Scientific Reports | 14 |
| Langmuir : the ACS journal of surfaces and colloids | 14 |
| Langmuir | 12 |
| Scientific reports | 10 |
| International journal of pharmaceutics | 10 |
| Journal of Nanobiotechnology | 9 |
| Ultrasonics sonochemistry | 9 |
| Molecular Pharmaceutics | 9 |
| International Journal of Applied Pharmaceutics | 8 |
| Frontiers in Pharmacology | 8 |

## Field Coverage

| Field | Warehouse yes | Benchmark 500 yes | Benchmark 1000 yes |
| --- | --- | --- | --- |
| likely_has_size | 13811 | 453 | 827 |
| likely_has_zeta_potential | 3412 | 273 | 390 |
| likely_has_stability | 10424 | 405 | 734 |
| likely_has_payload | 29087 | 441 | 899 |
| likely_has_loading_efficiency | 9985 | 352 | 577 |
| likely_has_release_profile | 12921 | 344 | 622 |

## Co-occurrence Matrix

| Field | likely_has_size | likely_has_zeta_potential | likely_has_stability | likely_has_payload | likely_has_loading_efficiency | likely_has_release_profile |
| --- | --- | --- | --- | --- | --- | --- |
| likely_has_size | 13811 | 1921 | 4054 | 9234 | 3975 | 4754 |
| likely_has_zeta_potential | 1921 | 3412 | 1114 | 1804 | 1000 | 1151 |
| likely_has_stability | 4054 | 1114 | 10424 | 5936 | 2993 | 2944 |
| likely_has_payload | 9234 | 1804 | 5936 | 29087 | 7850 | 10064 |
| likely_has_loading_efficiency | 3975 | 1000 | 2993 | 7850 | 9985 | 5106 |
| likely_has_release_profile | 4754 | 1151 | 2944 | 10064 | 5106 | 12921 |

## Notes

- Benchmark 500 and 1000 are balanced selections derived from the existing warehouse; no new records were collected.
- A1 precision is a proxy based on explicit nanobubble lexical evidence and current label assignment.
- Counts and ratios are computed from the current master inventory at the time of curation.
