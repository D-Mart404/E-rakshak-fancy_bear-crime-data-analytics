#!/usr/bin/env python3
"""
Step 1 — Staging directory bootstrap for the E-Rakshak ingestion pipeline.

Creates a standard upload layout under this package so later stages can:

  uploads/raw/         ← police / investigator dumps land here (untouched)
  uploads/processed/   ← validated + classified files, ready for extractors
  uploads/quarantine/  ← corrupted, MIME-mismatched, or unusable files

Run once (or anytime) from the project root or this folder:

    python ingestion_p/setup_staging.py
"""

from __future__ import annotations

from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent.parent

UPLOADS_ROOT = BACKEND_ROOT / "uploads" / "staging"

# Core staging tiers requested for the pipeline
STAGING_DIRS = [
    UPLOADS_ROOT / "raw",
    UPLOADS_ROOT / "processed",
    UPLOADS_ROOT / "quarantine",
]

# Optional category buckets under processed/ — used from Step 3 onward so
# extractors can be pointed at a clean folder without re-scanning everything.
# Safe to create now; empty until classification runs.
PROCESSED_CATEGORIES = [
    "cdr",
    "ipdr",
    "bank",
    "accounts",
    "transactions",
    "fir",
    "kyc",
    "cctv",
    "other",
]


def create_staging_layout(base: Path | None = None) -> dict[str, Path]:
    """
    Create the staging tree (idempotent). Returns a map of logical name → path.
    Also ensures canonical dataset folders (cdr_dataset, ipdr_docs, bank_folder, bank_account).
    """
    uploads = Path(base) if base else UPLOADS_ROOT
    created: dict[str, Path] = {"uploads": uploads}

    tiers = {
        "raw": uploads / "raw",
        "processed": uploads / "processed",
        "quarantine": uploads / "quarantine",
    }

    for name, path in tiers.items():
        path.mkdir(parents=True, exist_ok=True)
        (path / ".gitkeep").touch(exist_ok=True)
        created[name] = path

    processed = tiers["processed"]
    for category in PROCESSED_CATEGORIES:
        cat_path = processed / category
        cat_path.mkdir(parents=True, exist_ok=True)
        (cat_path / ".gitkeep").touch(exist_ok=True)
        created[f"processed/{category}"] = cat_path

    # Align with real extractor dataset folders
    try:
        from paths_config import ensure_dataset_dirs

        created.update(ensure_dataset_dirs())
    except ImportError:
        try:
            from ingestion_p.paths_config import ensure_dataset_dirs

            created.update(ensure_dataset_dirs())
        except ImportError:
            pass

    return created


def print_layout(paths: dict[str, Path]) -> None:
    print("E-Rakshak ingestion staging layout")
    print(f"  project root : {PROJECT_ROOT}")
    print(f"  package root : {PACKAGE_ROOT}")
    print()
    for key in ("raw", "processed", "quarantine"):
        print(f"  [{key:11}] {paths[key]}")
    print()
    print("  processed category buckets:")
    for category in PROCESSED_CATEGORIES:
        print(f"    - {paths[f'processed/{category}']}")


def main() -> None:
    paths = create_staging_layout()
    print_layout(paths)
    print("\nStaging directories ready (idempotent — safe to re-run).")


if __name__ == "__main__":
    main()
