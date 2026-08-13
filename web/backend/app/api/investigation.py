from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter(prefix="/api/investigation", tags=["investigation"])

# Preset thresholds (adjustable constants)
RAPID_LAYERING_WINDOW_HOURS = 24
RAPID_LAYERING_OUTGOING_RATIO = 0.90
MULTI_SEED_WINDOW_HOURS = 48
MULTI_SEED_MIN_DISTINCT_SOURCES = 3
CALL_TRANSFER_WINDOW_MINUTES = 15


async def _get_entity_seed_data(entity_id: str) -> dict[str, Any]:
    database = db.get_db()
    entity = await database["entities"].find_one({"entity_id": entity_id})
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")

    # Normalize Mongo _id to keep response JSON-serializable.
    entity.pop("_id", None)

    accounts = entity.get("accounts") or []
    account_ids = [
        a.get("account_id")
        for a in accounts
        if isinstance(a, dict) and a.get("account_id") not in (None, "")
    ]
    phones = entity.get("phones") or []

    return {
        "entity": entity,
        "account_ids": account_ids,
        "phones": phones,
    }


async def _compute_transaction_summary(database, account_ids: list[str]) -> dict[str, Any]:
    if not account_ids:
        return {
            "by_direction": [],
            "total_transactions": 0,
            "top_counterparties": [],
        }

    by_direction_pipeline = [
        {"$match": {"account_id": {"$in": account_ids}}},
        {
            "$group": {
                "_id": "$direction",
                "count": {"$sum": 1},
                "totalAmount": {"$sum": "$amount"},
            }
        },
        {"$sort": {"count": -1}},
    ]

    top_counterparties_pipeline = [
        {"$match": {"account_id": {"$in": account_ids}, "counterparty_name": {"$ne": ""}}},
        {
            "$group": {
                "_id": "$counterparty_name",
                "count": {"$sum": 1},
                "totalAmount": {"$sum": "$amount"},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]

    by_direction = await database["transactions"].aggregate(by_direction_pipeline).to_list(
        length=20
    )
    top_counterparties = await database["transactions"].aggregate(
        top_counterparties_pipeline
    ).to_list(length=10)

    total_transactions = sum(item.get("count", 0) for item in by_direction)

    return {
        "by_direction": by_direction,
        "total_transactions": total_transactions,
        "top_counterparties": top_counterparties,
    }


async def _compute_telecom_summary(database, phones: list[str]) -> dict[str, Any]:
    if not phones:
        return {
            "by_event_type": [],
            "cdr_total_duration_sec": 0,
            "ipdr_total_data_volume": 0.0,
        }

    by_event_type_pipeline = [
        {"$match": {"msisdn": {"$in": phones}}},
        {
            "$group": {
                "_id": "$event_type",
                "count": {"$sum": 1},
                "cdrDurationTotalSec": {
                    "$sum": {"$cond": [{"$eq": ["$event_type", "CDR"]}, "$duration_sec", 0]}
                },
                "ipdrDataVolumeTotal": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$event_type", "IPDR"]},
                            {"$add": ["$data_volume_up", "$data_volume_down"]},
                            0,
                        ]
                    }
                },
            }
        },
        {"$sort": {"count": -1}},
    ]

    by_event_type = await database["telecom_events"].aggregate(by_event_type_pipeline).to_list(
        length=10
    )

    cdr_total_duration_sec = next(
        (x["cdrDurationTotalSec"] for x in by_event_type if x.get("_id") == "CDR"), 0
    )
    ipdr_total_data_volume = next(
        (
            x["ipdrDataVolumeTotal"]
            for x in by_event_type
            if x.get("_id") == "IPDR"
        ),
        0.0,
    )

    return {
        "by_event_type": by_event_type,
        "cdr_total_duration_sec": cdr_total_duration_sec,
        "ipdr_total_data_volume": ipdr_total_data_volume,
    }


