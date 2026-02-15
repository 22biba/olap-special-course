"""
Dimension Navigator Agent: drill-down (Year → Quarter → Month) and roll-up.
"""
from typing import Any, Dict, List

from database.connection import get_connection

from .base_agent import BaseAgent

HIERARCHY = ["year", "quarter", "month", "day"]


class DimensionNavigatorAgent(BaseAgent):
    def run(self, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action")
        current_level = params.get("current_level")
        filters = params.get("filters", {})

        if action not in ("drill_down", "roll_up"):
            raise ValueError("action must be 'drill_down' or 'roll_up'")
        if current_level not in HIERARCHY:
            raise ValueError(f"current_level must be one of {HIERARCHY}")

        next_level = HIERARCHY[HIERARCHY.index(current_level) + 1] if action == "drill_down" else HIERARCHY[HIERARCHY.index(current_level) - 1] if HIERARCHY.index(current_level) > 0 else None
        if next_level is None:
            return {"current_level": current_level, "next_level": None, "members": []}

        col = {"year": "year", "quarter": "quarter", "month": "month", "day": "day"}[next_level]
        where_parts, args = [], []
        if filters.get("year") is not None:
            where_parts.append("year = ?")
            args.append(filters["year"])
        if filters.get("quarter") is not None:
            where_parts.append("quarter = ?")
            args.append(filters["quarter"])
        if filters.get("month") is not None:
            where_parts.append("month = ?")
            args.append(filters["month"])
        where_sql = " AND ".join(where_parts)
        where_sql = ("WHERE " + where_sql) if where_sql else ""

        con = get_connection()
        rows = con.execute(f"SELECT DISTINCT {col} FROM dim_date {where_sql} ORDER BY {col}", args).fetchall()
        return {"current_level": current_level, "next_level": next_level, "members": [{"level": next_level, "value": r[0]} for r in rows]}
