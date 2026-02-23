"""
Data access layer: DuckDB connection and star schema bootstrap.
"""
import os
from pathlib import Path
from typing import Optional

import duckdb

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = _PROJECT_ROOT / "data" / "bi_star.duckdb"
SCHEMA_SQL_PATH = Path(__file__).resolve().with_name("schema.sql")
CSV_PATH = _PROJECT_ROOT / "data" / "global_retail_sales.csv"

_connection: Optional[duckdb.DuckDBPyConnection] = None


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a singleton DuckDB connection and ensure the star schema exists."""
    global _connection
    if _connection is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _connection = duckdb.connect(str(DB_PATH))
        _ensure_schema(_connection)
        _seed_if_empty(_connection)
    return _connection


def _ensure_schema(con: duckdb.DuckDBPyConnection) -> None:
    """Create star schema tables if they do not exist."""
    if not SCHEMA_SQL_PATH.exists():
        return
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "fact_sales" in tables:
        return
    con.execute(SCHEMA_SQL_PATH.read_text(encoding="utf-8"))


def _seed_if_empty(con: duckdb.DuckDBPyConnection) -> None:
    """If fact_sales has no rows, load data from global_retail_sales.csv."""
    try:
        n = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
        if n > 0:
            return
    except Exception:
        return
    if not CSV_PATH.exists():
        return
    csv_path_str = CSV_PATH.as_posix().replace("\\", "/")
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staging AS
        SELECT * FROM read_csv_auto('{csv_path_str}', header=TRUE)
    """)
    con.execute("DELETE FROM fact_sales")
    con.execute("DELETE FROM dim_date")
    con.execute("""
        INSERT INTO dim_date (date_id, date_actual, year, quarter, month, day)
        SELECT
            ROW_NUMBER() OVER () AS date_id,
            CAST(date AS DATE) AS date_actual,
            EXTRACT(year FROM CAST(date AS DATE))::INTEGER AS year,
            'Q' || CAST(CEIL(EXTRACT(month FROM CAST(date AS DATE)) / 3.0) AS INTEGER) AS quarter,
            EXTRACT(month FROM CAST(date AS DATE))::INTEGER AS month,
            EXTRACT(day FROM CAST(date AS DATE))::INTEGER AS day
        FROM (SELECT DISTINCT date FROM staging) t
    """)
    con.execute("DELETE FROM dim_geography")
    con.execute("""
        INSERT INTO dim_geography (geography_id, region, country)
        SELECT ROW_NUMBER() OVER () AS geography_id, region, country
        FROM (SELECT DISTINCT region, country FROM staging) t
    """)
    con.execute("DELETE FROM dim_product")
    con.execute("""
        INSERT INTO dim_product (product_id, category, subcategory)
        SELECT ROW_NUMBER() OVER () AS product_id, category, subcategory
        FROM (SELECT DISTINCT category, subcategory FROM staging) t
    """)
    con.execute("DELETE FROM dim_customer")
    con.execute("""
        INSERT INTO dim_customer (customer_id, segment)
        SELECT ROW_NUMBER() OVER () AS customer_id, segment
        FROM (SELECT DISTINCT segment FROM staging) t
    """)
    con.execute("""
        INSERT INTO fact_sales (sales_id, date_id, geography_id, product_id, customer_id, quantity, revenue, cost, profit)
        SELECT
            ROW_NUMBER() OVER () AS sales_id,
            d.date_id, g.geography_id, p.product_id, c.customer_id,
            CAST(s.quantity AS DOUBLE), CAST(s.revenue AS DOUBLE), CAST(s.cost AS DOUBLE), CAST(s.profit AS DOUBLE)
        FROM staging s
        JOIN dim_date d ON d.date_actual = CAST(s.date AS DATE)
        JOIN dim_geography g ON g.region = s.region AND g.country = s.country
        JOIN dim_product p ON p.category = s.category AND p.subcategory = s.subcategory
        JOIN dim_customer c ON c.segment = s.segment
    """)
