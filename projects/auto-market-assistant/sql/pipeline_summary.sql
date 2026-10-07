-- Curated row counts for operational dashboard reconciliation.
SELECT 'vehicles' AS dataset, COUNT(*) AS rows
FROM auto_market_curated.vehicles
UNION ALL
SELECT 'reviews' AS dataset, COUNT(*) AS rows
FROM auto_market_curated.reviews
UNION ALL
SELECT 'vehicle_review_matches' AS dataset, COUNT(*) AS rows
FROM auto_market_curated.vehicle_review_matches;
