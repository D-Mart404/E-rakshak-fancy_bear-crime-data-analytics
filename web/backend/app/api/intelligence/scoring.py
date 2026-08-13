"""Evidence-based mule / layering risk scoring.

Scores are not participation trophies. Points are awarded only when a
measurable FATF-style indicator is present in this case's ledger or
telecom, and amount/velocity features are scaled against *this case*
(percentile rank), not hardcoded rupee cutoffs.

Method: additive weighted indicators, then confidence cap.
Breakdown rows sum to the displayed score.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from .common import as_dt, entity_accounts, fmt_money, norm_phone

# Minimum ledger activity before a pattern is treated as real (not noise).
_MIN_TX_FOR_PATTERN = 3
_MIN_INFLOW_FOR_PT = 25_000.0


def _pct_rank(value: float, sorted_vals: list[float]) -> float:
    if not sorted_vals or value <= 0:
        return 0.0
    n = len(sorted_vals)
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if sorted_vals[mid] <= value:
            lo = mid + 1
        else:
            hi = mid
    return lo / n


def _pts_above_percentile(rank: float, max_pts: int, floor: float = 0.60) -> int:
    """0 below `floor` percentile; linear to max_pts at 100th."""
    if rank < floor or max_pts <= 0:
        return 0
    return int(round(max_pts * (rank - floor) / (1.0 - floor)))


def _span_days(min_d: Any, max_d: Any) -> int | None:
    a, b = as_dt(min_d), as_dt(max_d)
    if not a or not b:
        return None
    return max(1, (b.date() - a.date()).days + 1)


def _ranges_overlap(a0: Any, a1: Any, b0: Any, b1: Any) -> bool:
    a, b = as_dt(a0), as_dt(a1)
    c, d = as_dt(b0), as_dt(b1)
    if not all((a, b, c, d)):
        return False
    return a <= d and c <= b


def _clean_set(values: list[Any]) -> set[str]:
    out: set[str] = set()
    for v in values or []:
        s = str(v or "").strip()
        if s and s.upper() not in {"NONE", "NULL", "UNKNOWN", "NA", "-"}:
            out.add(s)
    return out


def _empty_acct() -> dict[str, Any]:
    return {
        "tx_count": 0,
        "inflow": 0.0,
        "outflow": 0.0,
        "in_count": 0,
        "out_count": 0,
        "in_cp": [],
        "out_cp": [],
        "min_date": None,
        "max_date": None,
        "round_n": 0,
    }


async def _account_stats_map(database) -> dict[str, dict[str, Any]]:
    cr = {"$in": ["$direction", ["CR", "CREDIT", "IN"]]}
    dr = {"$in": ["$direction", ["DR", "DEBIT", "OUT"]]}
    cp_key = {"$ifNull": ["$counterparty_account", "$counterparty_name"]}
    rows = await database["transactions"].aggregate(
        [
            {
                "$group": {
                    "_id": "$account_id",
                    "tx_count": {"$sum": 1},
                    "inflow": {"$sum": {"$cond": [cr, "$amount", 0]}},
                    "outflow": {"$sum": {"$cond": [dr, "$amount", 0]}},
                    "in_count": {"$sum": {"$cond": [cr, 1, 0]}},
                    "out_count": {"$sum": {"$cond": [dr, 1, 0]}},
                    "in_cp": {"$addToSet": {"$cond": [cr, cp_key, "$$REMOVE"]}},
                    "out_cp": {"$addToSet": {"$cond": [dr, cp_key, "$$REMOVE"]}},
                    "min_date": {"$min": "$transaction_date"},
                    "max_date": {"$max": "$transaction_date"},
                    "round_n": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gte": ["$amount", 5000]},
                                        {
                                            "$eq": [
                                                {
                                                    "$mod": [
                                                        {
                                                            "$toLong": {
                                                                "$round": [
                                                                    {"$ifNull": ["$amount", 0]},
                                                                    0,
                                                                ]
                                                            }
                                                        },
                                                        5000,
                                                    ]
                                                },
                                                0,
                                            ]
                                        },
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                }
            }
        ],
        allowDiskUse=True,
    ).to_list(5000)
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        aid = str(r.get("_id") or "")
        if not aid:
            continue
        out[aid] = {
            "tx_count": int(r.get("tx_count") or 0),
            "inflow": float(r.get("inflow") or 0),
            "outflow": float(r.get("outflow") or 0),
            "in_count": int(r.get("in_count") or 0),
            "out_count": int(r.get("out_count") or 0),
            "in_cp": list(r.get("in_cp") or []),
            "out_cp": list(r.get("out_cp") or []),
            "min_date": r.get("min_date"),
            "max_date": r.get("max_date"),
            "round_n": int(r.get("round_n") or 0),
        }
    return out


async def _telecom_by_msisdn(database, phones: list[str]) -> dict[str, dict[str, Any]]:
    if not phones:
        return {}
    rows = await database["telecom_events"].aggregate(
        [
            {"$match": {"msisdn": {"$in": phones}}},
            {
                "$group": {
                    "_id": {"msisdn": "$msisdn", "event_type": "$event_type"},
                    "n": {"$sum": 1},
                    "min_ts": {"$min": "$timestamp"},
                    "max_ts": {"$max": "$timestamp"},
                }
            },
        ],
        allowDiskUse=True,
    ).to_list(4000)
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = r.get("_id") or {}
        msisdn = norm_phone(key.get("msisdn"))
        et = str(key.get("event_type") or "").upper()
        if not msisdn:
            continue
        slot = out.setdefault(
            msisdn, {"cdr": 0, "ipdr": 0, "min_ts": None, "max_ts": None}
        )
        n = int(r.get("n") or 0)
        if et == "IPDR":
            slot["ipdr"] += n
        else:
            slot["cdr"] += n
        for bound, field in (("min_ts", "min_ts"), ("max_ts", "max_ts")):
            cur = as_dt(slot.get(field))
            nxt = as_dt(r.get(bound))
            if nxt is None:
                continue
            if cur is None:
                slot[field] = r.get(bound)
            elif field == "min_ts" and nxt < cur:
                slot[field] = r.get(bound)
            elif field == "max_ts" and nxt > cur:
                slot[field] = r.get(bound)
    return out


def _merge_account_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return _empty_acct()
    merged = _empty_acct()
    in_cp: list[Any] = []
    out_cp: list[Any] = []
    mins: list[Any] = []
    maxs: list[Any] = []
    for r in rows:
        merged["tx_count"] += int(r["tx_count"])
        merged["inflow"] += float(r["inflow"])
        merged["outflow"] += float(r["outflow"])
        merged["in_count"] += int(r["in_count"])
        merged["out_count"] += int(r["out_count"])
        merged["round_n"] += int(r["round_n"])
        in_cp.extend(r.get("in_cp") or [])
        out_cp.extend(r.get("out_cp") or [])
        if r.get("min_date") is not None:
            mins.append(r["min_date"])
        if r.get("max_date") is not None:
            maxs.append(r["max_date"])
    merged["in_cp"] = list(_clean_set(in_cp))
    merged["out_cp"] = list(_clean_set(out_cp))
    if mins:
        merged["min_date"] = min((as_dt(x) or datetime.max for x in mins))
    if maxs:
        merged["max_date"] = max((as_dt(x) or datetime.min for x in maxs))
    return merged


def _operating_book(tx_count: int, span: int | None) -> bool:
    """Going-concern ledgers (hundreds of txns over weeks) are not mules."""
    if tx_count >= 400:
        return True
    if span is not None and span >= 45 and tx_count >= 80:
        return True
    return False


def _mule_shape(
    *,
    tx_count: int,
    span: int | None,
    in_cp: int,
    out_cp: int,
    round_n: int,
    is_seed: bool,
) -> dict[str, bool]:
    burst = span is not None and span <= 21 and tx_count >= 4
    compact = 4 <= tx_count <= 150
    fan = (in_cp >= 3 and out_cp <= 2) or (out_cp >= 3 and in_cp <= 2)
    roundish = tx_count >= 6 and (round_n / max(tx_count, 1)) >= 0.50
    seed_burst = is_seed and tx_count <= 200
    flags = {
        "burst": burst,
        "compact": compact,
        "fan": fan,
        "roundish": roundish,
        "seed_burst": seed_burst,
    }
    flags["ok"] = sum(1 for k, v in flags.items() if v) >= 2
    return flags


def _classify_role(
    in_n: int,
    out_n: int,
    in_cp: int,
    out_cp: int,
    pass_ratio: float,
    inflow: float,
    tx_count: int,
    span: int | None,
    shape: dict[str, bool],
) -> str:
    if in_n == 0 and out_n == 0:
        return "NO LEDGER"
    if _operating_book(tx_count, span) and in_n >= 2 and out_n >= 2:
        return "OPERATING ACCOUNT"
    if in_n == 0 and out_n > 0:
        return "SOURCE (ORIGINATOR)"
    if out_n == 0 and in_n > 0:
        return "SINK (TERMINAL)"
    both = in_n >= 2 and out_n >= 2 and inflow >= _MIN_INFLOW_FOR_PT
    if both and 0.85 <= pass_ratio <= 1.12 and shape["ok"]:
        return "INTERMEDIARY MULE"
    if shape["fan"] and in_cp >= 4 and out_cp <= 2 and not _operating_book(tx_count, span):
        return "FUNNEL / COLLECTOR"
    if shape["fan"] and out_cp >= 4 and in_cp <= 2 and not _operating_book(tx_count, span):
        return "DISTRIBUTOR"
    if both and pass_ratio >= 0.70 and shape["ok"]:
        return "LAYERED FORWARDER"
    return "STANDARD PARTICIPANT"


def _score_features(
    ent: dict,
    ledger: dict[str, Any],
    cdr_count: int,
    ipdr_count: int,
    tel_min: Any,
    tel_max: Any,
    norms: dict[str, list[float]],
) -> dict:
    is_seed = bool(ent.get("is_seed"))
    eid = str(ent.get("entity_id") or "")
    accounts = [
        a.get("account_id")
        for a in (ent.get("accounts") or [])
        if isinstance(a, dict) and a.get("account_id")
    ]
    if eid and eid not in accounts:
        accounts.append(eid)
    primary = accounts[0] if accounts else eid
    phones = [norm_phone(p) for p in (ent.get("phones") or []) if p]
    phone = phones[0] if phones else ""
    tx_h = f"/transactions?account_id={primary}" if primary else "/transactions"
    cdr_h = f"/telecom?event_type=CDR&q={phone}" if phone else "/telecom?event_type=CDR"
    ipdr_h = f"/telecom?event_type=IPDR&q={phone}" if phone else "/telecom?event_type=IPDR"
    ent_h = f"/entities/{eid}" if eid else "/entities"

    inflow = float(ledger["inflow"])
    outflow = float(ledger["outflow"])
    in_n = int(ledger["in_count"])
    out_n = int(ledger["out_count"])
    tx_count = int(ledger["tx_count"])
    in_cp = len(_clean_set(ledger.get("in_cp") or []))
    out_cp = len(_clean_set(ledger.get("out_cp") or []))
    round_n = int(ledger.get("round_n") or 0)
    pass_ratio = (outflow / inflow) if inflow > 0 else 0.0
    pass_pct = round(pass_ratio * 100.0, 1)
    span = _span_days(ledger.get("min_date"), ledger.get("max_date"))
    tx_per_day = (tx_count / span) if span else 0.0

    shape = _mule_shape(
        tx_count=tx_count,
        span=span,
        in_cp=in_cp,
        out_cp=out_cp,
        round_n=round_n,
        is_seed=is_seed,
    )
    operating = _operating_book(tx_count, span)
    role = _classify_role(
        in_n, out_n, in_cp, out_cp, pass_ratio, inflow, tx_count, span, shape
    )

    table: list[dict] = []
    buckets = {
        "case_link": 0,
        "transactions": 0,
        "behavior": 0,
        "communication": 0,
        "identifiers": 0,
    }

    def award(bucket: str, ev: str, finding: str, pts: int, href: str, label: str) -> None:
        if pts <= 0:
            return
        buckets[bucket] += pts
        table.append(
            {
                "evidence": ev,
                "finding": finding,
                "points": pts,
                "href": href,
                "href_label": label,
            }
        )

    # --- Pass-through (max 24): ratio near 1.0 AND mule shape, not a trading book ---
    pt_pts = 0
    if (
        not operating
        and shape["ok"]
        and inflow >= _MIN_INFLOW_FOR_PT
        and in_n >= 2
        and out_n >= 2
    ):
        tightness = 1.0 - min(1.0, abs(1.0 - pass_ratio) / 0.40)
        if pass_ratio >= 0.60 and tightness > 0:
            pt_pts = int(round(24 * tightness))
            if pt_pts >= 6:
                award(
                    "behavior",
                    "Pass-through",
                    f"Out/in = {pass_pct}% on {fmt_money(inflow)} inflow "
                    f"({in_n} CR / {out_n} DR; burst/fan/compact ledger)",
                    pt_pts,
                    tx_h,
                    "Open transfers",
                )

    # --- Rapid drain (max 10): high PT inside a short window ---
    if pt_pts >= 10 and span is not None:
        if span <= 3 and tx_count >= 4:
            award(
                "behavior",
                "Rapid drain",
                f"Ledger span {span} day(s), {tx_count} txns",
                10,
                tx_h,
                "Open transfers",
            )
        elif span <= 7 and tx_count >= 6:
            award(
                "behavior",
                "Short-window layering",
                f"Ledger span {span} day(s), {tx_count} txns",
                6,
                tx_h,
                "Open transfers",
            )

    # --- Fan-in / fan-out (max 12): compact ledgers only ---
    if (
        not operating
        and tx_count >= _MIN_TX_FOR_PATTERN
        and tx_count <= 200
        and inflow >= _MIN_INFLOW_FOR_PT
    ):
        if in_cp >= 5 and out_cp <= 2:
            award(
                "behavior",
                "Fan-in collector",
                f"{in_cp} inbound counterparties → {out_cp} outbound",
                12,
                tx_h,
                "Open transfers",
            )
        elif in_cp >= 3 and out_cp <= 1:
            award(
                "behavior",
                "Fan-in collector",
                f"{in_cp} inbound counterparties → {out_cp} outbound",
                8,
                tx_h,
                "Open transfers",
            )
        elif out_cp >= 5 and in_cp <= 2:
            award(
                "behavior",
                "Fan-out distributor",
                f"{in_cp} inbound → {out_cp} outbound counterparties",
                10,
                tx_h,
                "Open transfers",
            )

    # --- Parked funds / originator (max 8) — only if volume is case-high ---
    inflow_rank = _pct_rank(inflow, norms["inflows"])
    outflow_rank = _pct_rank(outflow, norms["outflows"])
    if out_n == 0 and in_n >= _MIN_TX_FOR_PATTERN and inflow_rank >= 0.75:
        award(
            "behavior",
            "Terminal sink",
            f"No outbound legs; inflow {fmt_money(inflow)} (case p{int(inflow_rank * 100)})",
            8,
            tx_h,
            "Open transfers",
        )
    elif in_n == 0 and out_n >= _MIN_TX_FOR_PATTERN and outflow_rank >= 0.75:
        award(
            "behavior",
            "Originator",
            f"No inbound legs; outflow {fmt_money(outflow)} (case p{int(outflow_rank * 100)})",
            6,
            tx_h,
            "Open transfers",
        )

    # --- Volume vs this case (max 16). Operating books capped; average = 0. ---
    vol_pts = _pts_above_percentile(max(inflow_rank, outflow_rank), 16, floor=0.62)
    if operating:
        vol_pts = min(vol_pts, 6)
    elif not shape["ok"]:
        vol_pts = min(vol_pts, 8)
    if vol_pts:
        award(
            "transactions",
            "Case-high volume",
            f"In {fmt_money(inflow)} / out {fmt_money(outflow)} "
            f"(p{int(max(inflow_rank, outflow_rank) * 100)} of this FIR)",
            vol_pts,
            tx_h,
            "Open transfers",
        )

    # --- Velocity vs this case (max 10) ---
    vel_rank = _pct_rank(tx_per_day, norms["tx_per_day"]) if tx_per_day else 0.0
    vel_pts = _pts_above_percentile(vel_rank, 10, floor=0.70)
    if operating:
        vel_pts = 0
    if vel_pts and span:
        award(
            "transactions",
            "High velocity",
            f"{tx_per_day:.1f} txn/day over {span} day(s) (p{int(vel_rank * 100)})",
            vel_pts,
            tx_h,
            "Open transfers",
        )

    # --- Round-amount structuring (max 8) ---
    if not operating and 6 <= tx_count <= 200:
        frac = round_n / tx_count
        if frac >= 0.55 and round_n >= 5:
            award(
                "transactions",
                "Round-amount structuring",
                f"{round_n}/{tx_count} txns are ₹5,000 multiples ({frac:.0%})",
                8 if frac >= 0.75 else 5,
                tx_h,
                "Open transfers",
            )

    # --- Telecom corroboration (max 12). Noise CDR does not score. ---
    tel_overlap = _ranges_overlap(
        ledger.get("min_date"), ledger.get("max_date"), tel_min, tel_max
    )
    if not operating and cdr_count >= 8 and ipdr_count >= 3:
        award(
            "communication",
            "CDR + IPDR both present",
            f"{cdr_count} CDR, {ipdr_count} IPDR",
            7 if tel_overlap else 5,
            cdr_h,
            "Open calls",
        )
        if tel_overlap:
            award(
                "communication",
                "Telecom window overlaps ledger",
                "CDR/IPDR timestamps fall inside bank statement span",
                5,
                ipdr_h,
                "Open IPDR",
            )
    elif not operating and ipdr_count >= 8:
        award(
            "communication",
            "Heavy IPDR",
            f"{ipdr_count} sessions",
            6 if tel_overlap else 4,
            ipdr_h,
            "Open IPDR",
        )
    elif not operating and tel_overlap and cdr_count >= 40:
        award(
            "communication",
            "Heavy CDR",
            f"{cdr_count} calls overlapping ledger window",
            4,
            cdr_h,
            "Open calls",
        )

    # --- FIR seed is a prior, not 30 free points ---
    behavioral = buckets["behavior"] + buckets["transactions"] + buckets["communication"]
    if is_seed and behavioral >= 12:
        award(
            "case_link",
            "FIR-named party + independent indicators",
            "Seed flag confirmed by ledger/telecom patterns",
            8,
            ent_h,
            "Open profile",
        )
    elif is_seed and tx_count >= _MIN_TX_FOR_PATTERN:
        award(
            "case_link",
            "FIR-named party",
            "On FIR list with ledger activity; pattern evidence still weak",
            4,
            ent_h,
            "Open profile",
        )
    elif is_seed:
        award(
            "identifiers",
            "FIR-named party",
            "On FIR list; no usable ledger pattern yet",
            3,
            ent_h,
            "Open profile",
        )

    raw = sum(buckets.values())
    if tx_count >= 20:
        confidence = 0.95
        cap = 100
    elif tx_count >= 8:
        confidence = 0.80
        cap = 92
    elif tx_count >= _MIN_TX_FOR_PATTERN:
        confidence = 0.62
        cap = 70
    elif tx_count >= 1:
        confidence = 0.35
        cap = 40
    else:
        confidence = 0.15 if (cdr_count or ipdr_count or is_seed) else 0.05
        cap = 25 if is_seed else 12

    total = min(100, raw, cap)
    if raw > total > 0:
        scale = total / raw
        for row in table:
            row["points"] = int(round(row["points"] * scale))
        table = [r for r in table if r["points"] > 0]
        drift = total - sum(r["points"] for r in table)
        if table and drift:
            table[0]["points"] = max(0, table[0]["points"] + int(drift))
        buckets = {k: 0 for k in buckets}
        behavior_ev = {
            "Pass-through",
            "Rapid drain",
            "Short-window layering",
            "Fan-in collector",
            "Fan-out distributor",
            "Terminal sink",
            "Originator",
        }
        comm_ev = {
            "CDR + IPDR both present",
            "Telecom window overlaps ledger",
            "Heavy IPDR",
            "Heavy CDR",
        }
        for row in table:
            ev = row["evidence"]
            if ev in behavior_ev:
                buckets["behavior"] += row["points"]
            elif ev in comm_ev:
                buckets["communication"] += row["points"]
            elif ev.startswith("FIR-named"):
                if "independent" in row["finding"]:
                    buckets["case_link"] += row["points"]
                else:
                    buckets["identifiers"] += row["points"]
            else:
                buckets["transactions"] += row["points"]
        total = sum(r["points"] for r in table)

    if not table:
        table.append(
            {
                "evidence": "Insufficient pattern evidence",
                "finding": "No mule/layering indicator met thresholds on this ledger",
                "points": 0,
                "href": ent_h,
                "href_label": "Open profile",
            }
        )

    mule_confirmed = (not operating) and shape["ok"] and (
        pt_pts >= 12 or buckets["behavior"] >= 12
    )
    if (
        mule_confirmed
        and total >= 58
        and buckets["behavior"] >= 16
        and 4 <= tx_count <= 250
        and confidence >= 0.62
    ):
        category = "CRITICAL"
    elif mule_confirmed and total >= 38 and confidence >= 0.62:
        category = "HIGH"
    elif total >= 28:
        category = "MEDIUM"
    else:
        category = "LOW"

    name = ent.get("entity_name") or eid or "Entity"
    fired = [r["evidence"] for r in table if r["points"] > 0]
    narrative = (
        f"{name}: {role}. In {fmt_money(inflow)} / out {fmt_money(outflow)} "
        f"({pass_pct}% pass-through, {tx_count} txns"
        + (f", {span}d span" if span else "")
        + f"). Indicators: {', '.join(fired) if fired else 'none'}. "
        f"Confidence {int(confidence * 100)}%."
    )

    return {
        "entity_id": eid,
        "entity_name": ent.get("entity_name"),
        "is_seed": is_seed,
        "account_role": role,
        "risk_score": int(total),
        "risk_category": category,
        "confidence": round(confidence, 2),
        "score_method": "case-relative FATF mule indicators",
        "transaction_count": tx_count,
        "inflow": inflow,
        "outflow": outflow,
        "pass_through_ratio": round(pass_ratio, 2),
        "cdr_count": cdr_count,
        "ipdr_count": ipdr_count,
        "primary_account_id": primary,
        "primary_phone": phone or None,
        "flow_stats": {
            "total_inflow": inflow,
            "total_outflow": outflow,
            "retained_amount": round(max(0.0, inflow - outflow), 2),
            "pass_through_ratio": pass_pct,
            "total_transactions": tx_count,
            "in_count": in_n,
            "out_count": out_n,
            "inbound_counterparties": in_cp,
            "outbound_counterparties": out_cp,
            "span_days": span,
            "tx_per_day": round(tx_per_day, 2),
        },
        "risk_decomposition": {
            "case_link": buckets["case_link"],
            "network": buckets["case_link"],
            "transactions": buckets["transactions"],
            "behavior": buckets["behavior"],
            "communication": buckets["communication"],
            "identifiers": buckets["identifiers"],
            "breakdown_table": table,
        },
        "plain_language_narrative": narrative,
        "proof": {
            "deep_links": [
                {"label": "Entity profile", "href": ent_h},
                {"label": "Bank transfers", "href": tx_h},
                {"label": "Phone calls (CDR)", "href": cdr_h},
                {"label": "Internet (IPDR)", "href": ipdr_h},
                {"label": "Timeline", "href": f"/timeline?entity={eid}"},
                {"label": "Money network", "href": f"/network?seed={eid}"},
                {"label": "STR", "href": f"/str?entity={eid}"},
            ],
            "sample_transactions": [],
            "sample_telecom": [],
        },
        "recommended_next_actions": [
            "Verify pass-through legs on bank transfers.",
            "Align CDR/IPDR clocks with transfer timestamps.",
            "Generate STR only after reviewing proof rows.",
        ],
    }


async def _case_context(database) -> dict[str, Any]:
    entities = await database["entities"].find({}, {"_id": 0}).to_list(2000)
    acct_map = await _account_stats_map(database)
    all_phones: list[str] = []
    seen_p: set[str] = set()
    for ent in entities:
        for p in ent.get("phones") or []:
            np = norm_phone(p)
            if np and np not in seen_p:
                seen_p.add(np)
                all_phones.append(np)
    tel_map = await _telecom_by_msisdn(database, all_phones)

    inflows: list[float] = []
    outflows: list[float] = []
    velocities: list[float] = []
    for row in acct_map.values():
        if int(row["tx_count"]) <= 0:
            continue
        if float(row["inflow"]) > 0:
            inflows.append(float(row["inflow"]))
        if float(row["outflow"]) > 0:
            outflows.append(float(row["outflow"]))
        span = _span_days(row.get("min_date"), row.get("max_date"))
        if span:
            velocities.append(int(row["tx_count"]) / span)
    inflows.sort()
    outflows.sort()
    velocities.sort()
    return {
        "entities": entities,
        "acct_map": acct_map,
        "tel_map": tel_map,
        "norms": {"inflows": inflows, "outflows": outflows, "tx_per_day": velocities},
    }


def _profile_from_context(ent: dict, ctx: dict[str, Any]) -> dict:
    accounts: list[str] = []
    # entity_accounts is async in common.py — inline the same logic
    eid = str(ent.get("entity_id") or "")
    accounts = [
        a.get("account_id")
        for a in (ent.get("accounts") or [])
        if isinstance(a, dict) and a.get("account_id")
    ]
    if eid and eid not in accounts:
        accounts.append(eid)
    rows = [ctx["acct_map"][a] for a in accounts if a in ctx["acct_map"]]
    ledger = _merge_account_rows(rows)
    phones = [norm_phone(p) for p in (ent.get("phones") or []) if p]
    cdr = ipdr = 0
    tel_min = tel_max = None
    for p in phones:
        slot = ctx["tel_map"].get(p)
        if not slot:
            continue
        cdr += int(slot.get("cdr") or 0)
        ipdr += int(slot.get("ipdr") or 0)
        if slot.get("min_ts") is not None:
            tel_min = slot["min_ts"] if tel_min is None else min(
                as_dt(tel_min) or datetime.max, as_dt(slot["min_ts"]) or datetime.max
            )
        if slot.get("max_ts") is not None:
            tel_max = slot["max_ts"] if tel_max is None else max(
                as_dt(tel_max) or datetime.min, as_dt(slot["max_ts"]) or datetime.min
            )
    return _score_features(ent, ledger, cdr, ipdr, tel_min, tel_max, ctx["norms"])


async def attach_proof(database, profile: dict, accounts: list[str], phones: list[str]) -> dict:
    txs = []
    if accounts:
        for t in await database["transactions"].find(
            {"account_id": {"$in": accounts}},
            {
                "_id": 0,
                "transaction_id": 1,
                "account_id": 1,
                "transaction_date": 1,
                "amount": 1,
                "direction": 1,
                "counterparty_name": 1,
            },
        ).sort("amount", -1).limit(8).to_list(8):
            tid = t.get("transaction_id")
            txs.append(
                {
                    "transaction_id": tid,
                    "account_id": t.get("account_id"),
                    "transaction_date": str(t.get("transaction_date") or ""),
                    "amount": float(t.get("amount") or 0),
                    "direction": t.get("direction"),
                    "counterparty_name": t.get("counterparty_name"),
                    "href": f"/transactions/{tid}" if tid else None,
                }
            )
    tels = []
    if phones:
        for e in await database["telecom_events"].find(
            {"msisdn": {"$in": phones}},
            {
                "_id": 0,
                "event_id": 1,
                "event_type": 1,
                "msisdn": 1,
                "timestamp": 1,
                "b_party": 1,
                "ip_address": 1,
            },
        ).sort("timestamp", -1).limit(8).to_list(8):
            eid = e.get("event_id")
            tels.append(
                {
                    "event_id": eid,
                    "event_type": e.get("event_type"),
                    "msisdn": e.get("msisdn"),
                    "timestamp": str(e.get("timestamp") or ""),
                    "b_party": e.get("b_party"),
                    "ip_address": e.get("ip_address"),
                    "href": f"/telecom/{eid}" if eid else None,
                }
            )
    proof = profile.setdefault("proof", {})
    proof["sample_transactions"] = txs
    proof["sample_telecom"] = tels
    return profile


async def build_leaderboard(database, limit: int = 50) -> list[dict]:
    ctx = await _case_context(database)
    scored = [_profile_from_context(ent, ctx) for ent in ctx["entities"]]
    scored.sort(
        key=lambda x: (x["risk_score"], x.get("confidence") or 0, x.get("inflow") or 0),
        reverse=True,
    )
    return scored[:limit]


async def risk_for_entity(database, entity_id: str) -> dict | None:
    entity = await database["entities"].find_one({"entity_id": entity_id}, {"_id": 0})
    if not entity:
        return None
    ctx = await _case_context(database)
    profile = _profile_from_context(entity, ctx)
    accounts = await entity_accounts(entity)
    phones = [norm_phone(p) for p in (entity.get("phones") or []) if p]
    return await attach_proof(database, profile, accounts, phones)
