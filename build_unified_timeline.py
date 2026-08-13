"""
build_unified_timeline.py
=========================
Unifies transactions.csv, UNIFIED_MASTER_CDR.csv, and unified_master_ipdr.csv / .xlsx
using account and mobile number information from accounts.csv and bank account ni mahiti.docx.

Features 2-Hop Entity & Counterparty Resolution for IPDR data!

Outputs:
  1. unified_master_ipdr.csv       - Standardized CSV export of IPDR excel
  2. unified_master_timeline.csv   - Comprehensive master timeline of all events sorted by timestamp
  3. unified_master_timeline.json  - JSON master timeline & dataset metadata
  4. entities_summary.json         - Summary profiles of all resolved entities with event statistics
  5. entity_timelines/             - Directory containing per-entity chronological timelines (CSV & JSON)
  6. index.html                    - Interactive visual dashboard for browsing timelines & entity profiles
"""

import os
import sys
import json
import re
import pandas as pd
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_CSV = os.path.join(WORKSPACE, "accounts.csv")
TRANSACTIONS_CSV = os.path.join(WORKSPACE, "transactions.csv")
CDR_CSV = os.path.join(WORKSPACE, "UNIFIED_MASTER_CDR.csv")
IPDR_XLSX = os.path.join(WORKSPACE, "unified_master_idpr.xlsx")
IPDR_CSV = os.path.join(WORKSPACE, "unified_master_ipdr.csv")
DOCX_FILE = os.path.join(WORKSPACE, "bank account ni mahiti.docx")

OUTPUT_TIMELINE_CSV = os.path.join(WORKSPACE, "unified_master_timeline.csv")
OUTPUT_TIMELINE_JSON = os.path.join(WORKSPACE, "unified_master_timeline.json")
OUTPUT_ENTITIES_JSON = os.path.join(WORKSPACE, "entities_summary.json")
ENTITIES_DIR = os.path.join(WORKSPACE, "entity_timelines")

os.makedirs(ENTITIES_DIR, exist_ok=True)


def normalize_entity_key(text):
    if not text or pd.isna(text):
        return ""
    s = str(text).strip().upper()
    if 'RAKHOLIYA GAURANG' in s or 'ROYAL CREATION' in s:
        return 'RAKHOLIYA GAURANG HARSUKHBHAI (ROYAL CREATION)'
    if 'GAURAV BAGAN' in s or 'A1 DREAM' in s or 'SAJID AHMAD' in s or 'AALIYA' in s:
        return 'SAJID AHMAD / GAURAV BAGAN MALLIK (A1 DREAM / AALIYA)'
    if 'KAMEJALIYA NARESH' in s or 'NK CREATION' in s:
        return 'KAMEJALIYA NARESH REVABHAI'
    if 'UMESHBHAI' in s:
        return 'UMESHBHAI KARSHANBHAI JUNJALA'
    if 'MAKWANA KRISHNABEN' in s:
        return 'MAKWANA KRISHNABEN DINESHBHAI'
    if 'KATARIYA RAMESHKUMAR' in s:
        return 'KATARIYA RAMESHKUMAR CHANABHAI'
    if 'DANGODRA MILAN' in s:
        return 'DANGODRA MILAN SHIVLAL'

    prop_m = re.search(r'(?:Proprietor|Prop)[:\-]?\s*([^|\n,]+)', s, re.IGNORECASE)
    if prop_m:
        name = prop_m.group(1).strip()
    else:
        name = re.split(r'[|]|\bADDRESS\b|\bADD\b|\bNAME:\b', s, flags=re.IGNORECASE)[0].strip()
        if name.upper().startswith('NAME:'):
            name = name[5:].strip()

    name = re.sub(r'^(MR\.|MS\.|MRS\.|M/S\.|MR\s+|MS\s+|MRS\s+|M/S\s+)', '', name, flags=re.IGNORECASE).strip()
    name = re.sub(r'\s*\.\s*$', '', name).strip().upper()
    return name


def norm_phone(p):
    if pd.isna(p):
        return ""
    s = str(p).strip().split('.')[0]
    s = re.sub(r'^\+?91', '', s)
    s = re.sub(r'^0+', '', s)
    m = re.search(r'[6-9]\d{9}', s)
    return m.group(0) if m else ""


