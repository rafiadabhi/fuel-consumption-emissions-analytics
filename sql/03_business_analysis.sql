-- Portfolio queries for MySQL Workbench (MySQL 8.0+).
-- Each numbered query answers a business or validation question.

-- 1. Data-quality checkpoint after ingestion.
SELECT
    COUNT(*) AS row_count,
    COUNT(DISTINCT vehicle_id) AS unique_vehicle_ids,
    MIN(model_year) AS first_model_year,
    MAX(model_year) AS latest_model_year,
    SUM(co2_emissions_g_km IS NULL) AS missing_target_rows,
    SUM(fuel_type_code NOT IN ('X', 'Z', 'D', 'E', 'N')) AS invalid_fuel_code_rows
FROM vehicle_ratings;

-- 2. Annual rated-emission trend and year-over-year movement.
WITH yearly AS (
    SELECT
        model_year,
        COUNT(*) AS vehicle_records,
        AVG(co2_emissions_g_km) AS average_co2_g_km,
        AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km
    FROM vehicle_ratings
    GROUP BY model_year
)
SELECT
    yearly.*,
    LAG(average_co2_g_km) OVER (ORDER BY model_year) AS previous_year_co2,
    average_co2_g_km /
        NULLIF(LAG(average_co2_g_km) OVER (ORDER BY model_year), 0) - 1
        AS co2_yoy_change_pct
FROM yearly
ORDER BY model_year;

-- 3. Three-year rolling trend reduces single-year product-mix noise.
WITH yearly AS (
    SELECT model_year, AVG(co2_emissions_g_km) AS average_co2_g_km
    FROM vehicle_ratings
    GROUP BY model_year
)
SELECT
    model_year,
    average_co2_g_km,
    AVG(average_co2_g_km) OVER (
        ORDER BY model_year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ) AS rolling_three_year_average_co2
FROM yearly
ORDER BY model_year;

-- 4. Latest-year vehicle classes ranked from highest to lowest average CO2.
WITH latest_year AS (
    SELECT MAX(model_year) AS model_year FROM vehicle_ratings
), class_summary AS (
    SELECT
        v.vehicle_class,
        COUNT(*) AS vehicle_records,
        AVG(v.co2_emissions_g_km) AS average_co2_g_km,
        AVG(v.fuel_cons_comb_l_100km) AS average_combined_l_100km
    FROM vehicle_ratings AS v
    JOIN latest_year AS y ON v.model_year = y.model_year
    GROUP BY v.vehicle_class
)
SELECT
    class_summary.*,
    RANK() OVER (ORDER BY average_co2_g_km DESC) AS high_emission_rank
FROM class_summary
ORDER BY high_emission_rank;

-- 5. Latest-year manufacturer benchmark with a minimum sample-size guard.
WITH latest_year AS (
    SELECT MAX(model_year) AS model_year FROM vehicle_ratings
), make_summary AS (
    SELECT
        v.make,
        COUNT(*) AS vehicle_records,
        AVG(v.co2_emissions_g_km) AS average_co2_g_km,
        AVG(v.engine_size_l) AS average_engine_size_l
    FROM vehicle_ratings AS v
    JOIN latest_year AS y ON v.model_year = y.model_year
    GROUP BY v.make
)
SELECT
    make_summary.*,
    RANK() OVER (ORDER BY average_co2_g_km) AS low_emission_rank
FROM make_summary
WHERE vehicle_records >= 5
ORDER BY low_emission_rank;

-- 6. Engine-size relationship using auditable CASE-based bands.
SELECT
    CASE
        WHEN engine_size_l <= 2.0 THEN '<=2.0L'
        WHEN engine_size_l <= 3.0 THEN '2.1-3.0L'
        WHEN engine_size_l <= 4.0 THEN '3.1-4.0L'
        ELSE '>4.0L'
    END AS engine_size_band,
    COUNT(*) AS vehicle_records,
    AVG(co2_emissions_g_km) AS average_co2_g_km,
    AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km
