-- Auto Market Assistant | SQL analytics examples for Athena engine v3
-- Run statements separately in auto-market-analytics.
-- Historical asking prices; review ratings are self-selected owner opinions.
-- Aggregate each fact independently BEFORE joining on manufacturer.

-- 1. Manufacturer overview using CTEs, joins and window functions.
WITH vehicle_metrics AS (
  SELECT manufacturer, COUNT(*) AS vehicle_count,
         ROUND(AVG(CAST(price AS DOUBLE)),2) AS avg_asking_price,
         approx_percentile(price,0.5) AS median_asking_price,
         ROUND(AVG(odometer),0) AS avg_odometer
  FROM auto_market_curated.vehicles GROUP BY manufacturer
), review_metrics AS (
  SELECT manufacturer, COUNT(*) AS review_count,
         ROUND(AVG(rating),2) AS avg_rating
  FROM auto_market_curated.reviews GROUP BY manufacturer
)
SELECT v.manufacturer, v.vehicle_count, r.review_count,
       v.avg_asking_price, v.median_asking_price,
       v.avg_odometer, r.avg_rating,
       ROUND(100.0*v.vehicle_count/SUM(v.vehicle_count) OVER(),2)
         AS pct_vehicle_listings,
       DENSE_RANK() OVER(ORDER BY v.avg_asking_price DESC)
         AS price_rank
FROM vehicle_metrics v
LEFT JOIN review_metrics r ON v.manufacturer=r.manufacturer
ORDER BY v.avg_asking_price DESC;

-- 2. Vehicle age segment: distribution and price.
WITH segmented AS (
  SELECT manufacturer, price,
         CASE
           WHEN vehicle_age < 3 THEN '0-2 years'
           WHEN vehicle_age < 6 THEN '3-5 years'
           WHEN vehicle_age < 11 THEN '6-10 years'
           ELSE '11+ years'
         END AS age_band,
         CASE
           WHEN vehicle_age < 3 THEN 1
           WHEN vehicle_age < 6 THEN 2
           WHEN vehicle_age < 11 THEN 3
           ELSE 4
         END AS age_order
  FROM auto_market_curated.vehicles
  WHERE vehicle_age IS NOT NULL AND vehicle_age >= 0
)
SELECT manufacturer, age_band, count(*) AS listings,
       ROUND(avg(CAST(price AS DOUBLE)),2) AS avg_asking_price,
       approx_percentile(price,0.5) AS median_asking_price
FROM segmented GROUP BY manufacturer, age_band, age_order
ORDER BY manufacturer, age_order;

-- 3. Data-quality band distribution by manufacturer.
SELECT manufacturer, quality_band, count(*) AS listings,
       ROUND(100.0*count(*)/SUM(count(*)) OVER(PARTITION BY manufacturer),2)
         AS share_within_make_pct,
       ROUND(AVG(CAST(price AS DOUBLE)),2) AS avg_asking_price
FROM auto_market_curated.vehicles
GROUP BY manufacturer, quality_band
ORDER BY manufacturer, listings DESC;
