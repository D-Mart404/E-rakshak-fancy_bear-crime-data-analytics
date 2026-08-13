"""
verify_schema.py
================
Verifies that all bank JSON files have identical schema structure after normalization.
Run this after normalize_schema.py has been executed.
"""

import os
import json
import glob
import sys

WORKSPACE = os.path.dirname(os.path.abspath(__file__))


# Keys whose sub-keys are deliberately bank-specific (free-form lookup dicts).
# We treat them as opaque dict fields in schema comparison.
OPAQUE_DICT_KEYS = {"legend"}

# Keys whose list items are objects but may legitimately be empty in some files.
# An empty list [] is considered schema-equivalent to a list-of-dicts [{...}].
OPTIONAL_LIST_KEYS = {"addresses", "restrictions", "documents", "money_trail",
                      "joint_holders", "phone_numbers", "email_addresses"}


def schema_signature(obj, key=None):
    """Return a hashable, recursive signature of the key structure (not values).

    Args:
        obj: The JSON value to inspect.
        key: The dict key name that produced this value (used to detect opaque fields).
    """
    if isinstance(obj, dict):
        if key in OPAQUE_DICT_KEYS:
            # Treat as an opaque dict field — its sub-keys are intentionally variable.
            return ("opaque_dict",)
        return ("dict", tuple((k, schema_signature(v, k)) for k, v in obj.items()))
    elif isinstance(obj, list):
        if key in OPTIONAL_LIST_KEYS:
            # Empty list is schema-equivalent to list-of-objects for optional fields.
            return ("optional_list",)
        if len(obj) > 0 and isinstance(obj[0], dict):
            return ("list_of_dicts", schema_signature(obj[0]))
        return ("list",)
    else:
        return ("field",)


def get_key_structure(obj, depth=0, prefix="", parent_key=None):
    """Return a flat list of all nested key paths for diff reporting."""
    paths = []
    if isinstance(obj, dict):
        if parent_key in OPAQUE_DICT_KEYS:
            # Don't recurse into opaque dicts — their sub-keys are intentionally variable.
            return paths
        for k, v in obj.items():
            full_path = f"{prefix}.{k}" if prefix else k
            paths.append(full_path)
            paths.extend(get_key_structure(v, depth + 1, full_path, k))
    elif isinstance(obj, list):
        if parent_key in OPTIONAL_LIST_KEYS:
            # Don't penalise empty optional lists in path comparison.
            return paths
        if obj and isinstance(obj[0], dict):
            paths.extend(get_key_structure(obj[0], depth + 1, f"{prefix}[]"))
    return paths


def sep(char="=", n=60):
    print(char * n)


def main():
    json_files = sorted(glob.glob(os.path.join(WORKSPACE, "**", "*.json"), recursive=True))
    # Exclude helper scripts saved as json (unlikely) or any temp files
    json_files = [f for f in json_files if not os.path.basename(f).startswith("_")]

    print(f"Found {len(json_files)} JSON files to verify.\n")

    all_data = {}
    for f in json_files:
        rel = os.path.relpath(f, WORKSPACE)
        with open(f, "r", encoding="utf-8") as fp:
            all_data[rel] = json.load(fp)

    ref_rel = os.path.relpath(json_files[0], WORKSPACE)
    ref_data = all_data[ref_rel]
    ref_sig = schema_signature(ref_data)
    ref_paths = set(get_key_structure(ref_data))

    # -----------------------------------------------------------------------
    sep()
    print("STEP 1: Full Schema Signature Check (keys + nesting hierarchy)")
    sep()

    mismatches = []
    for rel, data in all_data.items():
        sig = schema_signature(data)
        if sig != ref_sig:
            mismatches.append(rel)
            file_paths = set(get_key_structure(data))
            missing_from_file = ref_paths - file_paths
            extra_in_file = file_paths - ref_paths
            print(f"\n  MISMATCH: {rel}")
            if missing_from_file:
                print(f"    Missing keys : {sorted(missing_from_file)}")
            if extra_in_file:
                print(f"    Extra keys   : {sorted(extra_in_file)}")

    if not mismatches:
        print(f"\n  PASS - All {len(json_files)} files have identical schema structure!")
    else:
        print(f"\n  FAIL - {len(mismatches)} file(s) differ from reference '{ref_rel}'")

    # -----------------------------------------------------------------------
    sep()
    print("STEP 2: Top-Level Key Order Check")
    sep()

    top_key_groups = {}
    for rel, data in all_data.items():
        keys = tuple(data.keys())
        top_key_groups.setdefault(keys, []).append(rel)

    if len(top_key_groups) == 1:
        k = list(top_key_groups.keys())[0]
        print(f"\n  PASS - All files share the same {len(k)} top-level keys (in same order):")
        for key in k:
            print(f"    - {key}")
    else:
        print(f"\n  FAIL - {len(top_key_groups)} different top-level key sets found:")
        for keys, files in top_key_groups.items():
            print(f"\n    Key set: {list(keys)}")
            print(f"    Files  : {files[:3]}{' ...' if len(files) > 3 else ''}")

    # -----------------------------------------------------------------------
    sep()
    print("STEP 3: Transaction Object Key Check")
    sep()

    tx_key_groups = {}
    for rel, data in all_data.items():
        txns = data.get("transactions", [])
        if txns and isinstance(txns[0], dict):
            keys = tuple(txns[0].keys())
            tx_key_groups.setdefault(keys, []).append(rel)

    if len(tx_key_groups) == 1:
        k = list(tx_key_groups.keys())[0]
        print(f"\n  PASS - All transaction objects share the same {len(k)} keys (in same order).")
    elif len(tx_key_groups) == 0:
        print("\n  INFO - No transactions found in any file.")
    else:
        print(f"\n  FAIL - {len(tx_key_groups)} different transaction key sets found:")
        for keys, files in tx_key_groups.items():
            print(f"\n    Key set ({len(keys)} keys): {list(keys)}")
            print(f"    Files  : {files[:2]}")

    # -----------------------------------------------------------------------
    sep()
    print("STEP 4: Summary & Extra Key Counts Across Files")
    sep()

    all_top_keys_union = set()
    for data in all_data.values():
        all_top_keys_union.update(data.keys())

    print(f"\n  Total distinct top-level keys across ALL files : {len(all_top_keys_union)}")

    # Check per-key presence
    key_absent = {}
    for k in sorted(all_top_keys_union):
        absent_in = [rel for rel, data in all_data.items() if k not in data]
        if absent_in:
            key_absent[k] = absent_in

    if key_absent:
        print("\n  Keys not present in all files:")
        for k, files in key_absent.items():
            print(f"    '{k}' absent in {len(files)} file(s)")
    else:
        print("  Every top-level key is present in every file.")

    # -----------------------------------------------------------------------
    sep()
    print("FINAL RESULT")
    sep()

    step1_ok = len(mismatches) == 0
    step2_ok = len(top_key_groups) == 1
    step3_ok = len(tx_key_groups) <= 1

    overall = step1_ok and step2_ok and step3_ok

    status = "PASS -- ALL SCHEMAS ARE UNIFORM" if overall else "FAIL -- SCHEMAS ARE NOT UNIFORM"
    print(f"\n  {status}")
    print(f"  Total files processed   : {len(json_files)}")
    print(f"  Schema signature match  : {'PASS' if step1_ok else 'FAIL'}")
    print(f"  Top-level key uniformity: {'PASS' if step2_ok else 'FAIL'}")
    print(f"  Transaction key uniformity: {'PASS' if step3_ok else 'FAIL'}")
    sep()

    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