FROM vehicle_ratings
GROUP BY engine_size_band
ORDER BY MIN(engine_size_l);

-- 7. Fuel-type mix by year. Compare composition carefully; this is not causal.
SELECT
    v.model_year,
    f.fuel_type_name,
    COUNT(*) AS vehicle_records,
    AVG(v.co2_emissions_g_km) AS average_co2_g_km,
    COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY v.model_year) AS record_share
FROM vehicle_ratings AS v
JOIN fuel_type_lookup AS f
    ON v.fuel_type_code = f.fuel_type_code
GROUP BY v.model_year, f.fuel_type_name
ORDER BY v.model_year, vehicle_records DESC;

-- 8. Put 2022-2023 configurations into within-class opportunity quartiles.
-- Gap is a peer-benchmark scenario, not guaranteed engineering reduction.
WITH recent AS (
    SELECT
        vehicle_id,
        model_year,
        make,
        model,
        vehicle_class,
        co2_emissions_g_km,
        class_year_co2_p25,
        co2_gap_to_class_p25,
        NTILE(4) OVER (
            PARTITION BY model_year, vehicle_class
            ORDER BY co2_gap_to_class_p25 DESC
        ) AS opportunity_quartile
    FROM vehicle_ratings
    WHERE model_year >= 2022
)
SELECT *
FROM recent
WHERE opportunity_quartile = 1
ORDER BY co2_gap_to_class_p25 DESC, co2_emissions_g_km DESC;

-- 9. Independently recompute selected-model test metrics from prediction rows.
WITH test_predictions AS (
    SELECT *
    FROM model_predictions
    WHERE data_split = 'test'
), target_mean AS (
    SELECT AVG(actual_co2_g_km) AS mean_actual
    FROM test_predictions
)
SELECT
    p.model_name,
    COUNT(*) AS test_records,
    AVG(p.absolute_error_g_km) AS mae,
    SQRT(AVG(POWER(p.prediction_error_g_km, 2))) AS rmse,
    AVG(p.absolute_percentage_error) AS mape,
    1 - SUM(POWER(p.prediction_error_g_km, 2)) /
        NULLIF(SUM(POWER(p.actual_co2_g_km - m.mean_actual, 2)), 0) AS r_squared
FROM test_predictions AS p
CROSS JOIN target_mean AS m
GROUP BY p.model_name;

-- 10. Test-period residual error by vehicle class, with a sample-size filter.
SELECT
    v.vehicle_class,
    COUNT(*) AS test_records,
    AVG(p.absolute_error_g_km) AS mae,
    SQRT(AVG(POWER(p.prediction_error_g_km, 2))) AS rmse,
    AVG(p.prediction_error_g_km) AS mean_error_pred_minus_actual
FROM model_predictions AS p
JOIN vehicle_ratings AS v
    ON p.vehicle_id = v.vehicle_id
WHERE p.data_split = 'test'
GROUP BY v.vehicle_class
HAVING COUNT(*) >= 20
ORDER BY mae DESC;

-- 11. Largest 10% of test errors, using a derived-table subquery.
SELECT
    v.model_year,
    v.make,
    v.model,
    v.vehicle_class,
    v.engine_size_l,
    v.cylinders,
    f.fuel_type_name,
    p.actual_co2_g_km,
    p.predicted_co2_g_km,
    p.prediction_error_g_km,
    p.absolute_error_g_km,
    p.error_percentile
FROM (
    SELECT
        base.*,
        CUME_DIST() OVER (ORDER BY base.absolute_error_g_km) AS error_percentile
    FROM model_predictions AS base
    WHERE base.data_split = 'test'
) AS p
JOIN vehicle_ratings AS v
    ON p.vehicle_id = v.vehicle_id
JOIN fuel_type_lookup AS f
    ON v.fuel_type_code = f.fuel_type_code
WHERE p.error_percentile >= 0.90
ORDER BY p.absolute_error_g_km DESC;
