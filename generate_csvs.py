"""
generate_csvs.py
================
Generates two CSV files from all bank JSON files + docx extra data:

  1. accounts.csv  — One row per bank account/statement.
                     Linked to transactions via the `account_id` column.
  2. transactions.csv — All transactions from all files combined.
                        Linked to accounts via the `account_id` column.

The script DOES NOT modify any existing JSON file or folder.
It reads data as-is and writes only the two output CSV files.
"""

import os
import sys
import json
import glob
import csv
import re

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DOCX_FILE = os.path.join(WORKSPACE, "bank account ni mahiti.docx")
ACCOUNTS_CSV = os.path.join(WORKSPACE, "accounts.csv")
TRANSACTIONS_CSV = os.path.join(WORKSPACE, "transactions.csv")


# ---------------------------------------------------------------------------
# Helper: safely get nested value from dict
# ---------------------------------------------------------------------------
def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur if cur is not None else default


def join_list(lst):
    """Join a list of values into a semicolon-separated string."""
    if not lst:
        return ""
    return "; ".join(str(x) for x in lst if x is not None)


# ---------------------------------------------------------------------------
# Parse the docx table — keyed by normalised account number
# ---------------------------------------------------------------------------
def load_docx_data(docx_path):
    """
    Returns a dict keyed by cleaned account number -> row dict from docx.
    Columns: serial_no, raw_bank_info, bank_name_docx, account_number_docx,
             ifsc_docx, layer, amount_mentioned, holder_name, address_docx,
             mobile_numbers, email_docx
    """
    import docx as _docx

    doc = _docx.Document(docx_path)
    table = doc.tables[0]

    def clean_acnum(s):
        """Strip leading zeroes and non-digits from account number."""
        return re.sub(r'\s+', '', s).lstrip('0') or s

    rows_out = {}

    for row in table.rows[1:]:   # skip header
        cells = [c.text.strip() for c in row.cells]
        serial_no   = cells[0] if len(cells) > 0 else ""
        bank_cell   = cells[1] if len(cells) > 1 else ""
        holder_cell = cells[2] if len(cells) > 2 else ""
        mobile_cell = cells[3] if len(cells) > 3 else ""
        email_cell  = cells[4] if len(cells) > 4 else ""

        if not serial_no:
            continue

        # --- Parse bank_cell: bank name, A/C number, IFSC, layer, amount ---
        # Pattern: lines are usually:
        #   Bank Name
        #   A/C : <number>
        #   IFSC: <code>
        #   (layer info)
        #   (amount)
        lines = [l.strip() for l in bank_cell.splitlines() if l.strip()]
        bank_name_docx = ""
        acnum_docx = ""
        ifsc_docx = ""
        layer_info = ""
        amount_mentioned = ""

        for line in lines:
            # Account number
            ac_match = re.search(r'A[/\\]C\s*[:\-]?\s*([\d\w]+)', line, re.IGNORECASE)
            if ac_match:
                acnum_docx = ac_match.group(1).strip()
                continue
            # IFSC
            ifsc_match = re.search(r'IFSC[:\-]?\s*(\w+)', line, re.IGNORECASE)
            if ifsc_match:
                ifsc_docx = ifsc_match.group(1).strip()
                continue
            # Layer info e.g. (first layer)
            if re.search(r'\b(first|second|third|fourth|fifth)\s+layer\b', line, re.IGNORECASE):
                layer_info = line
                continue
            # Amount e.g. (75,00,000/-)
            if re.search(r'\d[\d,]+/-\)?', line):
                amount_mentioned = line.strip('()')
                continue
            # Otherwise it's the bank name (first meaningful non-matched line)
            if not bank_name_docx:
                bank_name_docx = line

        # --- Parse holder_cell ---
        holder_lines = [l.strip() for l in holder_cell.splitlines() if l.strip()]
        holder_name_docx = ""
        proprietor_docx = ""
        address_docx = ""
        addr_started = False
        for line in holder_lines:
            lc = line.lower()
            if lc.startswith('name:') or lc.startswith('proprietor:') or lc.startswith('prop:'):
                if lc.startswith('name:'):
                    holder_name_docx = line[5:].strip()
                elif lc.startswith('proprietor:'):
                    proprietor_docx = line[11:].strip()
                elif lc.startswith('prop:'):
                    proprietor_docx = line[5:].strip()
            elif lc.startswith('add') and ':' in line:
                addr_started = True
                address_docx = line.split(':', 1)[1].strip()
            elif lc.startswith('address') and ':' in line:
                addr_started = True
                address_docx = line.split(':', 1)[1].strip()
            elif addr_started:
                address_docx += " " + line
            elif not holder_name_docx and not proprietor_docx:
                # First non-labelled line is the entity name
                holder_name_docx = line

        # --- Mobile numbers (may be multi-line) ---
        mobile_numbers = "; ".join(
            p.strip() for p in re.split(r'[\n,]+', mobile_cell) if p.strip()
        )

        row_data = {
            "docx_serial_no": serial_no,
            "bank_name_docx": bank_name_docx,
            "account_number_docx": acnum_docx,
            "ifsc_docx": ifsc_docx,
            "layer_info": layer_info,
            "amount_mentioned": amount_mentioned,
            "holder_name_docx": holder_name_docx,
            "proprietor_docx": proprietor_docx,
            "address_docx": address_docx.strip(),
            "mobile_numbers": mobile_numbers,
            "email_docx": email_cell,
        }

        # Index by cleaned account number (primary key to match JSON)
        clean_ac = clean_acnum(acnum_docx)
        rows_out[clean_ac] = row_data
        # Also index by original (some JSONs may keep leading zeros)
        rows_out[acnum_docx] = row_data

    return rows_out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    json_files = sorted(glob.glob(os.path.join(WORKSPACE, "**", "*.json"), recursive=True))
    json_files = [f for f in json_files if not os.path.basename(f).startswith("_")]

    print(f"Found {len(json_files)} JSON files.")

    # Load docx enrichment data
    print("Loading docx enrichment data...")
    docx_data = load_docx_data(DOCX_FILE)
    print(f"  Loaded {len(set(v['docx_serial_no'] for v in docx_data.values()))} docx records.")

    # -----------------------------------------------------------------------
    # 1. ACCOUNTS CSV
    # -----------------------------------------------------------------------
    account_rows = []
    account_fieldnames = [
        # --- Link key ---
        "account_id",
        "statement_id",
        # --- Bank ---
        "bank_name",
        "bank_code",
        "swift_code",
        "currency",
        # --- Account core ---
        "account_number",
        "masked_account_number",
        "account_holder_name",
        "account_type",
        "scheme",
        "product_type",
        "mode_of_operation",
        "account_status",
        "account_open_date",
        "account_closed_date",
        "date_of_opening",
        "date_of_closing",
        # --- Branch ---
        "branch_name",
        "branch_code",
        "branch_ifsc",
        "branch_micr",
        "branch_city",
        "branch_state",
        # --- Customer ---
        "customer_id",
        "customer_name",
        "customer_type",
        "pan",
        "ckyc_number",
        # --- Address (account level) ---
        "address_line1",
        "address_line2",
        "address_city",
        "address_state",
        "address_postal_code",
        "address_country",
        # --- Balances ---
        "balance_opening",
        "balance_closing",
        "balance_current",
        "balance_available",
        # --- Statement period ---
        "statement_from",
        "statement_to",
        "statement_date",
        # --- Summary ---
        "total_credits",
        "total_debits",
        "credit_count",
        "debit_count",
        # --- KYC ---
        "kyc_status",
        # --- Limits ---
        "od_limit",
        "mab_requirement",
        "expected_amb",
        # --- Docx extra data ---
        "docx_serial_no",
        "docx_layer_info",
        "docx_amount_mentioned",
        "docx_ifsc",
        "docx_mobile_numbers",
        "docx_email",
        "docx_proprietor",
        "docx_address",
    ]

    for f in json_files:
        with open(f, "r", encoding="utf-8") as fp:
            d = json.load(fp)

        acc  = d.get("account", {})
        bank = d.get("bank", {})
        cust = d.get("customer", {})
        sp   = d.get("statement_period", {})
        summ = d.get("summary", {})
        bal  = acc.get("balances", {}) or {}
        br   = acc.get("branch", {}) or {}
        addr = acc.get("address", {}) or {}
        kyc  = acc.get("kyc", {}) or {}
        lim  = acc.get("limits", {}) or {}

        acnum = acc.get("account_number", "")

        # Try to find docx enrichment
        def find_docx(ac):
            """Try multiple keys to match the docx record."""
            for key in [ac, ac.lstrip("0"), ac.lstrip("-")]:
                if key in docx_data:
                    return docx_data[key]
            return {}

        enrich = find_docx(str(acnum) if acnum else "")

        # Customer addresses
        cust_addrs = cust.get("addresses", [])
        cust_addr = cust_addrs[0] if cust_addrs and isinstance(cust_addrs[0], dict) else {}

        row = {
            "account_id":           safe_get(acc, "account_id"),
            "statement_id":         d.get("statement_id"),
            "bank_name":            safe_get(bank, "bank_name"),
            "bank_code":            safe_get(bank, "bank_code"),
            "swift_code":           safe_get(bank, "swift_code"),
            "currency":             safe_get(acc, "currency") or safe_get(bank, "currency"),
            "account_number":       acnum,
            "masked_account_number": safe_get(acc, "masked_account_number"),
            "account_holder_name":  safe_get(acc, "account_holder_name"),
            "account_type":         safe_get(acc, "account_type"),
            "scheme":               safe_get(acc, "scheme"),
            "product_type":         safe_get(acc, "product_type"),
            "mode_of_operation":    safe_get(acc, "mode_of_operation"),
            "account_status":       safe_get(acc, "account_status"),
            "account_open_date":    safe_get(acc, "account_open_date"),
            "account_closed_date":  safe_get(acc, "account_closed_date"),
            "date_of_opening":      safe_get(acc, "date_of_opening"),
            "date_of_closing":      safe_get(acc, "date_of_closing"),
            "branch_name":          safe_get(br, "branch_name"),
            "branch_code":          safe_get(br, "branch_code"),
            "branch_ifsc":          safe_get(br, "ifsc"),
            "branch_micr":          safe_get(br, "micr"),
            "branch_city":          safe_get(br, "city"),
            "branch_state":         safe_get(br, "state"),
            "customer_id":          safe_get(cust, "customer_id"),
            "customer_name":        safe_get(cust, "customer_name"),
            "customer_type":        safe_get(cust, "customer_type"),
            "pan":                  safe_get(cust, "pan") or safe_get(kyc, "pan"),
            "ckyc_number":          safe_get(cust, "ckyc_number") or safe_get(kyc, "ckyc_number"),
            # Address: prefer account-level, fall back to customer address
            "address_line1":        safe_get(addr, "line1") or safe_get(cust_addr, "line1"),
            "address_line2":        safe_get(addr, "line2") or safe_get(cust_addr, "line2"),
            "address_city":         safe_get(addr, "city")  or safe_get(cust_addr, "city"),
            "address_state":        safe_get(addr, "state") or safe_get(cust_addr, "state"),
            "address_postal_code":  safe_get(addr, "postal_code") or safe_get(cust_addr, "postal_code"),
            "address_country":      safe_get(addr, "country") or safe_get(cust_addr, "country"),
            "balance_opening":      safe_get(bal, "opening"),
            "balance_closing":      safe_get(bal, "closing"),
            "balance_current":      safe_get(bal, "current"),
            "balance_available":    safe_get(bal, "available"),
            "statement_from":       safe_get(sp, "from"),
            "statement_to":         safe_get(sp, "to"),
            "statement_date":       safe_get(sp, "statement_date"),
            "total_credits":        safe_get(summ, "total_credits"),
            "total_debits":         safe_get(summ, "total_debits"),
            "credit_count":         safe_get(summ, "credit_count"),
            "debit_count":          safe_get(summ, "debit_count"),
            "kyc_status":           safe_get(kyc, "kyc_status"),
            "od_limit":             safe_get(lim, "od_limit"),
            "mab_requirement":      safe_get(lim, "mab_requirement"),
            "expected_amb":         safe_get(lim, "expected_amb"),
            # Docx enrichment
            "docx_serial_no":       enrich.get("docx_serial_no", ""),
            "docx_layer_info":      enrich.get("layer_info", ""),
            "docx_amount_mentioned": enrich.get("amount_mentioned", ""),
            "docx_ifsc":            enrich.get("ifsc_docx", ""),
            "docx_mobile_numbers":  enrich.get("mobile_numbers", ""),
            "docx_email":           enrich.get("email_docx", ""),
            "docx_proprietor":      enrich.get("proprietor_docx", ""),
            "docx_address":         enrich.get("address_docx", ""),
        }
        account_rows.append(row)

    with open(ACCOUNTS_CSV, "w", newline="", encoding="utf-8-sig") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=account_fieldnames)
        writer.writeheader()
        writer.writerows(account_rows)

    print(f"\nAccounts CSV written: {ACCOUNTS_CSV}")
    print(f"  Total account rows: {len(account_rows)}")

    # -----------------------------------------------------------------------
    # 2. TRANSACTIONS CSV
    # -----------------------------------------------------------------------
    tx_fieldnames = [
        # --- Link key (joins to accounts.csv) ---
        "account_id",
        "statement_id",
        # --- Transaction identity ---
        "transaction_id",
        "record_number",
        "journal_number",
        # --- Dates ---
        "transaction_date",
        "transaction_datetime",
        "posting_date",
        "posting_datetime",
        "value_date",
        # --- Classification ---
        "transaction_type",
        "transaction_subtype",
        "transaction_code",
        "transaction_mode",
        "transaction_direction",
        # --- Reference ---
        "reference_number",
        "instrument_number",
        "cheque_number",
        # --- Description ---
        "narration",
        "description",
        # --- Amounts ---
        "debit_amount",
        "credit_amount",
        "transaction_amount",
        "balance",
        "balance_type",
        # --- Counterparty ---
        "counterparty_name",
        "counterparty_account_number",
        "counterparty_masked_account",
        "counterparty_bank_name",
        "counterparty_bank_code",
        "counterparty_ifsc",
        "counterparty_upi_id",
        # --- Derived details ---
        "derived_transaction_mode",
        "derived_sender_receiver_name",
        "derived_bank_name",
        "derived_bank_ifsc",
        "derived_upi_id",
        "derived_reference_number",
        "derived_masked_account",
        "derived_atm_card",
        "derived_atm_location",
        "derived_charges_type",
        "derived_remarks",
        # --- Processing ---
        "processing_branch",
        "processing_teller_id",
        "processing_entry_user_id",
    ]

    total_txns = 0
    with open(TRANSACTIONS_CSV, "w", newline="", encoding="utf-8-sig") as csvf:
        writer = csv.DictWriter(csvf, fieldnames=tx_fieldnames, extrasaction="ignore")
        writer.writeheader()

        for f in json_files:
            with open(f, "r", encoding="utf-8") as fp:
                d = json.load(fp)

            acc_id    = safe_get(d, "account", "account_id")
            stmt_id   = d.get("statement_id")
            txns      = d.get("transactions", [])

            for tx in txns:
                if not isinstance(tx, dict):
                    continue

                cp  = tx.get("counterparty") or {}
                dd  = tx.get("derived_details") or {}
                prc = tx.get("processing") or {}

                row = {
                    "account_id":                    acc_id,
                    "statement_id":                  stmt_id,
                    "transaction_id":                tx.get("transaction_id"),
                    "record_number":                 tx.get("record_number"),
                    "journal_number":                tx.get("journal_number"),
                    "transaction_date":              tx.get("transaction_date"),
                    "transaction_datetime":          tx.get("transaction_datetime"),
                    "posting_date":                  tx.get("posting_date"),
                    "posting_datetime":              tx.get("posting_datetime"),
                    "value_date":                    tx.get("value_date"),
                    "transaction_type":              tx.get("transaction_type"),
                    "transaction_subtype":           tx.get("transaction_subtype"),
                    "transaction_code":              tx.get("transaction_code"),
                    "transaction_mode":              tx.get("transaction_mode"),
                    "transaction_direction":         tx.get("transaction_direction"),
                    "reference_number":              tx.get("reference_number"),
                    "instrument_number":             tx.get("instrument_number"),
                    "cheque_number":                 tx.get("cheque_number"),
                    "narration":                     tx.get("narration"),
                    "description":                   tx.get("description"),
                    "debit_amount":                  tx.get("debit_amount"),
                    "credit_amount":                 tx.get("credit_amount"),
                    "transaction_amount":            tx.get("transaction_amount"),
                    "balance":                       tx.get("balance"),
                    "balance_type":                  tx.get("balance_type"),
                    "counterparty_name":             cp.get("name"),
                    "counterparty_account_number":   cp.get("account_number"),
                    "counterparty_masked_account":   cp.get("masked_account"),
                    "counterparty_bank_name":        cp.get("bank_name"),
                    "counterparty_bank_code":        cp.get("bank_code"),
                    "counterparty_ifsc":             cp.get("ifsc"),
                    "counterparty_upi_id":           cp.get("upi_id"),
                    "derived_transaction_mode":      dd.get("transaction_mode"),
                    "derived_sender_receiver_name":  dd.get("sender_receiver_name"),
                    "derived_bank_name":             dd.get("bank_name"),
                    "derived_bank_ifsc":             dd.get("bank_ifsc"),
                    "derived_upi_id":                dd.get("upi_id"),
                    "derived_reference_number":      dd.get("reference_number"),
                    "derived_masked_account":        dd.get("masked_account"),
                    "derived_atm_card":              dd.get("atm_card"),
                    "derived_atm_location":          dd.get("atm_location"),
                    "derived_charges_type":          dd.get("charges_type"),
                    "derived_remarks":               dd.get("remarks"),
                    "processing_branch":             prc.get("transaction_branch"),
                    "processing_teller_id":          prc.get("teller_id"),
                    "processing_entry_user_id":      prc.get("entry_user_id"),
                }
                writer.writerow(row)
                total_txns += 1

    print(f"\nTransactions CSV written: {TRANSACTIONS_CSV}")
    print(f"  Total transaction rows: {total_txns}")

    # -----------------------------------------------------------------------
    # Docx coverage report
    # -----------------------------------------------------------------------
    print("\n--- Docx enrichment coverage ---")
    matched = sum(1 for r in account_rows if r["docx_serial_no"])
    unmatched = [r for r in account_rows if not r["docx_serial_no"]]
    print(f"  Matched  : {matched}/{len(account_rows)}")
    if unmatched:
        print(f"  Unmatched: {len(unmatched)} accounts (no docx record found by account number):")
        for r in unmatched:
            print(f"    {r['account_id']} | {r['account_number']} | {r['bank_name']} | {r['account_holder_name']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
