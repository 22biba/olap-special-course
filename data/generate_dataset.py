"""
Generate Global Retail Sales CSV: 10k transactions, Jan 2022 - Dec 2024.
Dimensions: date, region, country, category, subcategory, segment.
Measures: quantity, revenue, cost, profit.
"""
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "global_retail_sales.csv"

REGIONS = {
    "North America": ["United States", "Canada", "Mexico"],
    "Europe": ["United Kingdom", "Germany", "France", "Spain", "Italy"],
    "Asia Pacific": ["China", "Japan", "Australia", "India", "South Korea"],
    "Latin America": ["Brazil", "Argentina", "Chile", "Colombia"],
}

CATEGORIES = {
    "Electronics": ["Phones", "Computers", "Audio", "Accessories"],
    "Furniture": ["Chairs", "Tables", "Storage", "Desks"],
    "Office Supplies": ["Paper", "Pens", "Binders", "Labels"],
    "Clothing": ["Shirts", "Pants", "Outerwear", "Shoes"],
}

SEGMENTS = ["Consumer", "Corporate", "Home Office"]

def main():
    random.seed(42)
    start = datetime(2022, 1, 1)
    end = datetime(2024, 12, 31)
    rows = []
    for i in range(10000):
        d = start + timedelta(days=random.randint(0, (end - start).days))
        region = random.choice(list(REGIONS.keys()))
        country = random.choice(REGIONS[region])
        category = random.choice(list(CATEGORIES.keys()))
        subcategory = random.choice(CATEGORIES[category])
        segment = random.choice(SEGMENTS)
        quantity = random.randint(1, 5)
        unit_price = round(random.uniform(10, 500), 2)
        revenue = round(quantity * unit_price, 2)
        cost = round(revenue * random.uniform(0.4, 0.8), 2)
        profit = round(revenue - cost, 2)
        rows.append({
            "date": d.strftime("%Y-%m-%d"),
            "region": region,
            "country": country,
            "category": category,
            "subcategory": subcategory,
            "segment": segment,
            "quantity": quantity,
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("Generated", OUTPUT, "with", len(rows), "rows.")

if __name__ == "__main__":
    main()
