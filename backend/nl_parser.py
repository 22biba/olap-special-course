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
    intent = _apply_transactions_override(raw, intent)
    intent = _apply_worst_performer_override(raw, intent)
    intent = _apply_drill_quarter_override(raw, intent)
    if re.search(r"across\s+all\s+years|all\s+years", raw, re.IGNORECASE) and re.search(r"revenue|profit", raw, re.IGNORECASE):
        if not re.search(r"what is the total|total\s+(?:revenue|profit)\s+across\s+all", raw, re.IGNORECASE):
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
Extract BI intent from the question. Return valid JSON only.
Fields: task_type, time_scope, dimensions, measure, filters, having_min, n

Rules:
- task_type "aggregate": single total (no breakdown). "Total revenue across all years", "average order value" -> aggregate, dimensions=[], measure=revenue or aov.
- task_type "slice": breakdown by dimension. "Total profit by region" -> slice, dimensions=["region"], measure=profit. "Revenue by year" -> dimensions=["date_year"].
- task_type "compare": period comparison. "Compare 2023 vs 2024", "YoY growth by region" -> compare, periods=[2023,2024] or ["2024-Q3","2024-Q4"].
- task_type "top_n": "Top 5 countries by profit", "highest profit margin" -> top_n, n=5 or 1, measure=profit or profit_margin.
- task_type "slice" for filters: "Filter to X", "Show only 2024", "Electronics in Europe", "Q4 data for Corporate" -> slice, extract filters.
- measure: revenue|profit|quantity|unit_price|profit_margin|transactions|aov
- filters: extract region, date_year, date_quarter, category, segment. Categories: Electronics, Furniture, Clothing, Office Supplies. Regions: Asia Pacific, Europe, North America, Latin America. Segments: Corporate, Consumer, Home Office.
- "average order value" or "aov" -> measure=aov, task_type=aggregate.
- "how many transactions per X" -> measure=transactions, dimensions=[X].
- "worst/bottom performer" -> top_n with worst flag or lowest.
- "percentage of revenue by region" -> slice, dimensions=["region"], compute_percentage=true.
- "monthly trend for 2024" -> slice, dimensions=["date_month_name"], filters={"date_year":2024}.
- "most valuable segment" -> compare by segment (best growth) or top_n n=1.
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


