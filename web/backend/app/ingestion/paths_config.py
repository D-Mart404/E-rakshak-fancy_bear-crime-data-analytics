#!/usr/bin/env python3
"""
Canonical paths for E-Rakshak ingestion <-> existing extractors.

Override any path with env vars (optional):
  ERAKSHAK_CDR_DATASET, ERAKSHAK_CDR_OUTPUT,
  ERAKSHAK_IPDR_DATASET, ERAKSHAK_IPDR_OUTPUT,
  ERAKSHAK_BANK_FOLDER, ERAKSHAK_BANK_ACCOUNT_DIR, ERAKSHAK_BANK_STAGE
"""

from __future__ import annotations

import os
from pathlib import Path

# This package lives at web/backend/app/ingestion/
BACKEND_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent
# Optional local FIR dumps (gitignored) still live at the repo root.
PROJECT_ROOT = BACKEND_ROOT.parent.parent


def _env_path(key: str, default: Path) -> Path:
    raw = os.environ.get(key, "").strip()
    return Path(raw) if raw else default


# --- Staging (Steps 1-4) — inside the backend, not ingestion_p/ ---
UPLOADS_ROOT = BACKEND_ROOT / "uploads" / "staging"
RAW_DIR = UPLOADS_ROOT / "raw"
PROCESSED_DIR = UPLOADS_ROOT / "processed"
QUARANTINE_DIR = UPLOADS_ROOT / "quarantine"

# --- CDR ---
CDR_SCRIPT = BACKEND_ROOT / "app" / "parsers" / "cdr_ingestion.py"
CDR_DATASET = _env_path(
    "ERAKSHAK_CDR_DATASET", PROJECT_ROOT / "cdr_extraction" / "cdr_dataset"
)
CDR_OUTPUT = _env_path(
    "ERAKSHAK_CDR_OUTPUT", PROJECT_ROOT / "cdr_extraction" / "UNIFIED_MASTER_CDR.csv"
)

# --- IPDR ---
IPDR_SCRIPT = BACKEND_ROOT / "app" / "parsers" / "ipdr_extracter.py"
IPDR_DATASET = _env_path("ERAKSHAK_IPDR_DATASET", PROJECT_ROOT / "ipdr_docs")
IPDR_OUTPUT_XLSX = _env_path("ERAKSHAK_IPDR_OUTPUT", PROJECT_ROOT / "output.xlsx")
IPDR_OUTPUT_SECONDARY = IPDR_OUTPUT_XLSX.with_name(
    IPDR_OUTPUT_XLSX.stem + "_secondary" + IPDR_OUTPUT_XLSX.suffix
)
IPDR_OUTPUT_CSV = PROJECT_ROOT / "output_ipdr.csv"

# --- Bank ---
BANK_STAGE = _env_path(
    "ERAKSHAK_BANK_STAGE", PROJECT_ROOT / "bank_statements_and_next_stage"
)
BANK_FOLDER = _env_path("ERAKSHAK_BANK_FOLDER", BANK_STAGE / "bank_folder")
BANK_GENERATE_CSVS = BANK_STAGE / "generate_csvs.py"
BANK_NORMALIZE = BANK_STAGE / "normalize_schema.py"
BANK_DOCX = BANK_STAGE / "bank account ni mahiti.docx"
BANK_ACCOUNT_DIR = _env_path("ERAKSHAK_BANK_ACCOUNT_DIR", PROJECT_ROOT / "bank_account")
BANK_ACCOUNTS_CSV = BANK_ACCOUNT_DIR / "accounts.csv"
BANK_TRANSACTIONS_CSV = BANK_ACCOUNT_DIR / "transactions.csv"

ORCHESTRATION_OUTPUTS = BACKEND_ROOT / "uploads" / "outputs"


def ensure_dataset_dirs() -> dict[str, Path]:
    """Create staging folders. Dataset dumps at repo root stay optional/local."""
    dirs = {"uploads": UPLOADS_ROOT, "orchestration_outputs": ORCHESTRATION_OUTPUTS}
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def discover_bank_names() -> list[str]:
    """
    Dynamically discover bank folder names from bank_folder/ and JSON sibling dirs.
    Always merges a common-bank alias seed so filename guessing works for new banks
    before their folders exist on disk.
    """
    # Seed aliases (filename/JSON guessing). Real folders override/extend this.
    names: set[str] = {
        "axis",
        "bandhan",
        "bank of baroda",
        "bob",
        "baroda",
        "canara",
        "central bank of india",
        "city union",
        "federal bank",
        "hdfc",
        "icici",
        "idbi",
        "idfc",
        "kotak",
        "pnb",
        "punjab national",
        "rbl",
        "sbi",
        "state bank",
        "union bank",
        "utkarsh",
        "varachha",
        "yes",
        "yes bank",
    }
    if BANK_FOLDER.is_dir():
        for p in BANK_FOLDER.iterdir():
            if p.is_dir() and not p.name.startswith("."):
                names.add(p.name)
    if BANK_STAGE.is_dir():
        skip = {
            "bank_folder",
            "entity_timelines",
            "cdr_extraction",
            "__pycache__",
            "uploads",
            "outputs",
        }
        for p in BANK_STAGE.iterdir():
            if p.is_dir() and p.name not in skip and not p.name.startswith("."):
                # Only treat as bank dir if it contains statement-like JSON/PDF
                if any(p.glob("*.json")) or any(p.glob("*.pdf")):
                    names.add(p.name)
    names.add("_unsorted")
    names.add("_unsorted_json")
    # Longer names first so "bank of baroda" / "central bank of india" beat "bank"
    return sorted(names, key=lambda s: (-len(s), s.lower()))
