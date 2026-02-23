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

| Column      | Type    | Description        |
|-------------|---------|--------------------|
| date_id     | INTEGER | Primary key        |
| date_actual | DATE    | Calendar date      |
| year        | INTEGER | Year               |
| quarter     | VARCHAR | Q1, Q2, Q3, Q4     |
| month       | INTEGER | 1–12               |
| month_name  | VARCHAR | January … December |
| day         | INTEGER | Day of month       |

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

## DDL Scripts

Full DDL is in **`backend/database/schema.sql`**. Below is the complete script.

### schema.sql (DuckDB)

```sql
-- Star schema for BI Platform (Tier 3)
CREATE TABLE IF NOT EXISTS dim_date (
    date_id      INTEGER PRIMARY KEY,
    date_actual  DATE NOT NULL,
    year         INTEGER NOT NULL,
    quarter      VARCHAR(2) NOT NULL,
    month        INTEGER NOT NULL,
    month_name   VARCHAR(20) NOT NULL,
    day          INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_geography (
    geography_id INTEGER PRIMARY KEY,
    region       VARCHAR NOT NULL,
    country      VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_product (
    product_id   INTEGER PRIMARY KEY,
    category     VARCHAR NOT NULL,
    subcategory  VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_id  INTEGER PRIMARY KEY,
    segment      VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS fact_sales (
    sales_id      BIGINT PRIMARY KEY,
    date_id       INTEGER NOT NULL,
    geography_id  INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    customer_id   INTEGER NOT NULL,
    quantity      DOUBLE,
    unit_price    DOUBLE,
    revenue       DOUBLE,
    cost          DOUBLE,
    profit        DOUBLE,
    profit_margin DOUBLE
);
```

### Loading Data

1. Generate CSV: `python -m data.generate_dataset` → `data/global_retail_sales.csv`
2. Load schema + data: `python -m data.load_star_schema` → `data/bi_star.duckdb`
3. Or: backend auto-seeds on first connection when `fact_sales` is empty.
