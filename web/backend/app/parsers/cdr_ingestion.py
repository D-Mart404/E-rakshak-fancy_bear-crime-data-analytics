import argparse
import glob
import os
import re

import pandas as pd

# Canonical target schema
TARGET_COLUMNS = [
    "A_PARTY",
    "B_PARTY",
    "CALL_DATE",
    "CALL_TIME",
    "DURATION",
    "CALL_TYPE",
    "SERVICE_TYPE",
    "IMEI",
    "IMSI",
    "FIRST_CELL_ID",
    "LAST_CELL_ID",
    "LATITUDE",
    "LONGITUDE",
    "FIRST_LOCATION_ADDRESS",
    "CALL_FORWARDING_NO",
    "ROAMING",
]

# Alias tokens (normalized) → canonical column.
# Matching is fuzzy: header is normalized, then exact/contains/token-overlap scored.
COLUMN_ALIASES: dict[str, list[str]] = {
    "A_PARTY": [
        "target a party number",
        "target a party",
        "a party number",
        "a party no",
        "a party",
        "target no",
        "mobile no",
        "calling party telephone number",
        "calling party",
        "msisdn a",
    ],
    "B_PARTY": [
        "b party number",
        "b party no",
        "b party",
        "other party no",
        "other party",
        "called party telephone number",
        "called party",
        "msisdn b",
    ],
    "CALL_DATE": [
        "call date",
        "call_date",
        "date of call",
        "cdr date",
    ],
    "CALL_TIME": [
        "call initiation time cit",
        "call initiation time",
        "call_initiation_time",
        "call time",
        "cit",
        "start time",
    ],
    "DURATION": [
        "call duration",
        "call_duration",
        "dur s",
        "duration",
        "dur",
    ],
    "CALL_TYPE": [
        "call type",
        "call_type",
    ],
    "SERVICE_TYPE": [
        "service type",
        "service_type",
        "type of service",
    ],
    "IMEI": [
        "imei a",
        "imei",
    ],
    "IMSI": [
        "imsi a",
        "imsi",
    ],
    "FIRST_CELL_ID": [
        "first cell global id",
        "first cgi",
        "first cell id",
        "first_cell_id",
        "cgi",
    ],
    "LAST_CELL_ID": [
        "last cell global id",
        "last cgi",
        "last cell id",
        "last_cell_id",
    ],
    "FIRST_LOCATION_ADDRESS": [
        "first bts location",
        "first cell desc",
        "first location address",
        "first location",
        "bts location",
        "cell address",
    ],
    "LATITUDE": [
        "first lat",
        "latitude",
        "lat",
    ],
    "LONGITUDE": [
        "first long",
        "longitude",
        "long",
        "lng",
    ],
    "LAT_LONG": [
        "first cgi lat long",
        "lat long",
        "lat/long",
    ],
    "ROAMING": [
        "roaming network circle",
        "roaming circle name",
        "roaming circle",
        "roaming a",
        "roam nw",
        "roaming",
    ],
    "CALL_FORWARDING_NO": [
        "call forwarding number",
        "call forwarding",
        "call fow no",
        "call forward",
    ],
}

# Bare "DATE" / "TIME" are weak aliases — only use if no stronger match exists
WEAK_ALIASES = {
    "CALL_DATE": ["date"],
    "CALL_TIME": ["time"],
}


