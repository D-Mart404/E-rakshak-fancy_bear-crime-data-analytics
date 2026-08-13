#!/usr/bin/env python3
"""
Load ingestion_p/outputs into MongoDB (erakshak).

Inputs (5 files only):
  - accounts.csv
  - transactions.csv
  - UNIFIED_MASTER_CDR.csv
  - unified_master_ipdr.csv
  - orchestration_report.json  (metadata; user alias: db.json)

Usage:
  cd web/backend
  python scripts/load_ingestion_outputs.py --drop
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient

# Resolve paths relative to project root
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "ingestion_p" / "outputs"

ACCOUNTS_CSV = OUTPUTS_DIR / "accounts.csv"
TRANSACTIONS_CSV = OUTPUTS_DIR / "transactions.csv"
CDR_CSV = OUTPUTS_DIR / "UNIFIED_MASTER_CDR.csv"
IPDR_CSV = OUTPUTS_DIR / "unified_master_ipdr.csv"
METADATA_JSON = OUTPUTS_DIR / "orchestration_report.json"

DEFAULT_URI = "mongodb://localhost:27017"
DEFAULT_DB = "erakshak"
BATCH_SIZE = 2000


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _to_float(value: str | None) -> float:
    text = _clean(value)
    if not text:
        return 0.0
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return 0.0


def _to_int(value: str | None) -> int:
    return int(_to_float(value))


def _parse_phones(raw: str | None) -> list[str]:
    text = _clean(raw)
    if not text:
        return []
    parts = re.split(r"[,;|\s]+", text)
    phones: list[str] = []
    for part in parts:
        digits = re.sub(r"\D", "", part)
        if len(digits) >= 10:
            phones.append(digits[-10:] if len(digits) > 10 else digits)
    return list(dict.fromkeys(phones))


def _parse_date_time(date_str: str | None, time_str: str | None = None) -> datetime | None:
    date_text = _clean(date_str)
    if not date_text:
        return None
    time_text = _clean(time_str) or "00:00:00"

    candidates = [
        f"{date_text} {time_text}",
        date_text,
    ]
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ]
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    return None


def _entity_id_from_account_id(account_id: str) -> str:
    return account_id


def load_entities() -> list[dict]:
    if not ACCOUNTS_CSV.exists():
        raise FileNotFoundError(f"Missing {ACCOUNTS_CSV}")

    entities: list[dict] = []
    with ACCOUNTS_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            account_id = _clean(row.get("account_id"))
            if not account_id:
                continue

            phones = _parse_phones(row.get("docx_mobile_numbers"))
            if not phones:
                phones = _parse_phones(row.get("all_docx_mobile_numbers"))

            entity = {
                "entity_id": _entity_id_from_account_id(account_id),
                "entity_name": _clean(row.get("account_holder_name")) or account_id,
                "is_seed": "layer" in _clean(row.get("docx_layer_info")).lower(),
                "accounts": [
                    {
                        "account_id": account_id,
                        "account_number": _clean(row.get("account_number")),
                        "bank_name": _clean(row.get("bank_name")),
                        "ifsc": _clean(row.get("branch_ifsc")) or _clean(row.get("docx_ifsc")),
                        "branch": _clean(row.get("branch_name")),
                    }
                ],
                "phones": phones,
                "pan": _clean(row.get("pan")),
                "account_role": _clean(row.get("docx_layer_info")),
            }
            entities.append(entity)
    return entities


def load_transactions() -> list[dict]:
    if not TRANSACTIONS_CSV.exists():
        raise FileNotFoundError(f"Missing {TRANSACTIONS_CSV}")

    docs: list[dict] = []
    with TRANSACTIONS_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            transaction_id = _clean(row.get("transaction_id"))
            account_id = _clean(row.get("account_id"))
            if not transaction_id or not account_id:
                continue

            direction = _clean(row.get("transaction_direction")).upper()
            amount = _to_float(row.get("transaction_amount"))
            if amount <= 0:
                if direction == "CR":
                    amount = _to_float(row.get("credit_amount"))
                elif direction == "DR":
                    amount = _to_float(row.get("debit_amount"))

            docs.append(
                {
                    "transaction_id": transaction_id,
                    "account_id": account_id,
                    "statement_id": _clean(row.get("statement_id")),
                    "transaction_date": _parse_date_time(row.get("transaction_datetime") or row.get("posting_datetime") or row.get("transaction_date"))
                    or _parse_date_time(row.get("transaction_date")),
                    "amount": amount,
                    "direction": direction,
                    "narration": _clean(row.get("narration")) or _clean(row.get("description")),
                    "counterparty_name": _clean(row.get("derived_sender_receiver_name"))
                    or _clean(row.get("counterparty_name")),
                    "counterparty_account": _clean(row.get("counterparty_account_number")),
                    "counterparty_upi_id": _clean(row.get("derived_upi_id"))
                    or _clean(row.get("counterparty_upi_id")),
                    "mode": _clean(row.get("derived_transaction_mode"))
                    or _clean(row.get("transaction_mode")),
                }
            )
    return docs


def _stable_cdr_event_id(
    msisdn: str,
    call_date: str,
    call_time: str,
    b_party: str,
    duration: str | int,
    call_type: str,
    cell_id: str = "",
) -> str:
    """Must match web/backend/app/services/ingest_upload._stable_cdr_event_id."""
    date_s = str(call_date or "").strip()
    time_s = str(call_time or "").strip()
    date_s = re.sub(r"[./]", "-", date_s)
    time_s = time_s.split(".")[0]
    if " " in date_s and not time_s:
        parts = date_s.split()
        date_s, time_s = parts[0], parts[1] if len(parts) > 1 else ""
    raw = "|".join(
        [
            re.sub(r"\D", "", str(msisdn or ""))[-10:],
            date_s,
            time_s,
            str(duration or "").strip(),
            str(call_type or "").strip().upper(),
            str(cell_id or "").strip(),
        ]
    )
    return "CDR_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:20].upper()


def load_cdr_events() -> list[dict]:
    if not CDR_CSV.exists():
        raise FileNotFoundError(f"Missing {CDR_CSV}")

    docs: list[dict] = []
    with CDR_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            msisdn = _clean(row.get("A_PARTY"))
            if not msisdn:
                continue
            if len(msisdn) > 10:
                msisdn = msisdn[-10:]
            call_date = _clean(row.get("CALL_DATE"))
            call_time = _clean(row.get("CALL_TIME"))
            b_party = _clean(row.get("B_PARTY"))
            duration = _clean(row.get("DURATION"))
            call_type = _clean(row.get("CALL_TYPE"))
            cell = _clean(row.get("FIRST_CELL_ID"))
            docs.append(
                {
                    "event_id": _stable_cdr_event_id(
                        msisdn, call_date, call_time, b_party, duration, call_type, cell
                    ),
                    "event_type": "CDR",
                    "msisdn": msisdn,
                    "timestamp": _parse_date_time(call_date, call_time),
                    "b_party": b_party,
                    "duration_sec": _to_int(duration),
                    "call_type": call_type,
                    "first_cell_id": cell,
                    "location": _clean(row.get("FIRST_LOCATION_ADDRESS")),
                    "source_file": "UNIFIED_MASTER_CDR.csv",
                }
            )
    # Collapse identical call rows (same content hash)
    return list({d["event_id"]: d for d in docs}.values())


def load_ipdr_events(default_msisdn: str | None = None) -> list[dict]:
    if not IPDR_CSV.exists():
        raise FileNotFoundError(f"Missing {IPDR_CSV}")

    docs: list[dict] = []
    with IPDR_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        idx = 0
        for row in reader:
            idx += 1
            record_id = _clean(row.get("Record Id")) or f"IPDR_{idx:05d}"
            raw_msisdn = _clean(row.get("Msisdn"))
            # CSV often stores phones as 8669020636.0
            if raw_msisdn.endswith(".0"):
                raw_msisdn = raw_msisdn[:-2]
            msisdn = re.sub(r"\D", "", raw_msisdn)
            if len(msisdn) > 10:
                msisdn = msisdn[-10:]
            if not msisdn:
                msisdn = default_msisdn or ""

            docs.append(
                {
                    "event_id": record_id,
                    "event_type": "IPDR",
                    "msisdn": msisdn,
                    "timestamp": _parse_date_time(
                        row.get("Start Date"), row.get("Start Time")
                    ),
                    "ip_address": _clean(row.get("Ip Address")),
                    "data_volume_up": _to_float(row.get("Data Volume Up")),
                    "data_volume_down": _to_float(row.get("Data Volume Down")),
                    "cell_id": _clean(row.get("Cell Id")),
                    "duration_sec": _to_int(row.get("Duration Sec")),
                    "end_timestamp": _parse_date_time(
                        row.get("End Date"), row.get("End Time")
                    ),
                }
            )
    return docs


def load_metadata() -> dict:
    if not METADATA_JSON.exists():
        return {"source": "missing", "path": str(METADATA_JSON)}
    with METADATA_JSON.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def insert_batches(collection, docs: list[dict], label: str) -> int:
    if not docs:
        print(f"  {label}: 0 rows")
        return 0

    inserted = 0
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        collection.insert_many(batch, ordered=False)
        inserted += len(batch)
    print(f"  {label}: {inserted} rows")
    return inserted


def main() -> int:
    parser = argparse.ArgumentParser(description="Load ingestion_p/outputs into MongoDB")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--db", default=DEFAULT_DB)
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop target collections before insert",
    )
    parser.add_argument(
        "--ipdr-msisdn",
        default="6359371779",
        help="Fallback msisdn when IPDR rows have empty Msisdn",
    )
    args = parser.parse_args()

    required = [ACCOUNTS_CSV, TRANSACTIONS_CSV, CDR_CSV, IPDR_CSV, METADATA_JSON]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("Missing required output files:")
        for path in missing:
            print(f"  - {path}")
        return 1

    print(f"Loading from: {OUTPUTS_DIR}")
    metadata = load_metadata()
    entities = load_entities()
    transactions = load_transactions()
    cdr_events = load_cdr_events()
    ipdr_events = load_ipdr_events(default_msisdn=args.ipdr_msisdn)
    telecom_events = cdr_events + ipdr_events

    client = MongoClient(args.uri)
    database = client[args.db]

    collections = ("entities", "transactions", "telecom_events", "accounts", "ipdr")
    if args.drop:
        for name in collections:
            database[name].drop()
        print("Dropped collections: entities, transactions, telecom_events, accounts, ipdr")

    account_docs = []
    for ent in entities:
        for acc in ent.get("accounts") or []:
            if not acc.get("account_id"):
                continue
            account_docs.append(
                {
                    "account_id": acc["account_id"],
                    "entity_id": ent.get("entity_id"),
                    "account_number": acc.get("account_number") or "",
                    "bank_name": acc.get("bank_name") or "",
                    "ifsc": acc.get("ifsc") or "",
                    "branch": acc.get("branch") or "",
                    "holder_name": ent.get("entity_name") or "",
                    "phones": ent.get("phones") or [],
                    "pan": ent.get("pan") or "",
                    "is_seed": bool(ent.get("is_seed")),
                    "account_role": ent.get("account_role") or "",
                }
            )

    print("Inserting...")
    insert_batches(database["entities"], entities, "entities")
    insert_batches(database["accounts"], account_docs, "accounts")
    insert_batches(database["transactions"], transactions, "transactions")
    insert_batches(database["telecom_events"], telecom_events, "telecom_events")
    insert_batches(database["ipdr"], ipdr_events, "ipdr")

    # Store metadata in a lightweight collection for traceability.
    database["ingestion_metadata"].replace_one(
        {"_id": "orchestration_report"},
        {
            "_id": "orchestration_report",
            "loaded_at": datetime.now(timezone.utc),
            "source_dir": str(OUTPUTS_DIR),
            "metadata": metadata,
            "counts": {
                "entities": len(entities),
                "accounts": len(account_docs),
                "transactions": len(transactions),
                "telecom_events": len(telecom_events),
                "ipdr": len(ipdr_events),
            },
        },
        upsert=True,
    )

    print("Done.")
    print(f"Sample seed entity_id: {entities[0]['entity_id'] if entities else 'N/A'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
