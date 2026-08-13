"""STR reports, investigator query, audit trail, IPDR summary."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .common import active_case, fmt_money
from .correlations import multi_source_hubs
from .scoring import build_leaderboard, risk_for_entity
from .timeline import build_timeline


async def build_str(database, entity_id: str) -> dict | None:
    entity = await database["entities"].find_one({"entity_id": entity_id}, {"_id": 0})
    if not entity:
        return None
    profile = await risk_for_entity(database, entity_id)
    timeline = await build_timeline(database, entity_id, limit=40) or {"events": []}
    accounts = [
        a.get("account_id")
        for a in (entity.get("accounts") or [])
        if isinstance(a, dict) and a.get("account_id")
    ]
    sample_tx = []
    if accounts:
        sample_tx = await database["transactions"].find(
            {"account_id": {"$in": accounts}}, {"_id": 0}
        ).sort("amount", -1).limit(15).to_list(15)
    return {
        "report_type": "Individual STR",
        "generated_at": datetime.utcnow().isoformat(sep=" ", timespec="seconds") + " UTC",
        "entity": entity,
        "risk_profile": profile,
        "highlight_transactions": sample_tx,
        "recent_multimodal_events": timeline.get("events", [])[:25],
        "narrative": (
            f"Suspicious Transaction Report for {entity.get('entity_name') or entity_id}. "
            f"Risk category: {(profile or {}).get('risk_category', 'N/A')} "
            f"(score {(profile or {}).get('risk_score', 0)}/100). "
            f"Observed {(profile or {}).get('transaction_count', 0)} bank movements, "
            f"{(profile or {}).get('cdr_count', 0)} CDR calls, "
            f"{(profile or {}).get('ipdr_count', 0)} IPDR sessions."
        ),
    }


async def append_audit(database, user: str, action: str, case_id: str | None = None) -> dict:
    if not case_id:
        case = await active_case(database)
        case_id = case.get("case_id")
    row = {
        "timestamp": datetime.utcnow().isoformat(sep=" ", timespec="seconds") + " UTC",
        "user": user,
        "action": action,
        "case_id": case_id,
    }
    await database["audit_trail"].insert_one(dict(row))
    return row


async def list_audit(database, limit: int = 100) -> list[dict]:
    rows = await database["audit_trail"].find({}, {"_id": 0}).sort(
        "timestamp", -1
    ).limit(limit).to_list(limit)
    if not rows:
        rows = [
            {
                "timestamp": datetime.utcnow().isoformat(sep=" ", timespec="seconds"),
                "user": "System",
                "action": "Audit trail ready. Investigator actions will appear here.",
            }
        ]
    return rows


async def run_query(database, q: str) -> list[dict]:
    text = q.lower().strip()
    results: list[dict] = []

    if any(k in text for k in ("ipdr", "ip ", "internet", "session")):
        ipdr = await database["telecom_events"].find(
            {"event_type": "IPDR"}, {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        results.append(
            {
                "title": "IPDR sessions",
                "count": len(ipdr),
                "items": [
                    {
                        "label": f"{i.get('msisdn') or '—'} @ {i.get('ip_address')}",
                        "href": f"/telecom/{i.get('event_id')}",
                        "meta": i.get("timestamp"),
                    }
                    for i in ipdr
                ],
            }
        )

    if any(k in text for k in ("cdr", "call", "phone")):
        cdr = await database["telecom_events"].find(
            {"event_type": "CDR"}, {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        results.append(
            {
                "title": "Recent CDR calls",
                "count": len(cdr),
                "items": [
                    {
                        "label": f"{c.get('msisdn')} → {c.get('b_party')}",
                        "href": f"/telecom/{c.get('event_id')}",
                        "meta": c.get("timestamp"),
                    }
                    for c in cdr
                ],
            }
        )

    if any(k in text for k in ("seed", "fir", "suspect", "convergence", "multi")):
        hubs = await multi_source_hubs(database, min_sources=2, limit=15)
        results.append(
            {
                "title": "Convergence hubs",
                "count": len(hubs),
                "items": [
                    {
                        "label": f"{h['destination']} ({h['distinct_source_count']} sources)",
                        "href": f"/transactions?q={h['destination']}",
                        "meta": fmt_money(float(h["total_amount"])),
                    }
                    for h in hubs
                ],
            }
        )

    if any(k in text for k in ("risk", "lead", "priority", "leaderboard")):
        board = await build_leaderboard(database, limit=15)
        results.append(
            {
                "title": "Top priority leads",
                "count": len(board),
                "items": [
                    {
                        "label": f"{b['entity_name']} — {b['risk_category']} ({b['risk_score']})",
                        "href": f"/entities/{b['entity_id']}",
                        "meta": f"IPDR:{b['ipdr_count']} CDR:{b['cdr_count']}",
                    }
                    for b in board
                ],
            }
        )

    pattern = re.escape(q.strip())
    entities = await database["entities"].find(
        {
            "$or": [
                {"entity_name": {"$regex": pattern, "$options": "i"}},
                {"entity_id": {"$regex": pattern, "$options": "i"}},
                {"phones": {"$regex": pattern, "$options": "i"}},
            ]
        },
        {"_id": 0, "entity_id": 1, "entity_name": 1},
    ).limit(15).to_list(15)
    if entities:
        results.append(
            {
                "title": "Matching people / accounts",
                "count": len(entities),
                "items": [
                    {
                        "label": e.get("entity_name") or e.get("entity_id"),
                        "href": f"/entities/{e.get('entity_id')}",
                        "meta": e.get("entity_id"),
                    }
                    for e in entities
                ],
            }
        )

    await append_audit(database, "Investigator", f'Executed case query: "{q}"')
    return results


async def ipdr_summary(database) -> dict[str, Any]:
    total = await database["telecom_events"].count_documents({"event_type": "IPDR"})
    with_phone = await database["telecom_events"].count_documents(
        {"event_type": "IPDR", "msisdn": {"$nin": [None, ""]}}
    )
    top_ips = await database["telecom_events"].aggregate(
        [
            {"$match": {"event_type": "IPDR", "ip_address": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$ip_address", "count": {"$sum": 1}, "phones": {"$addToSet": "$msisdn"}}},
            {"$sort": {"count": -1}},
            {"$limit": 20},
        ]
    ).to_list(20)
    top_phones = await database["telecom_events"].aggregate(
        [
            {"$match": {"event_type": "IPDR", "msisdn": {"$nin": [None, ""]}}},
            {
                "$group": {
                    "_id": "$msisdn",
                    "sessions": {"$sum": 1},
                    "up": {"$sum": "$data_volume_up"},
                    "down": {"$sum": "$data_volume_down"},
                }
            },
            {"$sort": {"sessions": -1}},
            {"$limit": 20},
        ]
    ).to_list(20)
    recent = await database["telecom_events"].find(
        {"event_type": "IPDR"}, {"_id": 0}
    ).sort("timestamp", -1).limit(50).to_list(50)
    return {
        "stats": {"total": total, "with_phone": with_phone},
        "top_ips": [
            {"ip": r["_id"], "count": r["count"], "phones": [p for p in r["phones"] if p]}
            for r in top_ips
        ],
        "top_phones": [
            {
                "msisdn": r["_id"],
                "sessions": r["sessions"],
                "data_volume_up": r.get("up") or 0,
                "data_volume_down": r.get("down") or 0,
            }
            for r in top_phones
        ],
        "recent": recent,
    }
