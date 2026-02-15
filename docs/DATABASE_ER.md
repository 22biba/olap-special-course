# Database – Star Schema (ER)

## Entity-relationship overview

The dataset is modeled as a **star schema**: one fact table (`fact_sales`) and four dimension tables (`dim_date`, `dim_geography`, `dim_product`, `dim_customer`). All measures and foreign keys live in the fact table; dimensions hold attributes and surrogate keys.

```
                    ┌─────────────────┐
                    │    dim_date     │
                    ├─────────────────┤
                    │ PK date_id      │
                    │    date_actual  │
                    │    year         │
                    │    quarter      │
                    │    month        │
                    │    day          │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │                 │
    ┌───────────────┴───┐   ┌────────┴─────────────────┐
    │  dim_geography   │   │      fact_sales           │
    ├──────────────────┤   ├──────────────────────────┤
    │ PK geography_id  │   │ PK sales_id               │
    │    region        │   │ FK date_id       ─────────┤
    │    country       │   │ FK geography_id ─────────┤
    └────────┬─────────┘   │ FK product_id   ─────────┤
             │             │ FK customer_id ─────────┤
             │             │    quantity              │
             │             │    revenue               │
             │             │    cost                  │
             │             │    profit                │
             │             └────────┬─────────────────┘
             │                      │
    ┌────────┴────────┐   ┌─────────┴─────────┐
    │  dim_product   │   │   dim_customer   │
    ├────────────────┤   ├─────────────────┤
    │ PK product_id  │   │ PK customer_id   │
    │    category   │   │    segment       │
    │    subcategory │   └──────────────────┘
    └────────────────┘
```

## Tables

### fact_sales (measures)

| Column       | Type    | Description                    |
|-------------|---------|--------------------------------|
| sales_id    | BIGINT  | Primary key                    |
| date_id     | INTEGER | FK → dim_date                  |
| geography_id| INTEGER | FK → dim_geography             |
| product_id  | INTEGER | FK → dim_product               |
| customer_id | INTEGER | FK → dim_customer              |
| quantity    | DOUBLE  | Measure                        |
| revenue     | DOUBLE  | Measure                        |
| cost        | DOUBLE  | Measure                        |
| profit      | DOUBLE  | Measure                        |

### dim_date (time hierarchy)

| Column     | Type    | Description        |
|------------|---------|--------------------|
| date_id    | INTEGER | Primary key        |
| date_actual| DATE    | Calendar date       |
| year       | INTEGER | Year                |
| quarter    | VARCHAR | Q1, Q2, Q3, Q4     |
| month      | INTEGER | 1–12                |
| day        | INTEGER | Day of month        |

**Hierarchy:** Year → Quarter → Month → Day (drill-down / roll-up).

### dim_geography

| Column      | Type    | Description |
|-------------|---------|-------------|
| geography_id| INTEGER | Primary key |
| region      | VARCHAR | e.g. North America, Europe |
| country     | VARCHAR | e.g. United States, Germany |

**Hierarchy:** Region → Country.

### dim_product

| Column     | Type    | Description |
|------------|---------|-------------|
| product_id | INTEGER | Primary key |
| category   | VARCHAR | e.g. Electronics, Furniture |
| subcategory| VARCHAR | e.g. Phones, Chairs |

**Hierarchy:** Category → Subcategory.

### dim_customer

| Column     | Type    | Description |
|------------|---------|-------------|
| customer_id| INTEGER | Primary key |
| segment    | VARCHAR | e.g. Consumer, Corporate |

## DDL

Full DDL is in **`backend/database/schema.sql`**. Data is loaded from `data/global_retail_sales.csv` via `data/load_star_schema.py` or auto-seed on first backend connection when the fact table is empty.
