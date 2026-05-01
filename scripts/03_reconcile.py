"""Stage 3: Reconcile two annotators on the IAA subset.

Computes Cohen's kappa per field, value-match rate among emit-emit pairs,
unit-normalised numeric match, and span IoU.

I/O:
    in   <annotator_A.csv>  <annotator_B.csv>   (iaa_subset shape)
    out  annotation/gold_hard/iaa_stats.csv
         annotation/gold_hard/iaa_summary.md
         annotation/gold_hard/disagreements.csv
         annotation/gold_hard/gold_hard_template.csv

Run:
    python3 scripts/03_reconcile.py \\
        annotation/received/iaa_subset_elias.csv \\
        annotation/received/iaa_subset_collab.csv
"""

from __future__ import annotations

import sys

from nanobubbleval.cli import main
from nanobubbleval.paths import paths


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main([
        "reconcile",
        "--a", sys.argv[1],
        "--b", sys.argv[2],
        "--out", str(paths.iaa_gold_hard),
    ])