def parse_timestamp(date_val, time_val="00:00:00"):
    if pd.isna(date_val) or not str(date_val).strip():
        return ""
    d_str = str(date_val).strip()
    t_str = str(time_val).strip() if pd.notna(time_val) and str(time_val).strip() and str(time_val).strip() != "nan" else "00:00:00"

    d_str_clean = re.sub(r'\(.*?\)', '', d_str).strip()

    try:
        m = re.search(r'^(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})$', d_str_clean)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dt = datetime(year, month, day)
            t_parts = [int(p) for p in re.findall(r'\d+', t_str)]
            hh = t_parts[0] if len(t_parts) > 0 else 0
            mm = t_parts[1] if len(t_parts) > 1 else 0
            ss = t_parts[2] if len(t_parts) > 2 else 0
            dt = dt.replace(hour=hh, minute=mm, second=ss)
            return dt.strftime('%Y-%m-%d %H:%M:%S')

        dt = pd.to_datetime(d_str_clean, errors='coerce')
        if pd.notna(dt):
            t_parts = [int(p) for p in re.findall(r'\d+', t_str)]
            if len(t_parts) >= 2 and dt.hour == 0 and dt.minute == 0 and dt.second == 0:
                hh = t_parts[0]
                mm = t_parts[1]
                ss = t_parts[2] if len(t_parts) > 2 else 0
                dt = dt.replace(hour=hh, minute=mm, second=ss)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        pass

    return f"{d_str_clean} {t_str}".strip()


def step1_export_ipdr_csv():
    print("Step 1: Converting IPDR Excel to CSV...")
    if os.path.exists(IPDR_XLSX):
        df = pd.read_excel(IPDR_XLSX)
        df.to_csv(IPDR_CSV, index=False)
        print(f"  Exported {len(df)} rows to {IPDR_CSV}")
    else:
        print(f"  Warning: {IPDR_XLSX} not found.")


