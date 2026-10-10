from pathlib import Path
import duckdb

root = Path("/tmp/auto-market-etl")
source = root / "raw/craigslist/vehicles.csv"
reference = root / "reference/vehicles_clean.parquet"
database = root / "work/vehicle_features.duckdb"

con = duckdb.connect(str(database))
con.execute("SET memory_limit='1GB'")
con.execute("SET threads=2")
con.execute(
    f"SET temp_directory='{root / 'work/duckdb_tmp'}'"
)

print("===== BUILD VEHICLE WORKING TABLE =====", flush=True)

con.execute("""
CREATE OR REPLACE TABLE vehicle_stage AS
WITH normalized AS (
    SELECT
        id,
        price,
        year,
        odometer,
        posting_date,
        lower(trim(manufacturer)) AS manufacturer,
        trim(regexp_replace(
            lower(trim(model)), '[^a-z0-9]+', ' ', 'g'
        )) AS model,
        condition,
        fuel,
        title_status,
        transmission,
        drive,
        type,
        row_number() OVER (
            PARTITION BY id ORDER BY id
        ) AS duplicate_rank
    FROM read_csv_auto(?, sample_size=20000)
)
SELECT *,
       year(posting_date) AS posting_year,
       GREATEST(0, year(posting_date) - year)
           AS vehicle_age
FROM normalized
WHERE duplicate_rank = 1
  AND price BETWEEN 1000 AND 100000
  AND year BETWEEN 1990 AND year(posting_date) + 1
  AND posting_date IS NOT NULL
  AND manufacturer IS NOT NULL
  AND model IS NOT NULL
  AND manufacturer <> ''
  AND model <> ''
""", [str(source)])

print("Working table built.", flush=True)

print("\n===== CALCULATE PRICE THRESHOLDS =====", flush=True)

q01, q99 = con.execute("""
SELECT
    quantile_cont(price, 0.01),
    quantile_cont(price, 0.99)
FROM vehicle_stage
""").fetchone()

print("1st percentile:", q01)
print("99th percentile:", q99)

print("\n===== RECONSTRUCT SCOPED FEATURES =====", flush=True)

con.execute("""
CREATE OR REPLACE TABLE rebuilt_features AS
WITH cleaned AS (
    SELECT *,
        (price < ? OR price > ?) AS price_extreme_flag,
        (odometer = 0 AND vehicle_age > 2)
            AS odometer_zero_flag,
        CASE WHEN condition IS NULL THEN 1 ELSE 0 END
            AS condition_missing,
        CASE WHEN fuel IS NULL THEN 1 ELSE 0 END
            AS fuel_missing,
        CASE WHEN title_status IS NULL THEN 1 ELSE 0 END
            AS title_status_missing,
        CASE WHEN transmission IS NULL THEN 1 ELSE 0 END
            AS transmission_missing,
        CASE WHEN drive IS NULL THEN 1 ELSE 0 END
            AS drive_missing,
        CASE WHEN type IS NULL THEN 1 ELSE 0 END
            AS type_missing
    FROM vehicle_stage
    WHERE odometer BETWEEN 0 AND 300000
),
quality AS (
    SELECT *,
        condition_missing + fuel_missing +
        title_status_missing + transmission_missing +
        drive_missing + type_missing +
        CAST(price_extreme_flag AS INTEGER) +
        CAST(odometer_zero_flag AS INTEGER)
            AS quality_issue_count
    FROM cleaned
)
SELECT
    id, manufacturer, price, year, odometer,
    posting_date, posting_year, vehicle_age,
    price_extreme_flag, odometer_zero_flag,
    condition_missing, fuel_missing,
    title_status_missing, transmission_missing,
    drive_missing, type_missing,
    quality_issue_count,
    CASE
        WHEN quality_issue_count = 0 THEN '0 issues'
        WHEN quality_issue_count <= 2 THEN '1-2 issues'
        ELSE '3+ issues'
    END AS quality_band
FROM quality
WHERE manufacturer IN (
    'ford', 'chevrolet', 'toyota', 'honda', 'nissan',
    'jeep', 'ram', 'gmc', 'bmw', 'dodge'
)
""", [q01, q99])

print("Rebuilt rows:",
      con.execute("SELECT COUNT(*) FROM rebuilt_features").fetchone()[0],
      flush=True)

print("\n===== COMPARE AGAINST PRODUCTION =====", flush=True)

con.execute("""
CREATE TEMP VIEW production AS
SELECT *
FROM read_parquet('/tmp/auto-market-etl/reference/vehicles_clean.parquet')
""")

fields = [
    "posting_year", "vehicle_age",
    "price_extreme_flag", "odometer_zero_flag",
    "condition_missing", "fuel_missing",
    "title_status_missing", "transmission_missing",
    "drive_missing", "type_missing",
    "quality_issue_count", "quality_band"
]

for field in fields:
    mismatches = con.execute(f"""
    SELECT COUNT(*)
    FROM rebuilt_features r
    JOIN production p ON r.id = p.id
    WHERE r.{field} IS DISTINCT FROM p.{field}
    """).fetchone()[0]

    print(f"{field:25s}: {mismatches:,} mismatches", flush=True)

con.close()
