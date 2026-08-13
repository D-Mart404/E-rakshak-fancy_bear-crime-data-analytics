#!/usr/bin/env python3
from pymongo import MongoClient

db = MongoClient("mongodb://localhost:27017")["erakshak"]
print("counterparty_name filled:", db["transactions"].count_documents({"counterparty_name": {"$ne": ""}}))
print("counterparty_account filled:", db["transactions"].count_documents({"counterparty_account": {"$nin": ["", None]}}))
phones = set()
for e in db["entities"].find({}, {"phones": 1}):
    phones.update(e.get("phones") or [])
cdr_msisdn = set(db["telecom_events"].distinct("msisdn", {"event_type": "CDR"}))
print("entity phones", len(phones), "cdr msisdn", len(cdr_msisdn), "overlap", len(phones & cdr_msisdn))
seed = "ACC_AXIS_001"
acc = db["entities"].find_one({"entity_id": seed}, {"accounts": 1, "phones": 1})
acc_ids = [a["account_id"] for a in acc.get("accounts", []) if a.get("account_id")]
print(f"{seed} tx cp_name:", db["transactions"].count_documents({"account_id": {"$in": acc_ids}, "counterparty_name": {"$ne": ""}}))
print(f"{seed} tx cp_acct:", db["transactions"].count_documents({"account_id": {"$in": acc_ids}, "counterparty_account": {"$nin": ["", None]}}))
phones_seed = acc.get("phones") or []
print(f"{seed} phones:", phones_seed)
if phones_seed:
    print(f"{seed} cdr for phone:", db["telecom_events"].count_documents({"event_type": "CDR", "msisdn": {"$in": phones_seed}}))
