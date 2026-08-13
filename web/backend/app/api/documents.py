"""Case document upload with auto content-classify into exact folders + ingest."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from .. import db
from ..services.ingest_upload import ingest_uploaded_file
from ..services.stage_classify import UPLOADS_ROOT, ensure_staging, stage_classify_and_route

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Case locker copy (UI list) — separate from generalized ingestion inbox
CASE_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"
ALLOWED_EXT = {
    ".pdf",
    ".csv",
    ".xlsx",
    ".xls",
    ".xlsm",
    ".docx",
    ".doc",
    ".txt",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".zip",
    ".tsv",
    ".html",
    ".htm",
}


def _now() -> str:
    return datetime.utcnow().isoformat(sep=" ", timespec="seconds") + " UTC"


def _safe_name(name: str) -> str:
    base = Path(name).name
    return re.sub(r"[^A-Za-z0-9._\- ]+", "_", base)[:180]


@router.get("")
async def list_documents(case_id: str | None = None):
    database = db.get_db()
    query: dict[str, Any] = {}
    if case_id:
        query["case_id"] = case_id
    else:
        active = await database["cases"].find_one({"status": "active"}, {"case_id": 1})
        if active:
            query["case_id"] = active["case_id"]

    rows = (
        await database["case_documents"]
        .find(query, {"_id": 0})
        .sort("uploaded_at", -1)
        .to_list(300)
    )
    return {
        "status": "ok",
        "case_id": query.get("case_id"),
        "count": len(rows),
        "documents": rows,
        "staging_root": str(UPLOADS_ROOT),
    }


@router.get("/staging")
async def staging_layout():
    """Show generalized upload folder tree (raw / processed / quarantine)."""
    paths = ensure_staging()
    processed = UPLOADS_ROOT / "processed"
    buckets = {}
    if processed.is_dir():
        for p in sorted(processed.iterdir()):
            if p.is_dir():
                files = [f.name for f in p.iterdir() if f.is_file() and not f.name.endswith(".classify.json") and f.name != ".gitkeep"]
                buckets[p.name] = {"count": len(files), "files": files[:30]}
    quarantine = UPLOADS_ROOT / "quarantine"
    q_files = []
    if quarantine.is_dir():
        q_files = [f.name for f in quarantine.iterdir() if f.is_file() and f.name != ".gitkeep"][:30]
    raw = UPLOADS_ROOT / "raw"
    raw_files = []
    if raw.is_dir():
        raw_files = [f.name for f in raw.iterdir() if f.is_file() and f.name != ".gitkeep"][:30]
    return {
        "status": "ok",
        "root": str(UPLOADS_ROOT),
        "raw": {"count": len(raw_files), "files": raw_files},
        "processed": buckets,
        "quarantine": {"count": len(q_files), "files": q_files},
        "paths": {k: str(v) for k, v in paths.items() if k in {"raw", "processed", "quarantine"}},
    }


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    case_id: str | None = Form(None),
    doc_type: str = Form("auto"),
    note: str = Form(""),
    auto_ingest: str = Form("true"),
):
    database = db.get_db()
    if not case_id:
        active = await database["cases"].find_one({"status": "active"}, {"case_id": 1})
        case_id = (active or {}).get("case_id")
    if not case_id:
        raise HTTPException(status_code=400, detail="No active case. Open a case first.")

    original = file.filename or "upload.bin"
    safe = _safe_name(original)
    ext = Path(safe).suffix.lower()
    if ext and ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Use PDF/CSV/XLSX/JSON/DOCX/images.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50 MB)")

    # 1) Generalized inbox + content classify → exact folder
    force = None if (doc_type or "auto").strip().lower() in {"auto", "evidence", "other", ""} else doc_type
    stage = stage_classify_and_route(
        content=content,
        original_filename=original,
        case_id=case_id,
        force_category=force,
    )

    # 2) Case locker copy for UI list / re-ingest
    doc_id = f"DOC_{uuid.uuid4().hex[:12].upper()}"
    case_dir = CASE_UPLOAD_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{doc_id}_{safe}"
    dest = case_dir / stored_name
    dest.write_bytes(content)

    detected = stage.category
    kind_map = {
        "bank": "bank_statement",
        "accounts": "bank_statement",
        "transactions": "bank_statement",
        "cdr": "cdr",
        "ipdr": "ipdr",
        "fir": "fir",
        "kyc": "evidence",
        "cctv": "evidence",
        "other": "other",
        "quarantine": "other",
    }
    kind = kind_map.get(detected, "other")
    # If user forced a type, keep that for ingest preference
    if force:
        forced_kind = {
            "bank_statement": "bank_statement",
            "bank": "bank_statement",
            "cdr": "cdr",
            "ipdr": "ipdr",
            "fir": "fir",
        }.get(force.strip().lower())
        if forced_kind:
            kind = forced_kind

    ingest_result: dict[str, Any] | None = None
    do_ingest = str(auto_ingest).strip().lower() not in {"0", "false", "no"}
    ingest_type = stage.ingest_type or (
        kind if kind in {"bank_statement", "cdr", "ipdr"} else None
    )
    if do_ingest and ingest_type and stage.status == "classified":
        # Prefer staged processed file when available
        ingest_path = Path(stage.processed_path) if stage.processed_path else dest
        ingest_result = await ingest_uploaded_file(
            database, path=ingest_path, doc_type=ingest_type, case_id=case_id
        )

    row = {
        "document_id": doc_id,
        "case_id": case_id,
        "original_filename": original,
        "stored_filename": stored_name,
        "doc_type": kind,
        "note": (note or "").strip(),
        "content_type": file.content_type or "application/octet-stream",
        "size_bytes": len(content),
        "uploaded_at": _now(),
        "uploaded_by": "Investigator",
        "detected_category": detected,
        "classify_reason": stage.reason,
        "classify_matched": stage.matched,
        "classify_confidence": stage.confidence,
        "staged_path": stage.processed_path,
        "staging_status": stage.status,
        "ingest_status": (ingest_result or {}).get("status")
        or ("skipped" if stage.status != "classified" else "stored"),
        "ingest_message": (ingest_result or {}).get("message")
        or (
            f"Routed to processed/{detected}/"
            if stage.status == "classified"
            else f"Quarantined: {stage.reason}"
        ),
        "ingest_stats": {
            k: v
            for k, v in (ingest_result or {}).items()
            if k
            in {
                "entities",
                "transactions",
                "events",
                "events_added",
                "kind",
                "source",
                "source_file",
            }
        },
        "linked_account_ids": (ingest_result or {}).get("account_ids") or [],
        "linked_msisdns": (ingest_result or {}).get("msisdns") or [],
        "linked_source_file": (ingest_result or {}).get("source_file"),
    }
    await database["case_documents"].insert_one(dict(row))
    await database["audit_trail"].insert_one(
        {
            "timestamp": _now(),
            "user": "Investigator",
            "case_id": case_id,
            "action": (
                f"Uploaded {original} → classified as {detected} "
                f"({stage.status}) → {stage.processed_path or 'quarantine'}"
                + (f" — ingest: {row['ingest_message']}" if ingest_result else "")
            ),
        }
    )
    row.pop("_id", None)
    return {
        "status": "ok",
        "document": row,
        "classification": stage.as_dict(),
        "ingest": ingest_result,
    }


@router.post("/{document_id}/ingest")
async def reingest_document(document_id: str):
    """Re-parse an already uploaded bank/CDR/IPDR file into MongoDB."""
    database = db.get_db()
    doc = await database["case_documents"].find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    case_path = CASE_UPLOAD_ROOT / doc["case_id"] / doc["stored_filename"]
    path = None
    if doc.get("staged_path") and Path(doc["staged_path"]).exists():
        path = Path(doc["staged_path"])
    elif case_path.exists():
        path = case_path
    if not path:
        raise HTTPException(status_code=404, detail="Stored file missing on disk")

    kind = (doc.get("doc_type") or "").lower()
    detected = (doc.get("detected_category") or "").lower()
    ingest_type = {
        "bank_statement": "bank_statement",
        "bank": "bank_statement",
        "accounts": "bank_statement",
        "transactions": "bank_statement",
        "cdr": "cdr",
        "ipdr": "ipdr",
    }.get(kind) or {
        "bank": "bank_statement",
        "accounts": "bank_statement",
        "transactions": "bank_statement",
        "cdr": "cdr",
        "ipdr": "ipdr",
    }.get(detected)

    # Re-sniff tabular files — fix CDR misclassified as bank
    if path.suffix.lower() in {".csv", ".tsv", ".xlsx", ".xls", ".xlsm"}:
        try:
            import sys
            ingest_root = str(Path(__file__).resolve().parents[2] / "app" / "ingestion")
            if ingest_root not in sys.path:
                sys.path.insert(0, ingest_root)
            from classify_tabular import classify_tabular_file

            sniff = classify_tabular_file(path)
            sniff_cat = (sniff.category or "").lower()
            if sniff_cat == "cdr":
                ingest_type = "cdr"
                detected = "cdr"
            elif sniff_cat == "ipdr":
                ingest_type = "ipdr"
                detected = "ipdr"
            elif sniff_cat == "bank" and ingest_type != "cdr" and ingest_type != "ipdr":
                ingest_type = "bank_statement"
                detected = "bank"
        except Exception:
            pass

    # Phone-number filename → CDR even if doc row says bank
    orig_name = str(doc.get("original_filename") or path.name)
    if re.search(r"(?<!\d)([6-9]\d{9})(?!\d)", Path(orig_name).stem):
        ingest_type = "cdr"
        detected = "cdr"

    # Quarantined / misclassified Excel etc. — re-classify from case locker copy
    stage_info = None
    if not ingest_type and case_path.exists():
        stage_info = stage_classify_and_route(
            content=case_path.read_bytes(),
            original_filename=doc.get("original_filename") or case_path.name,
            case_id=doc.get("case_id"),
            force_category=None,
        )
        ingest_type = stage_info.ingest_type
        if stage_info.processed_path:
            path = Path(stage_info.processed_path)
        detected = stage_info.category

    # Last-resort: xlsx/csv/pdf named like statements → bank
    if not ingest_type:
        name = (doc.get("original_filename") or path.name).lower()
        ext = path.suffix.lower()
        if ext in {".xlsx", ".xls", ".xlsm", ".csv", ".pdf"} and any(
            k in name for k in ("stmt", "statement", "icore", "bank", "ledger", "account")
        ):
            ingest_type = "bank_statement"
            detected = "bank"

    if not ingest_type:
        raise HTTPException(
            status_code=400,
            detail="File was not classified as Bank / CDR / IPDR — cannot ingest.",
        )

    result = await ingest_uploaded_file(
        database, path=path, doc_type=ingest_type, case_id=doc.get("case_id")
    )
    update: dict[str, Any] = {
        "ingest_status": result.get("status"),
        "ingest_message": result.get("message"),
        "ingest_stats": {
            k: v
            for k, v in result.items()
            if k
            in {
                "entities",
                "transactions",
                "events",
                "events_added",
                "kind",
                "source",
                "source_file",
            }
        },
        "linked_account_ids": result.get("account_ids") or [],
        "linked_msisdns": result.get("msisdns") or [],
        "linked_source_file": result.get("source_file"),
        "doc_type": {
            "bank_statement": "bank_statement",
            "cdr": "cdr",
            "ipdr": "ipdr",
        }.get(ingest_type, doc.get("doc_type")),
        "detected_category": detected or doc.get("detected_category"),
    }
    if stage_info:
        update.update(
            {
                "classify_reason": stage_info.reason,
                "staged_path": stage_info.processed_path,
                "staging_status": stage_info.status,
            }
        )
    await database["case_documents"].update_one(
        {"document_id": document_id},
        {"$set": update},
    )
    return {"status": "ok", "document_id": document_id, "ingest": result}


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    purge_data: bool = Query(
        True,
        description="Also delete Mongo transactions/entities loaded from this document",
    ),
):
    database = db.get_db()
    doc = await database["case_documents"].find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    path = CASE_UPLOAD_ROOT / doc["case_id"] / doc["stored_filename"]
    if path.exists():
        path.unlink()

    purged = {"transactions": 0, "entities": 0, "accounts": 0, "telecom_events": 0, "ipdr": 0}
    if purge_data:
        account_ids = list(doc.get("linked_account_ids") or [])
        # Fallback: recover from known bad Canara mis-match / ingest message
        msg = str(doc.get("ingest_message") or "")
        if not account_ids and "canara_bank_statement" in msg.lower():
            account_ids = ["ACC_CANARA_001"]
        if not account_ids and "idbi_bank_statement" in msg.lower():
            account_ids = ["ACC_IDBI_001"]
        # ICORE filenames embed account numbers
        name = str(doc.get("original_filename") or "")
        m = re.search(r"ICORE_STMT_(\d{9,18})", name, re.I)
        if m:
            account_ids.append(f"ACC_{m.group(1)}")
        account_ids = list(dict.fromkeys(a for a in account_ids if a))

        if account_ids:
            tx_res = await database["transactions"].delete_many(
                {"account_id": {"$in": account_ids}}
            )
            purged["transactions"] = tx_res.deleted_count
            ent_res = await database["entities"].delete_many(
                {"entity_id": {"$in": account_ids}}
            )
            purged["entities"] = ent_res.deleted_count
            acc_res = await database["accounts"].delete_many(
                {"account_id": {"$in": account_ids}}
            )
            purged["accounts"] = acc_res.deleted_count

        # CDR/IPDR: purge by source file and/or MSISDN from filename / linked fields
        kind = (doc.get("doc_type") or doc.get("detected_category") or "").lower()
        if kind in {"cdr", "ipdr"} or (doc.get("ingest_stats") or {}).get("kind") in {
            "cdr",
            "ipdr",
        }:
            name = str(doc.get("original_filename") or "")
            variants = list(
                dict.fromkeys(
                    [
                        name,
                        Path(name).name,
                        str(doc.get("linked_source_file") or ""),
                        Path(str(doc.get("staged_path") or "")).name,
                    ]
                )
            )
            variants = [v for v in variants if v]
            msisdns = list(doc.get("linked_msisdns") or [])
            m = re.search(r"(?<!\d)(\d{10})(?!\d)", Path(name).stem)
            if m:
                msisdns.append(m.group(1))
            msisdns = list(dict.fromkeys(msisdns))
            tel_query: dict[str, Any] = {"$or": []}
            if variants:
                tel_query["$or"].append({"source_file": {"$in": variants}})
            if msisdns and kind == "cdr":
                # Only purge this A-party's CDR rows (not entire telecom collection)
                tel_query["$or"].append(
                    {"event_type": "CDR", "msisdn": {"$in": msisdns}}
                )
            if tel_query["$or"]:
                tel_res = await database["telecom_events"].delete_many(tel_query)
                purged["telecom_events"] = tel_res.deleted_count
                if kind == "ipdr":
                    ipdr_res = await database["ipdr"].delete_many(tel_query)
                    purged["ipdr"] = ipdr_res.deleted_count
                elif msisdns:
                    ipdr_res = await database["ipdr"].delete_many(
                        {"msisdn": {"$in": msisdns}}
                    )
                    purged["ipdr"] = ipdr_res.deleted_count

    await database["case_documents"].delete_one({"document_id": document_id})
    await database["audit_trail"].insert_one(
        {
            "timestamp": _now(),
            "user": "Investigator",
            "case_id": doc.get("case_id"),
            "action": (
                f"Deleted document {doc.get('original_filename')} ({document_id})"
                + (
                    f" and purged tx={purged['transactions']} entities={purged['entities']}"
                    f" telecom={purged['telecom_events']}"
                    if purge_data
                    else ""
                )
            ),
        }
    )
    return {"status": "ok", "deleted": document_id, "purged": purged}
