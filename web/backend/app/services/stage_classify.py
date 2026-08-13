"""
Generalized upload inbox → content classify → route into exact folders.

Layout (under web/backend/uploads/staging/):
  raw/                 ← every upload lands here first
  processed/cdr|ipdr|bank|fir|kyc|cctv|other|accounts|transactions
  quarantine/          ← unreadable / unknown
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent.parent
INGESTION_P = BACKEND_ROOT / "app" / "ingestion"
UPLOADS_ROOT = BACKEND_ROOT / "uploads" / "staging"
BANK_STAGE = PROJECT_ROOT / "bank_statements_and_next_stage"

TABULAR_EXT = {".csv", ".tsv", ".xls", ".xlsx", ".xlsm"}
UNSTRUCTURED_EXT = {
    ".pdf",
    ".doc",
    ".docx",
    ".txt",
    ".html",
    ".htm",
    ".eml",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".gif",
}

# Map processed category → ingest_upload doc_type (None = evidence only)
CATEGORY_TO_INGEST = {
    "bank": "bank_statement",
    "accounts": "bank_statement",
    "transactions": "bank_statement",
    "cdr": "cdr",
    "ipdr": "ipdr",
}


def _ensure_path():
    root = str(INGESTION_P)
    if root not in sys.path:
        sys.path.insert(0, root)


def ensure_staging() -> dict[str, Path]:
    _ensure_path()
    from setup_staging import create_staging_layout

    return create_staging_layout()


@dataclass
class StageResult:
    status: str  # classified | quarantined | failed
    category: str
    reason: str
    raw_path: str
    processed_path: str | None
    matched: list[str]
    ingest_type: str | None
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _unique(dest_dir: Path, filename: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem, suf = Path(filename).stem, Path(filename).suffix
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return dest_dir / f"{stem}_{stamp}{suf}"


def _looks_like_statement_json(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig") as fh:
            head = fh.read(4096).lower()
        if '"bank_statement"' in head or '"document_type": "bank_statement"' in head:
            return True
        if '"statement_id"' in head and (
            '"transactions"' in head or '"account"' in head or '"bank"' in head
        ):
            return True
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            return False
        if str((data.get("document") or {}).get("document_type") or "").upper() == "BANK_STATEMENT":
            return True
        return bool(
            data.get("statement_id")
            and (isinstance(data.get("transactions"), list) or isinstance(data.get("account"), dict))
        )
    except Exception:
        return False


def _filename_phone_hint(name: str) -> str | None:
    """10-digit Indian mobile in filename → CDR (not bank account)."""
    n = Path(name).name
    n = re.sub(r"^FIR-\d{4}-\d+_", "", n, flags=re.I)
    n = re.sub(r"^\d{8}_\d{6}_", "", n)
    stem = Path(n).stem
    if re.fullmatch(r"\d{10}", stem) and re.match(r"[6-9]", stem):
        return "cdr"
    m = re.search(r"(?<!\d)([6-9]\d{9})(?!\d)\s*$", stem)
    if m:
        return "cdr"
    return None


def _filename_hint(name: str) -> str | None:
    """Hint from original upload name only (never staged FIR-case prefixes)."""
    n = Path(name).name.lower()
    n = re.sub(r"^fir-\d{4}-\d+[_\-]", "", n)
    n = re.sub(r"^\d{8}_\d{6}_", "", n)

    phone = _filename_phone_hint(name)
    if phone:
        return phone

    if "unified_master_cdr" in n or re.search(r"(^|[^a-z])cdr([^a-z]|$)", n):
        return "cdr"
    if "unified_master_ipdr" in n or re.search(r"(^|[^a-z])ipdr([^a-z]|$)", n):
        return "ipdr"
    if n.startswith("accounts") or "accounts.csv" in n:
        return "accounts"
    if n.startswith("transactions") or "transactions.csv" in n:
        return "transactions"
    if (
        "statement" in n
        or re.search(r"(^|[^a-z])stmt([^a-z]|$)", n)
        or "icore" in n
        or "bank" in n
        or "ledger" in n
        or re.search(r"\d{12,18}", n)  # bank account nos — not 10-digit mobiles
    ):
        return "bank"
    if re.search(r"(^|[^a-z0-9])fir([^a-z0-9-]|$)", n) or "first information" in n:
        return "fir"
    return None


def _match_existing_bank_json(original_filename: str) -> Path | None:
    """If upload matches a known statement JSON, treat as bank (same as generate_csvs)."""
    try:
        from app.services.ingest_upload import find_matching_statement_json
    except Exception:
        find_matching_statement_json = None  # type: ignore

    stem = Path(original_filename).stem
    digit_hints = re.findall(r"\d{6,18}", stem)
    if find_matching_statement_json and digit_hints:
        hit = find_matching_statement_json(digit_hints)
        if hit:
            return hit

    # Name-token match (e.g. MADHU010.pdf → VOJA MADHU statement)
    tokens = [t.lower() for t in re.split(r"[^A-Za-z]+", stem) if len(t) >= 4]
    skip = {
        "document",
        "statement",
        "bank",
        "account",
        "new",
        "scan",
        "copy",
        "file",
        "nov",
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "dec",
    }
    tokens = [t for t in tokens if t not in skip]
    if not tokens or not BANK_STAGE.is_dir():
        return None

    skip_dirs = {
        "bank_folder",
        "entity_timelines",
        "cdr_extraction",
        "__pycache__",
        "uploads",
        "outputs",
    }
    best: Path | None = None
    best_score = 0
    for jf in BANK_STAGE.rglob("*.json"):
        if not jf.is_file() or any(part in skip_dirs for part in jf.parts):
            continue
        if jf.name.startswith("_") or jf.name.lower() in {
            "entities_summary.json",
            "unified_master_timeline.json",
            "investigation_data.json",
        }:
            continue
        try:
            head = jf.read_text(encoding="utf-8-sig", errors="ignore")[:12000].lower()
        except OSError:
            continue
        score = sum(1 for t in tokens if t in head)
        if score > best_score and score >= 1:
            # Prefer real statement schema
            if '"statement_id"' in head or '"transactions"' in head:
                best_score = score
                best = jf
    return best


def _local_bank_header_boost(path: Path) -> tuple[str, str, list[str], float] | None:
    """Catch core-banking Excel exports (ICORE etc.) that score just under threshold."""
    try:
        from classify_tabular import extract_headers, normalize_header
    except Exception:
        return None
    try:
        headers = [normalize_header(h) for h in extract_headers(path)]
    except Exception:
        return None
    joined = " | ".join(headers)
    hits = []
    for label, pat in (
        ("narration", r"narration|description|particulars"),
        ("dr/cr", r"\bdr\s*amt\b|\bcr\s*amt\b|debit|credit"),
        ("tran date", r"tran\s*date|transaction\s*date|\bdate\b"),
        ("ac no", r"\bac\s*no\b|account\s*(no|number)|a/?c"),
        ("balance", r"\bbalance\b"),
        ("tran id", r"tran\s*id|transaction\s*id"),
    ):
        if re.search(pat, joined, re.I):
            hits.append(label)
    if len(hits) >= 3:
        return "bank", f"core-banking Excel headers ({', '.join(hits)})", hits, 0.9
    return None


def _match_bank_folder_source(original_filename: str, size: int | None = None) -> Path | None:
    """Exact filename match under bank_folder/ only — no fuzzy substring."""
    folder = BANK_STAGE / "bank_folder"
    if not folder.is_dir():
        return None
    target = Path(original_filename).name.lower()
    target_norm = re.sub(r"[^a-z0-9]+", "", target)
    # Never treat phone-number filenames as bank_folder hits
    if _filename_phone_hint(original_filename):
        return None
    for p in folder.rglob("*"):
        if not p.is_file():
            continue
        pname = p.name.lower()
        pnorm = re.sub(r"[^a-z0-9]+", "", pname)
        if pname == target or pnorm == target_norm:
            return p
    if size:
        hits = [
            p
            for p in folder.rglob("*")
            if p.is_file()
            and p.stat().st_size == size
            and p.suffix.lower() == Path(target).suffix.lower()
            and (
                p.name.lower() == target
                or re.sub(r"[^a-z0-9]+", "", p.name.lower()) == target_norm
            )
        ]
        if len(hits) == 1:
            return hits[0]
    return None


def _classify_one(
    path: Path, *, original_filename: str | None = None
) -> tuple[str, str, list[str], float]:
    """Return (category, reason, matched, confidence)."""
    _ensure_path()
    ext = path.suffix.lower()
    orig = original_filename or path.name
    hint = _filename_hint(orig)
    try:
        size = path.stat().st_size
    except OSError:
        size = None

    # Tabular content beats filename / bank_folder heuristics
    if ext in TABULAR_EXT:
        from classify_tabular import classify_tabular_file

        res = classify_tabular_file(path)
        cat = res.category if res.category and res.category != "quarantine" else ""
        if cat == "cdr":
            return cat, res.reason, res.matched_signals or [], 0.92
        if cat == "ipdr":
            return cat, res.reason, res.matched_signals or [], 0.92
        if cat == "bank":
            if hint in {"accounts", "transactions"}:
                return hint, f"headers→bank + filename→{hint}", res.matched_signals or [], 0.9
            return cat, res.reason, res.matched_signals or [], 0.88
        if not cat:
            boost = _local_bank_header_boost(path)
            if boost:
                return boost
        if not cat and hint in {"cdr", "ipdr", "bank", "accounts", "transactions"}:
            return hint, f"filename hint after weak headers ({res.reason})", [hint], 0.65
        if not cat:
            return "quarantine", res.reason, res.matched_signals or [], 0.0

    # Strong filename hints when tabular classify was inconclusive
    if hint in {"cdr", "ipdr"}:
        return hint, f"filename phone/type hint ({hint})", [hint], 0.8

    # Exact bank_folder filename match (evidence pack PDFs)
    bf = _match_bank_folder_source(orig, size)
    if bf:
        return "bank", f"matches bank_folder file ({bf.parent.name}/{bf.name})", [bf.name], 0.95

    # Scanned / oddly named bank PDFs: prefer known statement JSON match
    json_hit = _match_existing_bank_json(orig)
    if json_hit and ext in {".pdf", ".xlsx", ".xls", ".xlsm", ".csv", ".json"}:
        return (
            "bank",
            f"matched existing statement JSON ({json_hit.name})",
            [json_hit.name],
            0.92,
        )

    if ext == ".json":
        if _looks_like_statement_json(path):
            return "bank", "JSON bank-statement schema", ["statement_id/transactions"], 0.95
        return "other", "JSON without bank-statement schema", [], 0.4

    if ext in UNSTRUCTURED_EXT:
        from classify_unstructured import classify_unstructured_file

        res = classify_unstructured_file(path)
        cat = res.category or "other"
        # Never trust FIR from empty OCR when we have a bank filename/account hint
        if cat in {"quarantine", "fir", "other"} and hint == "bank":
            return "bank", f"bank filename hint after weak text ({res.reason})", [hint], 0.65
        if cat == "quarantine" and hint and hint != "fir":
            return hint, f"filename hint after weak text ({res.reason})", [hint], 0.5
        if cat == "quarantine" and hint == "fir":
            # only accept fir hint from original name, not case prefix
            return "fir", f"filename hint after weak text ({res.reason})", [hint], 0.5
        conf = float(getattr(res, "confidence", 0.7) or 0.7)
        return cat, res.reason, list(res.matched_keywords or []), conf

    if hint:
        return hint, "filename hint for unknown extension", [hint], 0.45
    return "other", f"unclassified extension {ext}", [], 0.3


def _sync_canonical(category: str, src: Path) -> Path | None:
    """Also drop a copy into extractor dataset folders used by orchestrate."""
    _ensure_path()
    try:
        from paths_config import BANK_FOLDER, CDR_DATASET, IPDR_DATASET, discover_bank_names
    except ImportError:
        return None

    if category in {"bank", "accounts", "transactions"}:
        # Guess bank subfolder from filename
        names = discover_bank_names()
        compact = re.sub(r"[^a-z0-9]+", "", src.name.lower())
        sub = "_unsorted"
        for name in names:
            if name.startswith("_"):
                continue
            token = re.sub(r"[^a-z0-9]+", "", name.lower())
            if token and token in compact:
                sub = name
                break
        dest_dir = BANK_FOLDER / sub
        dest = _unique(dest_dir, src.name)
        shutil.copy2(src, dest)
        return dest

    if category == "cdr":
        data = CDR_DATASET / "Data"
        dest_dir = data if data.is_dir() else CDR_DATASET
        dest = _unique(dest_dir, src.name)
        shutil.copy2(src, dest)
        return dest

    if category == "ipdr":
        dest = _unique(IPDR_DATASET, src.name)
        shutil.copy2(src, dest)
        return dest

    return None


def stage_classify_and_route(
    *,
    content: bytes,
    original_filename: str,
    case_id: str | None = None,
    force_category: str | None = None,
) -> StageResult:
    """
    Save bytes into generalized raw/, classify content, move into processed/<cat>/.
    """
    ensure_staging()
    safe = re.sub(r"[^A-Za-z0-9._\- ]+", "_", Path(original_filename).name)[:180]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    case_prefix = f"{case_id}_" if case_id else ""
    raw_name = f"{case_prefix}{stamp}_{safe}"
    raw_path = UPLOADS_ROOT / "raw" / raw_name
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)

    # Manual override from UI (when user picks Bank/CDR/IPDR explicitly)
    force_map = {
        "bank_statement": "bank",
        "bank": "bank",
        "cdr": "cdr",
        "ipdr": "ipdr",
        "fir": "fir",
        "kyc": "kyc",
        "cctv": "cctv",
    }
    forced = force_map.get((force_category or "").strip().lower())

    if forced:
        category, reason, matched, confidence = (
            forced,
            f"user-selected type → {forced}",
            [forced],
            1.0,
        )
    else:
        category, reason, matched, confidence = _classify_one(
            raw_path, original_filename=original_filename
        )

    if category in {"quarantine", ""}:
        dest = _unique(UPLOADS_ROOT / "quarantine", raw_path.name)
        shutil.move(str(raw_path), str(dest))
        return StageResult(
            status="quarantined",
            category="quarantine",
            reason=reason,
            raw_path=str(dest),
            processed_path=None,
            matched=matched,
            ingest_type=None,
            confidence=confidence,
        )

    # Normalize aliases
    if category == "accounts":
        dest_cat = "accounts"
    elif category == "transactions":
        dest_cat = "transactions"
    else:
        dest_cat = category

    dest_dir = UPLOADS_ROOT / "processed" / dest_cat
    dest = _unique(dest_dir, raw_path.name)
    shutil.move(str(raw_path), str(dest))

    try:
        _sync_canonical(dest_cat if dest_cat not in {"accounts", "transactions"} else "bank", dest)
    except Exception:
        pass

    # Sidecar classify note
    sidecar = dest.with_suffix(dest.suffix + ".classify.json")
    try:
        sidecar.write_text(
            json.dumps(
                {
                    "category": dest_cat,
                    "reason": reason,
                    "matched": matched,
                    "confidence": confidence,
                    "original_filename": original_filename,
                    "case_id": case_id,
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except OSError:
        pass

    return StageResult(
        status="classified",
        category=dest_cat,
        reason=reason,
        raw_path=str(UPLOADS_ROOT / "raw"),
        processed_path=str(dest),
        matched=matched,
        ingest_type=CATEGORY_TO_INGEST.get(dest_cat),
        confidence=confidence,
    )
