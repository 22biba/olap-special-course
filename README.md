# OLAP BI Platform – Tier 3 Architect

AI-powered Business Intelligence platform for analyzing **global retail sales** (10k transactions, 2022–2024) via natural language and structured queries. Built with a **multi-agent system**, **star schema** database, **FastAPI** backend, and **React** frontend.

## Features

- **Natural language:** e.g. “Compare Q3 vs Q4 2024 by region”
- **Four agents:** Dimension Navigator (drill/roll-up), Cube Operations (slice/dice/pivot), KPI Calculator (YoY, MoM, margins, Top N), Report Generator (tables, totals, summaries)
- **Planner/orchestrator** to coordinate agents and interpret queries
- **Charts** (Recharts) and **formatted reports** with conditional formatting
- **Follow-up suggestions** for next questions

## Quick start

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Data (from project root; optional – backend can auto-seed)
python -m data.generate_dataset
python -m data.load_star_schema

# Frontend
cd frontend
npm install
npm run dev
```

Optional: set `OPENAI_API_KEY` for LLM-based natural language parsing (copy `.env.example` to `.env`).

- Frontend: **http://localhost:5173**
- API docs: **http://localhost:8000/docs**

## Deliverables

| Deliverable | Location |
|-------------|----------|
| **Working demo** | [docs/WORKING_DEMO.md](docs/WORKING_DEMO.md) – run locally, sample questions, offline Swagger |
| **Database schema** | [docs/DATABASE_ER.md](docs/DATABASE_ER.md) – ER diagram, table descriptions, DDL scripts |
| **Agent specifications** | [docs/agent_specifications.md](docs/agent_specifications.md) – purpose, I/O, logic for each agent |

## Repository structure

```
├── backend/          # FastAPI, agents, planner, DB connection
├── frontend/         # React + Vite, chat input, tables, charts
├── data/             # generate_dataset.py, load_star_schema.py, CSV, DuckDB
├── docs/             # Architecture, ER, API, User guide, Working demo
└── README.md
```


## Tech stack

- **Frontend:** React, Vite, Recharts
- **API:** FastAPI, Pydantic
- **Database:** DuckDB (star schema)
- **LLM:** OpenAI API for NL parsing when `OPENAI_API_KEY` is set; keyword fallback otherwise

## License

Use as required by your course or organization.
