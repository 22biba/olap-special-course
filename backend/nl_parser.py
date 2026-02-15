"""
Natural language to structured intent. Uses OpenAI API when OPENAI_API_KEY is set;
falls back to keyword parsing otherwise.
"""
import json
import os
import re
from typing import Any, Dict, List, Optional


def parse_natural_language(text: str, conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """Convert natural language question to structured BI intent (task_type, time_scope, dimensions, measure)."""
    if not text or not text.strip():
        return _default_intent()

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            return _parse_with_llm(text.strip(), api_key, conversation_history or [])
        except Exception:
            pass
    return _parse_with_keywords(text.strip())


def _parse_with_llm(text: str, api_key: str, history: List[Dict]) -> Dict[str, Any]:
    """Use OpenAI to extract structured intent from natural language."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    schema_desc = """
Extract a structured BI intent from the user's question. Return valid JSON only.
Fields:
- task_type: one of "compare", "top_n", "slice", "dice", "pivot", "drill_down", "roll_up", "kpi"
- time_scope: { "granularity": "year|quarter|month", "periods": ["2024-Q3", "2024-Q4"] or [] }
- dimensions: ["region"|"country"|"category"|"segment"] (one or more)
- measure: "revenue"|"profit"|"quantity"
- filters: {} or e.g. {"region": "Europe"}
- n: integer for top_n (default 5)
For compare: use periods like ["2024-Q3","2024-Q4"]. For top_n: set n. For pivot: row_dim, col_dim.
"""
    messages = [
        {
            "role": "system",
            "content": "You are a BI query parser. Output only valid JSON, no markdown or extra text.",
        },
        {"role": "user", "content": schema_desc + f"\nUser question: {text}"},
    ]
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0,
    )
    raw = resp.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```\w*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
    intent = json.loads(raw)
    return _normalize_intent(intent)


def _normalize_intent(intent: Dict) -> Dict[str, Any]:
    """Ensure intent has required fields with sensible defaults."""
    return {
        "task_type": intent.get("task_type", "compare"),
        "time_scope": intent.get("time_scope", {"granularity": "quarter", "periods": ["2024-Q3", "2024-Q4"]}),
        "dimensions": intent.get("dimensions", ["region"]),
        "measure": intent.get("measure", "revenue"),
        "filters": intent.get("filters", {}),
        "n": intent.get("n", 5),
        "row_dim": intent.get("row_dim"),
        "col_dim": intent.get("col_dim"),
    }


def _parse_with_keywords(text: str) -> Dict[str, Any]:
    """Keyword-based fallback when LLM is not available."""
    t = text.strip().lower()
    intent = {
        "task_type": "compare",
        "time_scope": {"granularity": "quarter", "periods": ["2024-Q3", "2024-Q4"]},
        "dimensions": ["region"],
        "measure": "revenue",
        "filters": {},
        "n": 5,
    }

    quarter_match = re.search(r"q(\d)\s*(?:and|vs?\.?| versus )\s*q(\d)\s*(?:(\d{4})|(\d{4}))?", t)
    if quarter_match:
        q1, q2, y1, y2 = quarter_match.groups()
        year = y1 or y2 or "2024"
        intent["time_scope"]["periods"] = [f"{year}-Q{q1}", f"{year}-Q{q2}"]
        intent["time_scope"]["granularity"] = "quarter"
    if re.search(r"year\s*over\s*year|yoy|y-o-y", t):
        intent["time_scope"]["granularity"] = "quarter"
    if re.search(r"month\s*over\s*month|mom|m-o-m", t):
        intent["time_scope"]["granularity"] = "month"

    if re.search(r"\bregion", t):
        intent["dimensions"] = ["region"]
    if re.search(r"\bcountry|countries", t):
        intent["dimensions"] = ["country"]
    if re.search(r"\bcategory|categories|product", t):
        intent["dimensions"] = ["category"]
    if re.search(r"\bsegment|customer", t):
        intent["dimensions"] = ["segment"]

    if re.search(r"\bprofit\b", t) and "margin" not in t:
        intent["measure"] = "profit"
    if re.search(r"\b(revenue|sales)\b", t):
        intent["measure"] = "revenue"
    if re.search(r"margin", t):
        intent["measure"] = "profit"

    if re.search(r"compare|versus|vs\.?|against", t):
        intent["task_type"] = "compare"
    if re.search(r"top\s*(\d+)|ranking|best\s*(\d+)", t):
        m = re.search(r"top\s*(\d+)|best\s*(\d+)", t)
        intent["task_type"] = "top_n"
        if m:
            intent["n"] = int(m.group(1) or m.group(2) or 5)
    if re.search(r"drill|break\s*down|breakdown", t):
        intent["task_type"] = "drill_down"
    if re.search(r"roll\s*up|rollup", t):
        intent["task_type"] = "roll_up"
    if re.search(r"pivot", t):
        intent["task_type"] = "pivot"

    return intent


def _default_intent() -> Dict[str, Any]:
    return {
        "task_type": "compare",
        "time_scope": {"granularity": "quarter", "periods": ["2024-Q3", "2024-Q4"]},
        "dimensions": ["region"],
        "measure": "revenue",
        "filters": {},
    }
