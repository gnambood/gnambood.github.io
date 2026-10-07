-- Review coverage by make and normalized model family.
SELECT
    manufacturer,
    model_family,
    COUNT(*) AS matched_reviews,
    COUNT(DISTINCT vehicle_year) AS covered_years,
    ROUND(AVG(rating), 2) AS avg_owner_rating
FROM auto_market_curated.vehicle_review_matches
GROUP BY manufacturer, model_family
ORDER BY matched_reviews DESC;