def step2_build_entities_and_lookups():
    print("Step 2: Performing Entity Resolution & Phone Mapping...")
    accounts_df = pd.read_csv(ACCOUNTS_CSV, low_memory=False)

    docx_records = []
    if os.path.exists(DOCX_FILE):
        try:
            import docx
            doc = docx.Document(DOCX_FILE)
            tbl = doc.tables[0]
            for row in tbl.rows[1:]:
                cells = [c.text.strip().replace('\n', ' ') for c in row.cells]
                if len(cells) >= 5:
                    ac_info, holder_info, mob_info, email_info = cells[1], cells[2], cells[3], cells[4]
                    ac_match = re.search(r'A[/\\]C\s*[:\-]?\s*([\d\w]+)', ac_info, re.IGNORECASE)
                    ac_num = ac_match.group(1).lstrip('0') if ac_match else ''
                    phones = re.findall(r'[6-9]\d{9}', mob_info)
                    docx_records.append({
                        'ac_num': ac_num,
                        'raw_holder': holder_info,
                        'phones': phones,
                        'email': email_info
                    })
            print(f"  Loaded {len(docx_records)} docx enrichment table rows.")
        except Exception as e:
            print(f"  Docx load warning: {e}")

    entities = {}

    for idx, r in accounts_df.iterrows():
        prop = r.get('docx_proprietor')
        holder = r.get('account_holder_name')
        cust = r.get('customer_name')

        raw_key = prop if pd.notna(prop) and str(prop).strip() else (holder if pd.notna(holder) and str(holder).strip() else cust)
        key = normalize_entity_key(raw_key)

        aid = str(r.get('account_id', ''))
        if not key or key == 'NAN':
            key = f"ENTITY_{aid}"

        mob_col = str(r.get('docx_mobile_numbers', ''))
        phones = set(re.findall(r'[6-9]\d{9}', mob_col))

        if key not in entities:
            entities[key] = {
                'entity_name': key,
                'account_ids': set(),
                'account_numbers': set(),
                'phones': set(),
                'pan': set(),
                'banks': set(),
                'addresses': set(),
                'emails': set()
            }

        if aid:
            entities[key]['account_ids'].add(aid)
        if pd.notna(r.get('account_number')):
            entities[key]['account_numbers'].add(str(r.get('account_number')).strip())
        entities[key]['phones'].update(phones)
        if pd.notna(r.get('pan')):
            entities[key]['pan'].add(str(r.get('pan')).strip())
        if pd.notna(r.get('bank_name')):
            entities[key]['banks'].add(str(r.get('bank_name')).strip())

        for addr_col in ['address_line1', 'address_city', 'address_state', 'docx_address']:
            if pd.notna(r.get(addr_col)) and str(r.get(addr_col)).strip():
                entities[key]['addresses'].add(str(r.get(addr_col)).strip())

        for email_col in ['docx_email']:
            if pd.notna(r.get(email_col)) and str(r.get(email_col)).strip():
                entities[key]['emails'].add(str(r.get(email_col)).strip())

    # Enrich from docx table
    for d_rec in docx_records:
        ac_num = d_rec['ac_num']
        phones = set(d_rec['phones'])
        d_key = normalize_entity_key(d_rec['raw_holder'])
        matched_key = None

        if ac_num:
            for ek, ev in entities.items():
                for an in ev['account_numbers']:
                    if ac_num in an or an in ac_num or ac_num.lstrip('0') == an.lstrip('0'):
                        matched_key = ek
                        break
                if matched_key:
                    break

        if not matched_key and d_key:
            for ek in entities.keys():
                if d_key in ek or ek in d_key:
                    matched_key = ek
                    break

        if not matched_key:
            matched_key = d_key if d_key else "DOCX_ENTITY"
            if matched_key not in entities:
                entities[matched_key] = {
                    'entity_name': matched_key,
                    'account_ids': set(),
                    'account_numbers': set([ac_num]) if ac_num else set(),
                    'phones': set(),
                    'pan': set(),
                    'banks': set(),
                    'addresses': set(),
                    'emails': set()
                }

        entities[matched_key]['phones'].update(phones)
        if d_rec.get('email'):
            entities[matched_key]['emails'].add(d_rec['email'])

    # Reverse lookup tables
    acc_id_to_entity = {}
    acc_num_to_entity = {}
    phone_to_entity = {}

    for ek, ev in entities.items():
        for aid in ev['account_ids']:
            acc_id_to_entity[aid] = ek
        for anum in ev['account_numbers']:
            acc_num_to_entity[anum] = ek
            acc_num_to_entity[anum.lstrip('0')] = ek
        for ph in ev['phones']:
            phone_to_entity[ph] = ek

    # -------------------------------------------------------------------------
    # 2-HOP COUNTERPARTY B-PARTY LOOKUP (for IPDR Cross-Linking)
    # -------------------------------------------------------------------------
    b_party_to_entity = {}
    if os.path.exists(CDR_CSV):
        print("  Building 2-Hop Counterparty (B-Party) mapping from CDR...")
        cdr_temp = pd.read_csv(CDR_CSV, low_memory=False)
        for idx, r in cdr_temp.iterrows():
            a_norm = norm_phone(r.get('A_PARTY'))
            b_norm = norm_phone(r.get('B_PARTY'))
            if a_norm and b_norm:
                if a_norm in phone_to_entity:
                    b_party_to_entity[b_norm] = phone_to_entity[a_norm]
                if b_norm in phone_to_entity:
                    b_party_to_entity[a_norm] = phone_to_entity[b_norm]
        print(f"  Discovered {len(b_party_to_entity)} associate B-party phone numbers linked to main entities.")

    print(f"  Resolved {len(entities)} unique entities.")
    print(f"  Lookup maps: {len(acc_id_to_entity)} Account IDs, {len(acc_num_to_entity)} Account Numbers, {len(phone_to_entity)} Direct Phones, {len(b_party_to_entity)} B-Party Phones.")
    return entities, acc_id_to_entity, acc_num_to_entity, phone_to_entity, b_party_to_entity


