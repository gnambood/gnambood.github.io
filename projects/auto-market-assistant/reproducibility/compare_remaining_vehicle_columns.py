import duckdb
from pathlib import Path

root = Path("/tmp/auto-market-etl")

con = duckdb.connect(
    str(root / "work/vehicle_features.duckdb")
)
con.execute("SET memory_limit='1GB'")
con.execute("SET threads=2")
con.execute(
    f"SET temp_directory='{root / 'work/duckdb_tmp'}'"
)

con.execute("""
CREATE OR REPLACE TEMP VIEW production AS
SELECT *
FROM read_parquet(
    '/tmp/auto-market-etl/reference/vehicles_clean.parquet'
)
""")

print("===== RESTORE REMAINING FIELDS =====", flush=True)

con.execute("""
CREATE OR REPLACE TABLE raw_selected AS
SELECT
    r.id,
    r.region,
    r.model,
    r.condition,
    r.fuel,
    r.title_status,
    r.transmission,
    r.drive,
    r.type,
    r.state,
    r.posting_date
FROM read_csv_auto(
    '/tmp/auto-market-etl/raw/craigslist/vehicles.csv',
    sample_size=20000
) r
SEMI JOIN rebuilt_features f ON r.id = f.id
""")

print("Raw selected rows:",
      con.execute("SELECT COUNT(*) FROM raw_selected").fetchone()[0],
      flush=True)

fields = [
    "region", "model", "condition", "fuel",
    "title_status", "transmission", "drive",
    "type", "state"
]

print("\n===== FIELD RECONCILIATION =====")

total_mismatches = 0

for field in fields:
    if field == "model":
        expression = """
        trim(regexp_replace(
            lower(trim(r.model)),
            '[^a-z0-9]+', ' ', 'g'
        ))
        """
    else:
        expression = f"""
        regexp_replace(
            lower(trim(r.{field})),
            '[[:space:]]+', ' ', 'g'
        )
        """
        if field in [
            "condition", "fuel", "title_status",
            "transmission", "drive", "type"
        ]:
            expression = f"coalesce({expression}, 'unknown')"

    sql = f"""
    SELECT COUNT(*)
    FROM raw_selected r
    JOIN production p ON r.id = p.id
    WHERE ({expression}) IS DISTINCT FROM p.{field}
    """

    mismatches = con.execute(sql).fetchone()[0]
    total_mismatches += mismatches
    print(f"{field:20s}: {mismatches:,} mismatches")

date_mismatches = con.execute("""
SELECT COUNT(*)
FROM raw_selected r
JOIN production p ON r.id = p.id
WHERE r.posting_date
    IS DISTINCT FROM p.posting_date
""").fetchone()[0]

total_mismatches += date_mismatches

print(f"{'posting_date':20s}: {date_mismatches:,} mismatches")

print("\n===== FINAL RESULT =====")

production_count = con.execute(
    "SELECT COUNT(*) FROM production"
).fetchone()[0]

rebuilt_count = con.execute(
    "SELECT COUNT(*) FROM rebuilt_features"
).fetchone()[0]

print("Production rows:", production_count)
print("Reconstructed rows:", rebuilt_count)
print("Total field mismatches:", total_mismatches)

passed = (
    production_count == 238959
    and rebuilt_count == 238959
    and total_mismatches == 0
)

print(
    "REMAINING VEHICLE FIELDS:",
    "PASS" if passed else "REVIEW REQUIRED"
)

con.close()