def _norm_header(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\ufeff", "").lower()
    text = text.replace("_", " ").replace("/", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _score_alias(header_norm: str, alias: str) -> int:
    if not header_norm or not alias:
        return 0
    if header_norm == alias:
        return 100
    if alias in header_norm:
        # Prefer tighter containment (alias covers more of header)
        return 70 + int(40 * len(alias) / max(len(header_norm), 1))
    if header_norm in alias:
        return 50
    # Token overlap
    ht = set(header_norm.split())
    at = set(alias.split())
    if not ht or not at:
        return 0
    overlap = len(ht & at) / len(at)
    if overlap >= 0.75:
        return int(40 + 30 * overlap)
    return 0


def map_headers_dynamically(columns: list) -> dict[str, str]:
    """
    Map raw dataframe columns → canonical TARGET / helper names.
    Returns {original_col_name: canonical_name}.
    """
    norms = {col: _norm_header(col) for col in columns}
    assigned: dict[str, str] = {}  # canonical -> original
    mapping: dict[str, str] = {}  # original -> canonical

    # Pass 1: strong aliases
    candidates: list[tuple[int, str, str]] = []  # score, canonical, original
    for orig, norm in norms.items():
        for canonical, aliases in COLUMN_ALIASES.items():
            best = max((_score_alias(norm, a) for a in aliases), default=0)
            if best >= 50:
                candidates.append((best, canonical, str(orig)))

    # Highest score wins; one original col -> one canonical
    candidates.sort(key=lambda x: x[0], reverse=True)
    used_orig: set[str] = set()
    for score, canonical, orig in candidates:
        if canonical in assigned or orig in used_orig:
            continue
        assigned[canonical] = orig
        mapping[orig] = canonical
        used_orig.add(orig)

    # Pass 2: weak aliases only for still-missing fields
    for canonical, aliases in WEAK_ALIASES.items():
        if canonical in assigned:
            continue
        best_score, best_orig = 0, None
        for orig, norm in norms.items():
            if orig in used_orig:
                continue
            for a in aliases:
                sc = _score_alias(norm, a)
                if sc > best_score:
                    best_score, best_orig = sc, orig
        if best_score >= 100 and best_orig is not None:
            # only exact "date"/"time"
            assigned[canonical] = best_orig
            mapping[best_orig] = canonical
            used_orig.add(best_orig)

    return mapping


def find_header_row(file_path, max_scan=40):
    """Bypasses preambles to find the real header."""
    encodings = ("utf-8-sig", "utf-8", "latin1", "cp1252")
    keywords = ["PARTY", "DATE", "TIME", "DURATION", "IMEI", "CELL", "LATITUDE", "CALL", "MSISDN"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, errors="replace") as f:
                for i, line in enumerate(f):
                    if i >= max_scan:
                        break
                    upper_line = line.upper()
                    if sum(1 for kw in keywords if kw in upper_line) >= 2:
                        return i
            break
        except OSError:
            continue
    return 0


def clean_data_artifacts(df):
    """Strips ="VALUE" (BSNL) and 'VALUE' (Airtel/Jio) formatting — only object cols."""
    for col in df.columns:
        if df[col].dtype != "object":
            continue
        s = df[col].astype(str)
        # Fast path: skip columns with no quote/= artifacts
        sample = "".join(s.head(50).tolist())
        if not any(ch in sample for ch in ("'", '"', "=")):
            df[col] = s.replace({"nan": pd.NA, "<NA>": pd.NA, "None": pd.NA})
            continue
        df[col] = s.str.replace(r"^[\'\"=]+|[\'\"=]+$", "", regex=True).replace(
            {"nan": pd.NA, "<NA>": pd.NA, "None": pd.NA}
        )
    return df


def normalize_phone_number(val):
    """
    Standardizes Indian phone numbers to 10 digits.
    Preserves service/alphanumeric IDs (e.g. 'VD-ViCARE').
    """
    if pd.isna(val):
        return pd.NA
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    cleaned = re.sub(r"[^\w-]", "", s)
    if cleaned.isdigit():
        if len(cleaned) == 12 and cleaned.startswith("91"):
            return cleaned[2:]
        if len(cleaned) == 11 and cleaned.startswith("0"):
            return cleaned[1:]
        if len(cleaned) == 10:
            return cleaned
    return cleaned


def _normalize_phone_series(series: pd.Series) -> pd.Series:
    """Vectorized-ish phone normalize (much faster than row apply on large CDRs)."""
    s = series.astype(str).str.strip()
    s = s.str.replace(r"\.0$", "", regex=True)
    cleaned = s.str.replace(r"[^\w-]", "", regex=True)
    digits = cleaned.str.fullmatch(r"\d+")
    out = cleaned.copy()
    # 91XXXXXXXXXX → 10 digits
    m12 = digits & cleaned.str.len().eq(12) & cleaned.str.startswith("91")
    out = out.mask(m12, cleaned.str.slice(2))
    m11 = digits & cleaned.str.len().eq(11) & cleaned.str.startswith("0")
    out = out.mask(m11, cleaned.str.slice(1))
    out = out.replace({"nan": pd.NA, "<NA>": pd.NA, "None": pd.NA, "": pd.NA})
    return out


def process_and_unify_cdr(file_path):
    try:
        if file_path.lower().endswith(".csv"):
            header_idx = find_header_row(file_path)
            df = pd.read_csv(
                file_path,
                encoding="latin1",
                dtype=str,
                skiprows=header_idx,
                on_bad_lines="skip",
                index_col=False,
                low_memory=False,
            )
        elif file_path.lower().endswith((".xls", ".xlsx", ".xlsm")):
            # Try first few rows as header dynamically
            df = None
            for hdr in range(0, 6):
                trial = pd.read_excel(file_path, dtype=str, header=hdr)
                mapped = map_headers_dynamically(list(trial.columns))
                if sum(1 for v in mapped.values() if v in ("A_PARTY", "B_PARTY", "CALL_DATE")) >= 1:
                    df = trial
                    break
            if df is None:
                df = pd.read_excel(file_path, dtype=str)
        else:
            return None
    except Exception as e:
        print(f"Failed to read {file_path}. Error: {e}")
        return None

    if df is None or df.empty:
        return None

    # Dynamic rename (do not rely on exact uppercase keys)
    rename_map = map_headers_dynamically(list(df.columns))
    df = df.rename(columns=rename_map)
    df = df.loc[:, ~df.columns.duplicated()]
    # Only scrub columns we keep — full-frame regex is the main slowdown
    keep_for_clean = [c for c in TARGET_COLUMNS if c in df.columns]
    if keep_for_clean:
        df[keep_for_clean] = clean_data_artifacts(df[keep_for_clean].copy())

    # Split combined Lat/Long
    if "LAT_LONG" in df.columns:
        split_coords = df["LAT_LONG"].astype(str).str.split(r"[/,|;]", expand=True)
        if split_coords.shape[1] >= 2:
            if "LATITUDE" not in df.columns:
                df["LATITUDE"] = split_coords[0]
            if "LONGITUDE" not in df.columns:
                df["LONGITUDE"] = split_coords[1]

    if "CALL_TYPE" in df.columns:
        df["CALL_TYPE"] = (
            df["CALL_TYPE"]
            .astype(str)
            .str.upper()
            .replace(
                {
                    "IN": "INCOMING",
                    "OUT": "OUTGOING",
                    "SMT": "SMS INCOMING",
                    "SMO": "SMS OUTGOING",
                    "A2P_SMSIN": "SMS INCOMING",
                }
            )
        )

    for col in TARGET_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    for col in ("A_PARTY", "B_PARTY", "CALL_FORWARDING_NO"):
        if col in df.columns:
            df[col] = _normalize_phone_series(df[col])

    return df[TARGET_COLUMNS]


def collect_cdr_files(folder_path: str) -> list[str]:
    """Recursively collect CDR inputs; skip unified outputs."""
    patterns = ("*.csv", "*.xls", "*.xlsx", "*.xlsm")
    files: list[str] = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(folder_path, "**", pat), recursive=True))
    out = []
    for f in files:
        name = os.path.basename(f).upper()
        if name.startswith("UNIFIED_"):
            continue
        if name.endswith(".CLASSIFY.JSON") or name.endswith(".GITKEEP"):
            continue
        out.append(f)
    return sorted(set(out))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Unify multi-operator CDR exports into UNIFIED_MASTER_CDR.csv"
    )
    parser.add_argument(
        "input_folder",
        nargs="?",
        default=None,
        help="Folder of raw CDR .csv/.xls/.xlsx (default: ./cdr_dataset next to this script)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output CSV path (default: UNIFIED_MASTER_CDR.csv next to this script)",
    )
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = args.input_folder or os.path.join(script_dir, "cdr_dataset")
    output_path = args.output or os.path.join(script_dir, "UNIFIED_MASTER_CDR.csv")

    files = collect_cdr_files(folder_path)
    all_dataframes = []
    for file in files:
        processed_df = process_and_unify_cdr(file)
        if processed_df is not None and not processed_df.empty:
            all_dataframes.append(processed_df)

    if all_dataframes:
        master_cdr = pd.concat(all_dataframes, ignore_index=True)
        master_cdr.dropna(subset=["A_PARTY"], inplace=True)
        print("\n Unification Complete!")
        print(f"Files processed: {len(files)}")
        print(f"Total unified rows: {len(master_cdr)}")
        os.makedirs(os.path.dirname(os.path.abspath(output_path)) or ".", exist_ok=True)
        master_cdr.to_csv(output_path, index=False)
        print(f"Saved cleanly to '{output_path}'")
        try:
            display(master_cdr.head())
        except NameError:
            pass
    else:
        print(f"No valid data found in: {folder_path}")
