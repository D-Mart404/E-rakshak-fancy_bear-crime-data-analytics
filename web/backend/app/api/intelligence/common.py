"""Shared helpers used by all intelligence modules."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

WINDOW_MINUTES = 10
MAX_CORRELATIONS = 40
MAX_SANKEY = 30
MAX_TIMELINE = 300


def norm_phone(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().split(".")[0]
    s = re.sub(r"^\+?91", "", s)
    s = re.sub(r"^0+", "", s)
    m = re.search(r"[6-9]\d{9}", s)
    return m.group(0) if m else s


def fmt_money(amount: float) -> str:
    if amount >= 1e7:
        return f"₹ {amount / 1e7:.2f} Cr"
    if amount >= 1e5:
        return f"₹ {amount / 1e5:.2f} L"
    return f"₹ {amount:,.0f}"


def as_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "")
    try:
        return datetime.fromisoformat(text.replace(" ", "T", 1) if "T" not in text[:19] and " " in text else text)
    except Exception:
        return None


def has_clock_time(value: Any) -> bool:
    """False when source was date-only (stored as midnight 00:00:00)."""
    dt = as_dt(value)
    if not dt:
        return False
    return not (dt.hour == 0 and dt.minute == 0 and dt.second == 0)


def _valid_hms(h: int, m: int, s: int) -> bool:
    return 0 <= h <= 23 and 0 <= m <= 59 and 0 <= s <= 59


def extract_clock_from_text(text: str, anchor: datetime | None = None) -> datetime | None:
    """Recover HH:MM:SS from narration / UTR / IMPS / UPI refs."""
    blob = str(text or "")
    if not blob:
        return None

    m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?\b", blob)
    if m and anchor:
        h, mi, s = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
        if _valid_hms(h, mi, s):
            return anchor.replace(hour=h, minute=mi, second=s, microsecond=0)

    for m in re.finditer(r"(?<!\d)(\d{2})(\d{2})(\d{4})(\d{2})(\d{2})(\d{2})(?!\d)", blob):
        dd, mo, yy, h, mi, s = (int(x) for x in m.groups())
        if not (1 <= dd <= 31 and 1 <= mo <= 12 and yy >= 2020 and _valid_hms(h, mi, s)):
            continue
        try:
            dt = datetime(yy, mo, dd, h, mi, s)
        except ValueError:
            continue
        if anchor and dt.date() != anchor.date():
            continue
        return dt

    for m in re.finditer(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(?!\d)", blob):
        yy, mo, dd, h, mi, s = (int(x) for x in m.groups())
        if not (1 <= dd <= 31 and 1 <= mo <= 12 and _valid_hms(h, mi, s)):
            continue
        try:
            dt = datetime(yy, mo, dd, h, mi, s)
        except ValueError:
            continue
        if anchor and dt.date() != anchor.date():
            continue
        return dt

    if anchor:
        day_token = anchor.strftime("%Y%m%d")
        idx = blob.find(day_token)
        if idx >= 0:
            rest = re.sub(r"\D", "", blob[idx + 8 : idx + 20])
            if len(rest) >= 6:
                h, mi, s = int(rest[0:2]), int(rest[2:4]), int(rest[4:6])
                if _valid_hms(h, mi, s):
                    return anchor.replace(hour=h, minute=mi, second=s, microsecond=0)
    return None


def resolve_tx_time(
    tx: dict,
    related_telecom: list[dict] | None = None,
) -> tuple[datetime | None, str]:
    """Best available clock for a bank row. Never drops the date."""
    raw = (
        tx.get("transaction_datetime")
        or tx.get("posting_datetime")
        or tx.get("transaction_date")
    )
    dt = as_dt(raw)
    if dt and has_clock_time(dt):
        return dt, "statement"

    blob = " ".join(
        str(tx.get(k) or "")
        for k in (
            "narration",
            "description",
            "reference_number",
            "derived_reference_number",
            "counterparty_upi_id",
            "mode",
        )
    )
    extracted = extract_clock_from_text(blob, dt)
    if extracted:
        return extracted, "narration"

    if related_telecom and dt:
        same_day = []
        kinds = []
        for ev in related_telecom:
            edt = as_dt(ev.get("timestamp"))
            if edt and has_clock_time(edt) and edt.date() == dt.date():
                same_day.append(edt)
                kinds.append(str(ev.get("event_type") or "CDR").lower())
        if same_day:
            same_day.sort()
            picked = same_day[len(same_day) // 2]
            merged = datetime(dt.year, dt.month, dt.day, picked.hour, picked.minute, picked.second)
            kind = "linked_ipdr" if any("ipdr" in k for k in kinds) and not any(
                k == "cdr" for k in kinds
            ) else "linked_cdr"
            return merged, kind

    if dt:
        return dt, "date_only"
    return None, "unknown"


def fmt_timeline_ts(value: Any, source: str = "") -> tuple[str, str]:
    """Always keep HH:MM:SS on the timeline."""
    dt = as_dt(value)
    if not dt:
        return "", source or "unknown"
    clock = dt.strftime("%d-%b-%Y %H:%M:%S")
    if source:
        return clock, source
    if has_clock_time(dt):
        return clock, "clock"
    return clock, "date_only"


async def active_case(database) -> dict[str, Any]:
    case = await database["cases"].find_one({"status": "active"}, {"_id": 0})
    if not case:
        case = await database["cases"].find_one({}, {"_id": 0})
    if not case:
        return {
            "case_id": "FIR-UNASSIGNED",
            "title": "No case selected",
            "unit": "Special Financial Cybercrime Unit",
            "lead_investigator": "—",
            "status": "open",
        }
    return {
        "case_id": case.get("case_id"),
        "title": case.get("title"),
        "unit": case.get("unit"),
        "lead_investigator": case.get("lead_investigator"),
        "status": case.get("status"),
        "fir_number": case.get("fir_number"),
    }


async def seed_entities(database) -> list[dict]:
    seeds = await database["entities"].find({"is_seed": True}, {"_id": 0}).to_list(200)
    return seeds or await database["entities"].find({}, {"_id": 0}).limit(10).to_list(10)


async def seed_account_ids(seeds: list[dict]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        ids = [
            str(a["account_id"])
            for a in (seed.get("accounts") or [])
            if isinstance(a, dict) and a.get("account_id")
        ]
        if seed.get("entity_id"):
            ids.append(str(seed["entity_id"]))
        for a in ids:
            if a not in seen:
                seen.add(a)
                out.append(a)
    return out


async def entity_accounts(ent: dict) -> list[str]:
    eid = str(ent.get("entity_id") or "")
    accounts = [
        a.get("account_id")
        for a in (ent.get("accounts") or [])
        if isinstance(a, dict) and a.get("account_id")
    ]
    if eid and eid not in accounts:
        accounts.append(eid)
    return accounts


async def phone_map(database) -> dict[str, dict]:
    mapping: dict[str, dict] = {}
    async for ent in database["entities"].find(
        {},
        {"_id": 0, "entity_id": 1, "entity_name": 1, "phones": 1, "is_seed": 1, "accounts": 1},
    ):
        for phone in ent.get("phones") or []:
            np = norm_phone(phone)
            if np:
                mapping[np] = ent
    return mapping
