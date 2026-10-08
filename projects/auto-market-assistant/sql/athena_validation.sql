-- Auto Market Assistant | Athena read-only verification
-- Catalog: AwsDataCatalog | Database: auto_market_curated
-- Run statements separately in the auto-market-analytics workgroup.
-- Note: validation targets the 2026-10-08 processed-derived curated snapshot.

-- 1. Expected total row counts; must return PASS for both datasets.
WITH actual AS (
  SELECT 'vehicles' AS dataset, count(*) AS actual_rows
  FROM auto_market_curated.vehicles
  UNION ALL
  SELECT 'reviews', count(*)
  FROM auto_market_curated.reviews
), expected AS (
  SELECT 'vehicles' AS dataset, BIGINT '238959' AS expected_rows
  UNION ALL
  SELECT 'reviews', BIGINT '70665'
)
SELECT a.dataset, a.actual_rows, e.expected_rows,
       IF(a.actual_rows=e.expected_rows, 'PASS', 'FAIL') AS status
FROM actual a JOIN expected e ON a.dataset=e.dataset
ORDER BY a.dataset;

-- 2. Manufacturer-level reconciliation against validated Parquet snapshot.
WITH expected(manufacturer, vehicle_rows, review_rows) AS (
  VALUES
    ('bmw',13020,5702),
    ('chevrolet',44912,9934),
    ('dodge',10871,2557),
    ('ford',59737,15689),
    ('gmc',14451,2751),
    ('honda',18927,10507),
    ('jeep',15905,2405),
    ('nissan',16414,7450),
    ('ram',14848,536),
    ('toyota',29874,13134)
), v AS (
  SELECT manufacturer, count(*) AS rows FROM auto_market_curated.vehicles GROUP BY 1
), r AS (
  SELECT manufacturer, count(*) AS rows FROM auto_market_curated.reviews GROUP BY 1
)
SELECT e.manufacturer, e.vehicle_rows AS expected_vehicles, v.rows AS actual_vehicles,
       e.review_rows AS expected_reviews, r.rows AS actual_reviews,
       IF(e.vehicle_rows=coalesce(v.rows,-1)
          AND e.review_rows=coalesce(r.rows,-1),'PASS','FAIL') AS status
FROM expected e
LEFT JOIN v ON v.manufacturer=e.manufacturer
LEFT JOIN r ON r.manufacturer=e.manufacturer
ORDER BY e.manufacturer;

-- 3. Physical content checks. Expect zero null IDs, invalid price, blank review text.
SELECT
  count_if(id IS NULL) AS missing_vehicle_id,
  count_if(price IS NULL OR price < 1000 OR price > 100000) AS out_of_scope_price,
  count_if(manufacturer IS NULL OR trim(manufacturer)='') AS missing_make,
  count_if(posting_date IS NULL) AS missing_posting_date
FROM auto_market_curated.vehicles;

-- 4. Review data quality, independently of vehicle records.
SELECT
  count_if(review_id IS NULL OR trim(review_id)='') AS missing_review_id,
  count_if(review_text IS NULL OR trim(review_text)='') AS empty_review_text,
  count_if(manufacturer IS NULL OR trim(manufacturer)='') AS missing_make,
  count_if(rating IS NOT NULL AND (rating < 0 OR rating > 5)) AS invalid_rating
FROM auto_market_curated.reviews;

-- 5. Duplicate identifiers (investigate if rows returned).
SELECT id, count(*) AS occurrences
FROM auto_market_curated.vehicles
GROUP BY id HAVING count(*) > 1
ORDER BY occurrences DESC LIMIT 20;

SELECT review_id, count(*) AS occurrences
FROM auto_market_curated.reviews
GROUP BY review_id HAVING count(*) > 1
ORDER BY occurrences DESC LIMIT 20;
