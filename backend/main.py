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
from pydantic import BaseModel

from nl_parser import parse_natural_language
from orchestrator.planner import Planner

app = FastAPI(
    title="OLAP BI Platform",
    description="Tier 3 – AI-powered Business Intelligence with multi-agent OLAP analysis. OpenAPI: /docs",
    version="1.0.0",
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
    natural_language_query: Optional[str] = None
    conversation_history: Optional[List[Dict[str, Any]]] = None


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


@app.get("/")
def root():
    return {
        "message": "OLAP BI Platform API",
        "docs": "/docs",
        "endpoints": ["POST /query", "POST /kpi", "POST /report"],
    }


@app.post("/query", response_model=BIQueryResponse)
async def query(payload: BIQueryRequest) -> BIQueryResponse:
    """Main NL endpoint: natural-language query; returns full agent pipeline result."""
    intent, history = _get_intent(payload)
    result = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result=result)


@app.post("/kpi", response_model=BIQueryResponse)
async def kpi(payload: BIQueryRequest) -> BIQueryResponse:
    """Return KPI-focused result: kpi_data, best_performer, and minimal report."""
    intent, history = _get_intent(payload)
    full = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result={
        "kpi_data": full.get("kpi_data", []),
        "best_performer": full.get("best_performer"),
        "report": full.get("report", {}),
    })


@app.post("/report", response_model=BIQueryResponse)
async def report(payload: BIQueryRequest) -> BIQueryResponse:
    """Return report-only: executive summary, totals, formatting, formatted table, follow-up suggestions."""
    intent, history = _get_intent(payload)
    full = planner.handle_query(intent, conversation_history=history)
    return BIQueryResponse(result={"report": full.get("report", {})})
