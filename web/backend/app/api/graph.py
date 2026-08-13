from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from .. import db

router = APIRouter(prefix="/api/investigation", tags=["graph"])

# Graph build limits (adjustable)
MAX_COUNTERPARTY_NODES = 25
MAX_CALL_TARGET_NODES = 20
MAX_IPDR_NODES = 15


def _risk_score(
    is_seed: bool,
    tx_count: int,
    counterparties: int,
    call_targets: int,
) -> float:
    """Graph node tint only — leaderboard uses case-relative scoring."""
    score = 0.0
    if tx_count >= 3:
        score += min(40.0, (tx_count - 2) * 1.5)
    if counterparties >= 3:
        score += min(30.0, (counterparties - 2) * 4.0)
    if call_targets >= 8:
        score += min(18.0, call_targets * 0.4)
    if is_seed and score >= 12:
        score += 8
    elif is_seed:
        score += 3
    return round(min(100.0, score), 1)


def _node(
    node_id: str,
    node_type: str,
    label: str,
    risk_score: float,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "position": {"x": 0, "y": 0},
        "data": {
            "label": label,
            "nodeType": node_type,
            "riskScore": risk_score,
            "metadata": metadata,
        },
    }


def _edge(
    edge_id: str,
    source: str,
    target: str,
    label: str = "",
    edge_type: str = "default",
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "label": label,
        "type": edge_type,
        "animated": edge_type in {"transaction", "call"},
    }


async def _get_entity_seed_data(entity_id: str) -> dict[str, Any]:
    database = db.get_db()
    entity = await database["entities"].find_one({"entity_id": entity_id})
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    entity.pop("_id", None)
    accounts = entity.get("accounts") or []
    account_ids = [
        a.get("account_id")
        for a in accounts
        if isinstance(a, dict) and a.get("account_id") not in (None, "")
    ]
    phones = entity.get("phones") or []
    return {"entity": entity, "account_ids": account_ids, "phones": phones}


