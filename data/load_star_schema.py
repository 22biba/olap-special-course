"""
Load global_retail_sales.csv into DuckDB star schema.
Expects CSV columns: date, region, country, category, subcategory, segment, quantity, unit_price, revenue, cost, profit, profit_margin.
Run from project root: python -m data.load_star_schema
Or from backend (with PYTHONPATH including project root): python -m data.load_star_schema
"""
from pathlib import Path

# Project root: this file is in project_root/data/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = PROJECT_ROOT / "data" / "global_retail_sales.csv"
DB_PATH = PROJECT_ROOT / "data" / "bi_star.duckdb"
SCHEMA_SQL = PROJECT_ROOT / "backend" / "database" / "schema.sql"


def _migrate_schema(con):
    """Add new columns to existing schema for backward compatibility."""
    try:
        con.execute("ALTER TABLE dim_date ADD COLUMN month_name VARCHAR(20)")
    except Exception:
        pass
    try:
        con.execute("ALTER TABLE fact_sales ADD COLUMN unit_price DOUBLE")
    except Exception:
        pass
    try:
        con.execute("ALTER TABLE fact_sales ADD COLUMN profit_margin DOUBLE")
    except Exception:
        pass


def main():
    import duckdb

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Generate data first: python -m data.generate_dataset -> {CSV_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH))

    if SCHEMA_SQL.exists():
        con.execute(SCHEMA_SQL.read_text(encoding="utf-8"))

    # Migrate existing DB: add new columns if missing
    _migrate_schema(con)

    # DuckDB read_csv_auto
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staging AS
        SELECT * FROM read_csv_auto('{CSV_PATH.as_posix()}', header=TRUE)
    """)

    # Surrogate keys for dimensions (use INSERT INTO ... SELECT with row_number)
    con.execute("DELETE FROM fact_sales")
    con.execute("DELETE FROM dim_date")
    con.execute("""
        INSERT INTO dim_date (date_id, date_actual, year, quarter, month, month_name, day)
        SELECT
            ROW_NUMBER() OVER () AS date_id,
            CAST(date AS DATE) AS date_actual,
            EXTRACT(year FROM CAST(date AS DATE))::INTEGER AS year,
            'Q' || CAST(CEIL(EXTRACT(month FROM CAST(date AS DATE)) / 3.0) AS INTEGER) AS quarter,
            EXTRACT(month FROM CAST(date AS DATE))::INTEGER AS month,
            strftime(CAST(date AS DATE), '%B') AS month_name,
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
        INSERT INTO fact_sales (sales_id, date_id, geography_id, product_id, customer_id, quantity, unit_price, revenue, cost, profit, profit_margin)
        SELECT
            ROW_NUMBER() OVER () AS sales_id,
            d.date_id,
            g.geography_id,
            p.product_id,
            c.customer_id,
            CAST(s.quantity AS DOUBLE),
            CAST(s.unit_price AS DOUBLE),
            CAST(s.revenue AS DOUBLE),
            CAST(s.cost AS DOUBLE),
            CAST(s.profit AS DOUBLE),
            CAST(s.profit_margin AS DOUBLE)
        FROM staging s
        JOIN dim_date d ON d.date_actual = CAST(s.date AS DATE)
        JOIN dim_geography g ON g.region = s.region AND g.country = s.country
        JOIN dim_product p ON p.category = s.category AND p.subcategory = s.subcategory
        JOIN dim_customer c ON c.segment = s.segment
    """)

    con.close()
    print("Loaded star schema at", DB_PATH)


if __name__ == "__main__":
    main()