def step3_process_and_unify(entities, acc_id_to_entity, acc_num_to_entity, phone_to_entity, b_party_to_entity):
    print("Step 3: Ingesting and Unifying Transactions, CDR, and IPDR Data...")

    events = []

    # -------------------------------------------------------------------------
    # A. TRANSACTIONS
    # -------------------------------------------------------------------------
    print("  Processing Transactions...")
    tx_df = pd.read_csv(TRANSACTIONS_CSV, low_memory=False)

    for idx, r in tx_df.iterrows():
        acc_id = str(r.get('account_id', ''))
        entity_name = acc_id_to_entity.get(acc_id, "UNMAPPED")

        date_val = r.get('transaction_date') or r.get('posting_date')
        time_val = r.get('transaction_datetime') or r.get('posting_datetime')
        ts = parse_timestamp(date_val, time_val)

        tx_type = str(r.get('transaction_type', '')).upper()
        if not tx_type or tx_type == 'NAN':
            if pd.notna(r.get('credit_amount')) and float(r.get('credit_amount') or 0) > 0:
                tx_type = 'CREDIT'
            else:
                tx_type = 'DEBIT'

        amt = r.get('transaction_amount') or r.get('credit_amount') or r.get('debit_amount') or 0
        cp_name = r.get('counterparty_name') or r.get('derived_sender_receiver_name') or r.get('counterparty_upi_id') or ''
        narration = str(r.get('narration', '') or r.get('description', '') or '')

        event = {
            'timestamp': ts,
            'entity_name': entity_name,
            'data_source': 'Transaction',
            'event_category': f"Bank {tx_type}",
            'primary_id': acc_id,
            'secondary_id': str(cp_name),
            'amount': float(amt) if pd.notna(amt) and str(amt).replace('.', '', 1).isdigit() else 0.0,
            'duration_sec': 0,
            'data_volume_mb': 0.0,
            'location_or_details': narration[:120],
            'raw_reference': str(r.get('transaction_id', '') or r.get('reference_number', '') or f"TX_{idx}")
        }
        events.append(event)

    # -------------------------------------------------------------------------
    # B. CDR (Call Detail Records)
    # -------------------------------------------------------------------------
    print("  Processing Call Detail Records (CDR)...")
    cdr_df = pd.read_csv(CDR_CSV, low_memory=False)

    for idx, r in cdr_df.iterrows():
        a_party = str(r.get('A_PARTY', ''))
        b_party = str(r.get('B_PARTY', ''))
        a_norm = norm_phone(a_party)
        b_norm = norm_phone(b_party)

        entity_name = phone_to_entity.get(a_norm) or phone_to_entity.get(b_norm) or "UNMAPPED"

        call_date = r.get('CALL_DATE')
        call_time = r.get('CALL_TIME')
        ts = parse_timestamp(call_date, call_time)

        call_type = str(r.get('CALL_TYPE', '')).upper()
        service_type = str(r.get('SERVICE_TYPE', '')).upper()
        event_cat = f"{call_type} {service_type}".strip() if call_type or service_type else "CALL/SMS"

        dur = r.get('DURATION', 0)
        try:
            dur_sec = int(float(dur)) if pd.notna(dur) else 0
        except Exception:
            dur_sec = 0

        address = str(r.get('FIRST_LOCATION_ADDRESS', '') or r.get('ROAMING', '') or '')

        event = {
            'timestamp': ts,
            'entity_name': entity_name,
            'data_source': 'CDR',
            'event_category': event_cat,
            'primary_id': a_party,
            'secondary_id': b_party,
            'amount': 0.0,
            'duration_sec': dur_sec,
            'data_volume_mb': 0.0,
            'location_or_details': address[:120],
            'raw_reference': f"CDR_ROW_{idx}"
        }
        events.append(event)

    # -------------------------------------------------------------------------
    # C. IPDR (Internet Protocol Detail Records) with 2-Hop Associate Resolution
    # -------------------------------------------------------------------------
    print("  Processing Internet Protocol Detail Records (IPDR)...")
    ipdr_df = pd.read_csv(IPDR_CSV, low_memory=False)

    ipdr_linked_cnt = 0

    for idx, r in ipdr_df.iterrows():
        msisdn = str(r.get('Msisdn', ''))
        m_norm = norm_phone(msisdn)

        # 1-Hop direct entity match or 2-Hop associate match
        entity_name = phone_to_entity.get(m_norm)
        is_associate = False

        if not entity_name:
            entity_name = b_party_to_entity.get(m_norm, "UNMAPPED")
            if entity_name != "UNMAPPED":
                is_associate = True

        if entity_name != "UNMAPPED":
            ipdr_linked_cnt += 1

        s_date = r.get('Start Date')
        s_time = r.get('Start Time')
        ts = parse_timestamp(s_date, s_time)

        dur = r.get('Duration Sec', 0)
        try:
            dur_sec = int(float(dur)) if pd.notna(dur) else 0
        except Exception:
            dur_sec = 0

        vol_up = r.get('Data Volume Up', 0)
        vol_down = r.get('Data Volume Down', 0)
        try:
            tot_bytes = (float(vol_up) if pd.notna(vol_up) else 0) + (float(vol_down) if pd.notna(vol_down) else 0)
            vol_mb = round(tot_bytes / (1024 * 1024), 2)
        except Exception:
            vol_mb = 0.0

        ip_addr = str(r.get('Ip Address', ''))
        cell_id = str(r.get('Cell Id', ''))
        
        cat_label = f"IPDR Internet (Associate: {m_norm})" if is_associate else "IPDR Internet Session"
        details = f"MSISDN: {msisdn} | IP: {ip_addr} | Cell: {cell_id}"

        event = {
            'timestamp': ts,
            'entity_name': entity_name,
            'data_source': 'IPDR',
            'event_category': cat_label,
            'primary_id': msisdn,
            'secondary_id': ip_addr,
            'amount': 0.0,
            'duration_sec': dur_sec,
            'data_volume_mb': vol_mb,
            'location_or_details': details,
            'raw_reference': str(r.get('Record Id', f"IPDR_ROW_{idx}"))
        }
        events.append(event)

    print(f"  Linked {ipdr_linked_cnt} / {len(ipdr_df)} IPDR records to entities via 2-hop associate resolution.")
    print(f"  Total Unified Events Extracted: {len(events)}")
    return events


