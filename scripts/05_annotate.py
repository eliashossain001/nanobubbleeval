"""Stage 5: Interactive blind annotation helper for the gold-hard tier.

Reads a 40-record IAA subset, presents one record at a time, prompts for
the six headline fields, and writes back to
``annotation/received/iaa_subset_<initials>.csv``.

Design principles
-----------------
* **Blind protocol.** The script does NOT load any other annotator's labels.
  Pre-existing files at the output path will be reloaded as the user's own
  in-progress annotations only.
* **Autosave per record.** The output file is rewritten after every record
  so a crash, Ctrl-C, or laptop sleep loses at most one record's typing.
* **Resume.** If the output file already exists, the helper skips records
  that are fully populated (every cell either filled or NR), and resumes
  on the first incomplete record.
* **Verbatim evidence enforcement.** Evidence quotes are checked against
  the abstract; non-substring quotes are rejected with a re-prompt.
* **NR by default.** Empty input on a value cell is recorded as NOT_REPORTED.

Run
---
    python3 scripts/05_annotate.py <your-initials>

Example: ``python3 scripts/05_annotate.py elias`` opens
``annotation/packet/iaa_subset.csv`` and writes
``annotation/received/iaa_subset_elias.csv``.

After both annotators are done, run::
    python3 scripts/03_reconcile.py \\
        annotation/received/iaa_subset_elias.csv \\
        annotation/received/iaa_subset_<other>.csv
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pandas as pd

from nanobubbleval.paths import paths
from nanobubbleval.schema import HEADLINE_FIELDS, NR


# ---------------------------------------------------------------------------
# Field prompts
# ---------------------------------------------------------------------------

FIELD_HELP = {
    "size":               ("Particle / bubble diameter",        "nm"),
    "zeta_potential":     ("Surface charge",                     "mV"),
    "stability":          ("Persistence / lifetime / shelf life","h"),
    "payload":            ("Drug, dye, gene, gas, or cargo",     ""),
    "loading_efficiency": ("Encapsulation / loading percentage", "%"),
    "release_profile":    ("Release behaviour (text)",           ""),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wrap(text: str, width: int = 88, indent: str = "  ") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent, subsequent_indent=indent)


def _is_complete_row(row: pd.Series) -> bool:
    """A row is 'complete' if every headline field has a non-empty value cell.
    The user can record NR explicitly; an empty cell is treated as 'not done'."""
    for f in HEADLINE_FIELDS:
        v = str(row.get(f"{f}_value", "")).strip()
        if not v:
            return False
    return True


def _prompt_field(field: str, abstract: str) -> tuple[str, str, str]:
    """Prompt the user for one field and return (value, unit, evidence_quote)."""
    desc, canon_unit = FIELD_HELP[field]
    print()
    print(f"  ── {field}  ──  {desc}" + (f"  [canonical unit: {canon_unit}]" if canon_unit else ""))

    value = input(f"     value ({field}, ENTER for NOT_REPORTED): ").strip()
    if not value:
        return NR, NR, NR

    if canon_unit:
        unit = input(f"     unit  ({field}, default '{canon_unit}', ENTER to accept): ").strip() or canon_unit
    else:
        unit = ""

    while True:
        quote = input(f"     evidence quote (verbatim substring; '?' to skip with NR): ").strip()
        if quote == "?":
            return NR, NR, NR
        if not quote:
            print("     [warn] evidence quote required; type '?' to abandon this field.")
            continue
        if quote not in abstract:
            print("     [reject] not a verbatim substring of the abstract. Try again or type '?'.")
            continue
        return value, unit, quote


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def annotate(initials: str) -> int:
    in_path = paths.iaa_subset
    out_path = paths.iaa_received / f"iaa_subset_{initials}.csv"

    if not in_path.is_file():
        print(f"FATAL: input file not found at {in_path}")
        return 1
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Load input. Resume from existing output if present. ---
    if out_path.is_file():
        df = pd.read_csv(out_path, low_memory=False)
        print(f"Resuming from existing {out_path.name}")
    else:
        df = pd.read_csv(in_path, low_memory=False)
        for f in HEADLINE_FIELDS:
            for s in ("value", "unit", "evidence_quote"):
                if f"{f}_{s}" not in df.columns:
                    df[f"{f}_{s}"] = ""
        if "ambiguity_flag" not in df.columns:
            df["ambiguity_flag"] = ""
        if "annotator_notes" not in df.columns:
            df["annotator_notes"] = ""
        print(f"Starting fresh from {in_path.name}")
    df = df.loc[:, ~df.columns.duplicated()].copy()

    n = len(df)
    completed = sum(1 for _, r in df.iterrows() if _is_complete_row(r))
    print(f"Records: {n}, already complete: {completed}, remaining: {n - completed}")
    print()

    for i, row in df.iterrows():
        if _is_complete_row(row):
            continue
        rid = row["record_id"]
        title = str(row.get("title", "")).strip()
        abstract = str(row.get("abstract_or_summary", "")).strip()

        print("=" * 88)
        print(f"Record {i+1}/{n}  ({rid})")
        print()
        print(f"  Title:       {textwrap.shorten(title, width=80, placeholder='...')}")
        print(f"  Year:        {row.get('year', '?')}    "
              f"Type: {row.get('document_type', '?')}    "
              f"Label: {row.get('nanobubble_vs_nanoparticle', '?')}")
        print()
        print("  ABSTRACT:")
        print(_wrap(abstract))
        print()

        # Per-field prompts
        for f in HEADLINE_FIELDS:
            value, unit, quote = _prompt_field(f, abstract)
            df.at[i, f"{f}_value"] = value
            df.at[i, f"{f}_unit"] = unit
            df.at[i, f"{f}_evidence_quote"] = quote

        flag = input("\n  ambiguity_flag (direct/inferred/uncertain, ENTER for 'direct'): ").strip() or "direct"
        notes = input("  annotator_notes (free text, ENTER to skip): ").strip()
        df.at[i, "ambiguity_flag"] = flag
        df.at[i, "annotator_notes"] = notes

        # Autosave after each record
        df.to_csv(out_path, index=False)
        completed = sum(1 for _, r in df.iterrows() if _is_complete_row(r))
        print(f"\n  [saved] {completed}/{n} complete\n")

    print("=" * 88)
    print(f"All records complete. Output: {out_path}")
    print()
    print("Next step:")
    print(f"  python3 scripts/03_reconcile.py \\")
    print(f"    {out_path} \\")
    print(f"    annotation/received/iaa_subset_<other-initials>.csv")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(annotate(sys.argv[1].lower()))
