from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .db_indexes import backfill_accounts_and_ipdr, ensure_indexes
from .api.browse import router as browse_router
from .api.graph import router as graph_router
from .api.investigation import router as investigation_router
from .api.intelligence import router as intelligence_router
from .api.cases import router as cases_router
from .api.cases import ensure_default_case
from .api.documents import router as documents_router


@asynccontextmanager
async def lifespan(application: FastAPI):
    await db.connect()
    database = db.get_db()
    # Ensure collections exist
    existing = await database.list_collection_names()
    for col in (
        "entities",
        "transactions",
        "telecom_events",
        "accounts",
        "ipdr",
        "audit_trail",
        "cases",
        "case_documents",
    ):
        if col not in existing:
            await database.create_collection(col)
    await ensure_indexes(database)
    await backfill_accounts_and_ipdr(database)
    await ensure_default_case(database)
    yield
    await db.disconnect()


app = FastAPI(title="E-Rakshak Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(investigation_router)
app.include_router(graph_router)
app.include_router(browse_router)
app.include_router(intelligence_router)
app.include_router(cases_router)
app.include_router(documents_router)


@app.get("/")
async def root():
    return {
        "service": "E-Rakshak Backend",
        "docs": "/docs",
        "health": "/api/health",
        "frontend": "http://localhost:3000",
    }


@app.get("/api/health")
async def health_check():
    database = db.get_db()
    collections = await database.list_collection_names()
    return {"status": "ok", "db": "connected", "collections": sorted(collections)}
