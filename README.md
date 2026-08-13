# E-Rakshak

Investigation UI for financial cybercrime cases: bank statements, CDR, IPDR, risk ranking, and proof links.

The **product is `web/`**. Case dumps (Excel/CSV/PDF) stay on the investigator machine and are gitignored.

```
web/
  backend/     FastAPI + MongoDB (ingest, scoring, APIs)
  frontend/    Next.js investigator console
```

Local FIR folders (`ingestion_p/`, `cdr_extraction/`, `bank_statements_and_next_stage/`, root CSVs) are **not** part of the GitHub tree. They are optional caches for this machine only.

## Run locally

MongoDB on `127.0.0.1:27017`, database `erakshak`.

```powershell
cd web\backend
copy .env.example .env
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

```powershell
cd web\frontend
copy .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000 — API is http://127.0.0.1:8001.

Upload bank/CDR/IPDR from **Evidence → Uploaded files**. Scoring is case-relative mule indicators (not a flat FIR-seed bonus).

## What not to commit

Bank statements, CDR extracts, IPDR grids, and `uploads/` are evidence. Keep them off GitHub.
