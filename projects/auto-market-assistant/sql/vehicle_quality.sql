-- Vehicle coverage and input-quality profile used by Tableau / QA.
SELECT
    manufacturer,
    COUNT(*) AS listings,
    ROUND(AVG(price), 2) AS avg_price,
    ROUND(AVG(odometer), 2) AS avg_mileage,
    SUM(CASE WHEN price_extreme_flag THEN 1 ELSE 0 END) AS extreme_price_flags,
    SUM(CASE WHEN odometer_zero_flag THEN 1 ELSE 0 END) AS zero_mileage_flags,
    SUM(CASE WHEN quality_band = '3+ issues' THEN 1 ELSE 0 END) AS high_issue_rows
FROM auto_market_curated.vehicles
GROUP BY manufacturer
ORDER BY listings DESC;
