"""Stage 4: Evaluate a baseline's predictions against gold.

Runs Naive-F1, Acal-F1, num-match, unit accuracy, span IoU, and
answer-evidence consistency per headline field, plus a macro row.

Convention: results land under results/metrics/<baseline_name>.csv
(see ProjectPaths.results_metrics_for).

Run:
    python3 scripts/04_evaluate.py <gold.csv> <pred.csv> <baseline_name>

Example:
    python3 scripts/04_evaluate.py \\
        annotation/gold_hard/gold_hard.csv \\
        baselines/regex/regex-v1_predictions.csv \\
        regex-v1
"""

from __future__ import annotations

import sys

from nanobubbleval.cli import main
from nanobubbleval.paths import paths


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    main([
        "evaluate",
        "--gold", sys.argv[1],
        "--pred", sys.argv[2],
        "--out", str(paths.results_metrics_for(sys.argv[3])),
    ])
