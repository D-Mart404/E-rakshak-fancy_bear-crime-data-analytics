"""Match all account.docx rows to accounts.csv with confident connections only."""
import csv
import re
import sys
from pathlib import Path

import docx

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = Path(__file__).resolve().parent
DOCX_FILE = WORKSPACE / "all account.docx"
ACCOUNTS_CSV = WORKSPACE / "accounts.csv"


def clean_acnum(value: str) -> str:
    cleaned = re.sub(r"\s+", "", str(value or ""))
    stripped = cleaned.lstrip("0")
    return stripped or cleaned


def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def parse_holder_cell(holder_cell: str) -> dict:
    holder_lines = [line.strip() for line in holder_cell.splitlines() if line.strip()]
    holder_name = ""
    proprietor = ""
    dob = ""
    address_parts = []

    for line in holder_lines:
        lower = line.lower()
        if lower.startswith("account hodler:") or lower.startswith("account holder:"):
            continue
        if lower.startswith("dob:"):
            dob = line.split(":", 1)[1].strip()
            continue
        if not holder_name:
            holder_name = line
            continue
        if not proprietor and not re.search(r"\d", line) and len(line.split()) <= 4:
            proprietor = line
            continue
        address_parts.append(line)

    return {
        "holder_name": holder_name,
        "proprietor": proprietor,
        "dob": dob,
        "address": " ".join(address_parts).strip(),
    }


def parse_all_account_docx(path: Path) -> list[dict]:
    doc = docx.Document(str(path))
    table = doc.tables[0]
    rows = []

    for row in table.rows[1:]:
        cells = [cell.text.strip() for cell in row.cells]
        if len(cells) < 4:
            continue

        serial, bank_cell, holder_cell, contact_cell = cells[:4]
        lines = [line.strip() for line in bank_cell.splitlines() if line.strip()]
        bank_name = lines[0] if lines else ""
        account_number = ""
        ifsc = ""
        amount = ""

        for line in lines[1:]:
            ac_match = re.search(r"A[/\\]C\s*No\.?-?\s*:?\s*([\d\w]+)", line, re.IGNORECASE)
            if ac_match:
                account_number = ac_match.group(1).strip()
                continue
            ifsc_match = re.search(r"IFSC\s*Code-?\s*:?\s*(\w+)", line, re.IGNORECASE)
            if ifsc_match:
                ifsc = ifsc_match.group(1).strip()
                continue
            amount_match = re.search(r"Amount-?\s*:?\s*([\d,\.]+)", line, re.IGNORECASE)
            if amount_match:
                amount = amount_match.group(1).strip()

        holder_info = parse_holder_cell(holder_cell)
        contacts = [part.strip() for part in re.split(r"[\n|]+", contact_cell) if part.strip()]
        mobiles = []
        emails = []
        for contact in contacts:
            if "@" in contact:
                emails.append(contact)
                continue
            phone_match = re.search(r"\d{10}", contact)
            if phone_match:
                mobiles.append(phone_match.group())

        rows.append(
            {
                "all_docx_serial_no": serial,
                "all_docx_bank_name": bank_name,
                "all_docx_account_number": account_number,
                "all_docx_ifsc": ifsc,
                "all_docx_amount": amount,
                "all_docx_holder_name": holder_info["holder_name"],
                "all_docx_proprietor": holder_info["proprietor"],
                "all_docx_dob": holder_info["dob"],
                "all_docx_address": holder_info["address"],
                "all_docx_mobile_numbers": "; ".join(mobiles),
                "all_docx_email": "; ".join(emails),
            }
        )

    return rows


def name_matches(left: str, right: str) -> bool:
    left_norm = norm_name(left)
    right_norm = norm_name(right)
    if not left_norm or not right_norm:
        return False
    if left_norm == right_norm or left_norm in right_norm or right_norm in left_norm:
        return True
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    return len(left_tokens & right_tokens) >= 2


def score_match(docx_row: dict, account_row: dict) -> tuple[int, list[str]]:
    score = 0
    reasons = []

    docx_ac = clean_acnum(docx_row["all_docx_account_number"])
    account_ac = clean_acnum(account_row.get("account_number", ""))
    if docx_ac and account_ac and docx_ac == account_ac:
        score += 100
        reasons.append("account_number")

    docx_ifsc = (docx_row.get("all_docx_ifsc") or "").upper()
    account_ifsc = (account_row.get("branch_ifsc") or account_row.get("docx_ifsc") or "").upper()
    if docx_ifsc and account_ifsc and docx_ifsc == account_ifsc:
        score += 30
        reasons.append("ifsc")

    holder_names = [
        account_row.get("account_holder_name", ""),
        account_row.get("customer_name", ""),
    ]
    docx_names = [
        docx_row.get("all_docx_holder_name", ""),
        docx_row.get("all_docx_proprietor", ""),
    ]

    for docx_name in docx_names:
        for account_name in holder_names:
            if name_matches(docx_name, account_name):
                score += 20
                reasons.append("name")
                break

    for email in docx_row.get("all_docx_email", "").split(";"):
        email = email.strip().lower()
        if not email:
            continue
        existing_email = (account_row.get("docx_email") or account_row.get("all_docx_email") or "").lower()
        if email in existing_email:
            score += 40
            reasons.append("email")

    for mobile in docx_row.get("all_docx_mobile_numbers", "").split(";"):
        mobile = re.sub(r"\D", "", mobile)
        if not mobile:
            continue
        existing_mobiles = re.sub(
            r"\D",
            "",
            (account_row.get("docx_mobile_numbers") or account_row.get("all_docx_mobile_numbers") or ""),
        )
        if mobile in existing_mobiles:
            score += 35
            reasons.append("mobile")

    return score, sorted(set(reasons))


