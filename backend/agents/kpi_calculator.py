"""
KPI Calculator Agent: YoY/MoM growth, profit margin, Top N rankings.
"""
from typing import Any, Dict, List

from .base_agent import BaseAgent


class KPICalculatorAgent(BaseAgent):
    def run(self, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        kpi_type = params.get("kpi_type")
        data: List[Dict[str, Any]] = params.get("data", [])
        measure = params.get("measure", "revenue")
        dimension = params.get("dimension")
        period_key = params.get("period_key")
        current_period = params.get("current_period")
        previous_period = params.get("previous_period")
        n = params.get("n", 5)

        if kpi_type == "profit_margin":
            out = self._profit_margin(data)
        elif kpi_type in ("yoy_growth", "mom_change"):
            out = self._period_growth(data, measure, period_key, current_period, previous_period)
        elif kpi_type == "top_n":
            out = self._top_n(data, measure, dimension, n, ascending=False)
        elif kpi_type == "bottom_n":
            out = self._top_n(data, measure, dimension, n, ascending=True)
        else:
            raise ValueError("kpi_type must be profit_margin, yoy_growth, mom_change, top_n, or bottom_n")
        return {"kpi_type": kpi_type, "data": out}

    def _profit_margin(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        result = []
        for row in data:
            r = dict(row)
            rev = float(row.get("revenue") or 0.0)
            prof = float(row.get("profit") or 0.0)
            r["profit_margin"] = (prof / rev) if rev else 0.0
            result.append(r)
        return result

    def _period_growth(
        self, data: List[Dict[str, Any]], measure: str, period_key: str,
        current_period: Any, previous_period: Any,
    ) -> List[Dict[str, Any]]:
        cur_map, prev_map = {}, {}
        for row in data:
            period = row.get(period_key)
            val = float(row.get(measure) or 0.0)
            key = tuple((k, row[k]) for k in sorted(row) if k not in (measure, period_key))
            if period == current_period:
                cur_map[key] = cur_map.get(key, 0.0) + val
            elif period == previous_period:
                prev_map[key] = prev_map.get(key, 0.0) + val
        result = []
        for key in set(cur_map) | set(prev_map):
            c, p = cur_map.get(key, 0.0), prev_map.get(key, 0.0)
            growth = (c - p) / p if p else 0.0
            row = dict(key)
            row[f"{measure}_current"] = c
            row[f"{measure}_previous"] = p
            row[f"{measure}_growth"] = growth
            result.append(row)
        return result

    def _top_n(self, data: List[Dict[str, Any]], measure: str, dimension: str, n: int, ascending: bool = False) -> List[Dict[str, Any]]:
        agg = {}
        for row in data:
            d = row.get(dimension)
            if d is None:
                continue
            agg[d] = agg.get(d, 0.0) + float(row.get(measure) or 0.0)
        ranked = sorted(agg.items(), key=lambda x: x[1], reverse=not ascending)[:n]
        return [{"rank": i, dimension: d, measure: v} for i, (d, v) in enumerate(ranked, 1)]
