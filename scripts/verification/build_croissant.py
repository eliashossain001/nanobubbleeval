"""Build a valid Croissant 1.1 metadata file for the NanoBubbleEval v1.0 release.

Produces ``dataset_release/metadata/croissant.json`` that:
  * describes only artifacts actually shipped on HuggingFace v1.0,
  * carries SHA-256 + content size for every FileObject,
  * defines a GoldHardRecord RecordSet whose Field entries cite the
    gold-hard CSV via cr:source (required by the validator), and
  * carries the 14 RAI fields required by the NeurIPS ED hosting guidelines
    plus a ``citeAs`` recommendation.

Run:
    python3 scripts/verification/build_croissant.py
    mlcroissant validate --jsonld dataset_release/metadata/croissant.json
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "dataset_release" / "metadata" / "croissant.json"

HF_BASE = "https://huggingface.co/datasets/EliasHossain/nanobubbleeval/resolve/main"
GH_BASE = "https://github.com/eliashossain001/nanobubbleeval"


def _sha256(path: Path) -> tuple[int, str]:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return path.stat().st_size, h.hexdigest()


def _file_object(rel_release: str, rel_local: str, ident: str, name: str,
                 description: str, encoding: str) -> dict:
    """rel_release: path inside dataset_release/ (mirrors HF layout).
    rel_local: path on disk relative to project root (may differ from rel_release
    for verification/* which lives at top-level locally)."""
    p = ROOT / rel_local
    if not p.is_file():
        raise FileNotFoundError(p)
    size, digest = _sha256(p)
    return {
        "@type": "cr:FileObject",
        "@id": ident,
        "name": name,
        "description": description,
        "contentUrl": f"{HF_BASE}/{rel_release}",
        "encodingFormat": encoding,
        "sha256": digest,
        "contentSize": str(size),
    }


def _field(record_set_id: str, column: str, description: str,
           data_type: str, file_obj_id: str = "gold-hard-tier") -> dict:
    return {
        "@type": "cr:Field",
        "@id": f"{record_set_id}/{column}",
        "name": column,
        "description": description,
        "dataType": data_type,
        "source": {
            "fileObject": {"@id": file_obj_id},
            "extract": {"column": column},
        },
    }


def main() -> int:
    distribution: list[dict] = []

    # 1. v1.0 released artifacts (paths inside dataset_release/ mirror HF layout)
    distribution.append(_file_object(
        rel_release="warehouse/master_inventory.csv",
        rel_local="dataset_release/warehouse/master_inventory.csv",
        ident="warehouse-manifest",
        name="master_inventory.csv",
        description="51,566-record deduplicated warehouse manifest (2026-05 snapshot, post-recovery).",
        encoding="text/csv",
    ))
    distribution.append(_file_object(
        rel_release="gold_hard/iaa_subset.csv",
        rel_local="dataset_release/gold_hard/iaa_subset.csv",
        ident="gold-hard-tier",
        name="iaa_subset.csv",
        description="40-record gold-hard seed evaluation tier with first-annotator labels under the 18-field schema.",
        encoding="text/csv",
    ))
    for fname, ident, label in [
        ("regex-v1.csv",            "predictions-b1", "B1 regex baseline"),
        ("biobert-squadv2.csv",     "predictions-b2", "B2 BioBERT-SQuAD-v2 baseline"),
        ("qwen25-7b-instruct.csv",  "predictions-b3", "B3 Qwen2.5-7B-Instruct baseline"),
    ]:
        distribution.append(_file_object(
            rel_release=f"predictions/{fname}",
            rel_local=f"dataset_release/predictions/{fname}",
            ident=ident,
            name=fname,
            description=f"{label} predictions on the gold-hard tier.",
            encoding="text/csv",
        ))
    distribution.append(_file_object(
        rel_release="splits/leakage_report.md",
        rel_local="dataset_release/splits/leakage_report.md",
        ident="leakage-report",
        name="leakage_report.md",
        description="Disjointness audit confirming no record_id overlap across splits.",
        encoding="text/markdown",
    ))
    distribution.append(_file_object(
        rel_release="splits/slice_summary.md",
        rel_local="dataset_release/splits/slice_summary.md",
        ident="slice-summary",
        name="slice_summary.md",
        description="Per-slice membership counts on the gold-hard tier.",
        encoding="text/markdown",
    ))
    distribution.append(_file_object(
        rel_release="metadata/extraction_schema.json",
        rel_local="dataset_release/metadata/extraction_schema.json",
        ident="schema-spec",
        name="extraction_schema.json",
        description="18-field schema specification with normalisation rules and the NOT_REPORTED missing-value sentinel.",
        encoding="application/json",
    ))
    distribution.append(_file_object(
        rel_release="metadata/data_quality_report.md",
        rel_local="dataset_release/metadata/data_quality_report.md",
        ident="data-quality-report",
        name="data_quality_report.md",
        description="Warehouse-level QC summary (deduplication order, missing-field rates).",
        encoding="text/markdown",
    ))
    # Verification / Branch B recovery audit
    for fname, ident, desc in [
        ("gold_hard_identifier_parse.csv",
         "verif-id-parse",
         "DOI candidates parsed from each gold-hard record_id."),
        ("gold_hard_containment_before_merge.csv",
         "verif-containment-before",
         "Per-record match status against the 2026-05 re-harvest before merge."),
        ("gold_hard_refetch_log.csv",
         "verif-refetch-log",
         "Source API + DOI candidate that resolved each of the 14 missing records."),
        ("gold_hard_abstract_crosscheck.csv",
         "verif-abstract-crosscheck",
         "Per-record abstract cross-check classified as verbatim, normalised, or source-side revision."),
        ("gold_hard_containment_after_merge.csv",
         "verif-containment-after",
         "Post-merge containment confirming all 40 gold-hard records resolve into the released warehouse."),
        ("summary.json",
         "verif-summary",
         "Machine-readable summary of all recovery counts (Branch B)."),
        ("abstract_mismatches.txt",
         "verif-abstract-mismatches",
         "First 120 chars of each abstract mismatch flagged as a source-side editorial revision."),
    ]:
        encoding = (
            "application/json" if fname.endswith(".json")
            else "text/plain" if fname.endswith(".txt")
            else "text/csv"
        )
        distribution.append(_file_object(
            rel_release=f"verification/{fname}",
            rel_local=f"verification/{fname}",
            ident=ident,
            name=fname,
            description=desc,
            encoding=encoding,
        ))

    # 2. RecordSet over the gold-hard tier (the only released annotation file)
    record_set_id = "gold-hard-records"
    fields = [
        _field(record_set_id, "record_id",
               "Unique record identifier; encodes source API and DOI.", "sc:Text"),
        _field(record_set_id, "title", "Paper or trial title.", "sc:Text"),
        _field(record_set_id, "year", "Publication year.", "sc:Integer"),
        _field(record_set_id, "abstract_or_summary",
               "Abstract text used as the model input (annotation-time copy).", "sc:Text"),
        _field(record_set_id, "document_type",
               "One of {original, review, clinical_trial}.", "sc:Text"),
        _field(record_set_id, "nanobubble_vs_nanoparticle",
               "Slice label: nanobubble, nanoparticle, micro/nanobubble, or microbubble-adjacent.", "sc:Text"),
        _field(record_set_id, "size_value",
               "Particle / bubble diameter (numeric headline). Canonical unit: nm. NOT_REPORTED when absent.", "sc:Text"),
        _field(record_set_id, "zeta_potential_value",
               "Surface charge (numeric headline). Canonical unit: mV.", "sc:Text"),
        _field(record_set_id, "stability_value",
               "Persistence / lifetime (numeric headline). Canonical unit: h.", "sc:Text"),
        _field(record_set_id, "payload_value",
               "Drug, dye, gene, gas, or cargo loaded (text headline). Free text.", "sc:Text"),
        _field(record_set_id, "loading_efficiency_value",
               "Encapsulation / loading percentage (numeric headline). Canonical unit: %.", "sc:Text"),
        _field(record_set_id, "release_profile_value",
               "Release behaviour (text headline). Free text.", "sc:Text"),
    ]
    record_set = {
        "@type": "cr:RecordSet",
        "@id": record_set_id,
        "name": "GoldHardRecord",
        "description": "One record per entry in the 40-record gold-hard seed evaluation tier. Each row carries metadata (title, year, document type, nanobubble label) and the six headline fields (value/unit/evidence-quote triples).",
        "field": fields,
    }

    croissant = {
        "@context": {
            "@language": "en",
            "@vocab": "https://schema.org/",
            "citeAs": "cr:citeAs",
            "column": "cr:column",
            "conformsTo": "dct:conformsTo",
            "cr": "http://mlcommons.org/croissant/",
            "rai": "http://mlcommons.org/croissant/RAI/",
            "data": {"@id": "cr:data", "@type": "@json"},
            "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
            "dct": "http://purl.org/dc/terms/",
            "examples": {"@id": "cr:examples", "@type": "@json"},
            "extract": "cr:extract",
            "field": "cr:field",
            "fileProperty": "cr:fileProperty",
            "fileObject": "cr:fileObject",
            "fileSet": "cr:fileSet",
            "format": "cr:format",
            "includes": "cr:includes",
            "isLiveDataset": "cr:isLiveDataset",
            "jsonPath": "cr:jsonPath",
            "key": "cr:key",
            "md5": "cr:md5",
            "parentField": "cr:parentField",
            "path": "cr:path",
            "recordSet": "cr:recordSet",
            "references": "cr:references",
            "regex": "cr:regex",
            "repeated": "cr:repeated",
            "replace": "cr:replace",
            "sc": "https://schema.org/",
            "separator": "cr:separator",
            "source": "cr:source",
            "subField": "cr:subField",
            "transform": "cr:transform",
        },
        "@type": "sc:Dataset",
        "name": "NanoBubbleEval-v1.0",
        "description": (
            "An abstract-level structured benchmark and reproducible evaluation scaffold for "
            "nanobubble and nanocarrier extraction. v1.0 is positioned as a seed benchmark: "
            "it pairs a 51,566-record deduplicated warehouse with a 40-record gold-hard seed "
            "evaluation tier annotated under an 18-field schema, together with the harvest-to-"
            "evaluation pipeline that produced them. The benchmark operationalises three "
            "failure modes of scientific information extraction (schema-fill hallucination, "
            "unit drift, cite-hallucination) as decomposed metrics over three task views "
            "projected from a single annotation pass."
        ),
        "conformsTo": "http://mlcommons.org/croissant/1.1",
        "version": "1.0.0",
        "datePublished": "2026-05-02",
        "license": "https://creativecommons.org/licenses/by-nc/4.0/",
        "url": "https://huggingface.co/datasets/EliasHossain/nanobubbleeval",
        "sameAs": GH_BASE,
        "citeAs": (
            "Hossain, E. (2026). NanoBubbleEval: An Evidence-Grounded Benchmark for Schema "
            "Extraction, Numerical Grounding, and Evidence Attribution in the Nanobubble and "
            "Nanocarrier Literature. NeurIPS 2026 Datasets and Benchmarks Track (under review). "
            "https://huggingface.co/datasets/EliasHossain/nanobubbleeval"
        ),
        "keywords": [
            "scientific information extraction",
            "schema-constrained extraction",
            "numerical grounding",
            "evidence attribution",
            "abstention-calibrated F1",
            "cite-hallucination",
            "nanobubble",
            "nanocarrier",
            "benchmark",
        ],
        "creator": {
            "@type": "Person",
            "name": "Elias Hossain",
            "sameAs": "https://github.com/eliashossain001",
        },
        "publisher": {
            "@type": "Person",
            "name": "Elias Hossain",
        },
        # ---- RAI fields (NeurIPS ED hosting guidelines) ----
        "rai:dataCollection": (
            "Records were harvested from public scholarly APIs (PubMed/NCBI Entrez, Europe PMC, "
            "OpenAlex, CrossRef, Semantic Scholar, ClinicalTrials.gov v2) under five query "
            "families covering nanobubble core terminology, ultrasound and contrast imaging, "
            "delivery and release, biomedical nanocarriers, and environmental/agricultural "
            "applications. Deduplication is strictly ordered: DOI, then PMID/PMCID, then "
            "normalised title, then URL."
        ),
        "rai:dataCollectionType": "Public scholarly metadata APIs",
        "rai:dataCollectionMissingData": (
            "Some records lack abstracts (18.3% of the v1.0 warehouse). The high-precision core "
            "and the gold pool (scheduled for v1.1) are filtered to require an abstract."
        ),
        "rai:dataCollectionRawData": (
            "The raw API responses are not redistributed; the release ships the deduplicated "
            "warehouse manifest containing only fields permitted under the source-API terms of "
            "use."
        ),
        "rai:dataPreprocessingProtocol": (
            "Records are normalised to UTF-8, deduplicated in the order specified above, "
            "assigned tier labels A/B/C by lexical proximity to nanobubble-core vocabulary "
            "(Tier A is split A1/A2), and sampled into a 1,000-record balanced candidate "
            "pool. The 500-record gold pool is the top-ranked half of the candidate pool by an "
            "extraction-priority score; the gold-hard tier (n=40) is sampled with stratification "
            "on (nb_label, document_type) and pinned to the test split."
        ),
        "rai:dataAnnotationProtocol": (
            "Annotations on the gold-hard tier are produced by a professional biomedical "
            "annotator under a blind, abstract-only protocol. Each annotation records the value, "
            "the canonical unit (for numeric fields), and a verbatim evidence quote substring of "
            "the abstract. The NOT_REPORTED sentinel is used when the abstract does not state a "
            "property. v1.0 ships single-annotator-validated labels under a dual-annotator "
            "protocol; full dual annotation is scheduled for v1.1."
        ),
        "rai:dataAnnotationAnalysis": (
            "Inter-annotator agreement statistics (Cohen's kappa on NOT_REPORTED-versus-emit, "
            "character-set span IoU on emit-emit pairs, unit-normalised numerical match on "
            "numeric fields) are scheduled for the v1.1 release once the second-annotator pass "
            "completes. v1.0 ships a recovery and provenance audit (verification/) that "
            "documents an abstract cross-check across all 40 gold-hard records (14 verbatim, "
            "19 Unicode/whitespace-normalised, 7 source-side editorial revisions)."
        ),
        "rai:dataAnnotationPlatform": (
            "Internal annotation tooling; no third-party crowdsourcing platform was used."
        ),
        "rai:dataReleaseMaintenancePlan": (
            "The benchmark is versioned semantically. v1.0 is the abstract-only release "
            "shipping the warehouse, the 40-record gold-hard tier, three baseline-prediction "
            "files, and the recovery audit. v1.1 is scheduled to add the 8,006-record "
            "high-precision core, the 500-record gold pool, the 460-record gold-lite tier, "
            "the three task-view CSVs, the deterministic splits.json, an open-access full-text "
            "gold subset, finalised dual-annotator adjudication, and a same-family-larger "
            "ceiling baseline plus a retrieval-augmented variant."
        ),
        "rai:dataLimitation": (
            "v1.0 evaluates abstract-derived extraction only; properties stated in tables, "
            "methods, or supplementary material are out of scope. The schema and metric design "
            "generalise but the lexical patterns and unit-normalisation tables are calibrated "
            "to the nanobubble domain. The gold-hard tier is single-annotator-validated under a "
            "dual-annotator protocol; full dual-annotator IAA ships in v1.1. n=40 is sufficient "
            "for seed validation but not for definitive model ranking."
        ),
        "rai:dataSocialImpact": (
            "The benchmark exposes schema-fill hallucination, unit drift, and cite-hallucination "
            "as distinct failure modes in scientific information extraction, thereby guiding "
            "the development of more honest extraction systems. A foreseeable misuse is "
            "over-reliance on extracted property values for downstream scientific decisions; "
            "the abstention and evidence-provenance signals in the metric suite are designed to "
            "mitigate this."
        ),
        "rai:dataBiases": (
            "The warehouse is dominated by English-language abstracts indexed by the source "
            "APIs; this skews the benchmark towards English-language scientific literature. The "
            "cross-disciplinary balance reflects the relative volume of nanobubble research in "
            "biomedical, environmental, and fundamental physics venues."
        ),
        "rai:dataUseCases": (
            "Benchmarking schema-constrained extraction systems; benchmarking biomedical "
            "extractive-QA models; benchmarking instruction-tuned LLMs on numerical grounding "
            "under unit normalisation; evaluating evidence-attribution faithfulness in "
            "scientific NLP."
        ),
        "rai:personalSensitiveInformation": (
            "None. The benchmark contains structured metadata and abstract-derived annotations "
            "only; it does not contain identifiable medical records, patient-level information, "
            "or any personally identifiable data."
        ),
        "distribution": distribution,
        "recordSet": [record_set],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        json.dump(croissant, f, indent=2, ensure_ascii=False)
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