def is_confident_match(score: int, reasons: list[str]) -> bool:
    if score >= 100 and "account_number" in reasons:
        return True
    if score >= 75 and len(reasons) >= 2:
        return True
    if score >= 55 and "email" in reasons and ("name" in reasons or "mobile" in reasons):
        return True
    return False


def merge_docx_fields(account_row: dict, docx_row: dict) -> dict:
    field_map = {
        "all_docx_serial_no": "all_docx_serial_no",
        "all_docx_bank_name": "all_docx_bank_name",
        "all_docx_account_number": "all_docx_account_number",
        "all_docx_ifsc": "all_docx_ifsc",
        "all_docx_amount": "all_docx_amount",
        "all_docx_holder_name": "all_docx_holder_name",
        "all_docx_proprietor": "all_docx_proprietor",
        "all_docx_dob": "all_docx_dob",
        "all_docx_address": "all_docx_address",
        "all_docx_mobile_numbers": "all_docx_mobile_numbers",
        "all_docx_email": "all_docx_email",
    }

    updated = dict(account_row)
    for csv_field, docx_field in field_map.items():
        value = docx_row.get(docx_field, "")
        if value and not updated.get(csv_field):
            updated[csv_field] = value
    return updated


def main(dry_run: bool = False) -> None:
    docx_rows = parse_all_account_docx(DOCX_FILE)

    with open(ACCOUNTS_CSV, encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = list(reader.fieldnames or [])
        accounts = list(reader)

    new_fields = [
        "all_docx_serial_no",
        "all_docx_bank_name",
        "all_docx_account_number",
        "all_docx_ifsc",
        "all_docx_amount",
        "all_docx_holder_name",
        "all_docx_proprietor",
        "all_docx_dob",
        "all_docx_address",
        "all_docx_mobile_numbers",
        "all_docx_email",
    ]
    for field in new_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    matched = []
    unmatched = []

    for docx_row in docx_rows:
        best_score = -1
        best_reasons: list[str] = []
        best_account = None

        for account_row in accounts:
            score, reasons = score_match(docx_row, account_row)
            if score > best_score:
                best_score = score
                best_reasons = reasons
                best_account = account_row

        if best_account and is_confident_match(best_score, best_reasons):
            idx = accounts.index(best_account)
            accounts[idx] = merge_docx_fields(accounts[idx], docx_row)
            matched.append(
                {
                    "docx_serial": docx_row["all_docx_serial_no"],
                    "docx_bank": docx_row["all_docx_bank_name"],
                    "docx_account_number": docx_row["all_docx_account_number"],
                    "account_id": best_account["account_id"],
                    "score": best_score,
                    "reasons": best_reasons,
                }
            )
        else:
            unmatched.append(
                {
                    "docx_serial": docx_row["all_docx_serial_no"],
                    "docx_bank": docx_row["all_docx_bank_name"],
                    "docx_account_number": docx_row["all_docx_account_number"],
                    "best_score": best_score,
                    "best_reasons": best_reasons,
                    "best_account_id": best_account["account_id"] if best_account else "",
                }
            )

    output_path = ACCOUNTS_CSV.with_suffix(".preview.csv") if dry_run else ACCOUNTS_CSV
    with open(output_path, "w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(accounts)

    print(f"Parsed {len(docx_rows)} rows from all account.docx")
    if dry_run:
        print(f"Dry run: wrote preview to {output_path}")
    else:
        print(f"Updated {output_path}")
    print(f"Confident matches applied: {len(matched)}")
    for item in matched:
        print(
            f"  #{item['docx_serial']} {item['docx_bank']} ({item['docx_account_number']}) "
            f"-> {item['account_id']} [{item['score']}: {', '.join(item['reasons'])}]"
        )

    print(f"Unmatched (not added): {len(unmatched)}")
    for item in unmatched:
        print(
            f"  #{item['docx_serial']} {item['docx_bank']} ({item['docx_account_number']}) "
            f"best={item['best_score']} reasons={item['best_reasons']} "
            f"candidate={item['best_account_id']}"
        )


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
