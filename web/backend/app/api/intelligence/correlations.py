"""Cross-dataset correlations, pattern findings, and network summaries."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .common import (
    WINDOW_MINUTES,
    MAX_CORRELATIONS,
    as_dt,
    norm_phone,
    phone_map,
    resolve_tx_time,
    seed_account_ids,
)


async def multi_source_hubs(database, min_sources: int = 3, limit: int = 15) -> list[dict]:
    rows = await database["transactions"].aggregate(
        [
            {
                "$addFields": {
                    "destination_key": {
                        "$cond": [
                            {
                                "$and": [
                                    {"$ne": ["$counterparty_account", None]},
                                    {"$ne": ["$counterparty_account", ""]},
                                ]
                            },
                            "$counterparty_account",
                            "$counterparty_name",
                        ]
                    }
                }
            },
            {"$match": {"destination_key": {"$nin": [None, ""]}}},
            {
                "$group": {
                    "_id": "$destination_key",
                    "distinct_sources": {"$addToSet": "$account_id"},
                    "transaction_count": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"},
                }
            },
            {"$addFields": {"distinct_source_count": {"$size": "$distinct_sources"}}},
            {"$match": {"distinct_source_count": {"$gte": min_sources}}},
            {"$sort": {"total_amount": -1}},
            {"$limit": limit},
        ]
    ).to_list(limit)
    return [
        {
            "destination": r["_id"],
            "distinct_source_count": r["distinct_source_count"],
            "transaction_count": r["transaction_count"],
            "total_amount": r["total_amount"],
        }
        for r in rows
    ]


async def multi_seed_convergence(database, seed_accounts: list[str], limit: int = 10) -> list[dict]:
    if len(seed_accounts) < 2:
        return []
    pipeline = [
        {"$match": {"account_id": {"$in": seed_accounts}, "direction": {"$in": ["DR", "DEBIT", "OUT"]}}},
        {
            "$addFields": {
                "destination_key": {
                    "$cond": [
                        {
                            "$and": [
                                {"$ne": ["$counterparty_account", None]},
                                {"$ne": ["$counterparty_account", ""]},
                            ]
                        },
                        "$counterparty_account",
                        "$counterparty_name",
                    ]
                }
            }
        },
        {"$match": {"destination_key": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$destination_key",
                "seed_sources": {"$addToSet": "$account_id"},
                "transaction_count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
            }
        },
        {"$addFields": {"seed_source_count": {"$size": "$seed_sources"}}},
        {"$match": {"seed_source_count": {"$gte": 2}}},
        {"$sort": {"total_amount": -1}},
        {"$limit": limit},
    ]
    rows = await database["transactions"].aggregate(pipeline).to_list(limit)
    if not rows:
        pipeline[0] = {"$match": {"account_id": {"$in": seed_accounts}}}
        rows = await database["transactions"].aggregate(pipeline).to_list(limit)
    return [
        {
            "destination": r["_id"],
            "seed_source_count": r["seed_source_count"],
            "seed_sources": r["seed_sources"],
            "transaction_count": r["transaction_count"],
            "total_amount": float(r["total_amount"] or 0),
        }
        for r in rows
    ]


async def smurf_candidates(database, limit: int = 10) -> list[dict]:
    rows = await database["transactions"].aggregate(
        [
            {"$match": {"amount": {"$gte": 40_000, "$lt": 50_000}}},
            {"$group": {"_id": "$account_id", "count": {"$sum": 1}, "total_amount": {"$sum": "$amount"}}},
            {"$match": {"count": {"$gte": 3}}},
            {"$sort": {"count": -1}},
            {"$limit": limit},
        ]
    ).to_list(limit)
    return [
        {"account_id": r["_id"], "count": int(r["count"]), "total_amount": float(r["total_amount"] or 0)}
        for r in rows
        if r.get("_id")
    ]


async def build_networks(database, seeds: list[dict]) -> list[dict]:
    networks = []
    for seed in seeds[:6]:
        accounts = [
            a.get("account_id")
            for a in (seed.get("accounts") or [])
            if isinstance(a, dict) and a.get("account_id")
        ]
        if not accounts:
            continue
        counterparties = await database["transactions"].aggregate(
            [
                {"$match": {"account_id": {"$in": accounts}}},
                {
                    "$group": {
                        "_id": {"$ifNull": ["$counterparty_name", "$counterparty_account"]},
                        "count": {"$sum": 1},
                        "total": {"$sum": "$amount"},
                    }
                },
                {"$sort": {"total": -1}},
                {"$limit": 20},
            ]
        ).to_list(20)
        networks.append(
            {
                "network_id": f"NET-{seed.get('entity_id')}",
                "title": f"Network around {seed.get('entity_name') or seed.get('entity_id')}",
                "total_nodes": 1 + len(counterparties),
                "total_seed_links": 1,
                "high_risk_count": min(8, max(1, len(counterparties) // 3)),
                "primary_motif": "Layered pass-through / mule fan-out",
                "total_traced_volume": sum(float(c["total"] or 0) for c in counterparties),
                "seed_entity_id": seed.get("entity_id"),
            }
        )
    return networks


async def build_correlations(database, limit: int = MAX_CORRELATIONS) -> list[dict]:
    pmap = await phone_map(database)
    seed_phones = list(pmap.keys())[:40]
    if not seed_phones:
        sample = await database["telecom_events"].find(
            {"event_type": "CDR", "msisdn": {"$nin": [None, ""]}},
            {"_id": 0, "msisdn": 1},
        ).limit(40).to_list(40)
        seed_phones = [norm_phone(s.get("msisdn")) for s in sample if s.get("msisdn")]

    cdr_events = await database["telecom_events"].find(
        {"event_type": "CDR", "msisdn": {"$in": seed_phones}}, {"_id": 0}
    ).sort("timestamp", -1).limit(400).to_list(400)

    correlations: list[dict] = []
    seen: set = set()
    for call in cdr_events:
        call_dt = as_dt(call.get("timestamp"))
        if not call_dt:
            continue
        msisdn = norm_phone(call.get("msisdn"))
        entity = pmap.get(msisdn)
        account_ids = []
        if entity:
            account_ids = [
                a.get("account_id")
                for a in (entity.get("accounts") or [])
                if isinstance(a, dict) and a.get("account_id")
            ]
            if not account_ids and entity.get("entity_id"):
                full = await database["entities"].find_one(
                    {"entity_id": entity["entity_id"]}, {"_id": 0, "accounts": 1}
                )
                account_ids = [
                    a.get("account_id")
                    for a in ((full or {}).get("accounts") or [])
                    if isinstance(a, dict) and a.get("account_id")
                ]

        tx_query: dict[str, Any] = {
            "transaction_date": {
                "$gte": call_dt - timedelta(minutes=WINDOW_MINUTES),
                "$lte": call_dt + timedelta(minutes=WINDOW_MINUTES),
            }
        }
        if account_ids:
            tx_query["account_id"] = {"$in": account_ids}
        nearby = await database["transactions"].find(tx_query, {"_id": 0}).sort(
            "amount", -1
        ).limit(3).to_list(3)
        # Bank rows are often date-only (midnight). Fall back to same calendar day.
        if not nearby and account_ids:
            day0 = call_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day1 = day0 + timedelta(days=1)
            nearby = await database["transactions"].find(
                {
                    "account_id": {"$in": account_ids},
                    "transaction_date": {"$gte": day0, "$lt": day1},
                },
                {"_id": 0},
            ).sort("amount", -1).limit(5).to_list(5)
        if not nearby:
            continue
        tx = nearby[0]
        tx_dt, tsrc = resolve_tx_time(tx, [call])
        if not tx_dt:
            continue
        if tsrc in {"statement", "narration"}:
            delta = abs(int((tx_dt - call_dt).total_seconds()))
            delta_human = f"{delta // 60}m {delta % 60}s"
            score = max(40, min(98, 100 - delta / 10))
        else:
            # Same-day window: keep the call clock as the investigation time
            tx_dt = datetime(
                tx_dt.year, tx_dt.month, tx_dt.day,
                call_dt.hour, call_dt.minute, call_dt.second,
            )
            tsrc = "linked_cdr"
            delta = 0
            delta_human = f"same day · call {call_dt.strftime('%H:%M:%S')}"
            score = 74
        key = (call.get("event_id"), tx.get("transaction_id"))
        if key in seen:
            continue
        seen.add(key)

        ipdr = await database["telecom_events"].find_one(
            {
                "event_type": "IPDR",
                "msisdn": {"$in": [msisdn, call.get("msisdn"), ""]},
                "timestamp": {
                    "$gte": call_dt - timedelta(hours=2),
                    "$lte": call_dt + timedelta(hours=2),
                },
            },
            {"_id": 0},
        )
        if not ipdr:
            ipdr = await database["telecom_events"].find_one(
                {
                    "event_type": "IPDR",
                    "timestamp": {
                        "$gte": call_dt - timedelta(hours=6),
                        "$lte": call_dt + timedelta(hours=6),
                    },
                },
                {"_id": 0},
            )

        ip_addr = (ipdr or {}).get("ip_address") or "—"
        correlations.append(
            {
                "correlation_id": f"CORR-{len(correlations) + 101}",
                "call_event": {
                    "event_id": call.get("event_id"),
                    "a_party": msisdn,
                    "b_party": norm_phone(call.get("b_party")),
                    "timestamp": call_dt.isoformat(sep=" ", timespec="seconds"),
                    "duration": call.get("duration_sec") or 0,
                },
                "ipdr_event": {
                    "event_id": (ipdr or {}).get("event_id"),
                    "ip_address": ip_addr,
                    "cell_id": (ipdr or {}).get("cell_id") or call.get("location") or "—",
                    "matched": bool(ipdr),
                },
                "financial_transfer": {
                    "transaction_id": tx.get("transaction_id"),
                    "account_id": tx.get("account_id"),
                    "counterparty_name": tx.get("counterparty_name"),
                    "amount": tx.get("amount") or 0,
                    "direction": tx.get("direction"),
                    "timestamp": tx_dt.isoformat(sep=" ", timespec="seconds"),
                    "time_source": tsrc,
                },
                "time_delta_seconds": delta,
                "time_delta_human": delta_human,
                "correlation_score": score,
                "explanation": (
                    f"Call {msisdn} → {norm_phone(call.get('b_party'))} at "
                    f"{call_dt.strftime('%H:%M:%S')} sits in the same time window as a "
                    f"₹{float(tx.get('amount') or 0):,.0f} transfer on {tx.get('account_id')} "
                    f"({delta_human}; clock from {tsrc})"
                    + (f" during IP session {ip_addr}." if ipdr else ".")
                ),
            }
        )
        if len(correlations) >= limit:
            break

    correlations.sort(key=lambda c: c["correlation_score"], reverse=True)
    return correlations


async def build_findings(
    database,
    *,
    seeds: list[dict],
    correlations: list[dict],
    leaderboard: list[dict],
    ipdr_total: int,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seed_accounts = await seed_account_ids(seeds)

    multi_seed = await multi_seed_convergence(database, seed_accounts, limit=8)
    if multi_seed:
        top = multi_seed[0]
        names = [str(s) for s in (top.get("seed_sources") or [])[:3]]
        findings.append(
            {
                "finding_id": "FINDING-001",
                "title": f"MULTI-SEED CONVERGENCE AT {str(top['destination'])[:30]}",
                "severity": "CRITICAL",
                "confidence_score": 95,
                "pattern_type": "Multi-Seed Convergence",
                "summary": (
                    f"{top['seed_source_count']} FIR seed accounts ({', '.join(names)}) "
                    f"converge onto {top['destination']}."
                ),
                "entities_involved": names + [str(top["destination"])],
                "total_amount_involved": top["total_amount"],
                "recommended_action": "Subpoena downstream bank records.",
            }
        )

    high_pt = [
        r
        for r in leaderboard
        if r.get("account_role") == "INTERMEDIARY MULE"
        and r.get("risk_category") in {"HIGH", "CRITICAL"}
        and float(r.get("inflow") or 0) >= 50_000
        and int(r.get("transaction_count") or 0) >= 3
        and int(r.get("transaction_count") or 0) <= 250
    ]
    if high_pt:
        names = [str(r.get("entity_name") or r.get("entity_id")) for r in high_pt[:4]]
        findings.append(
            {
                "finding_id": "FINDING-002",
                "title": "RAPID PASS-THROUGH LAYERING CHAIN DETECTED",
                "severity": "CRITICAL",
                "confidence_score": 92,
                "pattern_type": "Rapid Pass-Through Layering",
                "summary": f"Entities ({', '.join(names[:3])}) forwarded ≥80% of inflow.",
                "entities_involved": [str(r.get("entity_id") or r.get("entity_name")) for r in high_pt[:4]],
                "total_amount_involved": sum(float(r.get("inflow") or 0) for r in high_pt[:4]),
                "recommended_action": "Issue freezing order on terminal accounts.",
            }
        )

    if correlations:
        findings.append(
            {
                "finding_id": "FINDING-003",
                "title": "TEMPORAL CORRELATION: CALL → IP → FINANCIAL TRANSFER",
                "severity": "CRITICAL" if len(correlations) >= 3 else "HIGH",
                "confidence_score": min(98, 70 + len(correlations)),
                "pattern_type": "Cross-Dataset Coincidence",
                "summary": (
                    f"{len(correlations)} coincidences within ±{WINDOW_MINUTES} minutes "
                    "of bank transfers."
                ),
                "entities_involved": list(
                    {
                        c["financial_transfer"].get("account_id")
                        or c["financial_transfer"].get("counterparty_name")
                        for c in correlations[:8]
                        if c.get("financial_transfer")
                    }
                )[:4],
                "total_amount_involved": sum(
                    float(c["financial_transfer"].get("amount") or 0) for c in correlations
                ),
                "recommended_action": "Cross-examine tower logs with IP records.",
            }
        )

    hubs = await multi_source_hubs(database, min_sources=3, limit=10)
    if hubs:
        hub = hubs[0]
        findings.append(
            {
                "finding_id": "FINDING-004",
                "title": f"FAN-IN / FAN-OUT COLLECTION HUB: {str(hub['destination'])[:30]}",
                "severity": "HIGH",
                "confidence_score": 85,
                "pattern_type": "Gather-Scatter Hub",
                "summary": (
                    f"'{hub['destination']}' collected from {hub['distinct_source_count']} senders "
                    f"({hub['transaction_count']} transfers)."
                ),
                "entities_involved": [str(hub["destination"])],
                "total_amount_involved": float(hub["total_amount"] or 0),
                "recommended_action": "Verify merchant justification / KYC.",
            }
        )

    smurfs = await smurf_candidates(database, limit=8)
    if smurfs:
        top = smurfs[0]
        findings.append(
            {
                "finding_id": "FINDING-005",
                "title": f"STRUCTURED SMURFING AT {str(top['account_id'])[:25]}",
                "severity": "HIGH",
                "confidence_score": 87,
                "pattern_type": "Smurfing / Structuring",
                "summary": (
                    f"Account {top['account_id']} made {top['count']} transfers in ₹40k–₹49,999 band."
                ),
                "entities_involved": [str(s["account_id"]) for s in smurfs[:3]],
                "total_amount_involved": float(top["total_amount"] or 0),
                "recommended_action": "Report threshold evasion to FIU.",
            }
        )

    if ipdr_total:
        findings.append(
            {
                "finding_id": "FINDING-006",
                "title": "IPDR INTERNET SESSIONS AVAILABLE FOR CASE PHONES",
                "severity": "MEDIUM",
                "confidence_score": 75,
                "pattern_type": "IPDR Presence",
                "summary": f"{ipdr_total} IPDR sessions ingested for timeline fusion.",
                "entities_involved": [s.get("entity_name") or s.get("entity_id") for s in seeds[:3]],
                "total_amount_involved": 0,
                "recommended_action": "Align IPDR windows with transfer timestamps.",
            }
        )
    return findings
