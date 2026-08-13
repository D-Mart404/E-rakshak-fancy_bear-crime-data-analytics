"""Parse uploaded bank / CDR / IPDR files and upsert into MongoDB."""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent.parent
CDR_SCRIPT = BACKEND_ROOT / "app" / "parsers" / "cdr_ingestion.py"
IPDR_SCRIPT = BACKEND_ROOT / "app" / "parsers" / "ipdr_extracter.py"
BANK_STAGE = PROJECT_ROOT / "bank_statements_and_next_stage"
BANK_ACCOUNT_DIR = PROJECT_ROOT / "bank_account"
DATE_RE = re.compile(
    r"\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4})\b"
)
MONEY_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(Cr|Dr|CR|DR)?\b")
ACCT_RE = re.compile(
    r"(?:A/?C\s*(?:No|Number|Num)?\.?\s*[:\-]?\s*|Account\s*No\.?\s*[:\-]?\s*|"
    r"Acct\s*Range\s*:\s*|Account\s*Number\s*[:\-]?\s*)(\d{9,18})",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    # Delegate to _cell once defined; keep simple fallback for import order
    if value is None:
        return ""
    try:
        if isinstance(value, float) and value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text in {"", "<NA>", "nan", "NaN", "None", "NaT"}:
        return ""
    return text


def _to_float(value: Any) -> float:
    text = _clean(value).replace(",", "")
    if not text or text.lower() in {"nan", "none", "null", "-"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _to_int(value: Any) -> int:
    return int(_to_float(value))


def _parse_phones(raw: Any) -> list[str]:
    text = _clean(raw)
    if not text:
        return []
    parts = re.split(r"[,;|\s]+", text)
    out: list[str] = []
    for part in parts:
        digits = re.sub(r"\D", "", part)
        if len(digits) >= 10:
            out.append(digits[-10:] if len(digits) > 10 else digits)
    return list(dict.fromkeys(out))


def _as_dt(date_str: Any, time_str: Any = None) -> datetime | None:
    date_text = _clean(date_str)
    if not date_text:
        return None
    if isinstance(date_str, datetime):
        return date_str
    time_text = _clean(time_str) or "00:00:00"
    candidates = [f"{date_text} {time_text}", date_text]
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d-%b-%y",
    ]
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                continue
    try:
        return datetime.fromisoformat(date_text.replace("Z", ""))
    except Exception:
        return None


_MODULE_CACHE: dict[str, Any] = {}


def _load_module(name: str, path: Path):
    key = str(path.resolve())
    cached = _MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    _MODULE_CACHE[key] = mod
    return mod


def _cell(value: Any) -> str:
    """Safe string for pandas NA / NaN / None without truthiness checks."""
    if value is None:
        return ""
    try:
        # NaN
        if isinstance(value, float) and value != value:
            return ""
    except Exception:
        pass
    text = str(value).strip()
    if text in {"", "<NA>", "nan", "NaN", "None", "NaT"}:
        return ""
    return text


def _norm_header(h: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(h or "").lower()).strip()


def _pick_col(headers: list[str], aliases: list[str]) -> str | None:
    norms = {_norm_header(h): h for h in headers}
    for alias in aliases:
        a = _norm_header(alias)
        if a in norms:
            return norms[a]
    for nh, original in norms.items():
        for alias in aliases:
            a = _norm_header(alias)
            if a and (a in nh or nh in a):
                return original
    return None


async def _upsert_many(collection, docs: list[dict], key: str, batch_size: int = 2000) -> int:
    from pymongo import ReplaceOne

    ops: list[ReplaceOne] = []
    n = 0
    for doc in docs:
        kid = doc.get(key)
        if not kid:
            continue
        ops.append(ReplaceOne({key: kid}, doc, upsert=True))
        if len(ops) >= batch_size:
            await collection.bulk_write(ops, ordered=False)
            n += len(ops)
            ops = []
    if ops:
        await collection.bulk_write(ops, ordered=False)
        n += len(ops)
    return n


async def _insert_missing(collection, docs: list[dict], key: str, batch_size: int = 5000) -> tuple[int, int]:
    """
    Fast path: look up existing keys once, insert_many only the missing docs.
    Avoids ReplaceOne-per-row (very slow on large CDR files).
    """
    if not docs:
        return 0, 0
    ids = [d.get(key) for d in docs if d.get(key)]
    existing: set[str] = set()
    for i in range(0, len(ids), 5000):
        chunk = ids[i : i + 5000]
        cursor = collection.find({key: {"$in": chunk}}, {key: 1, "_id": 0})
        async for row in cursor:
            kid = row.get(key)
            if kid:
                existing.add(kid)
    new_docs = [d for d in docs if d.get(key) and d.get(key) not in existing]
    inserted = 0
    for i in range(0, len(new_docs), batch_size):
        batch = new_docs[i : i + batch_size]
        if not batch:
            continue
        result = await collection.insert_many(batch, ordered=False)
        inserted += len(result.inserted_ids)
    return len(docs), inserted


async def _merge_entity(database, entity: dict) -> None:
    eid = entity.get("entity_id")
    if not eid:
        return
    existing = await database["entities"].find_one({"entity_id": eid})
    if not existing:
        await database["entities"].insert_one(entity)
        await _upsert_account_docs(database, entity)
        return
    phones = list(
        dict.fromkeys((existing.get("phones") or []) + (entity.get("phones") or []))
    )
    accounts = {
        a.get("account_id"): a
        for a in (existing.get("accounts") or [])
        if isinstance(a, dict) and a.get("account_id")
    }
    for a in entity.get("accounts") or []:
        if isinstance(a, dict) and a.get("account_id"):
            accounts[a["account_id"]] = {**accounts.get(a["account_id"], {}), **a}
    update = {
        "entity_name": entity.get("entity_name") or existing.get("entity_name"),
        "phones": phones,
        "accounts": list(accounts.values()),
        "is_seed": bool(existing.get("is_seed") or entity.get("is_seed")),
        "pan": entity.get("pan") or existing.get("pan"),
        "account_role": entity.get("account_role") or existing.get("account_role"),
    }
    await database["entities"].update_one({"entity_id": eid}, {"$set": update})
    merged = {**(existing or {}), **entity, **update, "entity_id": eid}
    await _upsert_account_docs(database, merged)


async def _upsert_account_docs(database, entity: dict) -> None:
    """Keep a first-class `accounts` collection (Compass / SQL-style browsing)."""
    eid = entity.get("entity_id")
    for acc in entity.get("accounts") or []:
        if not isinstance(acc, dict):
            continue
        aid = acc.get("account_id")
        if not aid:
            continue
        doc = {
            "account_id": aid,
            "entity_id": eid,
            "account_number": acc.get("account_number") or "",
            "bank_name": acc.get("bank_name") or "",
            "ifsc": acc.get("ifsc") or "",
            "branch": acc.get("branch") or "",
            "holder_name": entity.get("entity_name") or "",
            "phones": entity.get("phones") or [],
            "pan": entity.get("pan") or "",
            "is_seed": bool(entity.get("is_seed")),
            "account_role": entity.get("account_role") or "",
        }
        await database["accounts"].replace_one({"account_id": aid}, doc, upsert=True)


# ---------------------------------------------------------------------------
# Bank
# ---------------------------------------------------------------------------

def _entity_from_account_fields(
    *,
    account_id: str,
    account_number: str = "",
    holder: str = "",
    bank_name: str = "",
    ifsc: str = "",
    branch: str = "",
    phones: list[str] | None = None,
    pan: str = "",
    is_seed: bool = False,
    role: str = "",
) -> dict:
    return {
        "entity_id": account_id,
        "entity_name": holder or account_id,
        "is_seed": is_seed,
        "accounts": [
            {
                "account_id": account_id,
                "account_number": account_number,
                "bank_name": bank_name,
                "ifsc": ifsc,
                "branch": branch,
            }
        ],
        "phones": phones or [],
        "pan": pan,
        "account_role": role,
    }


def _tx_from_row(
    *,
    transaction_id: str,
    account_id: str,
    date_val: Any,
    amount: float,
    direction: str,
    narration: str = "",
    counterparty_name: str = "",
    counterparty_account: str = "",
    mode: str = "",
    statement_id: str = "",
) -> dict:
    return {
        "transaction_id": transaction_id,
        "account_id": account_id,
        "statement_id": statement_id,
        "transaction_date": _as_dt(date_val),
        "amount": amount,
        "direction": direction.upper() if direction else "",
        "narration": narration,
        "counterparty_name": counterparty_name,
        "counterparty_account": counterparty_account,
        "counterparty_upi_id": "",
        "mode": mode,
    }


def parse_bank_statement_json(path: Path) -> tuple[list[dict], list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    acc = data.get("account") or {}
    bank = data.get("bank") or {}
    cust = data.get("customer") or {}
    account_id = _clean(acc.get("account_id")) or f"ACC_{path.stem.upper()}"
    phones = []
    for p in cust.get("phone_numbers") or []:
        phones.extend(_parse_phones(p))
    br = acc.get("branch") or {}
    entity = _entity_from_account_fields(
        account_id=account_id,
        account_number=_clean(acc.get("account_number")),
        holder=_clean(acc.get("account_holder_name")) or _clean(cust.get("customer_name")),
        bank_name=_clean(bank.get("bank_name")),
        ifsc=_clean(br.get("ifsc")),
        branch=_clean(br.get("branch_name")),
        phones=phones,
        pan=_clean(cust.get("pan")),
        is_seed=False,
    )
    txs = []
    for i, t in enumerate(data.get("transactions") or [], start=1):
        if not isinstance(t, dict):
            continue
        tid = _clean(t.get("transaction_id")) or f"{account_id}_TXN_{i:04d}"
        direction = _clean(t.get("transaction_direction")).upper()
        amount = _to_float(t.get("transaction_amount"))
        if amount <= 0:
            amount = _to_float(t.get("credit_amount") if direction == "CR" else t.get("debit_amount"))
        cp = t.get("counterparty") if isinstance(t.get("counterparty"), dict) else {}
        txs.append(
            _tx_from_row(
                transaction_id=tid,
                account_id=account_id,
                date_val=t.get("transaction_date") or t.get("transaction_datetime"),
                amount=amount,
                direction=direction or ("CR" if _to_float(t.get("credit_amount")) else "DR"),
                narration=_clean(t.get("narration") or t.get("description")),
                counterparty_name=_clean(cp.get("name") or t.get("counterparty_name")),
                counterparty_account=_clean(cp.get("account_number") or t.get("counterparty_account_number")),
                mode=_clean(t.get("transaction_mode") or t.get("derived_transaction_mode")),
                statement_id=_clean(data.get("statement_id")),
            )
        )
    return [entity], txs


def parse_accounts_transactions_csv(path: Path) -> tuple[list[dict], list[dict]]:
    """Load loader-format accounts.csv or transactions.csv."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return [], []
    headers = list(rows[0].keys())
    entities: list[dict] = []
    txs: list[dict] = []

    if "account_holder_name" in headers or (
        "account_id" in headers and "transaction_id" not in headers
    ):
        for row in rows:
            account_id = _clean(row.get("account_id"))
            if not account_id:
                continue
            phones = _parse_phones(row.get("docx_mobile_numbers")) or _parse_phones(
                row.get("all_docx_mobile_numbers")
            )
            entities.append(
                _entity_from_account_fields(
                    account_id=account_id,
                    account_number=_clean(row.get("account_number")),
                    holder=_clean(row.get("account_holder_name")) or account_id,
                    bank_name=_clean(row.get("bank_name")),
                    ifsc=_clean(row.get("branch_ifsc") or row.get("docx_ifsc")),
                    branch=_clean(row.get("branch_name")),
                    phones=phones,
                    pan=_clean(row.get("pan")),
                    is_seed="layer" in _clean(row.get("docx_layer_info")).lower(),
                    role=_clean(row.get("docx_layer_info")),
                )
            )
        return entities, []

    if "transaction_id" in headers or "transaction_amount" in headers:
        for row in rows:
            tid = _clean(row.get("transaction_id"))
            account_id = _clean(row.get("account_id"))
            if not tid or not account_id:
                continue
            direction = _clean(row.get("transaction_direction")).upper()
            amount = _to_float(row.get("transaction_amount"))
            if amount <= 0:
                amount = _to_float(row.get("credit_amount") if direction == "CR" else row.get("debit_amount"))
            txs.append(
                _tx_from_row(
                    transaction_id=tid,
                    account_id=account_id,
                    date_val=row.get("transaction_datetime")
                    or row.get("posting_datetime")
                    or row.get("transaction_date"),
                    amount=amount,
                    direction=direction,
                    narration=_clean(row.get("narration") or row.get("description")),
                    counterparty_name=_clean(
                        row.get("derived_sender_receiver_name") or row.get("counterparty_name")
                    ),
                    counterparty_account=_clean(row.get("counterparty_account_number")),
                    mode=_clean(row.get("derived_transaction_mode") or row.get("transaction_mode")),
                    statement_id=_clean(row.get("statement_id")),
                )
            )
            entities.append(
                _entity_from_account_fields(
                    account_id=account_id,
                    holder=account_id,
                )
            )
        # de-dupe entity stubs
        seen = {}
        for e in entities:
            seen[e["entity_id"]] = e
        return list(seen.values()), txs

    return parse_bank_tabular_rows(rows, source_stem=path.stem)


def parse_bank_tabular_rows(
    rows: list[dict], *, source_stem: str, account_hint: str = ""
) -> tuple[list[dict], list[dict]]:
    if not rows:
        return [], []
    headers = list(rows[0].keys())
    date_c = _pick_col(headers, ["transaction date", "txn date", "tran date", "date", "value date", "value dt", "pstd dt", "posting date"])
    narr_c = _pick_col(headers, ["narration", "description", "particulars", "remarks", "details"])
    debit_c = _pick_col(headers, ["debit", "withdrawal", "debit amount", "dr amt", "dr", "withdrawals"])
    credit_c = _pick_col(headers, ["credit", "deposit", "credit amount", "cr amt", "cr", "deposits"])
    amount_c = _pick_col(headers, ["amount", "transaction amount", "txn amount", "tran amount"])
    dir_c = _pick_col(headers, ["direction", "transaction direction", "dr cr", "type", "tran type"])
    acct_c = _pick_col(headers, ["account id", "account number", "a/c no", "ac no", "account", "acct no"])
    name_c = _pick_col(headers, ["account holder", "account name", "customer name", "ac name", "name"])
    bank_c = _pick_col(headers, ["bank", "bank name"])
    tid_c = _pick_col(headers, ["transaction id", "tran id", "txn id", "ref no", "reference"])

    if not date_c or not (debit_c or credit_c or amount_c):
        raise ValueError(
            "Could not map bank columns (need Date + Debit/Credit/Amount). "
            "Prefer statement JSON or accounts/transactions CSV."
        )

    account_id = account_hint or f"ACC_UPLOAD_{re.sub(r'[^A-Z0-9]+', '_', source_stem.upper())[:40]}"
    holder = ""
    bank_name = ""
    if rows and name_c:
        holder = _clean(rows[0].get(name_c))
    if rows and bank_c:
        bank_name = _clean(rows[0].get(bank_c))
    if rows and acct_c and _clean(rows[0].get(acct_c)):
        raw_acc = re.sub(r"\D", "", _clean(rows[0].get(acct_c)))
        if raw_acc:
            account_id = f"ACC_{raw_acc[-12:]}"

    entity = _entity_from_account_fields(
        account_id=account_id,
        account_number=account_id.replace("ACC_", ""),
        holder=holder or account_id,
        bank_name=bank_name,
        is_seed=True,
    )
    txs: list[dict] = []
    for i, row in enumerate(rows, start=1):
        debit = _to_float(row.get(debit_c)) if debit_c else 0.0
        credit = _to_float(row.get(credit_c)) if credit_c else 0.0
        amount = credit or debit or (_to_float(row.get(amount_c)) if amount_c else 0.0)
        if amount <= 0:
            continue
        direction = _clean(row.get(dir_c)).upper() if dir_c else ""
        if not direction:
            if credit > 0:
                direction = "CR"
            elif debit > 0:
                direction = "DR"
            else:
                direction = "DR"
        if direction in {"CREDIT", "CR.", "C"}:
            direction = "CR"
        if direction in {"DEBIT", "DR.", "D"}:
            direction = "DR"
        # Core banking codes: prefer amount columns over vague Tran Type (T/L/C)
        if direction not in {"CR", "DR"}:
            if credit > 0 and debit <= 0:
                direction = "CR"
            elif debit > 0 and credit <= 0:
                direction = "DR"
            else:
                direction = "DR"
        raw_tid = _clean(row.get(tid_c)) if tid_c else ""
        tid = raw_tid if raw_tid else f"{account_id}_U{i:05d}"
        if raw_tid and not raw_tid.startswith(account_id):
            tid = f"{account_id}_{raw_tid}"
        txs.append(
            _tx_from_row(
                transaction_id=tid,
                account_id=account_id,
                date_val=row.get(date_c),
                amount=amount,
                direction=direction,
                narration=_clean(row.get(narr_c)) if narr_c else "",
            )
        )
    return [entity], txs


def _dataframe_to_dicts(df) -> list[dict]:
    return [
        {str(k): ("" if v is None or (isinstance(v, float) and v != v) else v) for k, v in row.items()}
        for row in df.to_dict(orient="records")
    ]


def parse_bank_excel_or_csv(path: Path) -> tuple[list[dict], list[dict]]:
    import pandas as pd

    if path.suffix.lower() == ".csv":
        # Prefer known loader schemas first
        try:
            return parse_accounts_transactions_csv(path)
        except Exception:
            pass
        df = pd.read_csv(path, dtype=str, encoding="utf-8-sig", on_bad_lines="skip")
        return parse_bank_tabular_rows(_dataframe_to_dicts(df), source_stem=path.stem)

    df = None
    for hdr in range(0, 8):
        trial = pd.read_excel(path, dtype=str, header=hdr)
        headers = [str(c) for c in trial.columns]
        if _pick_col(
            headers,
            ["date", "transaction date", "tran date", "value dt", "pstd dt"],
        ) and _pick_col(
            headers,
            [
                "debit",
                "credit",
                "amount",
                "narration",
                "description",
                "dr amt",
                "cr amt",
                "balance",
            ],
        ):
            df = trial
            break
    if df is None:
        df = pd.read_excel(path, dtype=str)
    return parse_bank_tabular_rows(_dataframe_to_dicts(df), source_stem=path.stem)


def _pdf_text_sample(path: Path, max_pages: int = 4) -> str:
    import pdfplumber

    chunks: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:max_pages]:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks)


def _extract_account_candidates(text: str, filename: str = "") -> list[str]:
    found: list[str] = []
    for m in ACCT_RE.finditer(text or ""):
        found.append(m.group(1))
    # Contiguous account-like runs in filename only (NOT concatenated date scraps)
    stem = Path(filename).stem
    for m in re.finditer(r"\d{9,18}", stem):
        found.append(m.group(0))
    # Short trailing account stubs like 15126.pdf (5–8 digits alone as whole stem)
    if re.fullmatch(r"\d{5,8}", stem.strip()):
        found.append(stem.strip())
    for m in re.finditer(r"\b(\d{9,18})\b", text or ""):
        found.append(m.group(1))
    return list(dict.fromkeys(sorted(found, key=len, reverse=True)))


def _normalize_filename(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", Path(name).name.lower())


def find_matching_statement_json(account_hints: list[str]) -> Path | None:
    """
    Same source of truth as ingestion_p → generate_csvs:
    bank_statements_and_next_stage/<bank>/*.json
    """
    if not BANK_STAGE.is_dir() or not account_hints:
        return None
    skip_dirs = {
        "bank_folder",
        "entity_timelines",
        "cdr_extraction",
        "__pycache__",
        "uploads",
        "outputs",
    }
    json_files = [
        p
        for p in BANK_STAGE.rglob("*.json")
        if p.is_file()
        and not any(part in skip_dirs for part in p.parts)
        and not p.name.startswith("_")
        and p.name.lower()
        not in {
            "entities_summary.json",
            "unified_master_timeline.json",
            "investigation_data.json",
        }
    ]
    for hint in account_hints:
        hint_digits = re.sub(r"\D", "", hint)
        if len(hint_digits) < 5:
            continue
        for jf in json_files:
            try:
                head = jf.read_text(encoding="utf-8-sig", errors="ignore")[:8000]
            except OSError:
                continue
            if hint_digits in re.sub(r"\D", "", head):
                # Confirm account field when cheap
                try:
                    data = json.loads(jf.read_text(encoding="utf-8-sig"))
                    acc = (data.get("account") or {}).get("account_number") or ""
                    acc_digits = re.sub(r"\D", "", str(acc))
                    if acc_digits.endswith(hint_digits) or hint_digits.endswith(acc_digits[-min(12, len(acc_digits)):] if acc_digits else ""):
                        return jf
                    if hint_digits in acc_digits or acc_digits in hint_digits:
                        return jf
                except Exception:
                    if hint_digits in re.sub(r"\D", "", head):
                        return jf
    return None


def find_statement_json_by_filename(filename: str) -> Path | None:
    """Match statement JSON via account digits, holder name tokens, or bank_folder bank name."""
    stem = Path(filename).stem
    digit_hints = re.findall(r"\d{9,18}", stem)
    if re.fullmatch(r"\d{5,8}", stem.strip()):
        digit_hints.append(stem.strip())
    hit = find_matching_statement_json(digit_hints)
    if hit:
        return hit

    # bank_folder/<bank>/file.pdf → prefer that bank's JSON dir (fuzzy name match)
    bank_folder = BANK_STAGE / "bank_folder"
    bank_name = None
    target_norm = _normalize_filename(filename)
    if bank_folder.is_dir():
        for p in bank_folder.rglob("*"):
            if not p.is_file():
                continue
            if _normalize_filename(p.name) == target_norm or (
                len(target_norm) >= 12 and target_norm[:12] in _normalize_filename(p.name)
            ):
                bank_name = p.parent.name
                break

    tokens = [t.lower() for t in re.split(r"[^A-Za-z]+", stem) if len(t) >= 4]
    skip = {
        "document", "statement", "bank", "account", "new", "scan", "copy", "file",
        "nov", "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "dec",
    }
    tokens = [t for t in tokens if t not in skip]

    skip_dirs = {
        "bank_folder", "entity_timelines", "cdr_extraction", "__pycache__", "uploads", "outputs",
    }
    candidates: list[Path] = []
    if bank_name:
        for d in BANK_STAGE.iterdir() if BANK_STAGE.is_dir() else []:
            if d.is_dir() and d.name.lower() == bank_name.lower():
                candidates.extend(d.glob("*.json"))
        bank_dir = BANK_STAGE / bank_name
        if bank_dir.is_dir():
            candidates.extend(bank_dir.glob("*.json"))
        # Unique JSON in that bank folder wins immediately
        uniq = list({c.resolve(): c for c in candidates}.values())
        if len(uniq) == 1:
            return uniq[0]
        if uniq and not tokens:
            return uniq[0]

    # Name-token match only when we have a real token (e.g. MADHU) — never scan all banks blindly
    if not tokens:
        return None

    if not candidates and BANK_STAGE.is_dir():
        candidates = [
            p
            for p in BANK_STAGE.rglob("*.json")
            if p.is_file()
            and not any(part in skip_dirs for part in p.parts)
            and not p.name.startswith("_")
        ]

    best: Path | None = None
    best_score = 0
    for jf in candidates:
        try:
            data = json.loads(jf.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if not isinstance(data, dict) or not (
            data.get("statement_id") or isinstance(data.get("transactions"), list)
        ):
            continue
        acc = data.get("account") or {}
        blob = " ".join(
            [
                str(acc.get("account_holder_name") or ""),
                str(acc.get("account_number") or ""),
                str(acc.get("account_id") or ""),
                str((data.get("customer") or {}).get("customer_name") or ""),
                jf.name,
            ]
        ).lower()
        score = sum(1 for t in tokens if t in blob)
        if score > best_score:
            best_score = score
            best = jf
    return best if best_score >= 1 else None


def load_account_from_bank_csvs(account_hints: list[str]) -> tuple[list[dict], list[dict]] | None:
    """Fallback: accounts.csv + transactions.csv produced by generate_csvs / orchestrate."""
    accounts_csv = BANK_ACCOUNT_DIR / "accounts.csv"
    tx_csv = BANK_ACCOUNT_DIR / "transactions.csv"
    # Also accept copies under bank_statements_and_next_stage/
    if not accounts_csv.exists():
        accounts_csv = BANK_STAGE / "accounts.csv"
    if not tx_csv.exists():
        tx_csv = BANK_STAGE / "transactions.csv"
    if not accounts_csv.exists() or not tx_csv.exists():
        return None

    entities, _ = parse_accounts_transactions_csv(accounts_csv)
    matched_ids: list[str] = []
    for ent in entities:
        for acc in ent.get("accounts") or []:
            acn = re.sub(r"\D", "", str(acc.get("account_number") or ""))
            aid = str(acc.get("account_id") or ent.get("entity_id") or "")
            for hint in account_hints:
                h = re.sub(r"\D", "", hint)
                if len(h) >= 5 and (acn.endswith(h) or h.endswith(acn[-min(12, len(acn)):] if acn else "") or h in aid):
                    matched_ids.append(str(ent["entity_id"]))
    matched_ids = list(dict.fromkeys(matched_ids))
    if not matched_ids:
        return None

    _, all_txs = parse_accounts_transactions_csv(tx_csv)
    txs = [t for t in all_txs if t.get("account_id") in matched_ids]
    ents = [e for e in entities if e.get("entity_id") in matched_ids]
    if not txs:
        return None
    return ents, txs


def _parse_bank_pdf_tables(path: Path) -> tuple[list[dict], list[dict]] | None:
    import pdfplumber
    import pandas as pd

    tables: list[list[list[Any]]] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:min(40, len(pdf.pages))]:
            for table in page.extract_tables() or []:
                if table and len(table) >= 2:
                    tables.append(table)
    if not tables:
        return None

    best: tuple[list[dict], list[dict]] | None = None
    best_n = 0
    for table in tables:
        header = [str(c or "").strip() for c in table[0]]
        if not any(header):
            continue
        rows = []
        for raw in table[1:]:
            if not raw:
                continue
            row = {
                header[i] if i < len(header) else f"col_{i}": (raw[i] if i < len(raw) else "")
                for i in range(max(len(header), len(raw)))
            }
            rows.append(row)
        try:
            ents, txs = parse_bank_tabular_rows(rows, source_stem=path.stem)
            if len(txs) > best_n:
                best_n = len(txs)
                best = (ents, txs)
        except ValueError:
            continue
    if best:
        return best
    table = max(tables, key=len)
    df = pd.DataFrame(table[1:], columns=[str(c or f"c{i}") for i, c in enumerate(table[0])])
    try:
        return parse_bank_tabular_rows(_dataframe_to_dicts(df), source_stem=path.stem)
    except ValueError:
        return None


def _parse_bank_pdf_text_lines(path: Path) -> tuple[list[dict], list[dict]]:
    """
    Generalized text-line parser for statement PDFs that have no formal tables
    (common for BoB ledger / many Indian bank exports).
    Not bank-hardcoded: date + money amounts + optional Cr/Dr on balance.
    """
    import pdfplumber

    lines: list[str] = []
    holder = ""
    bank_name = ""
    account_no = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.extend(text.splitlines())
            if not bank_name:
                m = re.search(r"(BANK OF [A-Z ]+|HDFC BANK|ICICI BANK|AXIS BANK|SBI|YES BANK|PNB|KOTAK|BANDHAN BANK)", text, re.I)
                if m:
                    bank_name = m.group(1).strip()
            if not holder:
                m = re.search(r"(?:A/?C\s*Name|Account\s*Label|Account\s*Holder)\s*[:\-]?\s*(.+)", text, re.I)
                if m:
                    holder = m.group(1).strip()[:80]
            if not account_no:
                hints = _extract_account_candidates(text, path.name)
                if hints:
                    account_no = max(hints, key=len)

    account_id = f"ACC_{account_no[-12:]}" if account_no else f"ACC_UPLOAD_{re.sub(r'[^A-Z0-9]+', '_', path.stem.upper())[:40]}"
    entity = _entity_from_account_fields(
        account_id=account_id,
        account_number=account_no or account_id.replace("ACC_", ""),
        holder=holder or account_id,
        bank_name=bank_name,
        is_seed=True,
    )

    txs: list[dict] = []
    prev_balance: float | None = None
    for i, line in enumerate(lines):
        if not DATE_RE.search(line):
            continue
        low = line.lower()
        if any(k in low for k in ("page total", "opening balance", "closing balance", "statement of account", "period :", "helpline")):
            continue
        monies = list(MONEY_RE.finditer(line))
        # Need at least one amount; ignore tiny page numbers mistaken as money when alone
        amounts = []
        for m in monies:
            val = _to_float(m.group(1))
            tag = (m.group(2) or "").lower()
            if val <= 0:
                continue
            amounts.append((val, tag, m.start()))
        if len(amounts) < 1:
            continue

        date_m = DATE_RE.search(line)
        date_val = date_m.group(1) if date_m else ""
        # Drop the leading date(s) from narration
        narr = DATE_RE.sub("", line, count=2).strip()
        narr = MONEY_RE.sub("", narr).strip()
        narr = re.sub(r"\s{2,}", " ", narr).strip(" -|")

        # Heuristic: last amount often balance (especially with Cr/Dr suffix)
        balance = None
        txn_amt = None
        direction = "DR"
        if amounts and amounts[-1][1] in {"cr", "dr"}:
            balance = amounts[-1][0]
            body = amounts[:-1]
        else:
            body = amounts

        if len(body) >= 2:
            # withdrawals, deposits style: first non-zero is often debit or credit column
            a0, a1 = body[0][0], body[1][0]
            # Prefer non-zero
            if a0 > 0 and a1 == 0:
                txn_amt, direction = a0, "DR"
            elif a1 > 0 and a0 == 0:
                txn_amt, direction = a1, "CR"
            elif a0 > 0 and a1 > 0:
                # ambiguous: treat first as txn debit (common ledger)
                txn_amt, direction = a0, "DR"
            else:
                continue
        elif len(body) == 1:
            txn_amt = body[0][0]
            if balance is not None and prev_balance is not None:
                direction = "CR" if balance > prev_balance else "DR"
            elif body[0][1] == "cr":
                direction = "CR"
            elif body[0][1] == "dr":
                direction = "DR"
            else:
                direction = "DR"
        else:
            # only balance tagged — skip
            if balance is not None:
                prev_balance = balance
            continue

        if not txn_amt or txn_amt <= 0:
            continue
        if balance is not None:
            prev_balance = balance

        txs.append(
            _tx_from_row(
                transaction_id=f"{account_id}_PDF_{i:05d}",
                account_id=account_id,
                date_val=date_val,
                amount=txn_amt,
                direction=direction,
                narration=narr[:240],
            )
        )

    if not txs:
        raise ValueError(
            "Could not extract transactions from PDF text. "
            "Prefer statement JSON from bank_statements_and_next_stage/ or CSV export."
        )
    return [entity], txs


def parse_bank_pdf(path: Path) -> tuple[list[dict], list[dict], str]:
    """
    Bank PDF ingest aligned with ingestion_p / bank_statements_and_next_stage:
      1) Match existing statement JSON (same files generate_csvs uses)
      2) Match accounts.csv + transactions.csv if already generated
      3) Formal PDF tables (rare)
      4) Generalized text-line parse (no per-bank hardcoding)
    Returns (entities, txs, source_label).
    """
    # Recover original name from staged names like FIR-..._timestamp_MADHU010.pdf
    display_name = path.name
    m = re.search(r"(?:FIR-\d{4}-\d+_)?\d{8}_\d{6}_(.+)$", path.name, re.I)
    if m:
        display_name = m.group(1)
    # Also try DOC_*_ case locker names
    m2 = re.search(r"^DOC_[A-F0-9]+_(.+)$", path.name, re.I)
    if m2:
        display_name = m2.group(1)

    matched_json = find_statement_json_by_filename(display_name) or find_statement_json_by_filename(
        path.name
    )
    if matched_json:
        ents, txs = parse_bank_statement_json(matched_json)
        return ents, txs, f"statement JSON ({matched_json.name})"

    sample = _pdf_text_sample(path, max_pages=3)
    hints = _extract_account_candidates(sample, display_name)
    matched_json = find_matching_statement_json(hints)
    if matched_json:
        ents, txs = parse_bank_statement_json(matched_json)
        return ents, txs, f"statement JSON ({matched_json.name})"

    csv_hit = load_account_from_bank_csvs(hints)
    if csv_hit:
        ents, txs = csv_hit
        return ents, txs, "bank_account CSV (generate_csvs output)"

    table_hit = _parse_bank_pdf_tables(path)
    if table_hit and table_hit[1]:
        return table_hit[0], table_hit[1], "PDF tables"

    ents, txs = _parse_bank_pdf_text_lines(path)
    return ents, txs, "PDF text lines"


async def ingest_bank(database, path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    source = path.suffix.lower()
    if ext == ".json":
        entities, txs = parse_bank_statement_json(path)
        source = "statement JSON"
    elif ext in {".csv", ".xlsx", ".xls", ".xlsm"}:
        entities, txs = parse_bank_excel_or_csv(path)
        source = "tabular"
    elif ext == ".pdf":
        entities, txs, source = parse_bank_pdf(path)
    else:
        raise ValueError(f"Unsupported bank file type: {ext}")

    for ent in entities:
        await _merge_entity(database, ent)
    n_tx = await _upsert_many(database["transactions"], txs, "transaction_id")
    account_ids = list(
        dict.fromkeys(
            [e.get("entity_id") for e in entities if e.get("entity_id")]
            + [t.get("account_id") for t in txs if t.get("account_id")]
        )
    )
    tx_ids = [t.get("transaction_id") for t in txs if t.get("transaction_id")]
    return {
        "kind": "bank_statement",
        "entities": len(entities),
        "transactions": n_tx,
        "source": source,
        "account_ids": account_ids,
        "transaction_ids": tx_ids[:5000],  # cap stored refs
        "message": f"Loaded {len(entities)} account(s), {n_tx} transaction(s) via {source}",
    }


# ---------------------------------------------------------------------------
# CDR / IPDR
# ---------------------------------------------------------------------------

def _stable_cdr_event_id(
    msisdn: str,
    call_date: Any,
    call_time: Any,
    b_party: str,
    duration: Any,
    call_type: str,
    cell_id: str = "",
) -> str:
    """
    Content-stable ID so UNIFIED_MASTER_CDR.csv and per-phone CDR uploads
    upsert the same rows instead of doubling the collection.

    B_PARTY is intentionally excluded: CDR header mapping sometimes puts
    short codes vs names in that column across pipeline versions.
    """
    date_s = _cell(call_date)
    time_s = _cell(call_time)
    if hasattr(call_date, "strftime"):
        date_s = call_date.strftime("%d-%m-%Y")
    if hasattr(call_time, "strftime"):
        time_s = call_time.strftime("%H:%M:%S")
    date_s = re.sub(r"[./]", "-", date_s)
    time_s = time_s.split(".")[0]
    if " " in date_s and not time_s:
        parts = date_s.split()
        date_s, time_s = parts[0], parts[1] if len(parts) > 1 else ""
    raw = "|".join(
        [
            re.sub(r"\D", "", _cell(msisdn))[-10:],
            date_s,
            time_s,
            _cell(duration),
            _cell(call_type).upper(),
            _cell(cell_id),
        ]
    )
    return "CDR_" + hashlib.md5(raw.encode("utf-8")).hexdigest()[:20].upper()


def _cdr_docs_from_df(df, source_file: str) -> list[dict]:
    """Build CDR docs quickly — bulk timestamp parse, no iterrows."""
    try:
        import pandas as pd
    except ImportError:
        pd = None

    work = df.copy()
    for col in (
        "A_PARTY",
        "B_PARTY",
        "CALL_DATE",
        "CALL_TIME",
        "DURATION",
        "CALL_TYPE",
        "FIRST_CELL_ID",
        "FIRST_LOCATION_ADDRESS",
    ):
        if col not in work.columns:
            work[col] = ""

    msisdn_s = work["A_PARTY"].map(_cell)
    work = work.assign(_msisdn=msisdn_s)
    work = work[work["_msisdn"].astype(bool)]
    work["_msisdn"] = work["_msisdn"].map(lambda x: x[-10:] if len(x) > 10 else x)

    date_s = work["CALL_DATE"].map(_cell).str.replace(r"[./]", "-", regex=True)
    time_s = work["CALL_TIME"].map(_cell).str.split(".").str[0]
    # Prefer day-first Indian CDR dates
    if pd is not None:
        ts = pd.to_datetime(
            date_s + " " + time_s.replace("", "00:00:00"),
            dayfirst=True,
            errors="coerce",
        )
        timestamps = [None if pd.isna(v) else v.to_pydatetime() for v in ts]
    else:
        timestamps = [
            _as_dt(d, t) for d, t in zip(date_s.tolist(), time_s.tolist(), strict=False)
        ]

    b_party = work["B_PARTY"].map(_cell).tolist()
    duration = work["DURATION"].map(_to_int).tolist()
    call_type = work["CALL_TYPE"].map(lambda v: _cell(v).upper()).tolist()
    cell = work["FIRST_CELL_ID"].map(_cell).tolist()
    loc = work["FIRST_LOCATION_ADDRESS"].map(_cell).tolist()
    msisdns = work["_msisdn"].tolist()
    dates = date_s.tolist()
    times = time_s.tolist()

    docs: list[dict] = []
    for i, msisdn in enumerate(msisdns):
        docs.append(
            {
                "event_id": _stable_cdr_event_id(
                    msisdn,
                    dates[i],
                    times[i],
                    b_party[i],
                    duration[i],
                    call_type[i],
                    cell[i],
                ),
                "event_type": "CDR",
                "msisdn": msisdn,
                "timestamp": timestamps[i],
                "b_party": b_party[i],
                "duration_sec": duration[i],
                "call_type": call_type[i],
                "first_cell_id": cell[i],
                "location": loc[i],
                "source_file": source_file,
            }
        )
    return docs


def _quick_csv_row_estimate(path: Path) -> int:
    """Cheap line count (minus header) without full pandas parse."""
    try:
        with path.open("rb") as fh:
            n = sum(1 for _ in fh)
        return max(0, n - 1)
    except OSError:
        return 0


async def ingest_cdr(database, path: Path) -> dict[str, Any]:
    if not CDR_SCRIPT.exists():
        raise RuntimeError(f"Missing CDR parser: {CDR_SCRIPT}")

    # Ultra-fast skip before parsing: filename is often the A-party MSISDN
    stem = path.stem
    m = re.search(r"(?<!\d)(\d{10})(?!\d)", stem)
    stem_msisdn = m.group(1) if m else ""
    if stem_msisdn and path.suffix.lower() == ".csv":
        have = await database["telecom_events"].count_documents(
            {"event_type": "CDR", "msisdn": stem_msisdn}
        )
        est = _quick_csv_row_estimate(path)
        if have > 0 and est > 0 and have >= int(est * 0.9):
            return {
                "kind": "cdr",
                "events": have,
                "events_added": 0,
                "msisdns": [stem_msisdn],
                "source_file": path.name,
                "message": (
                    f"Skipped — {have} CDR events already in DB for {stem_msisdn} "
                    f"(file ~{est} rows)"
                ),
            }

    mod = _load_module("cdr_ingestion_runtime", CDR_SCRIPT)
    df = mod.process_and_unify_cdr(str(path))
    if df is None or df.empty:
        raise ValueError("CDR parser found 0 rows. Check headers (A-party, date, etc.).")
    docs = _cdr_docs_from_df(df, path.name)
    if not docs:
        raise ValueError("CDR parser produced rows but no usable A_PARTY values.")

    msisdns = list(dict.fromkeys(d["msisdn"] for d in docs if d.get("msisdn")))

    # Fast skip after parse: this A-party already fully loaded
    if len(msisdns) == 1:
        have = await database["telecom_events"].count_documents(
            {"event_type": "CDR", "msisdn": msisdns[0]}
        )
        if have >= len(docs):
            return {
                "kind": "cdr",
                "events": len(docs),
                "events_added": 0,
                "msisdns": msisdns,
                "source_file": path.name,
                "message": (
                    f"Skipped write — {have} CDR events already in DB for {msisdns[0]} "
                    f"(file has {len(docs)} rows)"
                ),
            }

    n, added = await _insert_missing(database["telecom_events"], docs, "event_id")
    return {
        "kind": "cdr",
        "events": n,
        "events_added": added,
        "msisdns": msisdns,
        "source_file": path.name,
        "message": (
            f"Loaded {added} new CDR row(s) from {path.name} "
            f"({n - added} already present, file has {n})"
        ),
    }

def _ipdr_docs_from_rows(rows: list[dict], source: str) -> list[dict]:
    docs = []
    for idx, row in enumerate(rows, start=1):
        # Support both pretty and snake headers
        def g(*keys):
            for k in keys:
                if k in row and _clean(row.get(k)):
                    return row.get(k)
            # case-insensitive
            lower = {_norm_header(k): v for k, v in row.items()}
            for k in keys:
                v = lower.get(_norm_header(k))
                if _clean(v):
                    return v
            return ""

        raw_msisdn = _clean(g("Msisdn", "msisdn", "MSISDN", "Mobile Number", "Mobile No"))
        if raw_msisdn.endswith(".0"):
            raw_msisdn = raw_msisdn[:-2]
        msisdn = re.sub(r"\D", "", raw_msisdn)
        if len(msisdn) > 10:
            msisdn = msisdn[-10:]
        record_id = _clean(g("Record Id", "record_id", "event_id")) or f"IPDR_{source}_{idx}"
        docs.append(
            {
                "event_id": record_id if record_id.startswith("IPDR_") else f"IPDR_{record_id}",
                "event_type": "IPDR",
                "msisdn": msisdn,
                "timestamp": _as_dt(
                    g("Start Date", "start_date", "Date"),
                    g("Start Time", "start_time", "Time"),
                ),
                "ip_address": _clean(g("Ip Address", "ip_address", "IP Address", "Public IP")),
                "data_volume_up": _to_float(g("Data Volume Up", "data_volume_up", "Upload")),
                "data_volume_down": _to_float(g("Data Volume Down", "data_volume_down", "Download")),
                "cell_id": _clean(g("Cell Id", "cell_id", "CGI")),
                "duration_sec": _to_int(g("Duration Sec", "duration_sec", "Duration")),
                "end_timestamp": _as_dt(
                    g("End Date", "end_date"),
                    g("End Time", "end_time"),
                ),
            }
        )
    return [d for d in docs if d.get("msisdn") or d.get("ip_address")]


async def ingest_ipdr(database, path: Path) -> dict[str, Any]:
    ext = path.suffix.lower()
    rows: list[dict] = []

    if ext == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    elif ext in {".xlsx", ".xls", ".xlsm", ".pdf", ".docx"}:
        if not IPDR_SCRIPT.exists():
            raise RuntimeError(f"Missing IPDR parser: {IPDR_SCRIPT}")
        mod = _load_module("ipdr_extracter_runtime", IPDR_SCRIPT)
        with tempfile.TemporaryDirectory(prefix="erakshak_ipdr_") as tmp:
            tmp_path = Path(tmp)
            work = tmp_path / "in"
            work.mkdir()
            dest = work / path.name
            dest.write_bytes(path.read_bytes())
            out_xlsx = tmp_path / "output.xlsx"
            mod.run(str(work), str(out_xlsx))
            if not out_xlsx.exists():
                raise ValueError("IPDR extractor produced no output")
            import pandas as pd

            try:
                df = pd.read_excel(out_xlsx, sheet_name="Primary_Info", dtype=str)
            except ValueError:
                df = pd.read_excel(out_xlsx, sheet_name=0, dtype=str)
            rows = _dataframe_to_dicts(df)
    else:
        raise ValueError(f"Unsupported IPDR file type: {ext}")

    docs = _ipdr_docs_from_rows(rows, path.stem)
    if not docs:
        raise ValueError("IPDR parser found 0 usable rows")
    n = await _upsert_many(database["ipdr"], docs, "event_id")
    await _upsert_many(database["telecom_events"], docs, "event_id")
    return {"kind": "ipdr", "events": n, "message": f"Loaded {n} IPDR session(s)"}


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

async def ingest_uploaded_file(
    database,
    *,
    path: Path,
    doc_type: str,
    case_id: str | None = None,
) -> dict[str, Any]:
    kind = (doc_type or "").strip().lower()
    if kind not in {"bank_statement", "cdr", "ipdr"}:
        return {
            "status": "skipped",
            "message": "Stored as evidence only (choose Bank / CDR / IPDR to parse into case data).",
        }

    try:
        if kind == "bank_statement":
            result = await ingest_bank(database, path)
        elif kind == "cdr":
            result = await ingest_cdr(database, path)
        else:
            result = await ingest_ipdr(database, path)
        result["status"] = "ok"
        if case_id:
            await database["audit_trail"].insert_one(
                {
                    "timestamp": datetime.utcnow().isoformat(sep=" ", timespec="seconds") + " UTC",
                    "user": "System",
                    "case_id": case_id,
                    "action": f"Ingested {kind} from {path.name}: {result.get('message')}",
                }
            )
        return result
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "kind": kind,
            "message": f"{type(exc).__name__}: {exc}",
        }
