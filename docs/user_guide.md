# OLAP BI Platform – User Guide

## What this platform does

The OLAP BI Platform is an AI-powered Business Intelligence app that lets you analyze **global retail sales** (10,000 transactions, 2022–2024) using:

- **Natural language** (e.g. “Compare Q3 vs Q4 2024 by region”)
- **Structured filters** (periods, dimension, measure)
- **Four agents**: Cube Operations, KPI Calculator, Dimension Navigator, Report Generator

You get **tables**, **charts**, **executive summary**, **totals**, and **follow-up suggestions**.

---

## How to run the platform

### 1. Backend (API + agents + database)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

- API base: **http://localhost:8000**
- Interactive API docs: **http://localhost:8000/docs**

### 2. Data (first time or to reset)

From the **project root**:

```bash
python -m data.generate_dataset    # creates data/global_retail_sales.csv
python -m data.load_star_schema    # loads CSV into DuckDB (stop backend if it locks the DB)
```

If you don’t load manually, the backend can **auto-seed** the database from the CSV on first use when the fact table is empty.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

- Open **http://localhost:5173**

---

## Using the interface

### Chat box (natural language)

- Type a question and click **Ask**, e.g.:
  - “Compare Q3 vs Q4 2024 by region”
  - “Compare by category”
  - “Show profit by region”
- The backend parses the text (keyword-based; LLM can be plugged in later) and runs the same pipeline as the form.

### Form (structured query)

- Set **Task type**, **Granularity**, **Period 1**, **Period 2**, **Dimension**, **Measure**.
- Click **Run comparison** to run the same flow with those parameters.

### Results

After a query you see:

1. **Follow-up suggestions** – Click a chip to run that question (e.g. “Compare by category”, “Top 5 regions by revenue”).
2. **Cube Operations Agent** – Raw dice/slice result (e.g. revenue by quarter and region).
3. **KPI Calculator Agent** – Growth (or other KPIs), best performer, and a table with conditional formatting (green/red).
4. **Chart** – Bar chart of revenue (and growth) by region (or selected dimension).
5. **Dimension Navigator** – Current level, next level, and members (e.g. quarter → months 1–12).
6. **Report Generator Agent** – Executive summary, totals, and the formatted table.

---

## API endpoints (for integration or scripts)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/query` | Main entry: natural-language or structured body; full result (cube, KPI, drill, report). |
| POST | `/analytics/query` | Same as `/query`. |
| POST | `/kpi` | Same input; response focused on KPI data and best performer. |
| POST | `/report` | Same input; response focused on report (summary, totals, table). |
| GET | `/docs` | OpenAPI/Swagger UI. |

**Example body (structured):**

```json
{
  "task_type": "compare",
  "time_scope": { "granularity": "quarter", "periods": ["2024-Q3", "2024-Q4"] },
  "dimensions": ["region"],
  "measure": "revenue"
}
```

**Example body (natural language):**

```json
{
  "natural_language_query": "Compare Q3 vs Q4 2024 by region"
}
```

---

## Features covered

- **Slice / Dice / Pivot** – Cube Operations Agent.
- **Drill-down / Roll-up** – Dimension Navigator (time hierarchy; drill shown in UI).
- **Compare** – Q vs Q (or two periods) by dimension.
- **KPI calculations** – YoY-style growth, profit margin, Top N (backend support).
- **Charts** – Bar chart of revenue and growth by dimension.
- **Formatted reports** – Tables, totals, conditional formatting, executive summary.
- **Follow-up suggestions** – Clickable chips for next questions.

---

## Troubleshooting

- **“No data for the selected filters”** – Ensure the database is filled: run `python -m data.generate_dataset` then `python -m data.load_star_schema` (with backend stopped), or let the backend auto-seed on first request.
- **404 or CORS errors** – Use the backend at `http://localhost:8000` and frontend at `http://localhost:5173`; CORS is set for these origins.
- **Q1/Q2 appears to have no data** – The dataset includes all quarters (2022–2024). Try reloading: stop the backend, run `python -m data.load_star_schema`, then restart. You can also run `python scripts/verify_data.py` (with backend stopped) to confirm quarter coverage.
- **Module not found (e.g. duckdb)** – From `backend`: `pip install -r requirements.txt`.
