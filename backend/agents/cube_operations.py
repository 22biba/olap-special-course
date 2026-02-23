"""
Cube Operations Agent: slice (single dimension), dice (multiple), pivot (reorganize).
Supports HAVING (e.g. revenue > 500) for filter queries.
"""
from typing import Any, Dict, List, Optional

from database.connection import get_connection

from .base_agent import BaseAgent

DIM_MAP = {
    "date_year": "dd.year",
    "date_quarter": "dd.quarter",
    "date_month": "dd.month",
    "date_month_name": "dd.month_name",
    "month_name": "dd.month_name",
    "date_day": "dd.day",
    "region": "dg.region",
    "country": "dg.country",
    "category": "dp.category",
    "subcategory": "dp.subcategory",
    "segment": "dc.segment",
}

AVG_MEASURES = {"unit_price", "profit_margin"}
COUNT_MEASURES = {"transactions"}
AOV_MEASURES = {"aov"}


def _normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Expand date_quarter values like '2024-Q3' into year + quarter for dim_date."""
    out = {}
    for k, v in filters.items():
        if k == "date_quarter" and isinstance(v, list):
            years, quarters = set(), set()
            for p in v:
                if isinstance(p, str) and "-" in p:
                    y, q = p.split("-", 1)
                    try:
                        years.add(int(y))
                        quarters.add(q.strip())
                    except ValueError:
                        quarters.add(p)
                else:
                    quarters.add(p)
            if years:
                out["date_year"] = list(years)[0] if len(years) == 1 else list(years)
            if quarters:
                out["date_quarter"] = list(quarters) if len(quarters) > 1 else list(quarters)[0]
        else:
            out[k] = v
    return out


def _build_fact_query(
    filters: Dict[str, Any],
    measure: str,
    group_by_dims: List[str],
    having_min: Optional[float] = None,
) -> tuple:
    select_parts = []
    group_parts = []
    for d in group_by_dims:
        if d in DIM_MAP:
            e = DIM_MAP[d]
            if d == "date_quarter":
                select_parts.append(f"CAST(dd.year AS VARCHAR) || '-' || dd.quarter AS date_quarter")
                group_parts.extend(["dd.year", "dd.quarter"])
            else:
                select_parts.append(f"{e} AS {d}")
                group_parts.append(e)
    if measure in COUNT_MEASURES:
        measure_expr = "COUNT(fs.sales_id) AS transactions"
    elif measure in AOV_MEASURES:
        measure_expr = "SUM(fs.revenue) / COUNT(fs.sales_id) AS aov"
    else:
        agg_fn = "AVG" if measure in AVG_MEASURES else "SUM"
        measure_expr = f"{agg_fn}(fs.{measure}) AS {measure}"
    select_sql = ", ".join(select_parts + [measure_expr]) if select_parts else measure_expr
    filters = _normalize_filters(filters)
    where_parts, params = [], []
    for k, v in filters.items():
        if k not in DIM_MAP:
            continue
        e = DIM_MAP[k]
        if isinstance(v, list):
            where_parts.append(f"{e} IN (" + ", ".join("?" for _ in v) + ")")
            params.extend(v)
        else:
            where_parts.append(f"{e} = ?")
            params.append(v)
    where_sql = " AND ".join(where_parts)
    where_sql = ("WHERE " + where_sql) if where_sql else ""
    group_sql = "GROUP BY " + ", ".join(group_parts) if group_parts else ""
    having_sql = ""
    if having_min is not None and group_parts and measure not in (COUNT_MEASURES | AOV_MEASURES):
        h_agg = "AVG" if measure in AVG_MEASURES else "SUM"
        having_sql = f" HAVING {h_agg}(fs.{measure}) > {float(having_min)}"
    sql = f"""
        SELECT {select_sql}
        FROM fact_sales fs
        JOIN dim_date dd ON fs.date_id = dd.date_id
        JOIN dim_geography dg ON fs.geography_id = dg.geography_id
        JOIN dim_product dp ON fs.product_id = dp.product_id
        JOIN dim_customer dc ON fs.customer_id = dc.customer_id
        {where_sql}
        {group_sql}
        {having_sql}
    """
    return sql, params


class CubeOperationsAgent(BaseAgent):
    def run(self, context: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        operation = params.get("operation", "dice")
        filters = params.get("filters", {})
        measure = params.get("measure", "revenue")
        row_dim = params.get("row_dim")
        col_dim = params.get("col_dim")

        if operation not in ("slice", "dice", "pivot"):
            raise ValueError("operation must be slice, dice, or pivot")

        if operation in ("slice", "dice"):
            group_dims = params.get("group_by") if "group_by" in params else (list(filters.keys()) or ["region"])
            having_min = params.get("having_min")
            sql, par = _build_fact_query(filters, measure, group_dims, having_min=having_min)
            con = get_connection()
            rows = con.execute(sql, par).fetchall()
            cols = group_dims + [measure]
            return {"type": operation, "data": [dict(zip(cols, r)) for r in rows]}

        if not row_dim or not col_dim:
            raise ValueError("row_dim and col_dim required for pivot")
        group_dims = [row_dim, col_dim]
        sql, par = _build_fact_query(filters, measure, group_dims)
        con = get_connection()
        rows = con.execute(sql, par).fetchall()
        row_vals = sorted({r[0] for r in rows})
        col_vals = sorted({r[1] for r in rows})
        matrix = {rv: {cv: 0.0 for cv in col_vals} for rv in row_vals}
        for rv, cv, val in rows:
            matrix[rv][cv] = float(val or 0.0)
        table = [{"row": rv, **{str(cv): matrix[rv][cv] for cv in col_vals}} for rv in row_vals]
        return {"type": "pivot", "row_dim": row_dim, "col_dim": col_dim, "rows": row_vals, "columns": col_vals, "table": table, "measure": measure}
