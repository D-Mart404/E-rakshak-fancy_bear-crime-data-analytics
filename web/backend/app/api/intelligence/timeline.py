"""Timeline stream, suspicious episodes, heatmap, and money-flow sankey."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .common import (
    MAX_SANKEY,
    as_dt,
    entity_accounts,
    fmt_timeline_ts,
    has_clock_time,
    norm_phone,
    resolve_tx_time,
    seed_account_ids,
    seed_entities,
)
from .correlations import build_correlations
from .scoring import build_leaderboard


async def build_sankey(database, limit: int = MAX_SANKEY) -> list[dict]:
    rows = await database["transactions"].aggregate(
        [
            {
                "$addFields": {
                    "target": {
                        "$ifNull": [
                            {
                                "$cond": [
                                    {
                                        "$and": [
                                            {"$ne": ["$counterparty_name", None]},
                                            {"$ne": ["$counterparty_name", ""]},
                                        ]
                                    },
                                    "$counterparty_name",
                                    "$counterparty_account",
                                ]
                            },
                            "UNKNOWN",
                        ]
                    }
                }
            },
            {"$match": {"target": {"$nin": [None, "", "UNKNOWN"]}}},
            {
                "$group": {
                    "_id": {"source": "$account_id", "target": "$target"},
                    "amount": {"$sum": "$amount"},
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"amount": -1}},
            {"$limit": limit},
        ]
    ).to_list(limit)
    return [
        {
            "source": r["_id"]["source"],
            "target": r["_id"]["target"],
            "amount": r["amount"],
            "count": r["count"],
        }
        for r in rows
    ]


async def build_timeline(
    database, entity_id: str, source: str | None = None, limit: int = 200
) -> dict | None:
    entity = await database["entities"].find_one({"entity_id": entity_id}, {"_id": 0})
    if not entity:
        return None
    accounts = await entity_accounts(entity)
    phones = [norm_phone(p) for p in (entity.get("phones") or []) if p]
    events: list[dict] = []
    src = (source or "").upper()
    related_tel: list[dict] = []
    if phones:
        related_tel = (
            await database["telecom_events"]
            .find({"msisdn": {"$in": phones}}, {"_id": 0, "timestamp": 1, "event_type": 1, "event_id": 1})
            .sort("timestamp", -1)
            .limit(800)
            .to_list(800)
        )

    if src in ("", "BANK") and accounts:
        for t in await database["transactions"].find(
            {"account_id": {"$in": accounts}}, {"_id": 0}
        ).sort("transaction_date", -1).limit(limit).to_list(limit):
            resolved, tsrc = resolve_tx_time(t, related_tel)
            display, precision = fmt_timeline_ts(resolved, tsrc)
            events.append(
                {
                    "source": "BANK",
                    "timestamp": display,
                    "time_precision": precision,
                    "ref": t.get("transaction_id"),
                    "title": f"{t.get('direction')} ₹{t.get('amount')}",
                    "detail": t.get("counterparty_name") or t.get("narration") or "",
                    "href": f"/transactions/{t.get('transaction_id')}",
                    "_sort": resolved or datetime.min,
                }
            )

    if src in ("", "CDR", "IPDR") and phones:
        q: dict[str, Any] = {"msisdn": {"$in": phones}}
        if src in ("CDR", "IPDR"):
            q["event_type"] = src
        for e in await database["telecom_events"].find(q, {"_id": 0}).sort(
            "timestamp", -1
        ).limit(limit).to_list(limit):
            et = e.get("event_type")
            if et == "IPDR":
                title = f"IPDR {e.get('ip_address') or 'session'}"
                detail = f"↑{e.get('data_volume_up') or 0} ↓{e.get('data_volume_down') or 0}"
            else:
                title = f"CDR → {e.get('b_party') or '—'}"
                detail = f"{e.get('call_type') or ''} {e.get('duration_sec') or 0}s"
            display, precision = fmt_timeline_ts(e.get("timestamp"), "clock")
            events.append(
                {
                    "source": et,
                    "timestamp": display,
                    "time_precision": precision,
                    "ref": e.get("event_id"),
                    "title": title,
                    "detail": detail,
                    "href": f"/telecom/{e.get('event_id')}",
                    "_sort": as_dt(e.get("timestamp")) or datetime.min,
                }
            )

    events.sort(key=lambda ev: ev.get("_sort") or datetime.min, reverse=True)
    events = events[:limit]
    for ev in events:
        ev.pop("_sort", None)
    return {
        "entity": entity,
        "counts": {
            "bank": sum(1 for e in events if e["source"] == "BANK"),
            "cdr": sum(1 for e in events if e["source"] == "CDR"),
            "ipdr": sum(1 for e in events if e["source"] == "IPDR"),
            "total": len(events),
        },
        "events": events,
    }


async def build_episodes(database, limit: int = 15) -> list[dict]:
    episodes: list[dict] = []
    for i, c in enumerate(await build_correlations(database, limit=max(limit, 20))):
        ip_ok = bool(c.get("ipdr_event", {}).get("matched"))
        score = min(98, int(c.get("correlation_score") or 50) + (8 if ip_ok else 0))
        evidence = []
        for kind, obj, path in (
            ("CDR", c.get("call_event") or {}, "/telecom/"),
            ("IPDR", c.get("ipdr_event") or {}, "/telecom/"),
            ("BANK", c.get("financial_transfer") or {}, "/transactions/"),
        ):
            rid = obj.get("event_id") or obj.get("transaction_id")
            if rid:
                evidence.append({"id": str(rid), "type": kind, "href": f"{path}{rid}"})
        ft, call = c.get("financial_transfer") or {}, c.get("call_event") or {}
        episodes.append(
            {
                "episode_id": f"TMP-{i}",
                "title": "Call → Transfer coincidence",
                "time_window_str": str(call.get("timestamp") or ""),
                "duration_human": c.get("time_delta_human") or "±10m",
                "calls_count": 1,
                "ip_sessions_count": 1 if ip_ok else 0,
                "transactions_count": 1,
                "total_money_moved_inr": float(ft.get("amount") or 0),
                "entities_involved": [ft.get("account_id"), call.get("a_party")],
                "detected_typologies": [
                    "Call-Transfer Coincidence",
                    *(["IPDR Session Overlap"] if ip_ok else []),
                ],
                "episode_score": score,
                "severity": "CRITICAL" if score >= 80 else "HIGH" if score >= 60 else "MEDIUM",
                "event_density_ratio": round(
                    1 + (10 - min(10, float(c.get("time_delta_seconds") or 0) / 60)), 1
                ),
                "plain_narrative": c.get("explanation"),
                "raw_evidence_ids": [e["id"] for e in evidence],
                "raw_evidence": evidence,
            }
        )

    seeds = await seed_entities(database)
    seed_accounts = await seed_account_ids(seeds)
    if seed_accounts:
        txs = await database["transactions"].find(
            {"account_id": {"$in": seed_accounts}},
            {"_id": 0, "transaction_id": 1, "account_id": 1, "transaction_date": 1, "amount": 1},
        ).to_list(8_000)
        by_day: dict[str, list[dict]] = {}
        for t in txs:
            dt = as_dt(t.get("transaction_date"))
            if dt:
                by_day.setdefault(dt.strftime("%Y-%m-%d"), []).append(t)
        for day, day_txs in by_day.items():
            if len(day_txs) < 3:
                continue
            tot = sum(float(t.get("amount") or 0) for t in day_txs)
            if tot < 100_000:
                continue
            score = min(95, 40 + min(30, len(day_txs)) + (20 if tot > 500_000 else 10))
            evidence = [
                {
                    "id": str(t["transaction_id"]),
                    "type": "BANK",
                    "href": f"/transactions/{t['transaction_id']}",
                }
                for t in day_txs[:12]
                if t.get("transaction_id")
            ]
            episodes.append(
                {
                    "episode_id": f"DAY-{day}",
                    "title": "High-Value Transfer Burst",
                    "time_window_str": f"{day} 00:00:00 → 23:59:59",
                    "duration_human": "1d window",
                    "calls_count": 0,
                    "ip_sessions_count": 0,
                    "transactions_count": len(day_txs),
                    "total_money_moved_inr": round(tot, 2),
                    "entities_involved": list(
                        dict.fromkeys(str(t.get("account_id")) for t in day_txs if t.get("account_id"))
                    )[:6],
                    "detected_typologies": ["Rapid Financial Velocity", "FIR Seed Connected"],
                    "episode_score": int(score),
                    "severity": "CRITICAL" if score >= 80 else "HIGH",
                    "event_density_ratio": round(len(day_txs) / 24, 1),
                    "plain_narrative": (
                        f"On {day}, FIR-linked accounts made {len(day_txs)} transfers "
                        f"totalling ₹{tot:,.2f}."
                    ),
                    "raw_evidence_ids": [e["id"] for e in evidence],
                    "raw_evidence": evidence,
                }
            )

    ranked = sorted(episodes, key=lambda x: x["episode_score"], reverse=True)[:limit]
    for i, ep in enumerate(ranked, start=1):
        kind = (
            "Multi-Modal Pass-Through"
            if ep["transactions_count"] and (ep["calls_count"] or ep["ip_sessions_count"])
            else "High-Value Transfer Burst"
            if ep["transactions_count"]
            else "Telecom Burst"
        )
        ep["episode_id"] = f"EPISODE-{i:02d}"
        ep["title"] = f"Suspicious Episode #{i:02d} ({kind})"
    return ranked


async def build_heatmap(database, limit_entities: int = 10) -> list[dict]:
    matrix = []
    for row in await build_leaderboard(database, limit=limit_entities):
        eid = row.get("entity_id")
        ent = await database["entities"].find_one({"entity_id": eid}, {"_id": 0})
        if not ent:
            continue
        phones = [norm_phone(p) for p in (ent.get("phones") or []) if p]
        accounts = await entity_accounts(ent)
        hourly = [0] * 24
        if phones:
            async for ev in database["telecom_events"].find(
                {"msisdn": {"$in": phones}}, {"_id": 0, "timestamp": 1}
            ):
                dt = as_dt(ev.get("timestamp"))
                if dt and has_clock_time(dt):
                    hourly[dt.hour] += 1
        if accounts:
            async for t in database["transactions"].find(
                {"account_id": {"$in": accounts}},
                {"_id": 0, "transaction_date": 1, "narration": 1, "description": 1},
            ):
                resolved, src = resolve_tx_time(t, None)
                if resolved and src in {"statement", "narration"}:
                    hourly[resolved.hour] += 1
        cells = []
        for hr, cnt in enumerate(hourly):
            val = min(100, cnt * 15)
            status = (
                "CRITICAL" if cnt >= 5 or val > 75 else "HIGH" if cnt >= 2 or val > 45 else "NORMAL"
            )
            cells.append({"hour": hr, "val": val, "count": cnt, "status": status})
        matrix.append(
            {
                "entity_id": eid,
                "entity_name": row.get("entity_name") or eid,
                "risk_score": row.get("risk_score"),
                "hours": cells,
            }
        )
    return matrix
