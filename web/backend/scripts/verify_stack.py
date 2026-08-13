#!/usr/bin/env python3
"""End-to-end verification for E-Rakshak web stack."""
from __future__ import annotations

import asyncio
import json
import sys

from app import db
from app.api.graph import investigation_graph
from app.api.investigation import (
    investigation_entity_report,
    investigation_preset_summary,
)


async def main() -> int:
    seed = "ACC_AXIS_001"
    results: dict[str, object] = {}

    await db.connect()
    try:
        results["entity_report"] = await investigation_entity_report(seed)
        for preset in (
            "rapid_layering_mules",
            "multi_seed_convergence",
            "call_transfer_coincidences",
        ):
            results[preset] = await investigation_preset_summary(preset, seed)
        results["graph"] = await investigation_graph(seed)
        database = db.get_db()
        results["entities_api_total"] = await database["entities"].count_documents({})
        results["transactions_api_total"] = await database["transactions"].count_documents({})
        results["telecom_api_total"] = await database["telecom_events"].count_documents({})
    finally:
        await db.disconnect()

    summary = {
        "entity_report_ok": results["entity_report"]["status"] == "ok",
        "rapid_layering_flags": results["rapid_layering_mules"]["summary"]["flagged_count"],
        "multi_seed_flags": results["multi_seed_convergence"]["summary"]["flagged_count"],
        "call_transfer_flags": results["call_transfer_coincidences"]["summary"]["flagged_count"],
        "graph_nodes": results["graph"]["summary"]["node_count"],
        "graph_edges": results["graph"]["summary"]["edge_count"],
        "entities_api_total": results["entities_api_total"],
        "transactions_api_total": results["transactions_api_total"],
        "telecom_api_total": results["telecom_api_total"],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
