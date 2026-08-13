"""
normalize_schema.py
===================
Makes all bank JSON files share an identical universal schema.

Rules:
  - NEVER change any existing non-null data value.
  - Add missing keys with null (None) as the default value.
  - Re-order keys to match the canonical key order defined in UNIVERSAL_TEMPLATE.
  - Extra bank-specific keys already in the data are preserved (appended after
    template keys so structural core is always identical).
  - customer.addresses items that are raw strings are converted to the canonical
    address object shape with the string stored in line1.
"""

import os
import json
import glob
import copy

WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Universal template — defines canonical KEY ORDER and structure.
# All values here are None (placeholder); actual data values from files are kept.
# ---------------------------------------------------------------------------
UNIVERSAL_TEMPLATE = {
    "statement_id": None,
    "document": {
        "document_id": None,
        "document_type": None,
        "source_file": None,
        "source_file_hash": None,
        "source_format": None,
        "page_count": None,
        "statement_generated_at": None,
        "additional_fields": {
            "report_type": None,
            "report_printed_pages": None,
            "reference_number": None,
            "statement_total_debit": None,
            "statement_total_credit": None,
            "debit_count": None,
            "credit_count": None
        }
    },
    "bank": {
        "bank_name": None,
        "bank_code": None,
        "swift_code": None,
        "currency": None,
        "additional_fields": {}
    },
    "customer": {
        "customer_id": None,
        "customer_number": None,
        "cif": None,
        "crn": None,
        "customer_name": None,
        "customer_type": None,
        "pan": None,
        "ckyc_number": None,
        "kyc_number": None,
        "phone_numbers": [],
        "email_addresses": [],
        "addresses": [
            {
                "address_id": None,
                "address_type": None,
                "line1": None,
                "line2": None,
                "line3": None,
                "city": None,
                "state": None,
                "country": None,
                "postal_code": None,
                "additional_fields": {
                    "district": None
                }
            }
        ],
        "additional_fields": {
            "joint_holder_raw": None,
            "joint_holder": None
        }
    },
    "account": {
        "account_id": None,
        "account_number": None,
        "masked_account_number": None,
        "old_account_number": None,
        "customer_id": None,
        "customer_number": None,
        "account_holder_name": None,
        "joint_holders": [],
        "account_type": None,
        "scheme": None,
        "scheme_code": None,
        "scheme_type": None,
        "product_type": None,
        "product_code": None,
        "currency": None,
        "mode_of_operation": None,
        "account_status": None,
        "customer_status": None,
        "account_open_date": None,
        "account_closed_date": None,
        "account_status_date": None,
        "date_of_opening": None,
        "date_of_closing": None,
        "branch": {
            "branch_id": None,
            "branch_code": None,
            "branch_name": None,
            "branch_address": None,
            "city": None,
            "state": None,
            "phone": None,
            "ifsc": None,
            "micr": None,
            "sol_id": None,
            "additional_fields": {
                "gstin": None
            }
        },
        "address": {
            "address_id": None,
            "address_type": None,
            "line1": None,
            "line2": None,
            "line3": None,
            "city": None,
            "state": None,
            "country": None,
            "postal_code": None,
            "additional_fields": {
                "district": None
            }
        },
        "contact": {
            "phone1": None,
            "phone2": None,
            "mobile": None,
            "pager": None,
            "telex": None,
            "email": None
        },
        "nomination": {
            "registered": None,
            "nominee_name": None,
            "registration_number": None,
            "effective_date": None,
            "additional_fields": {}
        },
        "kyc": {
            "pan": None,
            "ckyc_number": None,
            "kyc_number": None,
            "kyc_status": None,
            "additional_fields": {}
        },
        "limits": {
            "od_limit": None,
            "mab_requirement": None,
            "expected_amb": None,
            "additional_fields": {
                "qab_requirement": None,
                "mab_qab_requirement": None,
                "interest_rate_percent": None
            }
        },
        "balances": {
            "opening": None,
            "closing": None,
            "current": None,
            "available": None,
            "effective_available": None,
            "float": None,
            "funds_in_clearing": None
        },
        "additional_fields": {
            "joint_holder_raw": None,
            "lien": None,
            "uncleared_balance": None,
            "interest_rate_percent": None,
            "user_name": None,
            "report_number": None,
            "nominee_registered": None
        }
    },
    "statement_period": {
        "from": None,
        "to": None,
        "statement_date": None,
        "date_of_issue": None,
        "additional_fields": {
            "as_on": None,
            "derived_from_transaction_date_range": None,
            "reference_number": None,
            "statement_opening_balance_date": None,
            "footer_total_debit": None,
            "footer_total_credit": None,
            "footer_debit_count": None,
            "footer_credit_count": None,
            "footer_total_label": None
        }
    },
    "transactions": [
        {
            "transaction_id": None,
            "record_number": None,
            "journal_number": None,
            "transaction_date": None,
            "transaction_datetime": None,
            "posting_date": None,
            "posting_datetime": None,
            "value_date": None,
            "transaction_type": None,
            "transaction_subtype": None,
            "transaction_code": None,
            "transaction_mode": None,
            "transaction_direction": None,
            "reference_number": None,
            "instrument_number": None,
            "cheque_number": None,
            "narration": None,
            "description": None,
            "debit_amount": None,
            "credit_amount": None,
            "transaction_amount": None,
            "balance": None,
            "balance_type": None,
            "counterparty": {
                "name": None,
                "account_number": None,
                "masked_account": None,
                "bank_name": None,
                "bank_code": None,
                "ifsc": None,
                "branch": None,
                "upi_id": None
            },
            "derived_details": {
                "transaction_mode": None,
                "sender_receiver_name": None,
                "bank_name": None,
                "bank_code": None,
                "bank_ifsc": None,
                "upi_id": None,
                "reference_number": None,
                "masked_account": None,
                "atm_card": None,
                "atm_location": None,
                "charges_type": None,
                "remarks": None,
                "additional_fields": {
                    "source_page": None,
                    "source_inst_type": None,
                    "source_sub_type": None
                }
            },
            "processing": {
                "transaction_branch": None,
                "teller_id": None,
                "entry_user_id": None,
                "verified_user_id": None,
                "ctr_batch_number": None,
                "additional_fields": {}
            },
            "additional_fields": {
                "source_page": None
            }
        }
    ],
    "summary": {
        "opening_balance": None,
        "closing_balance": None,
        "current_balance": None,
        "available_balance": None,
        "effective_available_balance": None,
        "float_balance": None,
        "funds_in_clearing": None,
        "total_debits": None,
        "total_credits": None,
        "total_withdrawals": None,
        "total_deposits": None,
        "debit_count": None,
        "credit_count": None,
        "withdrawal_count": None,
        "deposit_count": None,
        "page_total_debit": None,
        "page_total_credit": None,
        "statement_total_debit": None,
        "statement_total_credit": None,
        "additional_fields": {
            "grand_total_debit": None,
            "grand_total_credit": None,
            "lien": None,
            "uncleared_balance": None,
            "pending_penal_charges": None
        }
    },
    "restrictions": [],
    "documents": [],
    "money_trail": [],
    "additional_fields": {
        "statement_account_label": None,
        "statement_pages": None,
        "legend": {},
        "statement_summary_dr_cr": None,
        "source_statement_period_text": None
    }
}