async def _run_rapid_layering_mules(
    database, seed: dict[str, Any], limit: int = 100
) -> dict[str, Any]:
    account_ids = seed["account_ids"]
    if not account_ids:
        return {"summary": {"flagged_count": 0}, "records": []}

    pipeline = [
        {
            "$match": {
                "account_id": {"$in": account_ids},
                "transaction_date": {"$ne": None},
                "amount": {"$ne": None},
                "direction": {"$in": ["CR", "DR"]},
            }
        },
        {"$sort": {"account_id": 1, "transaction_date": 1}},
        {
            "$setWindowFields": {
                "partitionBy": "$account_id",
                "sortBy": {"transaction_date": 1},
                "output": {
                    "rolling_credit": {
                        "$sum": {
                            "$cond": [{"$eq": ["$direction", "CR"]}, "$amount", 0]
                        },
                        "window": {
                            "range": [-RAPID_LAYERING_WINDOW_HOURS, 0],
                            "unit": "hour",
                        },
                    },
                    "rolling_debit": {
                        "$sum": {
                            "$cond": [{"$eq": ["$direction", "DR"]}, "$amount", 0]
                        },
                        "window": {
                            "range": [-RAPID_LAYERING_WINDOW_HOURS, 0],
                            "unit": "hour",
                        },
                    },
                },
            }
        },
        {
            "$addFields": {
                "outgoing_to_incoming_ratio": {
                    "$cond": [
                        {"$gt": ["$rolling_credit", 0]},
                        {"$divide": ["$rolling_debit", "$rolling_credit"]},
                        0,
                    ]
                }
            }
        },
        {
            "$match": {
                "rolling_credit": {"$gt": 0},
                "outgoing_to_incoming_ratio": {"$gte": RAPID_LAYERING_OUTGOING_RATIO},
            }
        },
        {
            "$project": {
                "_id": 0,
                "transaction_id": 1,
                "account_id": 1,
                "transaction_date": 1,
                "rolling_credit": 1,
                "rolling_debit": 1,
                "outgoing_to_incoming_ratio": 1,
            }
        },
        {"$sort": {"outgoing_to_incoming_ratio": -1, "transaction_date": -1}},
        {"$limit": limit},
    ]
    records = await database["transactions"].aggregate(pipeline).to_list(length=limit)
    return {"summary": {"flagged_count": len(records)}, "records": records}


async def _run_multi_seed_convergence(
    database, seed: dict[str, Any], limit: int = 100
) -> dict[str, Any]:
    account_ids = seed["account_ids"]
    if not account_ids:
        return {"summary": {"flagged_count": 0}, "records": []}

    # Seed-driven scope: include windows where at least one source account is a seed account.
    pipeline = [
        {
            "$match": {
                "transaction_date": {"$ne": None},
                "direction": "DR",
                "account_id": {"$nin": [None, ""]},
                "$or": [
                    {"counterparty_account": {"$nin": [None, ""]}},
                    {"counterparty_name": {"$nin": [None, ""]}},
                ],
            }
        },
        {
            "$addFields": {
                "destination_key": {
                    "$cond": [
                        {
                            "$gt": [
                                {"$strLenCP": {"$ifNull": ["$counterparty_account", ""]}},
                                0,
                            ]
                        },
                        "$counterparty_account",
                        "$counterparty_name",
                    ]
                }
            }
        },
        {"$match": {"destination_key": {"$nin": [None, ""]}}},
        {
            "$project": {
                "_id": 0,
                "source_account": "$account_id",
                "destination_key": 1,
                "amount": 1,
                "transaction_date": 1,
                "window_start": "$transaction_date",
                "window_end": {
                    "$dateAdd": {
                        "startDate": "$transaction_date",
                        "unit": "hour",
                        "amount": MULTI_SEED_WINDOW_HOURS,
                    }
                },
            }
        },
        {
            "$lookup": {
                "from": "transactions",
                "let": {
                    "dest": "$destination_key",
                    "ws": "$window_start",
                    "we": "$window_end",
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$direction", "DR"]},
                                    {"$gte": ["$transaction_date", "$$ws"]},
                                    {"$lte": ["$transaction_date", "$$we"]},
                                    {"$ne": ["$account_id", None]},
                                    {"$ne": ["$account_id", ""]},
                                    {
                                        "$eq": [
                                            {
                                                "$cond": [
                                                    {
                                                        "$gt": [
                                                            {
                                                                "$strLenCP": {
                                                                    "$ifNull": [
                                                                        "$counterparty_account",
                                                                        "",
                                                                    ]
                                                                }
                                                            },
                                                            0,
                                                        ]
                                                    },
                                                    "$counterparty_account",
                                                    "$counterparty_name",
                                                ]
                                            },
                                            "$$dest",
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "source_accounts": {"$addToSet": "$account_id"},
                            "tx_count": {"$sum": 1},
                            "total_amount": {"$sum": "$amount"},
                        }
                    },
                ],
                "as": "convergence",
            }
        },
        {"$unwind": "$convergence"},
        {
            "$addFields": {
                "distinct_source_count": {"$size": "$convergence.source_accounts"},
                "includes_seed_source": {
                    "$gt": [
                        {
                            "$size": {
                                "$setIntersection": [
                                    "$convergence.source_accounts",
                                    account_ids,
                                ]
                            }
                        },
                        0,
                    ]
                },
            }
        },
        {
            "$match": {
                "distinct_source_count": {"$gte": MULTI_SEED_MIN_DISTINCT_SOURCES},
                "includes_seed_source": True,
            }
        },
        {
            "$project": {
                "_id": 0,
                "destination_key": 1,
                "window_start": 1,
                "window_end": 1,
                "distinct_source_count": 1,
                "source_accounts": "$convergence.source_accounts",
                "transaction_count": "$convergence.tx_count",
                "total_amount": "$convergence.total_amount",
            }
        },
        {"$sort": {"distinct_source_count": -1, "total_amount": -1}},
        {
            "$group": {
                "_id": {
                    "destination_key": "$destination_key",
                    "window_start": "$window_start",
                },
                "doc": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$doc"}},
        {"$limit": limit},
    ]
    records = await database["transactions"].aggregate(pipeline).to_list(length=limit)
    return {"summary": {"flagged_count": len(records)}, "records": records}


async def _run_call_transfer_coincidences(
    database, seed: dict[str, Any], limit: int = 100
) -> dict[str, Any]:
    account_ids = seed["account_ids"]
    phones = seed["phones"]
    if not account_ids or not phones:
        return {"summary": {"flagged_count": 0}, "records": []}

    pipeline = [
        {
            "$match": {
                "account_id": {"$in": account_ids},
                "transaction_date": {"$ne": None},
                "amount": {"$ne": None},
            }
        },
        {
            "$lookup": {
                "from": "telecom_events",
                "let": {
                    "tx_time": "$transaction_date",
                },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": {
                                "$and": [
                                    {"$eq": ["$event_type", "CDR"]},
                                    {"$in": ["$msisdn", phones]},
                                    {"$ne": ["$b_party", None]},
                                    {"$ne": ["$b_party", ""]},
                                    {"$lt": ["$timestamp", "$$tx_time"]},
                                    {
                                        "$gte": [
                                            "$timestamp",
                                            {
                                                "$dateSubtract": {
                                                    "startDate": "$$tx_time",
                                                    "unit": "minute",
                                                    "amount": CALL_TRANSFER_WINDOW_MINUTES,
                                                }
                                            },
                                        ]
                                    },
                                ]
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "event_id": 1,
                            "timestamp": 1,
                            "msisdn": 1,
                            "b_party": 1,
                            "call_type": 1,
                        }
                    },
                ],
                "as": "matching_calls",
            }
        },
        {"$match": {"matching_calls.0": {"$exists": True}}},
        {
            "$project": {
                "_id": 0,
                "transaction_id": 1,
                "account_id": 1,
                "transaction_date": 1,
                "amount": 1,
                "direction": 1,
                "counterparty_account": 1,
                "matching_call_count": {"$size": "$matching_calls"},
                "matching_calls": 1,
            }
        },
        {"$sort": {"matching_call_count": -1, "transaction_date": -1}},
        {"$limit": limit},
    ]
    records = await database["transactions"].aggregate(pipeline).to_list(length=limit)
    return {"summary": {"flagged_count": len(records)}, "records": records}


