"""Regenerate paper/figs/publication_volume.{pdf,png} from the final warehouse.

The figure shows annual publication volume in the released v1.0 warehouse
between 2000 and 2025, with annotations for the post-2018 environmental
surge and the post-2020 biomedical acceleration.

Run as:
    python3 scripts/verification/build_publication_volume_figure.py

Outputs (overwrites if present):
    paper/figs/publication_volume.pdf
    paper/figs/publication_volume.png

Also prints the n value the figure caption should cite.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "raw" / "master_inventory.csv"
OUT_DIR = ROOT / "paper" / "figs"


def main() -> int:
    df = pd.read_csv(WAREHOUSE, low_memory=False)
    yrs = pd.to_numeric(df["year"], errors="coerce").dropna().astype(int)
    yrs = yrs[(yrs >= 2000) & (yrs <= 2025)]
    counts = yrs.value_counts().sort_index()

    n_total = int(counts.sum())
    print(f"Total records 2000-2025: {n_total}")

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    color = "#2463a7"
    ax.fill_between(counts.index, counts.values, alpha=0.15, color=color)
    ax.plot(counts.index, counts.values, "-o",
            color=color, linewidth=1.6, markersize=4)

    # Surge markers: post-2018 environmental (label to the left of the
    # vline so it doesn't collide with the post-2020 label).
    ax.axvline(2018, color="0.55", linestyle="--", linewidth=0.8)
    ax.axvline(2020, color="0.55", linestyle="--", linewidth=0.8)
    ax.annotate("post-2018\nenv. surge",
                xy=(2018, counts.max() * 0.85),
                xytext=(2017.8, counts.max() * 0.78),
                fontsize=9, color="0.30", ha="right")
    ax.annotate("post-2020\nbiomed surge",
                xy=(2020, counts.max() * 0.55),
                xytext=(2020.3, counts.max() * 0.45),
                fontsize=9, color="0.30", ha="left")

    ax.set_xlabel("Publication year")
    ax.set_ylabel("Records per year")
    ax.set_xlim(2000, 2025)
    ax.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
    ax.grid(axis="y", linestyle=":", color="0.85")

    fig.tight_layout()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = OUT_DIR / "publication_volume.pdf"
    png_path = OUT_DIR / "publication_volume.png"
    fig.savefig(pdf_path)
    fig.savefig(png_path, dpi=160)
    print(f"Wrote {pdf_path.relative_to(ROOT)}")
    print(f"Wrote {png_path.relative_to(ROOT)}")
    print()
    print(f"==> Figure caption should read n={n_total:,}".replace(",", "{,}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
