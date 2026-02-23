"""Verify Q1/Q2/Q3/Q4 data exists. Run with backend stopped: python scripts/verify_data.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    import duckdb
    db = ROOT / "data" / "bi_star.duckdb"
    if not db.exists():
        print("Run: python -m data.generate_dataset && python -m data.load_star_schema")
        return
    con = duckdb.connect(str(db))
    rows = con.execute("""
        SELECT dd.year, dd.quarter, COUNT(*) as cnt, SUM(fs.revenue) as rev
        FROM fact_sales fs
        JOIN dim_date dd ON fs.date_id = dd.date_id
        GROUP BY dd.year, dd.quarter
        ORDER BY dd.year, dd.quarter
    """).fetchall()
    print("Transactions and Revenue by Year-Quarter:")
    for r in rows:
        print(f"  {r[0]} {r[1]}: {r[2]} transactions, ${r[3]:,.0f} revenue")
    con.close()

if __name__ == "__main__":
    main()
