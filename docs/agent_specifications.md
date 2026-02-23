# Agent Specifications – Purpose, I/O, Prompts

Four agents collaborate in the OLAP BI Platform. Each receives context (intent, history) and params; returns structured output used by the Planner.

---

## 1. Cube Operations Agent

### Purpose

Execute OLAP operations on the star schema: **slice** (single dimension), **dice** (filter + group by multiple dimensions), **pivot** (row × column matrix). Supports measures: revenue, profit, quantity, unit_price, profit_margin, transactions, aov.

### Input

| Param        | Type   | Description                                      |
|--------------|--------|--------------------------------------------------|
| `operation`  | string | `"slice"` \| `"dice"` \| `"pivot"`             |
| `filters`    | dict   | `{region, date_year, date_quarter, category, segment}` |
| `measure`    | string | `"revenue"` \| `"profit"` \| `"profit_margin"` \| … |
| `group_by`   | list   | Dimensions to aggregate by                       |
| `row_dim`    | string | (pivot) Row dimension                            |
| `col_dim`    | string | (pivot) Column dimension                         |
| `having_min` | float  | HAVING measure > value                           |

### Output

| Key    | Type | Description                         |
|--------|------|-------------------------------------|
| `type` | str  | `"slice"` \| `"dice"` \| `"pivot"` |
| `data` | list | Rows `[{dim1, dim2, …, measure}]`   |
| (pivot)| `table`, `rows`, `columns`, `row_dim`, `col_dim`, `measure` |

### Prompt / Logic

- Map dimensions to schema: `region` → `dg.region`, `date_quarter` → `dd.year || '-' || dd.quarter`.
- For `transactions`: `COUNT(sales_id)`. For `aov`: `SUM(revenue)/COUNT(sales_id)`.
- Apply filters in WHERE, GROUP BY, optional HAVING.

---

## 2. KPI Calculator Agent

### Purpose

Compute KPIs on cube output: **yoy_growth** (year-over-year), **mom_change** (month-over-month), **profit_margin**, **top_n** (rank by measure), **bottom_n** (worst performers).

### Input

| Param             | Type  | Description                              |
|-------------------|-------|------------------------------------------|
| `kpi_type`        | str   | `"yoy_growth"` \| `"mom_change"` \| `"profit_margin"` \| `"top_n"` \| `"bottom_n"` |
| `data`            | list  | Cube output rows                         |
| `measure`         | str   | e.g. `"revenue"`, `"profit"`             |
| `dimension`       | str   | Grouping key (region, category, …)       |
| `period_key`      | str   | e.g. `"date_year"`, `"date_quarter"`      |
| `current_period`  | any   | Current period value                     |
| `previous_period` | any   | Previous period value                    |
| `n`               | int   | For top_n/bottom_n                       |

### Output

| Key        | Type | Description                                      |
|------------|------|--------------------------------------------------|
| `kpi_type` | str  | Echo of input kpi_type                           |
| `data`     | list | Rows with `{measure}_current`, `{measure}_previous`, `{measure}_growth` or ranked rows |

### Prompt / Logic

- **yoy_growth / mom_change:** Aggregate by dimension per period; compute `growth = (current - previous) / previous`.
- **profit_margin:** `profit / revenue` per row.
- **top_n / bottom_n:** Aggregate by dimension, sort by measure desc/asc, return top n.

---

## 3. Dimension Navigator Agent

### Purpose

Provide **drill-down** (Year → Quarter → Month → Day) and **roll-up** on the time hierarchy. Returns next-level members for navigation.

### Input

| Param           | Type  | Description                        |
|-----------------|-------|------------------------------------|
| `action`        | str   | `"drill_down"` \| `"roll_up"`     |
| `current_level` | str   | `"year"` \| `"quarter"` \| `"month"` \| `"day"` |
| `filters`       | dict  | `{year, quarter, month}` to scope  |

### Output

| Key            | Type | Description                    |
|----------------|------|--------------------------------|
| `current_level`| str  | Current hierarchy level        |
| `next_level`   | str  | Next level (or null if roll-up at top) |
| `members`      | list | `[{level, value}]` e.g. Q1, Q2, Q3, Q4 |

### Prompt / Logic

- `HIERARCHY = ["year", "quarter", "month", "day"]`.
- Drill: next = hierarchy[current+1]; query `SELECT DISTINCT {col} FROM dim_date WHERE …`.
- Roll: next = hierarchy[current-1]; same pattern.

---

## 4. Report Generator Agent

### Purpose

Produce formatted **report** from KPI or cube data: executive summary, totals, conditional formatting (green/red for growth), follow-up suggestions. Adds `filters_applied` when filters exist.

### Input

| Param   | Type | Description                  |
|---------|------|------------------------------|
| `data`  | list | KPI or cube rows             |
| `measure` | str | Primary measure              |
| Context | `intent` | task_type, dimensions, filters |

### Output

| Key                 | Type  | Description                          |
|---------------------|-------|--------------------------------------|
| `table`             | list  | Data rows                            |
| `totals`            | dict  | `{measure: sum}`                     |
| `formatting`        | dict  | `{rules: [{columns, positive, negative}]}` |
| `summary`           | str   | Executive summary sentence            |
| `follow_up_suggestions` | list | 5 suggested next questions        |
| `filters_applied`   | str   | e.g. `"2024, Q4, segment=Corporate"` |

### Prompt / Logic

- **Summary:** For pct columns → "Largest share: X% for …". For worst → min by measure. Else max by measure. Append "Filtered to …" when filters.
- **Follow-ups:** Contextual by task_type (compare → "Compare Q3 vs Q4 by X", top_n → "Show by Y", etc.).
- **Formatting:** Growth/margin columns → positive green, negative red.

---

## Orchestration (Planner)

The Planner selects flows based on `task_type`:

| task_type   | Flow           | Agents used                                   |
|-------------|----------------|-----------------------------------------------|
| `aggregate` | _flow_aggregate| Cube, KPI (yoy if by year), Dimension Nav, Report |
| `compare`   | _flow_compare  | Cube, KPI (yoy_growth), Dimension Nav, Report |
| `top_n`     | _flow_top_n    | Cube, KPI (top_n or bottom_n), Dimension Nav, Report |
| `slice`/`dice` | _flow_slice_dice | Cube, KPI (top_n or yoy), Dimension Nav, Report |
| `drill_down`| _flow_drill_down | Cube (by quarter/month), Dimension Nav, KPI, Report |
| `compound`  | _flow_compound | Runs two sub-queries, merges results          |

Context flows from intent; each agent receives only what it needs via params.