# Template for a single address object (used when normalizing list items)
ADDRESS_TEMPLATE = UNIVERSAL_TEMPLATE["customer"]["addresses"][0]


# ---------------------------------------------------------------------------
# Core normalization helpers
# ---------------------------------------------------------------------------

def normalize_address(addr):
    """Ensure an address is a dict. If it's a raw string, put it in line1."""
    if isinstance(addr, str):
        base = copy.deepcopy(ADDRESS_TEMPLATE)
        base["line1"] = addr
        return base
    if isinstance(addr, dict):
        return apply_template(ADDRESS_TEMPLATE, addr)
    return copy.deepcopy(ADDRESS_TEMPLATE)


def apply_template(tmpl, data):
    """
    Recursively merge `data` into `tmpl` structure:
      - Keys in tmpl come first (in template order).
      - Extra keys present in data but not in tmpl are appended at the end.
      - Existing non-null values in data are NEVER changed.
      - Missing keys are filled with the template's default (None / [] / {}).
    """
    if not isinstance(tmpl, dict):
        # Primitive placeholder: keep actual data value
        return data if data is not None else None

    result = {}
    if not isinstance(data, dict):
        data = {}

    # 1. Walk template keys in order
    for k, default_val in tmpl.items():
        val = data.get(k)

        if isinstance(default_val, dict):
            child_data = val if isinstance(val, dict) else {}
            result[k] = apply_template(default_val, child_data)

        elif isinstance(default_val, list):
            if len(default_val) > 0 and isinstance(default_val[0], dict):
                # It's a list-of-objects field
                item_tmpl = default_val[0]
                if k == "addresses" and isinstance(val, list):
                    # Special handling: list items may be strings
                    result[k] = [normalize_address(item) for item in val]
                elif isinstance(val, list):
                    result[k] = [apply_template(item_tmpl, item if isinstance(item, dict) else {}) for item in val]
                else:
                    result[k] = []
            else:
                # Plain list (phone_numbers, email_addresses, restrictions, etc.)
                result[k] = val if isinstance(val, list) else []
        else:
            # Primitive field: keep existing value even if None, fill with None only if key absent
            result[k] = val if k in data else None

    # 2. Append extra keys from data that aren't in the template
    for k, val in data.items():
        if k not in tmpl:
            result[k] = val

    return result


