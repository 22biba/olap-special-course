# OLAP BI Platform – System Architecture

## High-level architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + Vite)                      │
│  Chat box · Form · Tables · Charts · Follow-up suggestions        │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API LAYER (FastAPI)                         │
│  POST /query  ·  POST /kpi  ·  POST /report  ·  /analytics/query │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PLANNER / ORCHESTRATOR                         │
│  Query understanding · Agent selection · Coordination · Context  │
└─────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Dimension    │  │  Cube         │  │  KPI           │  │  Report       │
│  Navigator    │  │  Operations   │  │  Calculator    │  │  Generator    │
│  Agent        │  │  Agent        │  │  Agent         │  │  Agent        │
│  Drill/Roll-up│  │  Slice/Dice/  │  │  YoY, MoM,     │  │  Tables,      │
│               │  │  Pivot        │  │  margins, Top N│  │  summary      │
└───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
        │                  │                  │                  │
        └──────────────────┴──────────────────┴──────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                             │
│  DuckDB connection · Star schema bootstrap · Optional seed      │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STAR SCHEMA DATABASE (DuckDB)                 │
│  fact_sales · dim_date · dim_geography · dim_product · dim_customer │
└─────────────────────────────────────────────────────────────────┘
```

## Component roles

| Component | Responsibility |
|----------|----------------|
| **Frontend** | Chat input, structured form, tables, charts (Recharts), follow-up suggestion chips. Calls `/query` with NL or structured payload. |
| **API** | CORS, `/query` (main NL/structured), `/kpi`, `/report`, `/analytics/query`. NL parsed via `nl_parser` (keyword or future LLM). |
| **Planner** | Builds intent from API; runs compare flow: Cube (dice) → KPI (growth) → best performer → Dimension Navigator (drill) → Report. |
| **Dimension Navigator** | Drill-down (year→quarter→month→day) and roll-up on `dim_date`. |
| **Cube Operations** | Slice (single dimension), dice (multiple), pivot (row/col matrix) on fact + dimensions. |
| **KPI Calculator** | YoY/MoM growth, profit margin, Top N rankings. |
| **Report Generator** | Formatted table, totals, conditional formatting hints, executive summary. |
| **Data layer** | DuckDB file, schema DDL, auto-seed from CSV when empty. |

## Data flow (example)

**User:** “Compare Q3 vs Q4 2024 by region”

1. Frontend sends `POST /query` with `natural_language_query: "Compare Q3 vs Q4 2024 by region"`.
2. Backend parses to intent: `task_type=compare`, `periods=["2024-Q3","2024-Q4"]`, `dimensions=["region"]`, `measure=revenue`.
3. Planner runs:
   - **Cube**: dice by `date_quarter` and `region` → rows (period, region, revenue).
   - **KPI**: period-over-period growth → `revenue_growth` per region; best performer = max growth.
   - **Dimension Navigator**: drill quarter → month (members 1–12).
   - **Report**: summary, totals, formatting rules, formatted table.
4. Response returns `cube_result`, `kpi_data`, `best_performer`, `drill`, `report`.
5. Frontend renders Cube table, KPI table, chart, drill info, report summary/totals/table, and follow-up suggestions.

## Tech stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, Recharts |
| API | FastAPI, Pydantic |
| Agents | Python (no DSPy/LangChain in minimal version) |
| LLM | Optional (OpenAI/Anthropic); NL parsing currently keyword-based |
| Database | DuckDB (file-based star schema) |

## Deliverables mapping

- **Source code:** This repo (backend, frontend, data, docs).
- **API documentation:** OpenAPI/Swagger at `http://localhost:8000/docs`.
- **Architecture document:** This file.
- **Database schema:** See `docs/DATABASE_ER.md` and `backend/database/schema.sql`.
- **User guide:** See `docs/USER_GUIDE.md`.