@router.get("/graph/{entity_id}")
async def investigation_graph(entity_id: str):
    """Format MongoDB investigation data as React Flow nodes + edges."""
    database = db.get_db()
    seed = await _get_entity_seed_data(entity_id)
    entity = seed["entity"]
    account_ids = seed["account_ids"]
    phones = seed["phones"]

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    node_ids: set[str] = set()

    entity_node_id = f"entity:{entity_id}"
    entity_name = entity.get("entity_name") or entity_id
    is_seed = bool(entity.get("is_seed"))

    nodes.append(
        _node(
            entity_node_id,
            "entity",
            entity_name,
            _risk_score(is_seed, 0, 0, 0),
            {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "is_seed": is_seed,
                "pan": entity.get("pan"),
                "account_role": entity.get("account_role"),
            },
        )
    )
    node_ids.add(entity_node_id)

    account_node_ids: list[str] = []
    for account in entity.get("accounts") or []:
        if not isinstance(account, dict):
            continue
        account_id = account.get("account_id")
        if not account_id:
            continue
        account_node_id = f"account:{account_id}"
        if account_node_id not in node_ids:
            label = account.get("account_number") or account_id
            nodes.append(
                _node(
                    account_node_id,
                    "account",
                    label,
                    _risk_score(is_seed, 0, 0, 0),
                    {
                        "account_id": account_id,
                        "account_number": account.get("account_number"),
                        "bank_name": account.get("bank_name"),
                        "ifsc": account.get("ifsc"),
                        "branch": account.get("branch"),
                    },
                )
            )
            node_ids.add(account_node_id)
            account_node_ids.append(account_node_id)
        edges.append(
            _edge(
                f"edge:{entity_node_id}->{account_node_id}",
                entity_node_id,
                account_node_id,
                "owns",
                "ownership",
            )
        )

    phone_node_ids: list[str] = []
    for phone in phones:
        phone_node_id = f"phone:{phone}"
        if phone_node_id not in node_ids:
            nodes.append(
                _node(
                    phone_node_id,
                    "phone",
                    phone,
                    _risk_score(is_seed, 0, 0, 0),
                    {"msisdn": phone},
                )
            )
            node_ids.add(phone_node_id)
            phone_node_ids.append(phone_node_id)
        edges.append(
            _edge(
                f"edge:{entity_node_id}->{phone_node_id}",
                entity_node_id,
                phone_node_id,
                "linked",
                "ownership",
            )
        )

    tx_count = 0
    counterparties = 0
    call_targets = 0

    if account_ids:
        counterparty_pipeline = [
            {
                "$match": {
                    "account_id": {"$in": account_ids},
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
                "$group": {
                    "_id": {
                        "account_id": "$account_id",
                        "destination": "$destination_key",
                    },
                    "tx_count": {"$sum": 1},
                    "total_amount": {"$sum": "$amount"},
                    "counterparty_name": {"$first": "$counterparty_name"},
                    "counterparty_account": {"$first": "$counterparty_account"},
                    "directions": {"$addToSet": "$direction"},
                }
            },
            {"$sort": {"total_amount": -1}},
            {"$limit": MAX_COUNTERPARTY_NODES},
        ]
        counterparty_rows = await database["transactions"].aggregate(
            counterparty_pipeline
        ).to_list(length=MAX_COUNTERPARTY_NODES)

        tx_count_pipeline = [
            {"$match": {"account_id": {"$in": account_ids}}},
            {"$count": "count"},
        ]
        tx_count_row = await database["transactions"].aggregate(tx_count_pipeline).to_list(
            length=1
        )
        tx_count = tx_count_row[0]["count"] if tx_count_row else 0
        counterparties = len(counterparty_rows)

        source_account_id = account_node_ids[0] if account_node_ids else entity_node_id
        for row in counterparty_rows:
            group_id = row["_id"]
            dest_key = group_id["destination"]
            src_account = group_id["account_id"]
            cp_node_id = f"counterparty:{dest_key}"
            source_node = f"account:{src_account}" if f"account:{src_account}" in node_ids else source_account_id
            if cp_node_id not in node_ids:
                label = row.get("counterparty_name") or dest_key
                nodes.append(
                    _node(
                        cp_node_id,
                        "counterparty_account",
                        label,
                        _risk_score(False, row.get("tx_count", 0), 1, 0),
                        {
                            "counterparty_account": row.get("counterparty_account") or "",
                            "counterparty_name": row.get("counterparty_name"),
                            "destination_key": dest_key,
                            "transaction_count": row.get("tx_count", 0),
                            "total_amount": row.get("total_amount", 0),
                            "directions": row.get("directions", []),
                        },
                    )
                )
                node_ids.add(cp_node_id)

            edges.append(
                _edge(
                    f"edge:{source_node}->{cp_node_id}",
                    source_node,
                    cp_node_id,
                    f"{row.get('tx_count', 0)} tx",
                    "transaction",
                )
            )

    if phones:
        call_pipeline = [
            {
                "$match": {
                    "event_type": "CDR",
                    "msisdn": {"$in": phones},
                    "b_party": {"$nin": [None, "", "-"]},
                }
            },
            {
                "$group": {
                    "_id": "$b_party",
                    "call_count": {"$sum": 1},
                    "total_duration_sec": {"$sum": "$duration_sec"},
                }
            },
            {"$sort": {"call_count": -1}},
            {"$limit": MAX_CALL_TARGET_NODES},
        ]
        call_rows = await database["telecom_events"].aggregate(call_pipeline).to_list(
            length=MAX_CALL_TARGET_NODES
        )
        call_targets = len(call_rows)

        source_phone_id = phone_node_ids[0] if phone_node_ids else entity_node_id
        for row in call_rows:
            b_party = row["_id"]
            target_id = f"phone:{b_party}"
            if target_id not in node_ids:
                nodes.append(
                    _node(
                        target_id,
                        "phone",
                        b_party,
                        _risk_score(False, 0, 0, row.get("call_count", 0)),
                        {
                            "msisdn": b_party,
                            "call_count": row.get("call_count", 0),
                            "total_duration_sec": row.get("total_duration_sec", 0),
                        },
                    )
                )
                node_ids.add(target_id)

            edges.append(
                _edge(
                    f"edge:{source_phone_id}->{target_id}",
                    source_phone_id,
                    target_id,
                    f"{row.get('call_count', 0)} calls",
                    "call",
                )
            )

        ipdr_pipeline = [
            {
                "$match": {
                    "event_type": "IPDR",
                    "msisdn": {"$in": phones},
                    "ip_address": {"$nin": [None, ""]},
                }
            },
            {
                "$group": {
                    "_id": "$ip_address",
                    "session_count": {"$sum": 1},
                    "total_data_volume": {
                        "$sum": {
                            "$add": ["$data_volume_up", "$data_volume_down"]
                        }
                    },
                }
            },
            {"$sort": {"session_count": -1}},
            {"$limit": MAX_IPDR_NODES},
        ]
        ipdr_rows = await database["telecom_events"].aggregate(ipdr_pipeline).to_list(
            length=MAX_IPDR_NODES
        )

        source_phone_id = phone_node_ids[0] if phone_node_ids else entity_node_id
        for row in ipdr_rows:
            ip_addr = row["_id"]
            ip_node_id = f"ip:{ip_addr}"
            if ip_node_id not in node_ids:
                nodes.append(
                    _node(
                        ip_node_id,
                        "ip",
                        ip_addr,
                        _risk_score(False, 0, 0, row.get("session_count", 0)),
                        {
                            "ip_address": ip_addr,
                            "session_count": row.get("session_count", 0),
                            "total_data_volume": row.get("total_data_volume", 0),
                        },
                    )
                )
                node_ids.add(ip_node_id)

            edges.append(
                _edge(
                    f"edge:{source_phone_id}->{ip_node_id}",
                    source_phone_id,
                    ip_node_id,
                    f"{row.get('session_count', 0)} sessions",
                    "ipdr",
                )
            )

    # Refresh seed entity risk score with graph context.
    entity_risk = _risk_score(is_seed, tx_count, counterparties, call_targets)
    nodes[0]["data"]["riskScore"] = entity_risk
    nodes[0]["data"]["metadata"]["transaction_count"] = tx_count
    nodes[0]["data"]["metadata"]["counterparty_count"] = counterparties
    nodes[0]["data"]["metadata"]["call_target_count"] = call_targets

    return {
        "status": "ok",
        "entity_id": entity_id,
        "summary": {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "transaction_count": tx_count,
            "counterparty_count": counterparties,
            "call_target_count": call_targets,
        },
        "nodes": nodes,
        "edges": edges,
    }
