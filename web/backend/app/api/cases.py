"""Case registry — track all FIR / investigation workspaces."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import db

router = APIRouter(prefix="/api/cases", tags=["cases"])


class CaseCreate(BaseModel):
    case_id: str = Field(..., min_length=3, max_length=64)
    title: str = Field(..., min_length=3, max_length=200)
    unit: str = "Special Financial Cybercrime Unit"
    lead_investigator: str = "Inspector V. Sharma"
    fir_number: str | None = None
    police_station: str | None = None
    status: str = "open"  # open | active | closed | archived
    notes: str | None = None
    seed_entity_ids: list[str] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: str | None = None
    unit: str | None = None
    lead_investigator: str | None = None
    fir_number: str | None = None
    police_station: str | None = None
    status: str | None = None
    notes: str | None = None
    seed_entity_ids: list[str] | None = None


def _now() -> str:
    return datetime.utcnow().isoformat(sep=" ", timespec="seconds") + " UTC"


async def _case_stats(database, case: dict) -> dict[str, Any]:
    """Attach live evidence counts. Currently one shared evidence DB; scoped by seeds when present."""
    seed_ids = case.get("seed_entity_ids") or []
    entities_q: dict[str, Any] = {}
    if seed_ids:
        entities_q = {"entity_id": {"$in": seed_ids}}

    if seed_ids:
        seed_docs = await database["entities"].find(
            {"entity_id": {"$in": seed_ids}}, {"_id": 0, "accounts": 1, "phones": 1}
        ).to_list(200)
        account_ids: list[str] = []
        phones: list[str] = []
        for ent in seed_docs:
            for a in ent.get("accounts") or []:
                if isinstance(a, dict) and a.get("account_id"):
                    account_ids.append(a["account_id"])
            for p in ent.get("phones") or []:
                if p:
                    phones.append(str(p))
        tx_count = (
            await database["transactions"].count_documents(
                {"account_id": {"$in": account_ids}}
            )
            if account_ids
            else 0
        )
        cdr_count = (
            await database["telecom_events"].count_documents(
                {"event_type": "CDR", "msisdn": {"$in": phones}}
            )
            if phones
            else 0
        )
        ipdr_count = (
            await database["telecom_events"].count_documents(
                {"event_type": "IPDR", "msisdn": {"$in": phones}}
            )
            if phones
            else 0
        )
        entity_count = len(seed_ids)
    else:
        entity_count = await database["entities"].estimated_document_count()
        tx_count = await database["transactions"].estimated_document_count()
        cdr_count = await database["telecom_events"].count_documents({"event_type": "CDR"})
        ipdr_count = await database["telecom_events"].count_documents({"event_type": "IPDR"})

    audit_count = await database["audit_trail"].count_documents(
        {"case_id": case.get("case_id")}
    )

    return {
        "seed_count": len(seed_ids) if seed_ids else await database["entities"].count_documents({"is_seed": True}),
        "entity_count": entity_count,
        "transaction_count": tx_count,
        "cdr_count": cdr_count,
        "ipdr_count": ipdr_count,
        "audit_entries": audit_count,
        "total_events": tx_count + cdr_count + ipdr_count,
    }


async def ensure_default_case(database) -> dict:
    """Bootstrap FIR-2026-0417 from current Mongo evidence if registry is empty."""
    existing = await database["cases"].find_one({"case_id": "FIR-2026-0417"}, {"_id": 0})
    if existing:
        return existing

    seeds = await database["entities"].find(
        {"is_seed": True}, {"_id": 0, "entity_id": 1}
    ).to_list(100)
    seed_ids = [s["entity_id"] for s in seeds if s.get("entity_id")]

    case = {
        "case_id": "FIR-2026-0417",
        "title": "Unified Financial Cybercrime & Laundering Investigation",
        "unit": "Special Financial Cybercrime Unit",
        "lead_investigator": "Inspector V. Sharma",
        "fir_number": "FIR-2026-0417",
        "police_station": "Cyber Crime PS",
        "status": "active",
        "notes": "Auto-created from ingested bank + CDR + IPDR evidence.",
        "seed_entity_ids": seed_ids,
        "created_at": _now(),
        "updated_at": _now(),
        "last_opened_at": _now(),
    }
    await database["cases"].update_one(
        {"case_id": case["case_id"]}, {"$setOnInsert": case}, upsert=True
    )
    await database["audit_trail"].insert_one(
        {
            "timestamp": _now(),
            "user": "System",
            "case_id": case["case_id"],
            "action": f"Case registry initialized with {case['case_id']}.",
        }
    )
    return case


@router.get("")
async def list_cases():
    database = db.get_db()
    await ensure_default_case(database)
    rows = await database["cases"].find({}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    enriched = []
    for case in rows:
        stats = await _case_stats(database, case)
        enriched.append({**case, "stats": stats})
    active = next((c for c in enriched if c.get("status") == "active"), None)
    return {
        "status": "ok",
        "count": len(enriched),
        "active_case_id": active["case_id"] if active else None,
        "cases": enriched,
    }


@router.get("/active")
async def get_active_case():
    database = db.get_db()
    await ensure_default_case(database)
    case = await database["cases"].find_one({"status": "active"}, {"_id": 0})
    if not case:
        case = await database["cases"].find_one({}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="No cases found")
    stats = await _case_stats(database, case)
    return {"status": "ok", "case": {**case, "stats": stats}}


@router.get("/{case_id}")
async def get_case(case_id: str):
    database = db.get_db()
    case = await database["cases"].find_one({"case_id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")
    stats = await _case_stats(database, case)
    seeds = []
    if case.get("seed_entity_ids"):
        seeds = await database["entities"].find(
            {"entity_id": {"$in": case["seed_entity_ids"]}},
            {"_id": 0, "entity_id": 1, "entity_name": 1, "is_seed": 1, "phones": 1},
        ).to_list(100)
    recent_audit = await database["audit_trail"].find(
        {"case_id": case_id}, {"_id": 0}
    ).sort("timestamp", -1).limit(20).to_list(20)
    return {
        "status": "ok",
        "case": {**case, "stats": stats},
        "seed_entities": seeds,
        "recent_audit": recent_audit,
    }


@router.post("")
async def create_case(payload: CaseCreate):
    database = db.get_db()
    case_id = payload.case_id.strip().upper()
    exists = await database["cases"].find_one({"case_id": case_id})
    if exists:
        raise HTTPException(status_code=409, detail=f"Case '{case_id}' already exists")

    # Only one active case at a time
    if payload.status == "active":
        await database["cases"].update_many(
            {"status": "active"}, {"$set": {"status": "open", "updated_at": _now()}}
        )

    case = {
        "case_id": case_id,
        "title": payload.title.strip(),
        "unit": payload.unit.strip(),
        "lead_investigator": payload.lead_investigator.strip(),
        "fir_number": (payload.fir_number or case_id).strip(),
        "police_station": (payload.police_station or "").strip(),
        "status": payload.status if payload.status in {"open", "active", "closed", "archived"} else "open",
        "notes": (payload.notes or "").strip(),
        "seed_entity_ids": payload.seed_entity_ids,
        "created_at": _now(),
        "updated_at": _now(),
        "last_opened_at": None,
    }
    await database["cases"].insert_one(dict(case))
    await database["audit_trail"].insert_one(
        {
            "timestamp": _now(),
            "user": "Investigator",
            "case_id": case_id,
            "action": f"Created case {case_id}: {case['title']}",
        }
    )
    case.pop("_id", None)
    stats = await _case_stats(database, case)
    return {"status": "ok", "case": {**case, "stats": stats}}


@router.patch("/{case_id}")
async def update_case(case_id: str, payload: CaseUpdate):
    database = db.get_db()
    case = await database["cases"].find_one({"case_id": case_id})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "status" in updates and updates["status"] == "active":
        await database["cases"].update_many(
            {"status": "active", "case_id": {"$ne": case_id}},
            {"$set": {"status": "open", "updated_at": _now()}},
        )
    updates["updated_at"] = _now()
    await database["cases"].update_one({"case_id": case_id}, {"$set": updates})
    await database["audit_trail"].insert_one(
        {
            "timestamp": _now(),
            "user": "Investigator",
            "case_id": case_id,
            "action": f"Updated case {case_id}: {', '.join(updates.keys())}",
        }
    )
    refreshed = await database["cases"].find_one({"case_id": case_id}, {"_id": 0})
    stats = await _case_stats(database, refreshed or {})
    return {"status": "ok", "case": {**(refreshed or {}), "stats": stats}}


@router.post("/{case_id}/open")
async def open_case(case_id: str):
    """Set this case as the active workspace."""
    database = db.get_db()
    case = await database["cases"].find_one({"case_id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found")

    await database["cases"].update_many(
        {"status": "active"}, {"$set": {"status": "open", "updated_at": _now()}}
    )
    await database["cases"].update_one(
        {"case_id": case_id},
        {
            "$set": {
                "status": "active",
                "last_opened_at": _now(),
                "updated_at": _now(),
            }
        },
    )
    await database["audit_trail"].insert_one(
        {
            "timestamp": _now(),
            "user": "Investigator",
            "case_id": case_id,
            "action": f"Opened case workspace {case_id}",
        }
    )
    refreshed = await database["cases"].find_one({"case_id": case_id}, {"_id": 0})
    stats = await _case_stats(database, refreshed or {})
    return {"status": "ok", "case": {**(refreshed or {}), "stats": stats}}
