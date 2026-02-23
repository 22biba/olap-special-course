"""
Report Generator Agent: formatted tables, totals, conditional formatting hints,
executive summary, and follow-up suggestions.
"""
from typing import Any, Dict, List, Optional

from .base_agent import BaseAgent


class ReportGeneratorAgent(BaseAgent):
    def run(self, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        data: List[Dict[str, Any]] = params.get("data", [])
        measure = params.get("measure", "revenue")
        intent = context.get("intent", {})
        task_type = intent.get("task_type", "compare")
        dimensions = intent.get("dimensions", ["region"])
        dim = dimensions[0] if dimensions else "region"

        total = self._compute_total(data, measure)
        growth_cols = [k for k in (data[0].keys() if data else []) if k.endswith("_growth") or k.endswith("_margin") or k.endswith("_change")]
        formatting = {"rules": [{"columns": growth_cols, "positive": "green", "negative": "red"}]} if growth_cols else {}
        summary = self._summary(data, measure, intent)
        follow_up_suggestions = self._follow_up_suggestions(data, measure, task_type, dim, intent)
        return {
            "table": data,
            "totals": {measure: total},
            "formatting": formatting,
            "summary": summary,
            "follow_up_suggestions": follow_up_suggestions,
        }

    def _follow_up_suggestions(
        self,
        data: List[Dict[str, Any]],
        measure: str,
        task_type: str,
        dim: str,
        intent: Dict[str, Any],
    ) -> List[str]:
        """Generate contextual follow-up question suggestions."""
        suggestions = []
        dim_map = {"region": "region", "country": "country", "category": "category", "segment": "segment", "subcategory": "subcategory"}
        other_dims = [d for d in ["region", "country", "category", "segment", "subcategory"] if d != dim]

        if task_type == "compare":
            suggestions.extend([
                f"Compare Q3 vs Q4 2024 by {other_dims[0]}" if other_dims else "Compare by category",
                "Compare Q1 vs Q2 2024 by region",
                f"Top 5 {dim}s by {measure}",
                f"Drill into best performer",
            ])
        elif task_type == "top_n":
            suggestions.extend([
                f"Compare Q3 vs Q4 2024 by {dim}",
                f"Show {measure} by {other_dims[0]}" if other_dims else "Show revenue by region",
                "Show profit margin by region",
            ])
        else:
            suggestions.extend([
                "Compare Q3 vs Q4 2024 by region",
                "Top 5 regions by revenue",
                "Show profit by category",
                "Drill into best performer",
            ])
        return suggestions[:5]

    def _compute_total(self, data: List[Dict[str, Any]], measure: str) -> float:
        """Sum numeric values; for pivot tables, sum all numeric columns. Skips non-numeric values."""
        if not data:
            return 0.0
        first = data[0]
        if measure in first:
            total = 0.0
            for row in data:
                val = row.get(measure)
                try:
                    total += float(val) if val is not None else 0.0
                except (ValueError, TypeError):
                    pass
            return total
        return sum(
            float(v) for row in data for k, v in row.items()
            if k != "row" and isinstance(v, (int, float))
        )

    def _summary(self, data: List[Dict[str, Any]], measure: str, intent: Optional[Dict[str, Any]] = None) -> str:
        intent = intent or {}
        if not data:
            return "No data for the selected filters."
        pct_col = next((k for k in (data[0].keys() if data else []) if str(k).endswith("_pct")), None)
        if pct_col:
            try:
                top = max(data, key=lambda r: float(r.get(pct_col) or 0.0))
                dims = [k for k in top if k != measure and k != pct_col and not str(k).endswith("_growth")]
                desc = ", ".join(f"{k}={top[k]}" for k in dims[:3] if top.get(k) is not None)
                pct_val = float(top.get(pct_col) or 0)
                return f"Largest share: {pct_val:.1f}% for {desc}." if desc else f"Largest share: {pct_val:.1f}%."
            except (ValueError, TypeError):
                pass
        worst = intent.get("worst", False)
        try:
            top = min(data, key=lambda r: float(r.get(measure) or 0.0) if measure in r else 0.0) if worst else max(data, key=lambda r: float(r.get(measure) or 0.0) if measure in r else 0.0)
        except (ValueError, TypeError):
            return f"Report with {len(data)} rows."
        dims = [k for k in top if k != measure and not str(k).endswith("_growth") and not str(k).endswith("_pct") and k != "rank"]
        desc = ", ".join(f"{k}={top[k]}" for k in dims[:3] if top.get(k) is not None)
        val = float(top.get(measure) or 0)
        prefix = "Lowest" if worst else "Highest"
        return f"{prefix} {measure}: {val:.2f} for {desc}." if desc else f"{prefix} {measure}: {val:.2f}."
