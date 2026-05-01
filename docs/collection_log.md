# Collection Log

Initialized project structure for NanoBubbleEval.

## 2026-04-22
- Created base folder structure and seed files.
- Added search keyword table in `outputs/search_keywords.csv`.
- Collected an initial review-paper seed set in `seed_reviews.csv`.
- Drafted a terminology and application summary in `docs/review_summary.md`.
- Added an original-study seed set in `seed_original_studies.csv`.
- Added a separate ClinicalTrials.gov stream in `clinical_trials.csv`.
- Built a merged master inventory, extraction-ready subset, pilot annotation sheet, and QC/corpus statistics outputs.
- Added the normalized extraction schema and reusable merge/slice/quality-check scripts.
- Current merged inventory: 58 deduplicated records across reviews, original studies, and clinical trials.
- Expanded the metadata bank to 68 deduplicated records and removed duplicated titles detected by QC.
- 2026-04-22 expansion batch added literature from PubMed citation chasing and protocol-driven ClinicalTrials.gov queries.
- Query families used: nanobubble review, nanobubble imaging, nanobubble stability, nanobubble drug delivery, oxygen nanobubble, ultrasound nanobubble, micro/nanobubble aeration, and translational clinical terms.
- Net gain in this batch: +4 reviews, +13 original studies, +0 clinical trial records, +17 total deduplicated records.
- API-driven bulk harvest added 2,290 raw records across PubMed, Europe PMC, OpenAlex, CrossRef, and ClinicalTrials.gov v2.
- Final deduplicated master inventory after merge: 2,352 records.
- Current source mix: PubMed 859, OpenAlex 837, EuropePMC 317, CrossRef 301, ClinicalTrials.gov 10, plus the original curated seed records from Springer/ScienceDirect/MDPI and related venues.

## 2026-04-22 large-scale warehouse expansion
- Switched to API-first high-volume harvesting with PubMed, Europe PMC, OpenAlex, CrossRef, Semantic Scholar, and ClinicalTrials.gov.
- Added checkpointed crawl stages so partial harvests are preserved even if one API slows down or errors.
- Query families now cover nanobubble core, ultrasound/imaging/contrast, payload/release, biomedical nanocarriers, and environmental/water/agriculture.
- Raw harvest size reached 49,140 rows before the final deduplicated merge.
- Final merged master inventory reached 49,182 deduplicated records.
- Current source mix: OpenAlex 40,836, PubMed 6,280, EuropePMC 1,178, CrossRef 548, SemanticScholar 250, ClinicalTrials.gov 10, plus 80 curated seed records.
- Current tier mix: Tier C 31,937, Tier A 9,028, Tier B 8,217.
- Document mix: 39,009 original studies, 10,163 reviews, 10 clinical trials.

## 2026-04-22 benchmark curation
- Stopped further corpus expansion and shifted to benchmark curation.
- Built a high-precision A1/A2 core subset with 7785 records.
- Built benchmark candidate sets of 500 and 1000 records.
- Built gold annotation sets v2 (200) and v3 (500).
- Added task-packaged files for structured extraction, numerical grounding, and evidence attribution.

## 2026-04-29 benchmark curation
- Stopped further corpus expansion and shifted to benchmark curation.
- Built a high-precision A1/A2 core subset with 8006 records.
- Built benchmark candidate sets of 500 and 1000 records.
- Built gold annotation sets v2 (200) and v3 (500).
- Added task-packaged files for structured extraction, numerical grounding, and evidence attribution.
