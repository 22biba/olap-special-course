-- Star schema for BI Platform (Tier 3)
-- fact_sales: measures (quantity, unit_price, revenue, cost, profit, profit_margin)
-- dim_date: year, quarter, month, month_name, day
-- dim_geography: region, country
-- dim_product: category, subcategory
-- dim_customer: segment (customer_segment)

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
