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

        if task_type == "compound":
            return self._flow_compound(context, intent, conversation_history)
        if task_type == "aggregate":
            return self._flow_aggregate(context, measure, intent.get("filters", {}), intent)
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
            dim = (dimensions[0] if dimensions else "region")
            if granularity == "year" or (isinstance(prev_period, (int, str)) and str(prev_period).isdigit() and len(str(prev_period)) == 4):
                return self._flow_compare_years(context, measure, dim, int(cur_period) if str(cur_period).isdigit() else 2024, int(prev_period) if str(prev_period).isdigit() else 2023)
            return self._flow_compare(context, measure, dim, cur_period, prev_period)

        # slice (single filter) or dice (multiple filters)
        return self._flow_slice_dice(context, measure, dimensions, filters, intent)

    def _flow_compound(
        self, context: Dict[str, Any], intent: Dict[str, Any], conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """Run two steps (e.g. 'revenue by year' then 'drill into 2024 by quarter') and return combined result."""
        steps = intent.get("steps", [])
        if len(steps) < 2:
            # Fallback: run first step only
            step_context = {**context, "intent": steps[0]} if steps else context
            return self.handle_query(steps[0] if steps else intent, conversation_history)

        result0 = self.handle_query(steps[0], conversation_history)
        result1 = self.handle_query(steps[1], conversation_history)

        s0, s1 = steps[0], steps[1]
        if s0.get("dimensions") == ["category"] and s1.get("dimensions") == ["subcategory"]:
            step0_query = "Category totals"
            step1_query = f"Drill into {s1.get('filters', {}).get('category', 'category')} by subcategory"
        else:
            step0_query = "Revenue by year"
            step1_query = "Drill into year by quarter"

        out: Dict[str, Any] = {
            "compound": True,
            "step0": {"query": step0_query, "result": result0},
            "step1": {"query": step1_query, "result": result1},
            # Primary result = step1 so existing UI shows the drill
            "cube_result": result1.get("cube_result"),
            "cube": result1.get("cube_result"),
            "kpi_result": result1.get("kpi_result"),
            "kpi_data": result1.get("kpi_data"),
            "best_performer": result1.get("best_performer"),
            "drill": result1.get("drill"),
            "report": result1.get("report"),
        }
        return out

    def _flow_aggregate(
        self, context: Dict[str, Any], measure: str, filters: Dict[str, Any], intent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Total across all - no dimension grouping (2022, 2023, 2024 combined). Use all 4 agents."""
        agg = intent.get("agg", "sum")
        cube_result = self.cube_ops.run(
            context,
            {
                "operation": "dice",
                "filters": filters,
                "measure": measure,
                "group_by": [],
                "agg": agg,
            },
        )
        data = cube_result.get("data", [])
        out: Dict[str, Any] = {"cube_result": cube_result}

        # KPI: get breakdown by year and compute YoY growth so KPI agent contributes
        by_year = self.cube_ops.run(
            context,
            {"operation": "dice", "filters": filters, "measure": measure, "group_by": ["date_year"]},
        )
        year_data = by_year.get("data", [])
        if len(year_data) >= 2:
            years = sorted({int(r.get("date_year", 0)) for r in year_data if r.get("date_year") is not None})
            if len(years) >= 2:
                cy, py = years[-1], years[-2]
                kpi_result = self.kpi_calc.run(
                    context,
                    {
                        "kpi_type": "yoy_growth",
                        "data": year_data,
                        "measure": measure,
                        "period_key": "date_year",
                        "current_period": cy,
                        "previous_period": py,
                        "dimension": "date_year",
                    },
                )
                out["kpi_result"] = kpi_result
                out["kpi_data"] = kpi_result.get("data", [])
                kpi_data = out["kpi_data"]
                out["best_performer"] = max(kpi_data, key=lambda r: r.get(f"{measure}_growth", 0.0)) if kpi_data else None

        # Dimension Navigator: suggest drill from year to quarter
        try:
            out["drill"] = self.dimension_navigator.run(
                context,
                {"action": "drill_down", "current_level": "year", "filters": {}},
            )
        except Exception:
            pass

        report = self.report_gen.run(
            context,
            {"data": data, "measure": cube_result.get("measure", measure)},
        )
        out["report"] = report
        return out

    def _flow_compare_years(
        self,
        context: Dict[str, Any],
        measure: str,
        dimension: str,
        current_year: int,
        previous_year: int,
    ) -> Dict[str, Any]:
        """Compare two full years (e.g. 2023 vs 2024). Use all 4 agents."""
        dim = _dim_to_cube_key(dimension)
        cube_result = self.cube_ops.run(
            context,
            {
                "operation": "dice",
                "filters": {"date_year": [previous_year, current_year]},
                "measure": measure,
                "group_by": ["date_year", dim],
            },
        )
        data = cube_result.get("data", [])
        kpi_result = self.kpi_calc.run(
            context,
            {
                "kpi_type": "yoy_growth",
                "data": data,
                "measure": measure,
                "period_key": "date_year",
                "current_period": current_year,
                "previous_period": previous_year,
                "dimension": dim,
            },
        )
        kpi_data = kpi_result.get("data", [])
        best = max(kpi_data, key=lambda r: r.get(f"{measure}_growth", 0.0)) if kpi_data else None
        report = self.report_gen.run(context, {"data": kpi_data, "measure": f"{measure}_growth"})

        drill = None
        try:
            drill = self.dimension_navigator.run(
                context,
                {"action": "drill_down", "current_level": "year", "filters": {"year": current_year}},
            )
        except Exception:
            pass
        return {
            "cube_result": cube_result,
            "kpi_result": kpi_result,
            "kpi_data": kpi_data,
            "best_performer": best,
            "drill": drill,
            "report": report,
        }

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
        """Top N by dimension. Use all 4 agents."""
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

        drill = None
        try:
            drill = self.dimension_navigator.run(
                context,
                {"action": "drill_down", "current_level": "year", "filters": {}},
            )
        except Exception:
            pass

        report = self.report_gen.run(
            context,
            {"data": top_data, "measure": measure},
        )

        return {
            "cube_result": cube_result,
            "kpi_result": kpi_result,
            "kpi_data": top_data,
            "drill": drill,
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
                "having_min": intent.get("having_min"),
            },
        )
        data = cube_result.get("data", [])

        # "What percentage of revenue from each region?" -> add percentage column
        if intent.get("compute_percentage") and data and measure in (data[0] or {}):
            total = sum(float(r.get(measure) or 0) for r in data)
            pct_key = f"{measure}_pct"
            if total:
                for r in data:
                    r[pct_key] = round((float(r.get(measure) or 0) / total) * 100.0, 2)
            else:
                for r in data:
                    r[pct_key] = 0.0
            cube_result = dict(cube_result)
            cube_result["data"] = data
            cube_result["operation"] = cube_result.get("operation") or "slice"

        out: Dict[str, Any] = {"cube_result": cube_result, "cube": cube_result}

        # KPI + Dimension Navigator so all 4 agents contribute for every slice/dice.
        if row_dim == "date_year" and data:
            years = sorted({int(r.get("date_year", 0)) for r in data if r.get("date_year") is not None})
            if len(years) >= 2:
                current_year, previous_year = years[-1], years[-2]
                kpi_result = self.kpi_calc.run(
                    context,
                    {
                        "kpi_type": "yoy_growth",
                        "data": data,
                        "measure": measure,
                        "period_key": "date_year",
                        "current_period": current_year,
                        "previous_period": previous_year,
                        "dimension": "date_year",
                    },
                )
                out["kpi_result"] = kpi_result
                out["kpi_data"] = kpi_result.get("data", [])
                best = max(
                    out["kpi_data"],
                    key=lambda r: r.get(f"{measure}_growth", 0.0),
                ) if out["kpi_data"] else None
                out["best_performer"] = best
        else:
            # Non–date_year slice/dice: KPI = top_n on this result so KPI agent is used
            if data and row_dim in (data[0] if data else {}):
                kpi_result = self.kpi_calc.run(
                    context,
                    {"kpi_type": "top_n", "data": data, "measure": measure, "dimension": row_dim, "n": 5},
                )
                out["kpi_result"] = kpi_result
                out["kpi_data"] = kpi_result.get("data", [])

        try:
            out["drill"] = self.dimension_navigator.run(
                context,
                {"action": "drill_down", "current_level": "year", "filters": {}},
            )
        except Exception:
            pass

        report = self.report_gen.run(context, {"data": data, "measure": measure})
        out["report"] = report
        return out

    def _flow_pivot(self, context: Dict[str, Any], measure: str, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Pivot table. Use all 4 agents."""
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
        out: Dict[str, Any] = {"cube_result": cube_result, "pivot": cube_result}

        # KPI: top_n by row (aggregate across columns for each row)
        if table:
            row_agg = []
            for r in table:
                row_val = r.get("row")
                total = sum(v for k, v in r.items() if k != "row" and isinstance(v, (int, float)))
                row_agg.append({row_dim: row_val, measure: total})
            kpi_result = self.kpi_calc.run(
                context,
                {"kpi_type": "top_n", "data": row_agg, "measure": measure, "dimension": row_dim, "n": 5},
            )
            out["kpi_result"] = kpi_result
            out["kpi_data"] = kpi_result.get("data", [])

        try:
            out["drill"] = self.dimension_navigator.run(
                context,
                {"action": "drill_down", "current_level": "year", "filters": {}},
            )
        except Exception:
            pass

        report = self.report_gen.run(context, {"data": table, "measure": measure})
        out["report"] = report
        return out

    def _flow_drill_down(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Drill into a time level (e.g. 2024 by quarter). Use all 4 agents."""
        intent = context.get("intent", {})
        filters = dict(intent.get("filters") or {})
        if filters.get("date_year") is not None and filters.get("year") is None:
            filters["year"] = filters["date_year"]
        current_level = intent.get("current_level", "year")
        measure = intent.get("measure", "revenue")

        drill = self.dimension_navigator.run(
            context,
            {"action": "drill_down", "current_level": current_level, "filters": filters},
        )

        # Cube: get measure at the drilled level (e.g. revenue by quarter for year 2024)
        cube_result = None
        kpi_result = None
        kpi_data = []
        year = filters.get("year") or filters.get("date_year")
        if current_level == "year" and year is not None:
            cube_result = self.cube_ops.run(
                context,
                {
                    "operation": "dice",
                    "filters": {"date_year": year},
                    "measure": measure,
                    "group_by": ["date_quarter"],
                },
            )
            data = cube_result.get("data", [])
            if data:
                kpi_result = self.kpi_calc.run(
                    context,
                    {"kpi_type": "top_n", "data": data, "measure": measure, "dimension": "date_quarter", "n": 4},
                )
                kpi_data = kpi_result.get("data", [])
        elif current_level == "quarter":
            y, q = filters.get("year"), filters.get("quarter")
            if y is not None and q is not None:
                cube_result = self.cube_ops.run(
                    context,
                    {
                        "operation": "dice",
                        "filters": {"date_year": y, "date_quarter": q},
                        "measure": measure,
                        "group_by": ["date_month"],
                    },
                )
                data = cube_result.get("data", [])
                if data:
                    kpi_result = self.kpi_calc.run(
                        context,
                        {"kpi_type": "top_n", "data": data, "measure": measure, "dimension": "date_month", "n": 12},
                    )
                    kpi_data = kpi_result.get("data", [])

        report_data = kpi_data if kpi_data else [{"level": m.get("level"), "value": m.get("value")} for m in drill.get("members", [])]
        report = self.report_gen.run(context, {"data": report_data, "measure": measure if kpi_data else "value"})

        return {
            "cube_result": cube_result,
            "kpi_result": kpi_result,
            "kpi_data": kpi_data,
            "drill": drill,
            "report": report,
        }

    def _flow_roll_up(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Roll up time hierarchy. Use all 4 agents."""
        intent = context.get("intent", {})
        filters = intent.get("filters", {})
        current_level = intent.get("current_level", "month")
        measure = intent.get("measure", "revenue")

        roll = self.dimension_navigator.run(
            context,
            {"action": "roll_up", "current_level": current_level, "filters": filters},
        )

        # Cube: aggregate at rolled-up level (e.g. by quarter if rolling up from month)
        group_dim = "date_quarter" if current_level == "month" else "date_year" if current_level == "quarter" else None
        cube_result = None
        kpi_result = None
        kpi_data = []
        cube_filters = {}
        if filters.get("year") is not None:
            cube_filters["date_year"] = filters["year"]
        if filters.get("quarter") is not None:
            cube_filters["date_quarter"] = filters["quarter"]
        if filters.get("date_year") is not None:
            cube_filters["date_year"] = filters["date_year"]
        if group_dim:
            cube_result = self.cube_ops.run(
                context,
                {
                    "operation": "dice",
                    "filters": cube_filters,
                    "measure": measure,
                    "group_by": [group_dim],
                },
            )
            data = cube_result.get("data", [])
            if data:
                kpi_result = self.kpi_calc.run(
                    context,
                    {"kpi_type": "top_n", "data": data, "measure": measure, "dimension": group_dim, "n": 10},
                )
                kpi_data = kpi_result.get("data", [])

        report_data = kpi_data if kpi_data else [{"level": m.get("level"), "value": m.get("value")} for m in roll.get("members", [])]
        report = self.report_gen.run(context, {"data": report_data, "measure": measure if kpi_data else "value"})

        return {
            "cube_result": cube_result,
            "kpi_result": kpi_result,
            "kpi_data": kpi_data,
            "roll_up": roll,
            "report": report,
        }