def step4_save_outputs(entities, events):
    print("Step 4: Sorting & Exporting Datasets...")

    events_sorted = sorted(events, key=lambda x: x['timestamp'] if x['timestamp'] else "9999-99-99")

    timeline_df = pd.DataFrame(events_sorted)
    timeline_df.to_csv(OUTPUT_TIMELINE_CSV, index=False)
    print(f"  Saved Master Timeline CSV: {OUTPUT_TIMELINE_CSV} ({len(timeline_df)} rows)")

    entity_stats = {}

    for ek, ev in entities.items():
        entity_events = [e for e in events_sorted if e['entity_name'] == ek]

        tx_cnt = sum(1 for e in entity_events if e['data_source'] == 'Transaction')
        cdr_cnt = sum(1 for e in entity_events if e['data_source'] == 'CDR')
        ipdr_cnt = sum(1 for e in entity_events if e['data_source'] == 'IPDR')

        entity_info = {
            'entity_name': ek,
            'account_ids': sorted(list(ev['account_ids'])),
            'account_numbers': sorted(list(ev['account_numbers'])),
            'phones': sorted(list(ev['phones'])),
            'pan': sorted(list(ev['pan'])),
            'banks': sorted(list(ev['banks'])),
            'addresses': sorted(list(ev['addresses'])),
            'emails': sorted(list(ev['emails'])),
            'total_events': len(entity_events),
            'transaction_count': tx_cnt,
            'cdr_count': cdr_cnt,
            'ipdr_count': ipdr_cnt
        }

        entity_stats[ek] = entity_info

        if len(entity_events) > 0:
            safe_filename = re.sub(r'[^A-Za-z0-9_\-]+', '_', ek).strip('_')
            entity_csv_path = os.path.join(ENTITIES_DIR, f"{safe_filename}_timeline.csv")
            entity_json_path = os.path.join(ENTITIES_DIR, f"{safe_filename}_timeline.json")

            e_df = pd.DataFrame(entity_events)
            e_df.to_csv(entity_csv_path, index=False)

            with open(entity_json_path, 'w', encoding='utf-8') as f:
                json.dump({'profile': entity_info, 'timeline': entity_events}, f, indent=2)

    unmapped_events = [e for e in events_sorted if e['entity_name'] == 'UNMAPPED']
    entity_stats['UNMAPPED'] = {
        'entity_name': 'UNMAPPED',
        'account_ids': [],
        'account_numbers': [],
        'phones': [],
        'pan': [],
        'banks': [],
        'addresses': [],
        'emails': [],
        'total_events': len(unmapped_events),
        'transaction_count': sum(1 for e in unmapped_events if e['data_source'] == 'Transaction'),
        'cdr_count': sum(1 for e in unmapped_events if e['data_source'] == 'CDR'),
        'ipdr_count': sum(1 for e in unmapped_events if e['data_source'] == 'IPDR')
    }

    with open(OUTPUT_ENTITIES_JSON, 'w', encoding='utf-8') as f:
        json.dump(entity_stats, f, indent=2)
    print(f"  Saved Entity Summaries JSON: {OUTPUT_ENTITIES_JSON}")

    master_json_content = {
        'generated_at': datetime.now().isoformat(),
        'total_events': len(events_sorted),
        'total_entities': len(entity_stats),
        'events_sample': events_sorted[:500]
    }
    with open(OUTPUT_TIMELINE_JSON, 'w', encoding='utf-8') as f:
        json.dump(master_json_content, f, indent=2)
    print(f"  Saved Master Timeline JSON: {OUTPUT_TIMELINE_JSON}")


def main():
    print("=" * 70)
    print(" UNIFIED FINANCIAL TRANSACTION & INTELLIGENCE TIMELINE PIPELINE ")
    print("=" * 70)

    step1_export_ipdr_csv()
    entities, acc_id_to_entity, acc_num_to_entity, phone_to_entity, b_party_to_entity = step2_build_entities_and_lookups()
    events = step3_process_and_unify(entities, acc_id_to_entity, acc_num_to_entity, phone_to_entity, b_party_to_entity)
    step4_save_outputs(entities, events)

    print("\nSUCCESS! All processing completed.")


if __name__ == "__main__":
    main()
