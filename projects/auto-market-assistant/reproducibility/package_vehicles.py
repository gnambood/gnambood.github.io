from pathlib import Path
import duckdb

root = Path("/tmp/auto-market-etl")
db = root / "work/vehicle_features.duckdb"
reference = root / "reference/vehicles_clean.parquet"
output = root / "output/vehicles_rebuilt.parquet"

con = duckdb.connect(str(db))
con.execute("SET memory_limit='1GB'")
con.execute("SET threads=2")
con.execute(
    f"SET temp_directory='{root / 'work/duckdb_tmp'}'"
)

reference_sql = "'" + str(reference).replace("'", "''") + "'"
output_sql = "'" + str(output).replace("'", "''") + "'"

# Build the final schema from rebuilt data, not production rows.
con.execute("""
CREATE OR REPLACE TEMP VIEW reconstructed AS
SELECT
    CAST(f.id AS BIGINT) AS id,
    lower(trim(r.region)) AS region,
    CAST(f.price AS BIGINT) AS price,
    CAST(f.year AS DOUBLE) AS year,
    f.manufacturer,
    trim(regexp_replace(
        lower(trim(r.model)), '[^a-z0-9]+', ' ', 'g'
    )) AS model,
    coalesce(lower(trim(r.condition)), 'unknown') AS condition,
    coalesce(lower(trim(r.fuel)), 'unknown') AS fuel,
    CAST(f.odometer AS DOUBLE) AS odometer,
    coalesce(lower(trim(r.title_status)), 'unknown')
        AS title_status,
    coalesce(lower(trim(r.transmission)), 'unknown')
        AS transmission,
    coalesce(lower(trim(r.drive)), 'unknown') AS drive,
    coalesce(lower(trim(r.type)), 'unknown') AS type,
    lower(trim(r.state)) AS state,
    CAST(f.posting_date AS TIMESTAMPTZ) AS posting_date,
    CAST(f.posting_year AS INTEGER) AS posting_year,
    CAST(f.vehicle_age AS DOUBLE) AS vehicle_age,
    f.price_extreme_flag,
    f.odometer_zero_flag,
    CAST(f.condition_missing AS BIGINT) AS condition_missing,
    CAST(f.fuel_missing AS BIGINT) AS fuel_missing,
    CAST(f.title_status_missing AS BIGINT)
        AS title_status_missing,
    CAST(f.transmission_missing AS BIGINT)
        AS transmission_missing,
    CAST(f.drive_missing AS BIGINT) AS drive_missing,
    CAST(f.type_missing AS BIGINT) AS type_missing,
    CAST(f.quality_issue_count AS BIGINT)
        AS quality_issue_count,
    f.quality_band
FROM rebuilt_features f
JOIN raw_selected r ON f.id = r.id
""")

con.execute(f"""
COPY (SELECT * FROM reconstructed ORDER BY id)
TO {output_sql}
(FORMAT PARQUET, COMPRESSION ZSTD)
""")

fields = [
    row[0] for row in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet({reference_sql})"
    ).fetchall()
]

columns = ", ".join('"' + x + '"' for x in fields)

comparison = con.execute(f"""
WITH missing_from_production AS (
    SELECT {columns} FROM reconstructed
    EXCEPT ALL
    SELECT {columns} FROM read_parquet({reference_sql})
),
missing_from_rebuild AS (
    SELECT {columns} FROM read_parquet({reference_sql})
    EXCEPT ALL
    SELECT {columns} FROM reconstructed
)
SELECT
    (SELECT COUNT(*) FROM reconstructed),
    (SELECT COUNT(*) FROM read_parquet({reference_sql})),
    (SELECT COUNT(*) FROM missing_from_production),
    (SELECT COUNT(*) FROM missing_from_rebuild)
""").fetchone()

print("===== VEHICLE PARQUET PACKAGE =====")
print("Reconstructed rows:", comparison[0])
print("Production rows:", comparison[1])
print("Missing from production:", comparison[2])
print("Missing from rebuild:", comparison[3])
print("Output:", output)
print("Output bytes:", output.stat().st_size)

passed = (
    comparison == (238959, 238959, 0, 0)
)

print(
    "FULL VEHICLE PARQUET CONTENT:",
    "PASS" if passed else "REVIEW REQUIRED"
)

con.close()

if not passed:
    raise SystemExit(1)