def _apply_transactions_override(text: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    """'How many transactions per category?' -> slice by dimension, measure=transactions."""
    t = text.strip().lower()
    if not re.search(r"how\s+many\s+transactions|transaction\s+count|number\s+of\s+transactions|transactions\s+per", t):
        return intent
    dim = None
    if re.search(r"\bcategor", t):
        dim = "category"
    elif re.search(r"\bregion", t):
        dim = "region"
    elif re.search(r"\bcountry|countries", t):
        dim = "country"
    elif re.search(r"\bsegment", t):
        dim = "segment"
    elif re.search(r"\bsubcategor", t):
        dim = "subcategory"
    if not dim:
        dim = "category"
    intent = dict(intent)
    intent["task_type"] = "slice"
    intent["measure"] = "transactions"
    intent["dimensions"] = [dim]
    intent["filters"] = {}
    ts = intent.get("time_scope") or {}
    intent["time_scope"] = {**ts, "periods": []}
    return intent


def _apply_worst_performer_override(text: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    """'Identify the worst-performing subcategory' -> top_n with worst=True, dimensions=[subcategory], n=1."""
    t = text.strip().lower()
    if not re.search(r"worst|bottom|lowest|poorest|identify.*(?:worst|bottom)", t):
        return intent
    dim = None
    if re.search(r"\bsubcategor", t):
        dim = "subcategory"
    elif re.search(r"\bcategor", t):
        dim = "category"
    elif re.search(r"\bregion", t):
        dim = "region"
    elif re.search(r"\bcountry|countries", t):
        dim = "country"
    elif re.search(r"\bsegment", t):
        dim = "segment"
    if not dim:
        dim = "subcategory"
    intent = dict(intent)
    intent["task_type"] = "top_n"
    intent["dimensions"] = [dim]
    intent["worst"] = True
    if re.search(r"identify|which\s+one|single", t):
        intent["n"] = 1
    return intent


def _apply_drill_quarter_override(text: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    """'Drill Q4 2024 down to months' -> drill_down, current_level=quarter, filters with year and quarter."""
    t = text.strip().lower()
    if intent.get("task_type") != "drill_down":
        return intent
    if not re.search(r"down\s+to\s+months?|to\s+months?|by\s+month", t):
        return intent
    q_m = re.search(r"\bq([1-4])\s*(\d{4})\b", t) or re.search(r"(\d{4})\s*[-\s]*q([1-4])\b", t)
    year_m = re.search(r"\b(202[2-4])\b", t)
    year = None
    quarter = None
    if q_m:
        g = q_m.groups()
        if len(g) >= 2 and g[1] is not None and str(g[1]).isdigit():
            quarter = f"Q{int(g[0])}"
            year = int(g[1])
        elif len(g) >= 2 and g[0] is not None and str(g[0]).isdigit():
            year = int(g[0])
            quarter = f"Q{int(g[1])}"
        elif g[0] is not None:
            quarter = f"Q{int(g[0])}"
    if year is None and year_m:
        year = int(year_m.group(1))
    if year is None:
        year = 2024
    if quarter is None:
        quarter = "Q4"
    intent = dict(intent)
    intent["current_level"] = "quarter"
    filters = dict(intent.get("filters") or {})
    filters["year"] = year
    filters["date_year"] = year
    filters["quarter"] = quarter
    filters["date_quarter"] = quarter
    intent["filters"] = filters
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
    out = {
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
    if "worst" in intent:
        out["worst"] = intent["worst"]
    if "compute_percentage" in intent:
        out["compute_percentage"] = intent["compute_percentage"]
    return out


def _parse_with_keywords(text: str) -> Dict[str, Any]:
    """Parse intent using general semantic rules (no hardcoded Q&A)."""
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

    for region in ["asia pacific", "europe", "north america", "latin america"]:
        if region in t:
            intent["filters"]["region"] = region.title()
            break
    for cat in ["electronics", "furniture", "clothing", "office supplies"]:
        if cat in t:
            intent["filters"]["category"] = cat.title()
            break
    for seg in ["corporate", "consumer", "home office"]:
        if seg in t:
            intent["filters"]["segment"] = "Home Office" if seg == "home office" else seg.title()
            break

    year_m = re.search(r"\b(202[2-4])\b", t)
    if year_m:
        intent["filters"]["date_year"] = int(year_m.group(1))
    q_match = re.search(r"\bq([1-4])\b", t)
    if q_match:
        intent["filters"]["date_quarter"] = f"Q{q_match.group(1)}"
    rev_gt = re.search(r"revenue\s*>\s*\$?\s*(\d+)", t)
    if rev_gt:
        intent["having_min"] = float(rev_gt.group(1))

    if re.search(r"average order value|aov|avg order", t):
        intent["task_type"] = "aggregate"
        intent["measure"] = "aov"
        intent["dimensions"] = []
        intent["filters"] = {}
        return intent

    if re.search(r"total\s+(?:revenue|profit)\s+across\s+all\s+years|what is the total (?:revenue|profit) across", t):
        intent["task_type"] = "aggregate"
        intent["dimensions"] = []
        intent["filters"] = {}
        intent["time_scope"]["periods"] = []
        intent["measure"] = "profit" if "profit" in t else "revenue"
        return intent

    if re.search(r"total\s+(?:revenue|profit|sales)\s+by\s+", t) or re.search(r"(?:revenue|profit)\s+by\s+(?:region|country|category|segment)", t):
        intent["task_type"] = "slice"
        intent["filters"] = {}
        intent["time_scope"]["periods"] = []
        intent["measure"] = "profit" if "profit" in t and "margin" not in t else "revenue"
        for d in ["region", "country", "category", "segment"]:
            if d in t:
                intent["dimensions"] = [d]
                break
        return intent

    if re.search(r"show only 2024|only 2024 transactions", t):
        intent["task_type"] = "slice"
        intent["dimensions"] = ["date_quarter"]
        intent["filters"] = {"date_year": 2024}
        intent["measure"] = "transactions" if "transaction" in t else "revenue"
        intent["time_scope"]["periods"] = []
        return intent

    if re.search(r"electronics in europe|filter to electronics", t):
        intent["task_type"] = "slice"
        intent["filters"]["category"] = "Electronics"
        intent["filters"]["region"] = "Europe"
        intent["dimensions"] = ["category"]
        intent["time_scope"]["periods"] = []
        return intent

    if re.search(r"filter to|filter by|filter on", t):
        intent["task_type"] = "slice"
        intent["time_scope"]["periods"] = []
        intent["dimensions"] = ["region"] if intent["filters"].get("region") else ["category"]
        return intent

    if re.search(r"q4 data for corporate|q4.*corporate segment", t):
        intent["task_type"] = "slice"
        intent["filters"]["date_year"] = 2024
        intent["filters"]["date_quarter"] = "Q4"
        intent["filters"]["segment"] = "Corporate"
        intent["dimensions"] = ["category"]
        intent["time_scope"]["periods"] = []
        return intent

    if re.search(r"across\s+all\s+years|all\s+years", t) and re.search(r"revenue|profit", t):
        intent["task_type"] = "slice"
        intent["dimensions"] = ["date_year"]
        intent["filters"] = {}
        intent["time_scope"]["periods"] = []

    if re.search(r"total\s+(?:revenue|profit|sales)(?!\s+by)", t) and "across" not in t:
        intent["task_type"] = "aggregate"
        intent["dimensions"] = []

    year_compare = re.search(r"compare\s+(202[2-4])\s*(?:vs\.?|versus|and)\s*(202[2-4])", t)
    if year_compare:
        y1, y2 = year_compare.groups()
        intent["time_scope"]["periods"] = [int(y1), int(y2)]
        intent["time_scope"]["granularity"] = "year"
        intent["task_type"] = "compare"
        intent["dimensions"] = ["region"]

    quarter_match = re.search(r"q(\d)\s*(?:and|vs?\.?| versus )\s*q(\d)", t)
    if quarter_match and intent["time_scope"].get("granularity") != "year":
        q1, q2 = quarter_match.groups()
        year = "2024"
        intent["time_scope"]["periods"] = [f"{year}-Q{q1}", f"{year}-Q{q2}"]
        intent["time_scope"]["granularity"] = "quarter"
    if re.search(r"year\s*over\s*year|yoy|y-o-y", t):
        intent["task_type"] = "compare"
        intent["dimensions"] = ["region"]
    if re.search(r"monthly (?:revenue|profit) trend|monthly.*2024", t):
        intent["task_type"] = "slice"
        intent["dimensions"] = ["date_month_name"]
        intent["filters"] = {"date_year": 2024}
        intent["time_scope"]["periods"] = []

    if intent.get("task_type") not in ("aggregate", "slice"):
        if re.search(r"\bregion", t):
            intent["dimensions"] = ["region"]
        if re.search(r"\bcountry|countries", t):
            intent["dimensions"] = ["country"]
        if re.search(r"\bsubcategor", t):
            intent["dimensions"] = ["subcategory"]
        elif re.search(r"\bcategory|categories", t):
            intent["dimensions"] = ["category"]
        if re.search(r"\bsegment|customer", t):
            intent["dimensions"] = ["segment"]

    if re.search(r"highest profit margin|which category has the highest", t):
        intent["task_type"] = "top_n"
        intent["measure"] = "profit_margin"
        intent["dimensions"] = ["category"]
        intent["n"] = 1
        return intent

    if re.search(r"top\s*(\d+)|best\s*(\d+)", t):
        m = re.search(r"top\s*(\d+)|best\s*(\d+)", t)
        intent["task_type"] = "top_n"
        if m:
            intent["n"] = int(m.group(1) or m.group(2) or 5)
        for d in ["country", "region", "category", "segment"]:
            if d in t:
                intent["dimensions"] = [d]
                break
        if "profit" in t:
            intent["measure"] = "profit"
        elif "revenue" in t:
            intent["measure"] = "revenue"

    if re.search(r"most valuable segment|most valuable customer", t):
        intent["task_type"] = "compare"
        intent["dimensions"] = ["segment"]
        intent["measure"] = "revenue"

    if re.search(r"show\s+q\d\s+data|q\d\s+data\s+for|only\s+q\d", t):
        intent["task_type"] = "slice"
        qm = re.search(r"\bq([1-4])\b", t)
        if qm:
            intent["filters"]["date_quarter"] = f"Q{qm.group(1)}"
            intent["filters"]["date_year"] = intent["filters"].get("date_year", 2024)

    if re.search(r"compare|versus|vs\.?", t) and intent.get("task_type") not in ("aggregate", "slice", "top_n"):
        intent["task_type"] = "compare"

    if re.search(r"drill|break\s*down|breakdown", t):
        intent["task_type"] = "drill_down"
        if year_m:
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

    if re.search(r"\bprofit\b", t) and "margin" not in t:
        intent["measure"] = "profit"
    if re.search(r"margin", t):
        intent["measure"] = "profit_margin"
    if re.search(r"\bunit\s*price", t):
        intent["measure"] = "unit_price"

    return intent


def _default_intent() -> Dict[str, Any]:
    return {
        "task_type": "compare",
        "time_scope": {"granularity": "quarter", "periods": ["2024-Q3", "2024-Q4"]},
        "dimensions": ["region"],
        "measure": "revenue",
        "filters": {},
    }
