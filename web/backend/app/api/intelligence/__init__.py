"""HTTP routes for investigation intelligence (thin wrapper over modules)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ... import db
from .common import MAX_SANKEY, MAX_TIMELINE, active_case, fmt_money, seed_entities
from .correlations import build_correlations, build_findings, build_networks
from .reports import append_audit, build_str, ipdr_summary, list_audit, run_query
from .scoring import build_leaderboard, risk_for_entity
from .timeline import build_episodes, build_heatmap, build_sankey, build_timeline

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])


@router.get("/command-center")
async def command_center():
    database = db.get_db()
    seeds = await seed_entities(database)
    entities_total = await database["entities"].estimated_document_count()
    tx_total = await database["transactions"].estimated_document_count()
    cdr_total = await database["telecom_events"].count_documents({"event_type": "CDR"})
    ipdr_total = await database["telecom_events"].count_documents({"event_type": "IPDR"})

    credit = await database["transactions"].aggregate(
        [{"$match": {"direction": "CR"}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    ).to_list(1)
    credit_total = float(credit[0]["total"]) if credit else 0.0

    correlations = await build_correlations(database, limit=20)
    leaderboard = await build_leaderboard(database, limit=50)
    networks = await build_networks(database, seeds)
    findings = await build_findings(
        database,
        seeds=seeds,
        correlations=correlations,
        leaderboard=leaderboard,
        ipdr_total=ipdr_total,
    )
    critical = sum(1 for r in leaderboard if r["risk_category"] == "CRITICAL")
    high = sum(1 for r in leaderboard if r["risk_category"] == "HIGH")
    case = await active_case(database)

    return {
        "status": "ok",
        "case": {
            "case_id": case.get("case_id"),
            "unit": case.get("unit") or "Special Financial Cybercrime Unit",
            "title": case.get("title"),
            "lead_investigator": case.get("lead_investigator"),
        },
        "active_case": case,
        "stats": {
            "fir_seed_suspects": len(seeds),
            "resolved_entities": entities_total,
            "money_traced": credit_total,
            "money_traced_display": fmt_money(credit_total),
            "total_events": tx_total + cdr_total + ipdr_total,
            "transactions": tx_total,
            "cdr_events": cdr_total,
            "ipdr_events": ipdr_total,
            "priority_leads": critical + high,
        },
        "top_case_findings": findings,
        "discovered_networks": networks,
        "seed_entities": [
            {
                "entity_id": s.get("entity_id"),
                "entity_name": s.get("entity_name"),
                "phones": s.get("phones") or [],
            }
            for s in seeds
        ],
    }


@router.get("/correlations")
async def list_correlations(limit: int = Query(25, ge=1, le=100)):
    rows = await build_correlations(db.get_db(), limit=limit)
    return {"status": "ok", "count": len(rows), "correlations": rows}


@router.get("/findings")
async def list_findings():
    database = db.get_db()
    seeds = await seed_entities(database)
    ipdr_total = await database["telecom_events"].count_documents({"event_type": "IPDR"})
    correlations = await build_correlations(database, limit=20)
    leaderboard = await build_leaderboard(database, limit=50)
    findings = await build_findings(
        database,
        seeds=seeds,
        correlations=correlations,
        leaderboard=leaderboard,
        ipdr_total=ipdr_total,
    )
    return {
        "status": "ok",
        "count": len(findings),
        "findings": findings,
        "critical_count": sum(1 for f in findings if f.get("severity") == "CRITICAL"),
        "high_count": sum(1 for f in findings if f.get("severity") == "HIGH"),
    }


@router.get("/leaderboard")
async def leaderboard(limit: int = Query(50, ge=1, le=200)):
    rows = await build_leaderboard(db.get_db(), limit=limit)
    return {"status": "ok", "count": len(rows), "leaderboard": rows}


@router.get("/risk/{entity_id}")
async def entity_risk_profile(entity_id: str):
    profile = await risk_for_entity(db.get_db(), entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return {"status": "ok", "risk_profile": profile}


@router.get("/sankey")
async def sankey_flows(limit: int = Query(MAX_SANKEY, ge=5, le=100)):
    flows = await build_sankey(db.get_db(), limit=limit)
    return {"status": "ok", "count": len(flows), "flows": flows}


@router.get("/timeline/{entity_id}")
async def entity_timeline(
    entity_id: str,
    source: str | None = Query(None, description="BANK|CDR|IPDR"),
    limit: int = Query(200, ge=20, le=MAX_TIMELINE),
):
    data = await build_timeline(db.get_db(), entity_id, source=source, limit=limit)
    if not data:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return {"status": "ok", **data}


@router.get("/episodes")
async def suspicious_episodes(limit: int = Query(15, ge=1, le=50)):
    episodes = await build_episodes(db.get_db(), limit=limit)
    return {
        "status": "ok",
        "count": len(episodes),
        "critical_count": sum(1 for e in episodes if e.get("severity") == "CRITICAL"),
        "window_minutes": 15,
        "episodes": episodes,
    }


@router.get("/heatmap")
async def activity_heatmap(limit_entities: int = Query(10, ge=3, le=20)):
    matrix = await build_heatmap(db.get_db(), limit_entities=limit_entities)
    return {"status": "ok", "count": len(matrix), "heatmap_matrix": matrix}


@router.get("/str/{entity_id}")
async def str_report(entity_id: str):
    report = await build_str(db.get_db(), entity_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_id}' not found")
    return {"status": "ok", **report}


@router.get("/query")
async def intelligence_query(q: str = Query(..., min_length=2)):
    results = await run_query(db.get_db(), q)
    return {"status": "ok", "query": q, "results": results}


@router.get("/audit")
async def get_audit(limit: int = Query(100, ge=1, le=500)):
    rows = await list_audit(db.get_db(), limit=limit)
    return {"status": "ok", "count": len(rows), "items": rows}


@router.post("/audit")
async def post_audit(payload: dict[str, Any]):
    action = str(payload.get("action") or "").strip()
    user = str(payload.get("user") or "Investigator").strip()
    if not action:
        raise HTTPException(status_code=400, detail="action required")
    row = await append_audit(db.get_db(), user, action)
    return {"status": "ok", "item": row}


@router.get("/ipdr/summary")
async def get_ipdr_summary():
    return {"status": "ok", **await ipdr_summary(db.get_db())}