@router.get("/entity/{entity_id}")
async def investigation_entity_report(entity_id: str):
    """
    Deep-dive report for a single entity seed.

    This endpoint intentionally uses only schema-level fields already stored in Mongo:
    - Entities: `accounts.account_id`, `phones`
    - Transactions: `account_id`, `direction`, `amount`, `counterparty_name`
    - TelecomEvents: `msisdn`, `event_type`, CDR/IPDR metrics
    """

    database = db.get_db()
    seed = await _get_entity_seed_data(entity_id)

    tx_summary = await _compute_transaction_summary(database, seed["account_ids"])
    telecom_summary = await _compute_telecom_summary(database, seed["phones"])

    return {
        "status": "ok",
        "entity": seed["entity"],
        "analytics": {
            "transactions": tx_summary,
            "telecom": telecom_summary,
        },
    }


@router.get("/presets/{preset_key}")
async def investigation_preset_summary(preset_key: str, seed_entity_id: str):
    database = db.get_db()
    seed = await _get_entity_seed_data(seed_entity_id)

    if preset_key == "rapid_layering_mules":
        result = await _run_rapid_layering_mules(database, seed)
    elif preset_key == "multi_seed_convergence":
        result = await _run_multi_seed_convergence(database, seed)
    elif preset_key == "call_transfer_coincidences":
        result = await _run_call_transfer_coincidences(database, seed)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown preset '{preset_key}'")

    return {
        "status": "ok",
        "preset_key": preset_key,
        "seed_entity_id": seed_entity_id,
        "entity": seed["entity"],
        "rule_config": {
            "rapid_layering_window_hours": RAPID_LAYERING_WINDOW_HOURS,
            "rapid_layering_outgoing_ratio": RAPID_LAYERING_OUTGOING_RATIO,
            "multi_seed_window_hours": MULTI_SEED_WINDOW_HOURS,
            "multi_seed_min_distinct_sources": MULTI_SEED_MIN_DISTINCT_SOURCES,
            "call_transfer_window_minutes": CALL_TRANSFER_WINDOW_MINUTES,
        },
        "summary": result["summary"],
        "records": result["records"],
    }