def normalize_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        original = json.load(f)

    normalized = apply_template(UNIVERSAL_TEMPLATE, original)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)

    return normalized


# ---------------------------------------------------------------------------
# Schema signature — captures structure only (keys + nesting, not values)
# ---------------------------------------------------------------------------

def schema_signature(obj):
    """Return a hashable signature representing the key structure."""
    if isinstance(obj, dict):
        return ("dict", tuple((k, schema_signature(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        if len(obj) > 0 and isinstance(obj[0], dict):
            return ("list_of_dicts", schema_signature(obj[0]))
        return ("list",)
    else:
        return ("field",)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    json_files = sorted(glob.glob(os.path.join(WORKSPACE, "**", "*.json"), recursive=True))
    # Exclude this script itself or any generated files
    json_files = [f for f in json_files if not os.path.basename(f).startswith("_")]

    print(f"Found {len(json_files)} JSON files to normalize.\n")

    # --- Step 1: Normalize all files ---
    print("=" * 60)
    print("STEP 1: Normalizing all files...")
    print("=" * 60)
    for f in json_files:
        rel = os.path.relpath(f, WORKSPACE)
        normalize_file(f)
        print(f"  [OK] {rel}")

    # --- Step 2: Verify all schemas are identical ---
    print("\n" + "=" * 60)
    print("STEP 2: Verifying schema consistency...")
    print("=" * 60)

    signatures = {}
    all_match = True

    for f in json_files:
        rel = os.path.relpath(f, WORKSPACE)
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        sig = schema_signature(data)
        signatures[rel] = sig

    # Compare all signatures to the first one
    reference_file = json_files[0]
    reference_rel = os.path.relpath(reference_file, WORKSPACE)
    reference_sig = signatures[reference_rel]

    mismatches = []
    for rel, sig in signatures.items():
        if sig != reference_sig:
            all_match = False
            mismatches.append(rel)

    if all_match:
        print(f"\n  ✅ ALL {len(json_files)} FILES HAVE IDENTICAL SCHEMA STRUCTURE!")
        print(f"  Reference file: {reference_rel}")
    else:
        print(f"\n  ❌ SCHEMA MISMATCHES FOUND in {len(mismatches)} files:")
        for rel in mismatches:
            print(f"    - {rel}")

    # --- Step 3: Verify top-level keys are identical across all files ---
    print("\n" + "=" * 60)
    print("STEP 3: Top-level key check...")
    print("=" * 60)

    top_key_groups = {}
    for f in json_files:
        rel = os.path.relpath(f, WORKSPACE)
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        keys = tuple(data.keys())
        top_key_groups.setdefault(keys, []).append(rel)

    if len(top_key_groups) == 1:
        keys_list = list(top_key_groups.keys())[0]
        print(f"\n  ✅ All files share the same {len(keys_list)} top-level keys:")
        print(f"     {list(keys_list)}")
    else:
        print(f"\n  ❌ {len(top_key_groups)} different top-level key sets found:")
        for keys, files in top_key_groups.items():
            print(f"\n  Keys {list(keys)}")
            for rel in files[:3]:
                print(f"    -> {rel}")

    # --- Step 4: Check transaction keys ---
    print("\n" + "=" * 60)
    print("STEP 4: Transaction key check...")
    print("=" * 60)

    tx_key_groups = {}
    for f in json_files:
        rel = os.path.relpath(f, WORKSPACE)
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        txns = data.get("transactions", [])
        if txns:
            keys = tuple(txns[0].keys())
            tx_key_groups.setdefault(keys, []).append(rel)

    if len(tx_key_groups) == 1:
        print(f"  ✅ All transaction objects share the same {len(list(tx_key_groups.keys())[0])} keys.")
    else:
        print(f"  ❌ {len(tx_key_groups)} different transaction key sets found.")
        for keys, files in tx_key_groups.items():
            print(f"\n  Keys: {list(keys)}")
            for rel in files[:2]:
                print(f"    -> {rel}")

    # --- Summary ---
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total files processed : {len(json_files)}")
    print(f"  Schema uniform        : {'YES ✅' if all_match and len(top_key_groups) == 1 and len(tx_key_groups) == 1 else 'NO ❌'}")


if __name__ == "__main__":
    main()
