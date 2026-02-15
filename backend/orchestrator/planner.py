"""
Planner/Orchestrator: query understanding, agent selection, coordination, context.
Selects appropriate agents, passes context, maintains conversation history, aggregates results.
"""
from typing import Any, Dict, List, Optional

from agents.cube_operations import CubeOperationsAgent
from agents.dimension_navigator import DimensionNavigatorAgent
from agents.kpi_calculator import KPICalculatorAgent
from agents.report_generator import ReportGeneratorAgent


def _dim_to_cube_key(dim: str) -> str:
    if dim in ("region", "country", "category", "segment"):
        return dim
    return dim


class Planner:
    def __init__(self) -> None:
        self.dimension_navigator = DimensionNavigatorAgent()
        self.cube_ops = CubeOperationsAgent()
        self.kpi_calc = KPICalculatorAgent()
        self.report_gen = ReportGeneratorAgent()

    def handle_query(self, intent: Dict[str, Any], conversation_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        task_type = intent.get("task_type", "compare")
        measure = intent.get("measure", "revenue")
        dimensions = intent.get("dimensions", ["region"])
        time_scope = intent.get("time_scope", {})
        granularity = time_scope.get("granularity", "quarter")
        periods = time_scope.get("periods", [])
        filters = intent.get("filters", {})

        context: Dict[str, Any] = {
            "intent": intent,
            "conversation_history": conversation_history or [],
        }

        if task_type == "top_n":
            return self._flow_top_n(context, measure, dimensions, filters, intent.get("n", 5))
        if task_type == "drill_down":
            return self._flow_drill_down(context)
        if task_type == "roll_up":
            return self._flow_roll_up(context)
        if task_type == "pivot":
            return self._flow_pivot(context, measure, intent)
        if task_type == "compare" and len(periods) >= 2:
            prev_period, cur_period = periods[0], periods[1]
            return self._flow_compare(context, measure, dimensions[0], cur_period, prev_period)

        # slice (single filter) or dice (multiple filters)
        return self._flow_slice_dice(context, measure, dimensions, filters, intent)

    def _flow_compare(
        self,
        context: Dict[str, Any],
        measure: str,
        dimension: str,
        current_period: str,
        previous_period: str,
    ) -> Dict[str, Any]:
        period_key = "date_quarter"
        cube_result = self.cube_ops.run(
            context,
            {
                "operation": "dice",
                "filters": {"date_quarter": [previous_period, current_period]},
                "measure": measure,
                "group_by": [period_key, _dim_to_cube_key(dimension)],
            },
        )
        data = cube_result.get("data", [])

        kpi_result = self.kpi_calc.run(
            context,
            {
                "kpi_type": "yoy_growth",
                "data": data,
                "measure": measure,
                "period_key": period_key,
                "current_period": current_period,
                "previous_period": previous_period,
                "dimension": _dim_to_cube_key(dimension),
            },
        )
        kpi_data = kpi_result.get("data", [])
        best = max(kpi_data, key=lambda r: r.get(f"{measure}_growth", 0.0)) if kpi_data else None

        drill = None
        if best:
            try:
                year = int(current_period.split("-")[0])
                drill = self.dimension_navigator.run(
                    context,
                    {"action": "drill_down", "current_level": "quarter", "filters": {"year": year}},
                )
            except Exception:
                pass

        report = self.report_gen.run(
            context,
            {"data": kpi_data, "measure": f"{measure}_growth"},
        )

        return {
            "cube_result": {"type": "dice", "data": data, "operation": "Dice"},
            "kpi_result": {"kpi_type": "yoy_growth", "data": kpi_data},
            "kpi_data": kpi_data,
            "best_performer": best,
            "drill": drill,
            "report": report,
        }

    def _flow_top_n(
        self,
        context: Dict[str, Any],
        measure: str,
        dimensions: List[str],
        filters: Dict[str, Any],
        n: int,
    ) -> Dict[str, Any]:
        dim = _dim_to_cube_key(dimensions[0]) if dimensions else "region"
        cube_result = self.cube_ops.run(
            context,
            {
                "operation": "slice" if len(filters) <= 1 else "dice",
                "filters": filters,
                "measure": measure,
                "group_by": [dim],
            },
        )
        data = cube_result.get("data", [])

        kpi_result = self.kpi_calc.run(
            context,
            {"kpi_type": "top_n", "data": data, "measure": measure, "dimension": dim, "n": n},
        )
        top_data = kpi_result.get("data", [])

        report = self.report_gen.run(
            context,
            {"data": top_data, "measure": measure},
        )

        return {
            "cube_result": cube_result,
            "kpi_result": kpi_result,
            "kpi_data": top_data,
            "report": report,
        }

    def _flow_slice_dice(
        self,
        context: Dict[str, Any],
        measure: str,
        dimensions: List[str],
        filters: Dict[str, Any],
        intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        row_dim = _dim_to_cube_key(dimensions[0]) if dimensions else "region"
        op = "slice" if len(filters) <= 1 else "dice"
        cube_result = self.cube_ops.run(
            context,
            {
                "operation": op,
                "filters": filters,
                "measure": measure,
                "group_by": [row_dim],
            },
        )
        data = cube_result.get("data", [])
        report = self.report_gen.run(context, {"data": data, "measure": measure})
        return {"cube_result": cube_result, "cube": cube_result, "report": report}

    def _flow_pivot(self, context: Dict[str, Any], measure: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        row_dim = intent.get("row_dim") or intent.get("dimensions", ["region"])[0]
        col_dim = intent.get("col_dim") or "date_quarter"
        row_dim = _dim_to_cube_key(row_dim)
        col_dim = _dim_to_cube_key(col_dim) if col_dim in ("region", "country", "category", "segment") else "date_quarter"

        cube_result = self.cube_ops.run(
            context,
            {
                "operation": "pivot",
                "filters": intent.get("filters", {}),
                "measure": measure,
                "row_dim": row_dim,
                "col_dim": col_dim,
            },
        )
        table = cube_result.get("table", [])
        report = self.report_gen.run(context, {"data": table, "measure": measure})
        return {"cube_result": cube_result, "pivot": cube_result, "report": report}

    def _flow_drill_down(self, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get("intent", {})
        filters = intent.get("filters", {})
        current_level = intent.get("current_level", "year")

        drill = self.dimension_navigator.run(
            context,
            {"action": "drill_down", "current_level": current_level, "filters": filters},
        )
        report = self.report_gen.run(
            context,
            {"data": [{"level": m.get("level"), "value": m.get("value")} for m in drill.get("members", [])], "measure": "value"},
        )
        return {"drill": drill, "report": report}

    def _flow_roll_up(self, context: Dict[str, Any]) -> Dict[str, Any]:
        intent = context.get("intent", {})
        filters = intent.get("filters", {})
        current_level = intent.get("current_level", "month")

        roll = self.dimension_navigator.run(
            context,
            {"action": "roll_up", "current_level": current_level, "filters": filters},
        )
        report = self.report_gen.run(
            context,
            {"data": [{"level": m.get("level"), "value": m.get("value")} for m in roll.get("members", [])], "measure": "value"},
        )
        return {"roll_up": roll, "report": report}
