from __future__ import annotations

import re
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .. import db

router = APIRouter(prefix="/api", tags=["browse"])

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50

_OVERVIEW_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_OVERVIEW_TTL_SEC = 30.0

ENTITY_LIST_PROJECTION = {
    "_id": 0,
    "entity_id": 1,
    "entity_name": 1,
    "is_seed": 1,
    "account_role": 1,
    "phones": 1,
}

TX_LIST_PROJECTION = {
    "_id": 0,
    "transaction_id": 1,
    "transaction_date": 1,
    "account_id": 1,
    "direction": 1,
    "amount": 1,
    "counterparty_name": 1,
    "counterparty_account": 1,
    "mode": 1,
    "narration": 1,
}

TELECOM_LIST_PROJECTION = {
    "_id": 0,
    "event_id": 1,
    "timestamp": 1,
    "event_type": 1,
    "msisdn": 1,
    "b_party": 1,
    "ip_address": 1,
    "duration_sec": 1,
}


def _escape_regex(text: str) -> str:
    return re.escape(text.strip())


def _paginate(total: int, page: int, limit: int) -> dict[str, int]:
    pages = max(1, (total + limit - 1) // limit)
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages,
        "has_next": page < pages,
        "has_prev": page > 1,
    }


@router.get("/overview")
async def overview_stats():
    now = time.monotonic()
    if _OVERVIEW_CACHE["data"] is not None and (now - _OVERVIEW_CACHE["ts"]) < _OVERVIEW_TTL_SEC:
        return _OVERVIEW_CACHE["data"]

    database = db.get_db()
    entities_col = database["entities"]
    tx_col = database["transactions"]
    telecom_col = database["telecom_events"]

    entities_total = await entities_col.estimated_document_count()
    seeds_total = await entities_col.count_documents({"is_seed": True})
    transactions_total = await tx_col.estimated_document_count()
    telecom_total = await telecom_col.estimated_document_count()
    cdr_total = await telecom_col.count_documents({"event_type": "CDR"})
    ipdr_total = await database["ipdr"].estimated_document_count()
    if ipdr_total == 0:
        ipdr_total = await telecom_col.count_documents({"event_type": "IPDR"})

    credit_pipeline = [
        {"$match": {"direction": "CR"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    debit_pipeline = [
        {"$match": {"direction": "DR"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]
    credit_row = await tx_col.aggregate(credit_pipeline).to_list(length=1)
    debit_row = await tx_col.aggregate(debit_pipeline).to_list(length=1)

    payload = {
        "status": "ok",
        "stats": {
            "entities_total": entities_total,
            "seed_entities": seeds_total,
            "transactions_total": transactions_total,
            "telecom_events_total": telecom_total,
            "cdr_events": cdr_total,
            "ipdr_events": ipdr_total,
            "credit_total_amount": credit_row[0]["total"] if credit_row else 0,
            "credit_count": credit_row[0]["count"] if credit_row else 0,
            "debit_total_amount": debit_row[0]["total"] if debit_row else 0,
            "debit_count": debit_row[0]["count"] if debit_row else 0,
        },
    }
    _OVERVIEW_CACHE["ts"] = now
    _OVERVIEW_CACHE["data"] = payload
    return payload


@router.get("/entities")
async def list_entities(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = None,
    seed_only: bool = False,
):
    database = db.get_db()
    query: dict[str, Any] = {}
    if seed_only:
        query["is_seed"] = True
    if q and q.strip():
        pattern = _escape_regex(q)
        query["$or"] = [
            {"entity_id": {"$regex": pattern, "$options": "i"}},
            {"entity_name": {"$regex": pattern, "$options": "i"}},
            {"phones": {"$regex": pattern, "$options": "i"}},
            {"pan": {"$regex": pattern, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    total = await database["entities"].count_documents(query)
    cursor = (
        database["entities"]
        .find(query, ENTITY_LIST_PROJECTION)
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)

    return {
        "status": "ok",
        "items": items,
        "pagination": _paginate(total, page, limit),
    }


@router.get("/accounts")
async def list_accounts(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = None,
):
    database = db.get_db()
    query: dict[str, Any] = {}
    if q and q.strip():
        pattern = _escape_regex(q)
        query["$or"] = [
            {"account_id": {"$regex": pattern, "$options": "i"}},
            {"account_number": {"$regex": pattern, "$options": "i"}},
            {"holder_name": {"$regex": pattern, "$options": "i"}},
            {"bank_name": {"$regex": pattern, "$options": "i"}},
            {"ifsc": {"$regex": pattern, "$options": "i"}},
        ]
    skip = (page - 1) * limit
    total = await database["accounts"].count_documents(query)
    items = (
        await database["accounts"]
        .find(query, {"_id": 0})
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    return {
        "status": "ok",
        "items": items,
        "pagination": _paginate(total, page, limit),
    }


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    database = db.get_db()
    entity = await database["entities"].find_one({"entity_id": entity_id}, {"_id": 0})
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    account_ids = [
        a.get("account_id")
        for a in entity.get("accounts") or []
        if isinstance(a, dict) and a.get("account_id")
    ]
    phones = entity.get("phones") or []

    tx_count = 0
    if account_ids:
        tx_count = await database["transactions"].count_documents(
            {"account_id": {"$in": account_ids}}
        )
    telecom_count = 0
    if phones:
        telecom_count = await database["telecom_events"].count_documents(
            {"msisdn": {"$in": phones}}
        )

    recent_tx = []
    if account_ids:
        recent_tx = (
            await database["transactions"]
            .find({"account_id": {"$in": account_ids}}, TX_LIST_PROJECTION)
            .sort("transaction_date", -1)
            .limit(10)
            .to_list(length=10)
        )

    recent_telecom = []
    if phones:
        recent_telecom = (
            await database["telecom_events"]
            .find({"msisdn": {"$in": phones}}, TELECOM_LIST_PROJECTION)
            .sort("timestamp", -1)
            .limit(10)
            .to_list(length=10)
        )

    return {
        "status": "ok",
        "entity": entity,
        "related": {
            "transaction_count": tx_count,
            "telecom_count": telecom_count,
            "recent_transactions": recent_tx,
            "recent_telecom": recent_telecom,
        },
    }


def _fmt_tx_date(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        # Bank statements are usually date-only; hide useless midnight clock
        try:
            if value.hour == 0 and value.minute == 0 and value.second == 0:
                return value.strftime("%d-%b-%Y")
            return value.strftime("%d-%b-%Y %H:%M")
        except Exception:
            return str(value)[:19]
    text = str(value).strip()
    # ISO strings from Mongo / JSON (e.g. 2024-12-31T00:00:00)
    m = re.match(
        r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?",
        text,
    )
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        months = (
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        )
        label = f"{d}-{months[int(mo) - 1]}-{y}"
        hh, mm, ss = m.group(4), m.group(5), m.group(6) or "00"
        if hh and not (hh == "00" and mm == "00" and ss == "00"):
            return f"{label} {hh}:{mm}"
        return label
    return text[:16]


def _shape_telecom_rows(items: list[dict]) -> list[dict]:
    out = []
    for row in items:
        item = dict(row)
        item["timestamp"] = _fmt_tx_date(item.get("timestamp"))
        if item.get("event_type") == "IPDR" and not item.get("b_party"):
            item["b_party"] = item.get("ip_address") or ""
        dur = item.get("duration_sec")
        if dur is not None and str(dur).strip():
            try:
                d = int(float(dur))
                item["duration_sec"] = f"{d}s" if d < 3600 else f"{d // 60}m"
            except (TypeError, ValueError):
                pass
        out.append(item)
    return out


def _shape_tx_rows(items: list[dict]) -> list[dict]:
    out = []
    for row in items:
        item = dict(row)
        item["transaction_date"] = _fmt_tx_date(item.get("transaction_date"))
        if not item.get("counterparty_name") and item.get("narration"):
            item["counterparty_name"] = str(item.get("narration") or "")[:60]
        if not item.get("mode"):
            item["mode"] = "—"
        out.append(item)
    return out


@router.get("/transactions")
async def list_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = None,
    account_id: str | None = None,
    direction: str | None = None,
):
    database = db.get_db()
    query: dict[str, Any] = {}
    if account_id:
        query["account_id"] = account_id
    if direction:
        query["direction"] = direction.upper()
    if q and q.strip():
        pattern = _escape_regex(q)
        query["$or"] = [
            {"transaction_id": {"$regex": pattern, "$options": "i"}},
            {"account_id": {"$regex": pattern, "$options": "i"}},
            {"counterparty_name": {"$regex": pattern, "$options": "i"}},
            {"counterparty_account": {"$regex": pattern, "$options": "i"}},
            {"narration": {"$regex": pattern, "$options": "i"}},
            {"mode": {"$regex": pattern, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    total = await database["transactions"].count_documents(query)
    cursor = (
        database["transactions"]
        .find(query, TX_LIST_PROJECTION)
        .sort([("transaction_date", -1), ("transaction_id", -1)])
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)

    return {
        "status": "ok",
        "items": _shape_tx_rows(items),
        "pagination": _paginate(total, page, limit),
        "sort": "transaction_date desc (newest first)",
    }


@router.get("/transactions/{transaction_id}")
async def get_transaction(transaction_id: str):
    database = db.get_db()
    tx = await database["transactions"].find_one(
        {"transaction_id": transaction_id}, {"_id": 0}
    )
    if not tx:
        raise HTTPException(
            status_code=404, detail=f"Transaction '{transaction_id}' not found"
        )

    entity = None
    account_id = tx.get("account_id")
    if account_id:
        entity = await database["entities"].find_one(
            {"accounts.account_id": account_id},
            {"_id": 0, "entity_id": 1, "entity_name": 1, "phones": 1, "accounts": 1},
        )

    related_same_account = (
        await database["transactions"]
        .find({"account_id": account_id}, TX_LIST_PROJECTION)
        .sort("transaction_date", -1)
        .limit(10)
        .to_list(length=10)
    )

    related_counterparty = []
    cp_name = tx.get("counterparty_name")
    if cp_name:
        related_counterparty = (
            await database["transactions"]
            .find({"counterparty_name": cp_name}, TX_LIST_PROJECTION)
            .sort("transaction_date", -1)
            .limit(10)
            .to_list(length=10)
        )

    return {
        "status": "ok",
        "transaction": tx,
        "entity": entity,
        "related": {
            "same_account": related_same_account,
            "same_counterparty_name": related_counterparty,
        },
    }


@router.get("/telecom")
async def list_telecom(
    page: int = Query(1, ge=1),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    q: str | None = None,
    event_type: str | None = None,
    msisdn: str | None = None,
):
    database = db.get_db()
    query: dict[str, Any] = {}
    if event_type:
        query["event_type"] = event_type.upper()
    if msisdn:
        query["msisdn"] = msisdn
    if q and q.strip():
        pattern = _escape_regex(q)
        query["$or"] = [
            {"event_id": {"$regex": pattern, "$options": "i"}},
            {"msisdn": {"$regex": pattern, "$options": "i"}},
            {"b_party": {"$regex": pattern, "$options": "i"}},
            {"ip_address": {"$regex": pattern, "$options": "i"}},
            {"call_type": {"$regex": pattern, "$options": "i"}},
        ]

    skip = (page - 1) * limit
    total = await database["telecom_events"].count_documents(query)
    cursor = (
        database["telecom_events"]
        .find(query, TELECOM_LIST_PROJECTION)
        .sort("timestamp", -1)
        .skip(skip)
        .limit(limit)
    )
    items = await cursor.to_list(length=limit)

    return {
        "status": "ok",
        "items": _shape_telecom_rows(items),
        "pagination": _paginate(total, page, limit),
        "sort": "timestamp desc (newest first)",
    }


@router.get("/telecom/{event_id}")
async def get_telecom_event(event_id: str):
    database = db.get_db()
    event = await database["telecom_events"].find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail=f"Telecom event '{event_id}' not found")

    entity = None
    msisdn = event.get("msisdn")
    if msisdn:
        entity = await database["entities"].find_one(
            {"phones": msisdn},
            {"_id": 0, "entity_id": 1, "entity_name": 1, "phones": 1},
        )

    related = []
    if msisdn:
        related = (
            await database["telecom_events"]
            .find({"msisdn": msisdn}, TELECOM_LIST_PROJECTION)
            .sort("timestamp", -1)
            .limit(10)
            .to_list(length=10)
        )

    return {
        "status": "ok",
        "event": event,
        "entity": entity,
        "related": {"same_msisdn": related},
    }
