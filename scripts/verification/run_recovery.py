"""Gold-hard recovery and verification pipeline.

Steps (executed in order):

  1. Load May 2026 re-harvested warehouse + 40-record gold-hard tier.
  2. Parse identifiers from the gold-hard record_ids.
  3. Check warehouse containment by DOI / normalised title.
  4. For missing records, re-fetch by stable identifier.
  5. Cross-check the re-fetched abstract against the annotation-time
     abstract from the gold-hard file.
  6. Merge successful re-fetches into the warehouse and re-verify.
  7. Write verification artefacts under verification/.

This script does not change evaluation labels and never overwrites
the annotation-time abstract.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "verification"))

from _apis import (  # noqa: E402
    europepmc_by_doi,
    openalex_by_doi,
    openalex_extract,
    polite_sleep,
    pubmed_efetch,
    pubmed_esearch_doi,
    pubmed_idconv_doi_to_pmid,
)
from _id_parse import (  # noqa: E402
    normalize_doi,
    normalize_title,
    parse_record_id,
)


WAREHOUSE_PRE_MERGE = ROOT / "data" / "raw" / "master_inventory.pre-merge.csv"
WAREHOUSE_OUT = ROOT / "data" / "raw" / "master_inventory.csv"
GOLD_HARD = ROOT / "dataset_release" / "gold_hard" / "iaa_subset.csv"
VERIF_DIR = ROOT / "verification"

LOG = logging.getLogger("recovery")


# ---------------------------------------------------------------------------
# 1. Identifier parse table
# ---------------------------------------------------------------------------

def write_identifier_parse(gold: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for rid in gold["record_id"].tolist():
        p = parse_record_id(rid)
        rows.append({
            "record_id": rid,
            "source": p.source,
            "encoded_tail": p.encoded_tail,
            "doi_candidate_dash": p.doi_candidates[0] if len(p.doi_candidates) > 0 else "",
            "doi_candidate_dot": p.doi_candidates[1] if len(p.doi_candidates) > 1 else "",
            "primary_doi": p.primary_doi or "",
            "notes": p.notes,
        })
    df = pd.DataFrame(rows)
    out = VERIF_DIR / "gold_hard_identifier_parse.csv"
    df.to_csv(out, index=False)
    LOG.info("wrote %s (n=%d)", out, len(df))
    return df


# ---------------------------------------------------------------------------
# 2. Containment check
# ---------------------------------------------------------------------------

def _candidate_dois(parsed_row: dict) -> list[str]:
    cands = []
    for col in ("doi_candidate_dash", "doi_candidate_dot", "primary_doi"):
        v = parsed_row.get(col)
        if isinstance(v, str) and v:
            cands.append(v.lower())
    seen = set()
    out = []
    for c in cands:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def check_containment(
    parsed: pd.DataFrame, gold: pd.DataFrame, warehouse: pd.DataFrame, label: str,
) -> pd.DataFrame:
    wh_doi = warehouse["doi"].apply(normalize_doi)
    wh_doi_set = set(d for d in wh_doi.dropna().tolist() if d)
    wh_title_norm = warehouse["title"].apply(normalize_title)
    wh_title_to_idx: dict[str, int] = {}
    for idx, t in zip(warehouse.index, wh_title_norm):
        if t and t not in wh_title_to_idx:
            wh_title_to_idx[t] = idx

    rows = []
    for _, gr in gold.iterrows():
        rid = gr["record_id"]
        gold_title = gr.get("title", "") or ""
        gold_title_n = normalize_title(gold_title)
        prow = parsed[parsed["record_id"] == rid].iloc[0].to_dict() if (parsed["record_id"] == rid).any() else {}
        cands = _candidate_dois(prow)

        matched_by = ""
        matched_doi = ""
        matched_warehouse_record_id = ""
        for c in cands:
            if c in wh_doi_set:
                matched_by = "doi"
                matched_doi = c
                idx = warehouse.index[wh_doi == c][0]
                matched_warehouse_record_id = warehouse.at[idx, "record_id"]
                break
        if not matched_by and gold_title_n:
            if gold_title_n in wh_title_to_idx:
                matched_by = "normalized_title"
                idx = wh_title_to_idx[gold_title_n]
                matched_warehouse_record_id = warehouse.at[idx, "record_id"]
                d = wh_doi.iloc[warehouse.index.get_loc(idx)]
                matched_doi = d or ""

        rows.append({
            "record_id": rid,
            "source": prow.get("source", ""),
            "primary_doi": prow.get("primary_doi", ""),
            "doi_candidate_dash": prow.get("doi_candidate_dash", ""),
            "doi_candidate_dot": prow.get("doi_candidate_dot", ""),
            "title_first40": gold_title[:40],
            "matched": bool(matched_by),
            "matched_by": matched_by,
            "matched_doi": matched_doi,
            "matched_warehouse_record_id": matched_warehouse_record_id,
        })

    df = pd.DataFrame(rows)
    out = VERIF_DIR / f"gold_hard_containment_{label}.csv"
    df.to_csv(out, index=False)
    n_match = int(df["matched"].sum())
    LOG.info("containment %s: %d/%d matched -> %s", label, n_match, len(df), out)
    return df


# ---------------------------------------------------------------------------
# 3. Refetch missing
# ---------------------------------------------------------------------------

def refetch_missing(
    contain: pd.DataFrame, parsed: pd.DataFrame, gold: pd.DataFrame, *, do_network: bool = True,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """For records flagged missing, walk source-API direct lookups by DOI.

    Returns (log_df, fetched_metadata_by_record_id).
    """
    rows = []
    fetched: dict[str, dict] = {}

    missing = contain[~contain["matched"]]
    LOG.info("refetch: %d missing records", len(missing))

    for _, mr in missing.iterrows():
        rid = mr["record_id"]
        prow = parsed[parsed["record_id"] == rid].iloc[0].to_dict()
        cands = _candidate_dois(prow)
        source = mr["source"]
        log_row = {
            "record_id": rid,
            "source": source,
            "candidates_tried": "|".join(cands),
            "resolved_doi": "",
            "resolved_pmid": "",
            "resolved_openalex_id": "",
            "resolved_europepmc_id": "",
            "fetched_via": "",
            "title_first40": "",
            "ok": False,
            "error": "",
        }
        if not do_network:
            log_row["error"] = "network disabled"
            rows.append(log_row)
            continue

        ok = False
        # We try multiple source APIs for each missing record because the
        # encoded record_id source slug ("PubMed", "OpenAlex", "EuropePMC")
        # only tells us where it was originally drawn from; it does not
        # restrict which API can resolve the DOI.
        order = [source] + [s for s in ("PubMed", "OpenAlex", "EuropePMC") if s != source]
        for api in order:
            for cand in cands:
                meta = None
                if api == "OpenAlex":
                    work = openalex_by_doi(cand)
                    polite_sleep()
                    if work:
                        meta = openalex_extract(work)
                        if meta:
                            meta["source_api_used"] = "OpenAlex"
                elif api == "PubMed":
                    pmid = pubmed_idconv_doi_to_pmid(cand) or pubmed_esearch_doi(cand)
                    polite_sleep()
                    if pmid:
                        m = pubmed_efetch(pmid)
                        polite_sleep()
                        if m:
                            meta = m
                            meta["source_api_used"] = "PubMed"
                elif api == "EuropePMC":
                    m = europepmc_by_doi(cand)
                    polite_sleep()
                    if m:
                        meta = m
                        meta["source_api_used"] = "EuropePMC"
                if meta and meta.get("title"):
                    log_row["resolved_doi"] = meta.get("doi", "") or cand
                    log_row["resolved_pmid"] = meta.get("pmid", "") or ""
                    log_row["resolved_openalex_id"] = meta.get("openalex_id", "") or ""
                    log_row["resolved_europepmc_id"] = meta.get("europepmc_id", "") or ""
                    log_row["fetched_via"] = f"{api}:doi:{cand}"
                    log_row["title_first40"] = (meta.get("title") or "")[:40]
                    log_row["ok"] = True
                    fetched[rid] = meta
                    ok = True
                    break
            if ok:
                break
        if not ok:
            log_row["error"] = "all candidates exhausted"
        rows.append(log_row)

    df = pd.DataFrame(rows)
    out = VERIF_DIR / "gold_hard_refetch_log.csv"
    df.to_csv(out, index=False)
    LOG.info("refetch log: %d/%d success -> %s",
             int(df["ok"].sum()) if len(df) else 0, len(df), out)
    return df, fetched


# ---------------------------------------------------------------------------
# 4. Abstract cross-check
# ---------------------------------------------------------------------------

def _try_demojibake(s: str) -> str:
    """Repair UTF-8-as-Latin1 mojibake.

    The gold-hard CSV was saved through a cp1252/Latin-1 round-trip, so
    UTF-8 byte sequences such as 0xCE 0xBC (for the glyph µ 'mu') were
    stored as two cp1252 characters ('Î¼'). Round-tripping the
    string back through Latin-1 -> UTF-8 recovers the original glyph.
    Falls back to the input if the round-trip raises.
    """
    if not isinstance(s, str) or not s:
        return s
    try:
        return s.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _norm_text(s: str) -> str:
    """Demojibake then NFKC + whitespace-collapse + lowercase."""
    if not isinstance(s, str):
        return ""
    s = _try_demojibake(s)
    s = unicodedata.normalize("NFKC", s)
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("C"))
    s = s.replace(" ", " ").replace("​", "").replace(" ", " ")
    s = " ".join(s.split())
    return s.strip().lower()


def cross_check_abstracts(
    fetched: dict[str, dict],
    gold: pd.DataFrame,
    contain_before: pd.DataFrame,
    warehouse: pd.DataFrame,
) -> pd.DataFrame:
    """Compare the source-API abstract against the gold-hard annotation-time
    abstract for all 40 records.

    For records already present in the May 2026 re-harvest, the comparison
    target is the warehouse abstract (from the May 2026 fetch). For the
    14 records that were re-fetched, it is the freshly re-fetched abstract.
    Either way, we report whether the source-side text *today* still
    matches what the annotator read at annotation time.
    """
    rows = []
    gold_by_rid = {r["record_id"]: r for _, r in gold.iterrows()}
    contain_by_rid = {r["record_id"]: r for _, r in contain_before.iterrows()}

    wh_by_record = {r["record_id"]: r for _, r in warehouse.iterrows()}

    for _, gr in gold.iterrows():
        rid = gr["record_id"]
        gh_abs = gr.get("abstract_or_summary", "") or ""

        if rid in fetched:
            re_abs = (fetched[rid].get("abstract_or_summary") or "")
            origin = "refetched"
        else:
            cb = contain_by_rid.get(rid)
            wh_rid = cb["matched_warehouse_record_id"] if cb is not None else ""
            wh_row = wh_by_record.get(wh_rid)
            re_abs = (wh_row["abstract_or_summary"] if wh_row is not None and isinstance(wh_row.get("abstract_or_summary"), str) else "") or ""
            origin = "warehouse_existing"

        if gh_abs and re_abs and gh_abs == re_abs:
            status = "verbatim_match"
        elif gh_abs and re_abs and _norm_text(gh_abs) == _norm_text(re_abs):
            status = "normalized_match"
        elif not re_abs:
            status = "refetch_failed"
        elif not gh_abs:
            status = "no_gold_abstract"
        else:
            status = "source_side_revision_or_mismatch"

        rows.append({
            "record_id": rid,
            "origin": origin,
            "status": status,
            "gold_abstract_len": len(gh_abs) if isinstance(gh_abs, str) else 0,
            "refetched_abstract_len": len(re_abs),
            "gold_first120": (gh_abs[:120] if isinstance(gh_abs, str) else ""),
            "refetched_first120": re_abs[:120],
        })

    cols = ["record_id", "origin", "status", "gold_abstract_len",
            "refetched_abstract_len", "gold_first120", "refetched_first120"]
    df = pd.DataFrame(rows, columns=cols)
    out = VERIF_DIR / "gold_hard_abstract_crosscheck.csv"
    df.to_csv(out, index=False)
    LOG.info("abstract cross-check: %s -> %s",
             df["status"].value_counts().to_dict() if len(df) else {}, out)

    # Save raw mismatches as a side file for manual inspection.
    mismatches = df[df["status"] == "source_side_revision_or_mismatch"] if len(df) else df
    if len(mismatches):
        (VERIF_DIR / "abstract_mismatches.txt").write_text(
            "\n\n".join(
                f"== {r['record_id']} ==\nGOLD: {r['gold_first120']}\nFETCH: {r['refetched_first120']}"
                for _, r in mismatches.iterrows()
            ),
            encoding="utf-8",
        )
    return df


# ---------------------------------------------------------------------------
# 5. Merge into warehouse
# ---------------------------------------------------------------------------

WAREHOUSE_COLS = [
    "record_id", "source_api", "source_id", "title", "authors", "year",
    "journal_or_venue", "doi", "pmid", "pmcid", "url", "abstract_or_summary",
    "citation_count", "document_type", "query_family",
]


def _row_for_warehouse(rid: str, meta: dict, gold_row: pd.Series) -> dict:
    """Build a warehouse row for a re-fetched gold-hard record.

    The annotation-time abstract from the gold-hard file is used as
    the canonical `abstract_or_summary` so baseline reproducibility
    is preserved. Re-fetched abstracts are not silently substituted
    even when they differ.
    """
    gh_abs = gold_row.get("abstract_or_summary", "") if hasattr(gold_row, "get") else ""
    src = meta.get("source_api_used") or ""
    src_id = (
        meta.get("openalex_id") or meta.get("pmid") or meta.get("europepmc_id") or ""
    )
    return {
        "record_id": rid,  # preserve gold-hard record_id verbatim
        "source_api": src,
        "source_id": src_id or "",
        "title": meta.get("title") or gold_row.get("title", ""),
        "authors": "",
        "year": meta.get("year") or gold_row.get("year") or "",
        "journal_or_venue": meta.get("journal_or_venue") or gold_row.get("journal_or_venue", ""),
        "doi": (meta.get("doi") or "").lower() if meta.get("doi") else "",
        "pmid": meta.get("pmid") or "",
        "pmcid": meta.get("pmcid") or "",
        "url": meta.get("url") or "",
        "abstract_or_summary": gh_abs or meta.get("abstract_or_summary", ""),
        "citation_count": "",
        "document_type": meta.get("document_type") or gold_row.get("document_type", ""),
        "query_family": "gold_hard_refetch",
    }


def merge_warehouse(
    warehouse: pd.DataFrame,
    fetched: dict[str, dict],
    gold: pd.DataFrame,
    contain: pd.DataFrame,
) -> pd.DataFrame:
    """Append re-fetched rows to warehouse, dedupe by DOI/PMID/title/URL."""
    if not fetched:
        return warehouse

    gold_by_rid = {r["record_id"]: r for _, r in gold.iterrows()}
    new_rows = []
    for rid, meta in fetched.items():
        gh = gold_by_rid[rid]
        new_rows.append(_row_for_warehouse(rid, meta, gh))

    new_df = pd.DataFrame(new_rows, columns=WAREHOUSE_COLS)
    merged = pd.concat([warehouse, new_df], ignore_index=True)

    # Dedupe: keep first occurrence per identifier so existing warehouse
    # rows take precedence and the gold-hard record_id is preserved when
    # it is the only row carrying that DOI.
    merged["_doi_key"] = merged["doi"].apply(normalize_doi)
    merged["_title_key"] = merged["title"].apply(normalize_title)

    before = len(merged)
    # By DOI
    mask_doi = merged["_doi_key"].notna() & (merged["_doi_key"] != "")
    sub = merged[mask_doi].drop_duplicates(subset=["_doi_key"], keep="first")
    merged = pd.concat([sub, merged[~mask_doi]], ignore_index=True)
    # By PMID
    mask_pmid = merged["pmid"].astype(str).str.strip().ne("") & merged["pmid"].notna()
    sub = merged[mask_pmid].drop_duplicates(subset=["pmid"], keep="first")
    merged = pd.concat([sub, merged[~mask_pmid]], ignore_index=True)
    # By PMCID
    mask_pmcid = merged["pmcid"].astype(str).str.strip().ne("") & merged["pmcid"].notna()
    sub = merged[mask_pmcid].drop_duplicates(subset=["pmcid"], keep="first")
    merged = pd.concat([sub, merged[~mask_pmcid]], ignore_index=True)
    # By normalised title
    mask_title = merged["_title_key"].astype(str).str.len() > 0
    sub = merged[mask_title].drop_duplicates(subset=["_title_key"], keep="first")
    merged = pd.concat([sub, merged[~mask_title]], ignore_index=True)
    # By URL
    mask_url = merged["url"].astype(str).str.strip().ne("") & merged["url"].notna()
    sub = merged[mask_url].drop_duplicates(subset=["url"], keep="first")
    merged = pd.concat([sub, merged[~mask_url]], ignore_index=True)
    # Final pass on record_id
    merged = merged.drop_duplicates(subset=["record_id"], keep="first").reset_index(drop=True)

    merged = merged.drop(columns=["_doi_key", "_title_key"], errors="ignore")
    LOG.info("merge: %d -> %d records (added %d gold-hard re-fetches)",
             len(warehouse), len(merged), len(fetched))
    return merged[WAREHOUSE_COLS]


# ---------------------------------------------------------------------------
# 6. Main orchestrator
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-network", action="store_true",
                        help="Skip API calls. Useful for dry runs.")
    parser.add_argument("--write-warehouse", action="store_true",
                        help="Overwrite the released warehouse with the merged version.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    VERIF_DIR.mkdir(parents=True, exist_ok=True)

    LOG.info("loading gold-hard: %s", GOLD_HARD)
    gold = pd.read_csv(GOLD_HARD, low_memory=False)
    if len(gold) != 40:
        LOG.warning("gold-hard has %d rows (expected 40)", len(gold))

    LOG.info("loading warehouse (pre-merge): %s", WAREHOUSE_PRE_MERGE)
    warehouse = pd.read_csv(WAREHOUSE_PRE_MERGE, low_memory=False)

    parsed = write_identifier_parse(gold)

    contain_before = check_containment(parsed, gold, warehouse, "before_merge")

    refetch_log, fetched = refetch_missing(
        contain_before, parsed, gold, do_network=not args.no_network,
    )
    crosscheck = cross_check_abstracts(fetched, gold, contain_before, warehouse)

    merged = merge_warehouse(warehouse, fetched, gold, contain_before)
    contain_after = check_containment(parsed, gold, merged, "after_merge")

    if args.write_warehouse:
        merged.to_csv(WAREHOUSE_OUT, index=False)
        LOG.info("wrote merged warehouse -> %s", WAREHOUSE_OUT)

    # ---- summary.json ----
    n_gold = len(gold)
    found_before = int(contain_before["matched"].sum())
    missing_before = n_gold - found_before
    refetch_success = int(refetch_log["ok"].sum()) if len(refetch_log) else 0
    refetch_failed = int((~refetch_log["ok"]).sum()) if len(refetch_log) else 0
    contained_after = int(contain_after["matched"].sum())

    counts = crosscheck["status"].value_counts().to_dict() if len(crosscheck) else {}
    verbatim = int(counts.get("verbatim_match", 0))
    normalized = int(counts.get("normalized_match", 0))
    mismatch = int(counts.get("source_side_revision_or_mismatch", 0))
    refetch_failed_check = int(counts.get("refetch_failed", 0))

    failed_ids = refetch_log[~refetch_log["ok"]]["record_id"].tolist() if len(refetch_log) else []
    mismatch_ids = crosscheck[crosscheck["status"] == "source_side_revision_or_mismatch"]["record_id"].tolist() if len(crosscheck) else []

    summary = {
        "original_claimed_warehouse_count": 52519,
        "current_reharvest_count_before_merge": int(len(warehouse)),
        "final_warehouse_count_after_merge": int(len(merged)),
        "gold_hard_total": int(n_gold),
        "found_before_merge": found_before,
        "missing_before_merge": missing_before,
        "refetch_success_count": refetch_success,
        "refetch_failed_count": refetch_failed,
        "contained_after_merge_count": contained_after,
        "verbatim_match_count": verbatim,
        "normalized_match_count": normalized,
        "mismatch_or_revision_count": mismatch,
        "abstract_refetch_empty_count": refetch_failed_check,
        "failed_ids": failed_ids,
        "mismatch_ids": mismatch_ids,
        "warehouse_path_in": str(WAREHOUSE_PRE_MERGE.relative_to(ROOT)),
        "warehouse_path_out": str(WAREHOUSE_OUT.relative_to(ROOT)) if args.write_warehouse else None,
        "gold_hard_path": str(GOLD_HARD.relative_to(ROOT)),
        "network_used": (not args.no_network),
    }

    with (VERIF_DIR / "summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    LOG.info("wrote summary.json")

    # ---- console final report ----
    print()
    print("=" * 72)
    print("  Gold-hard recovery: final report")
    print("=" * 72)
    print(f"  Original (claimed) warehouse size : {summary['original_claimed_warehouse_count']}")
    print(f"  May 2026 re-harvest (before merge): {summary['current_reharvest_count_before_merge']}")
    print(f"  Warehouse after merge              : {summary['final_warehouse_count_after_merge']}")
    print()
    print(f"  Gold-hard total                    : {summary['gold_hard_total']}")
    print(f"  Already in warehouse before merge  : {summary['found_before_merge']}")
    print(f"  Missing before merge               : {summary['missing_before_merge']}")
    print(f"  Re-fetched successfully            : {summary['refetch_success_count']}")
    print(f"  Re-fetch failures                  : {summary['refetch_failed_count']}")
    print(f"  Contained after merge              : {summary['contained_after_merge_count']}/{summary['gold_hard_total']}")
    print()
    print("  Abstract cross-check (X/Y/Z):")
    print(f"    X  verbatim matches                              = {verbatim}")
    print(f"    Y  matches after Unicode/whitespace normalization = {normalized}")
    print(f"    Z  source-side revisions or mismatches           = {mismatch}")
    if failed_ids:
        print()
        print("  Failed re-fetches needing manual attention:")
        for rid in failed_ids:
            print(f"    - {rid}")
    if mismatch_ids:
        print()
        print("  Records with abstract differences vs annotation-time:")
        for rid in mismatch_ids:
            print(f"    - {rid}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
