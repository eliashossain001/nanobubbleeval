"""Push the v1.0 dataset bundle to a HuggingFace dataset repository.

The destination repository ID is set via the ``HF_REPO_ID`` environment
variable; reviewers will not need this script.

Uploads:
    warehouse/master_inventory.csv  (post-recovery 51,566-record manifest)
    verification/*                  (gold-hard recovery audit logs)
    README.md                       (refreshed dataset card)
    metadata/croissant.json         (warehouse description updated)

Reads HF_TOKEN from .env. The dataset repo is public.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parents[2]
LOG = logging.getLogger("hf-push")

REPO_ID = os.environ.get("HF_REPO_ID", "")
REPO_TYPE = "dataset"


def _load_token() -> str:
    env_path = ROOT / ".env"
    text = env_path.read_text()
    for line in text.splitlines():
        if line.startswith("HF_TOKEN="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("HF_TOKEN not found in .env")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(levelname)s %(name)s: %(message)s")

    if not REPO_ID:
        LOG.error("HF_REPO_ID environment variable not set; refusing to push.")
        return 1

    token = _load_token()
    api = HfApi(token=token)

    info = api.dataset_info(REPO_ID)
    LOG.info("Target repo: %s (private=%s, last_modified=%s)",
             info.id, info.private, info.last_modified)

    operations = [
        # path_in_repo, local_path
        ("README.md", ROOT / "dataset_release" / "README.md"),
        ("metadata/croissant.json", ROOT / "dataset_release" / "metadata" / "croissant.json"),
        ("warehouse/master_inventory.csv",
         ROOT / "dataset_release" / "warehouse" / "master_inventory.csv"),
        ("verification/gold_hard_identifier_parse.csv",
         ROOT / "verification" / "gold_hard_identifier_parse.csv"),
        ("verification/gold_hard_containment_before_merge.csv",
         ROOT / "verification" / "gold_hard_containment_before_merge.csv"),
        ("verification/gold_hard_refetch_log.csv",
         ROOT / "verification" / "gold_hard_refetch_log.csv"),
        ("verification/gold_hard_abstract_crosscheck.csv",
         ROOT / "verification" / "gold_hard_abstract_crosscheck.csv"),
        ("verification/gold_hard_containment_after_merge.csv",
         ROOT / "verification" / "gold_hard_containment_after_merge.csv"),
        ("verification/summary.json", ROOT / "verification" / "summary.json"),
        ("verification/abstract_mismatches.txt",
         ROOT / "verification" / "abstract_mismatches.txt"),
    ]

    # Validate every local file exists before pushing anything
    missing = [(p, lp) for p, lp in operations if not lp.exists()]
    if missing:
        for p, lp in missing:
            LOG.error("missing local file: %s -> %s", p, lp)
        return 1

    # Sizes
    total = sum(lp.stat().st_size for _, lp in operations)
    LOG.info("Uploading %d files (%.1f MB total)", len(operations), total / 1024**2)
    for path_in_repo, local_path in operations:
        size_kb = local_path.stat().st_size / 1024
        LOG.info("  %-55s %8.1f KB", path_in_repo, size_kb)

    LOG.info("Beginning upload...")
    for path_in_repo, local_path in operations:
        LOG.info("upload %s ...", path_in_repo)
        api.upload_file(
            path_or_fileobj=str(local_path),
            path_in_repo=path_in_repo,
            repo_id=REPO_ID,
            repo_type=REPO_TYPE,
            commit_message=f"v1.0 final: add {path_in_repo}",
            token=token,
        )
        LOG.info("  done")

    LOG.info("All files uploaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
