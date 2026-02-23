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

    raw = text.strip()
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            intent = _parse_with_llm(raw, api_key, conversation_history or [])
        except Exception:
            intent = _parse_with_keywords(raw)
    else:
        intent = _parse_with_keywords(raw)

    intent = _apply_filter_override(raw, intent)
    if re.search(r"across\s+all\s+years|all\s+years", raw, re.IGNORECASE) and re.search(r"revenue|profit", raw, re.IGNORECASE):
        intent = dict(intent)
        intent["task_type"] = "slice"
        intent["dimensions"] = ["date_year"]
        intent["filters"] = intent.get("filters") or {}
        ts = intent.get("time_scope") or {}
        intent["time_scope"] = {**ts, "periods": []}
    intent = _apply_compound_override(raw, intent)
    intent = _apply_percentage_override(raw, intent)
    return intent


def _parse_with_llm(text: str, api_key: str, history: List[Dict]) -> Dict[str, Any]:
    """Use OpenAI to extract structured intent from natural language."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    schema_desc = """
Extract a structured BI intent from the user's question. Return valid JSON only.
Fields:
- task_type: "aggregate"|"compare"|"top_n"|"slice"|"dice"|"pivot"|"drill_down"|"roll_up"
- time_scope: { "granularity": "year|quarter|month", "periods": [] or ["2024-Q3","2024-Q4"] }
- dimensions: ["region"|"country"|"category"|"segment"|"date_year"|"date_month_name"] or [] for aggregate
- measure: "revenue"|"profit"|"quantity"|"unit_price"|"profit_margin"
- filters: {"region": "Asia Pacific", "date_year": 2023} - extract ALL filters from the question
- having_min: number e.g. 500 for "revenue > 500" or "revenue > $500"
- n: integer for top_n (default 5)
Use task_type="slice" or "dice" for "Filter to X, Y, Z" - do NOT use compare. filters must include region and date_year when mentioned.
For "Filter to Asia Pacific, 2023, revenue > 500": task_type="slice", filters={"region":"Asia Pacific","date_year":2023}, having_min=500.
For "total revenue across all years" or "revenue across all years": task_type="slice", dimensions=["date_year"], filters={}, time_scope.periods=[] so the user sees revenue by year (2022, 2023, 2024).
For compare: use periods. For single global total (no breakdown): task_type="aggregate", dimensions=[].
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


