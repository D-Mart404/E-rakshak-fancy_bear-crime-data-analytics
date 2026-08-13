"""MongoDB index definitions for hot query paths (Phase 5 audit)."""

from motor.motor_asyncio import AsyncIOMotorDatabase


async def backfill_accounts_and_ipdr(database: AsyncIOMotorDatabase) -> None:
    """
    Compass shows collections, not nested fields.
    Accounts used to live only inside entities.accounts[]; IPDR only inside telecom_events.
    Copy them into first-class `accounts` and `ipdr` collections if those are empty.
    """
    accounts = database["accounts"]
    ipdr = database["ipdr"]

    if await accounts.estimated_document_count() == 0:
        docs: list[dict] = []
        async for ent in database["entities"].find({}, {"_id": 0}):
            eid = ent.get("entity_id")
            for acc in ent.get("accounts") or []:
                if not isinstance(acc, dict):
                    continue
                aid = acc.get("account_id")
                if not aid:
                    continue
                docs.append(
                    {
                        "account_id": aid,
                        "entity_id": eid,
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
        if docs:
            # unique by account_id
            uniq = {d["account_id"]: d for d in docs}
            await accounts.insert_many(list(uniq.values()), ordered=False)

    if await ipdr.estimated_document_count() == 0:
        cursor = database["telecom_events"].find({"event_type": "IPDR"}, {"_id": 0})
        rows = await cursor.to_list(length=500000)
        if rows:
            await ipdr.insert_many(rows, ordered=False)


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    entities = database["entities"]
    transactions = database["transactions"]
    telecom = database["telecom_events"]
    accounts = database["accounts"]
    ipdr = database["ipdr"]

    # Entities — seed lookup + nested account fields
    await entities.create_index("entity_id", unique=True)
    await entities.create_index("accounts.account_id")
    await entities.create_index("accounts.account_number")
    await entities.create_index("phones")

    cases = database["cases"]
    await cases.create_index("case_id", unique=True)
    await cases.create_index("status")
    await cases.create_index("updated_at")

    # Transactions — presets, graph, and time-window aggregations
    await transactions.create_index("transaction_id")
    await transactions.create_index("account_id")
    await transactions.create_index("transaction_date")
    await transactions.create_index("counterparty_account")
    await transactions.create_index("counterparty_name")
    await transactions.create_index("direction")
    await transactions.create_index(
        [("account_id", 1), ("transaction_date", 1)],
        name="account_id_transaction_date",
    )
    await transactions.create_index(
        [("counterparty_account", 1), ("transaction_date", 1)],
        name="counterparty_account_transaction_date",
    )
    await transactions.create_index(
        [("account_id", 1), ("direction", 1)],
        name="account_id_direction",
    )

    # Telecom — CDR/IPDR graph + call-transfer preset
    await telecom.create_index("event_id")
    await telecom.create_index("msisdn")
    await telecom.create_index("timestamp")
    await telecom.create_index("ip_address")
    await telecom.create_index("event_type")
    await telecom.create_index("b_party")
    await telecom.create_index(
        [("event_type", 1), ("msisdn", 1)],
        name="event_type_msisdn",
    )
    await telecom.create_index(
        [("event_type", 1), ("timestamp", 1)],
        name="event_type_timestamp",
    )
    await telecom.create_index(
        [("msisdn", 1), ("timestamp", 1)],
        name="msisdn_timestamp",
    )

    await accounts.create_index("account_id", unique=True)
    await accounts.create_index("entity_id")
    await accounts.create_index("account_number")
    await accounts.create_index("bank_name")

    await ipdr.create_index("event_id")
    await ipdr.create_index("msisdn")
    await ipdr.create_index("timestamp")
    await ipdr.create_index("ip_address")
