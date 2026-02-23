"""
API layer: FastAPI app – Tier 3 OLAP BI Platform.
Endpoints: /query, /kpi, /report.
Run from backend: uvicorn main:app --reload --port 8000
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from nl_parser import parse_natural_language
from orchestrator.planner import Planner

app = FastAPI(
    title="OLAP BI Platform API",
    description="""Tier 3 – AI-powered Business Intelligence with multi-agent OLAP analysis.

**Swagger UI:** `/docs`  
**ReDoc:** `/redoc`  
**OpenAPI JSON spec:** `/openapi.json`

Features: natural language queries, slice/dice/pivot, drill-down/roll-up, KPI calculations, reports.""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

planner = Planner()


class BIQueryRequest(BaseModel):
    """Request body for BI query endpoints. Use natural language or structured fields."""

    natural_language_query: Optional[str] = Field(
        default=None,
        description='Natural language question, e.g. "Compare Q3 vs Q4 2024 by region"',
        examples=["Compare Q3 vs Q4 2024 by region", "Top 5 regions by revenue"],
    )
    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional conversation history for context",
    )


class BIQueryResponse(BaseModel):
    result: Dict[str, Any]


def _get_intent(payload: BIQueryRequest) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Parse natural language to intent; pass conversation history for context."""
    history = []
    if payload.conversation_history:
        history = [{"query": h.get("query"), "result": h.get("result")} for h in payload.conversation_history]
    if payload.natural_language_query and payload.natural_language_query.strip():
        intent = parse_natural_language(payload.natural_language_query, history)
        return intent, history
    return {
        "task_type": "compare",
        "time_scope": {"granularity": "quarter", "periods": ["2024-Q3", "2024-Q4"]},
        "dimensions": ["region"],
        "measure": "revenue",
        "filters": {},
    }, history


@app.get("/", tags=["Health"])
def root():
    """Service info and links to Swagger/API docs."""
    return {
        "message": "OLAP BI Platform API",
        "swagger": "/docs",
        "redoc": "/redoc",
        "openapi_spec": "/openapi.json",
        "endpoints": ["POST /query", "POST /analytics/query", "POST /kpi", "POST /report"],
    }


@app.post("/query", response_model=BIQueryResponse, tags=["Query"])
async def query(payload: BIQueryRequest) -> BIQueryResponse:
    """Main endpoint: natural-language or structured query; returns full pipeline (cube, KPI, drill, report)."""
    intent, history = _get_intent(payload)
    result = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result=result)


@app.post("/analytics/query", response_model=BIQueryResponse, tags=["Query"])
async def analytics_query(payload: BIQueryRequest) -> BIQueryResponse:
    """Alias for /query. Same request/response."""
    intent, history = _get_intent(payload)
    result = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result=result)


@app.post("/kpi", response_model=BIQueryResponse, tags=["KPI"])
async def kpi(payload: BIQueryRequest) -> BIQueryResponse:
    """Return KPI-focused result: kpi_data, best_performer, and minimal report."""
    intent, history = _get_intent(payload)
    full = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result={
        "kpi_data": full.get("kpi_data", []),
        "best_performer": full.get("best_performer"),
        "report": full.get("report", {}),
    })


@app.post("/report", response_model=BIQueryResponse, tags=["Report"])
async def report(payload: BIQueryRequest) -> BIQueryResponse:
    """Return report-only: executive summary, totals, formatting, formatted table, follow-up suggestions."""
    intent, history = _get_intent(payload)
    full = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result={"report": full.get("report", {})})
