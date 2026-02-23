# API Documentation

The API is built with **FastAPI**. Swagger/OpenAPI documentation is available when the backend is running:

| UI | URL |
|----|-----|
| **Swagger UI** | http://localhost:8000/docs |
| **ReDoc** | http://localhost:8000/redoc |
| **OpenAPI JSON spec** | http://localhost:8000/openapi.json |

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info and list of endpoints. |
| POST | `/query` | **Main entry.** Accepts natural-language or structured body; returns full pipeline result (cube, KPI, drill, report). |
| POST | `/analytics/query` | Same as `/query`. |
| POST | `/kpi` | Same request body; returns only KPI-focused result (kpi_data, best_performer, report subset). |
| POST | `/report` | Same request body; returns only report (summary, totals, formatting, table). |

## Request body (all POST endpoints)

```json
{
  "natural_language_query": "Compare Q3 vs Q4 2024 by region",
  "task_type": "compare",
  "time_scope": {
    "granularity": "quarter",
    "periods": ["2024-Q3", "2024-Q4"]
  },
  "dimensions": ["region"],
  "measure": "revenue",
  "filters": {},
  "row_dim": null,
  "col_dim": null
}
```

- If **`natural_language_query`** is non-empty, it is parsed (keyword-based) and overrides other fields for intent.
- Otherwise **task_type**, **time_scope**, **dimensions**, **measure**, **filters** define the intent.

## Response shape (e.g. `/query`)

```json
{
  "result": {
    "cube_result": { "type": "dice", "operation": "...", "data": [...] },
    "kpi_result": { "kpi_type": "yoy_growth", "data": [...] },
    "kpi_data": [...],
    "best_performer": { "region": "...", "revenue_current": ..., "revenue_growth": ... },
    "drill": { "current_level": "quarter", "next_level": "month", "members": [...] },
    "report": {
      "summary": "...",
      "totals": { "revenue_growth": ... },
      "formatting": { "rules": [...] },
      "table": [...]
    }
  }
}
```

For **`/kpi`** and **`/report`**, the same `result` object is returned but only the relevant keys are populated.

## CORS

Allowed origins: `http://localhost:5173`, `http://127.0.0.1:5173` (Vite default).