def _apply_compound_override(text: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    """Detect compound queries: 'X, then Y' or 'Show category totals, drill into X by subcategory' (comma without 'then')."""
    raw = text.strip()

    if re.search(r"category\s+totals", raw, re.IGNORECASE) and re.search(r"drill\s+into\s+.+\s+by\s+subcategory", raw, re.IGNORECASE):
        parts = re.split(r",\s*(?:then\s+)?", raw, maxsplit=1)
        if len(parts) >= 2:
            first, second = parts[0].strip(), parts[1].strip()
            cat_second = re.search(r"drill\s+into\s+(.+?)\s+by\s+subcategory", second, re.IGNORECASE)
            if cat_second:
                category_name = cat_second.group(1).strip()
                measure = "revenue" if re.search(r"revenue", raw, re.IGNORECASE) else "profit" if re.search(r"profit", raw, re.IGNORECASE) else "revenue"
                step0 = _normalize_intent({
                    "task_type": "slice",
                    "dimensions": ["category"],
                    "measure": measure,
                    "filters": {},
                    "time_scope": intent.get("time_scope", {"granularity": "quarter", "periods": []}),
                })
                step1 = _normalize_intent({
                    "task_type": "slice",
                    "dimensions": ["subcategory"],
                    "measure": measure,
                    "filters": {"category": category_name},
                    "time_scope": intent.get("time_scope", {}),
                })
                step1["filters"] = {"category": category_name}
                return {
                    "task_type": "compound",
                    "steps": [step0, step1],
                    "measure": measure,
                    "filters": intent.get("filters", {}),
                    "time_scope": intent.get("time_scope", {}),
                    "dimensions": intent.get("dimensions", ["region"]),
                    "n": intent.get("n", 5),
                    "row_dim": intent.get("row_dim"),
                    "col_dim": intent.get("col_dim"),
                    "having_min": intent.get("having_min"),
                }

   
    if not re.search(r",\s*then\s+|\bthen\s+", raw, re.IGNORECASE):
        return intent
    parts = re.split(r",\s*then\s+|\bthen\s+", raw, maxsplit=1)
    if len(parts) != 2:
        return intent
    first, second = parts[0].strip(), parts[1].strip()
    first_ok = bool(
        re.search(r"(?:revenue|profit)\s+by\s+year|show\s+(?:revenue|profit)\s+by\s+year", first, re.IGNORECASE)
        or (re.search(r"by\s+year", first, re.IGNORECASE) and re.search(r"revenue|profit", first, re.IGNORECASE))
    )
    second_ok = bool(re.search(r"drill\s+into\s+\d{4}", second, re.IGNORECASE))
    if not (first_ok and second_ok):
        return intent
    year_m = re.search(r"drill\s+into\s+(\d{4})", second, re.IGNORECASE)
    year = int(year_m.group(1)) if year_m else 2024
    measure = "revenue" if re.search(r"revenue", first, re.IGNORECASE) else "profit" if re.search(r"profit", first, re.IGNORECASE) else "revenue"
    step0 = _normalize_intent({
        "task_type": "slice",
        "dimensions": ["date_year"],
        "measure": measure,
        "filters": {},
        "time_scope": {"granularity": "year", "periods": []},
    })
    step1 = {
        "task_type": "drill_down",
        "current_level": "year",
        "filters": {"year": year, "date_year": year},
        "measure": measure,
        "time_scope": {"granularity": "quarter", "periods": []},
        "dimensions": ["region"],
        "n": 5,
        "row_dim": None,
        "col_dim": None,
        "having_min": None,
    }
    return {
        "task_type": "compound",
        "steps": [step0, step1],
        "measure": measure,
        "filters": intent.get("filters", {}),
        "time_scope": intent.get("time_scope", {}),
        "dimensions": intent.get("dimensions", ["region"]),
        "n": intent.get("n", 5),
        "row_dim": intent.get("row_dim"),
        "col_dim": intent.get("col_dim"),
        "having_min": intent.get("having_min"),
    }


def _apply_percentage_override(text: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    """'What percentage of revenue comes from each region?' -> slice by that dimension and compute share."""
    raw = text.strip()
    if not re.search(r"percentage of (revenue|profit)|what percentage|share of (revenue|profit)", raw, re.IGNORECASE):
        return intent
    dim = None
    if re.search(r"\bregion|each region\b", raw, re.IGNORECASE):
        dim = "region"
    elif re.search(r"\bcountry|countries\b", raw, re.IGNORECASE):
        dim = "country"
    elif re.search(r"\bcategory|categories\b", raw, re.IGNORECASE):
        dim = "category"
    elif re.search(r"\bsegment|segments\b", raw, re.IGNORECASE):
        dim = "segment"
    if not dim:
        return intent
    intent = dict(intent)
    intent["task_type"] = "slice"
    intent["dimensions"] = [dim]
    intent["compute_percentage"] = True
    ts = intent.get("time_scope") or {}
    intent["time_scope"] = {**ts, "periods": []}
    if re.search(r"\bprofit\b", raw, re.IGNORECASE):
        intent["measure"] = "profit"
    else:
        intent["measure"] = "revenue"
    return intent


def _apply_filter_override(text: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    """When query explicitly says 'filter to' or 'filter by', force slice and extract filters from text.
    Ensures each filter query is evaluated on its own context, not previous compare/aggregate flows."""
    t = text.strip().lower()
    if not re.search(r"filter\s+to|filter\s+(?:by|on)", t):
        return intent

    intent = dict(intent)
    intent["task_type"] = "slice"
    ts = intent.get("time_scope") or {}
    ts = dict(ts)
    ts["periods"] = []
    intent["time_scope"] = ts

    filters = intent.get("filters") or {}
    filters = dict(filters)

    for region in ["asia pacific", "europe", "north america", "latin america"]:
        if region in t:
            filters["region"] = region.title()
            break
    year_m = re.search(r"\b(202[2-4])\b", t)
    if year_m:
        filters["date_year"] = int(year_m.group(1))
    rev_gt = re.search(r"revenue\s*>\s*\$?\s*(\d+)", t, re.IGNORECASE)
    if rev_gt:
        intent["having_min"] = float(rev_gt.group(1))

    intent["filters"] = filters
    return intent


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
        "having_min": intent.get("having_min"),
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
        "having_min": None,
    }

    if re.search(r"filter\s+to|filter\s+(?:by|on)", t):
        intent["task_type"] = "slice"
        intent["time_scope"]["periods"] = [] 

    for region in ["asia pacific", "europe", "north america", "latin america"]:
        if region in t:
            intent["filters"]["region"] = region.title()
            break

    year_m = re.search(r"\b(202[2-4])\b", t)
    if year_m:
        intent["filters"]["date_year"] = int(year_m.group(1))

    rev_gt = re.search(r"revenue\s*>\s*\$?\s*(\d+)", t, re.IGNORECASE)
    if rev_gt:
        intent["having_min"] = float(rev_gt.group(1))

    if re.search(r"across\s+all\s+years|all\s+years|total\s+(?:revenue|profit)\s+across\s+all", t) and re.search(r"revenue|profit", t):
        intent["task_type"] = "slice"
        intent["dimensions"] = ["date_year"]
        intent["filters"] = {}
        intent["time_scope"]["periods"] = []
    elif re.search(r"total\s+(?:revenue|profit|sales)", t) or re.search(r"(?:revenue|profit|sales)\s+across\s+all(?!\s+years)", t):
        intent["task_type"] = "aggregate"
        intent["dimensions"] = []
    elif re.search(r"total\s+across", t) and re.search(r"revenue|profit", t):
        intent["task_type"] = "aggregate"
        intent["dimensions"] = []

    year_compare = re.search(r"compare\s+(202[2-4])\s*(?:vs\.?|versus|and)\s*(202[2-4])", t)
    if year_compare:
        y1, y2 = year_compare.groups()
        intent["time_scope"]["periods"] = [int(y1), int(y2)]
        intent["time_scope"]["granularity"] = "year"
        intent["task_type"] = "compare"
        if re.search(r"total\s+revenue|total\s+profit", t):
            intent["dimensions"] = ["region"]

    quarter_match = re.search(r"q(\d)\s*(?:and|vs?\.?| versus )\s*q(\d)\s*(?:(\d{4})|(\d{4}))?", t)
    if quarter_match and intent["time_scope"].get("granularity") != "year":
        q1, q2, y1, y2 = quarter_match.groups()
        year = y1 or y2 or "2024"
        intent["time_scope"]["periods"] = [f"{year}-Q{q1}", f"{year}-Q{q2}"]
        intent["time_scope"]["granularity"] = "quarter"
    if re.search(r"year\s*over\s*year|yoy|y-o-y", t):
        intent["time_scope"]["granularity"] = "quarter"
    if re.search(r"month\s*over\s*month|mom|m-o-m", t):
        intent["time_scope"]["granularity"] = "month"

    if intent.get("task_type") != "aggregate":
        if re.search(r"\bregion", t):
            intent["dimensions"] = ["region"]
        if re.search(r"\bcountry|countries", t):
            intent["dimensions"] = ["country"]
        if re.search(r"\bcategory|categories|product", t):
            intent["dimensions"] = ["category"]
        if re.search(r"\bsegment|customer", t):
            intent["dimensions"] = ["segment"]
        if re.search(r"\bmonth\s*name|month_name", t):
            intent["dimensions"] = ["date_month_name"]
        if re.search(r"\bcorporate\b", t):
            intent["filters"]["segment"] = "Corporate"
        if re.search(r"\bconsumer\b", t):
            intent["filters"]["segment"] = "Consumer"
        if re.search(r"home\s*office", t):
            intent["filters"]["segment"] = "Home Office"

    if re.search(r"\bprofit\b", t) and "margin" not in t:
        intent["measure"] = "profit"
    if re.search(r"\b(revenue|sales)\b", t):
        intent["measure"] = "revenue"
    if re.search(r"margin", t):
        intent["measure"] = "profit"
    if re.search(r"\bunit\s*price|unit_price\b", t):
        intent["measure"] = "unit_price"

    if re.search(r"show\s+q\d\s+data|q\d\s+data\s+for|only\s+q\d|q\d\s+only", t):
        q_match = re.search(r"q(\d)", t)
        if q_match:
            intent["filters"]["date_quarter"] = [f"2024-Q{q_match.group(1)}"]
        intent["task_type"] = "slice"
    elif re.search(r"compare|versus|vs\.?|against", t) and intent.get("task_type") != "aggregate":
        intent["task_type"] = "compare"
    if re.search(r"top\s*(\d+)|ranking|best\s*(\d+)", t):
        m = re.search(r"top\s*(\d+)|best\s*(\d+)", t)
        intent["task_type"] = "top_n"
        if m:
            intent["n"] = int(m.group(1) or m.group(2) or 5)
    if re.search(r"drill|break\s*down|breakdown", t):
        intent["task_type"] = "drill_down"
        year_m = re.search(r"\b(202[2-4])\b", t)
        if year_m:
            intent["filters"] = intent.get("filters") or {}
            intent["filters"]["year"] = int(year_m.group(1))
            intent["filters"]["date_year"] = int(year_m.group(1))
        if re.search(r"quarter|by\s+quarter", t):
            intent["current_level"] = "year"
        elif re.search(r"month|by\s+month", t):
            intent["current_level"] = "quarter"
        else:
            intent["current_level"] = intent.get("current_level", "year")
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
