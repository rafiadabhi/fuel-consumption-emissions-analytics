-- MySQL 8.0+ views consumed by the Streamlit dashboard.
-- Run automatically by: python -m src.04_build_dashboard_views

CREATE OR REPLACE VIEW vw_dashboard_vehicle_detail AS
SELECT
    v.vehicle_id,
    v.model_year,
    v.make,
    v.model,
    v.vehicle_class,
    v.engine_size_l,
    v.engine_size_band,
    v.cylinders,
    t.transmission_family_name AS transmission_family,
    v.gear_count,
    f.fuel_type_name AS fuel_type,
    v.fuel_cons_city_l_100km,
    v.fuel_cons_hwy_l_100km,
    v.fuel_cons_comb_l_100km,
    v.fuel_economy_comb_mpg,
    v.co2_emissions_g_km,
    v.co2_rating,
    v.smog_rating,
    v.class_year_co2_median,
    v.class_year_co2_p25,
    v.co2_vs_class_year_median,
    v.co2_gap_to_class_p25,
    v.above_class_year_median,
    v.emission_band,
    v.model_split,
    p.model_name,
    p.predicted_co2_g_km,
    p.prediction_error_g_km,
    p.absolute_error_g_km,
    p.absolute_percentage_error,
    p.predicted_emission_band,
    p.high_error_flag
FROM vehicle_ratings AS v
JOIN fuel_type_lookup AS f
    ON v.fuel_type_code = f.fuel_type_code
JOIN transmission_family_lookup AS t
    ON v.transmission_family_code = t.transmission_family_code
LEFT JOIN model_predictions AS p
    ON v.vehicle_id = p.vehicle_id;

CREATE OR REPLACE VIEW vw_dashboard_yearly_trend AS
WITH yearly AS (
    SELECT
        model_year,
        COUNT(*) AS vehicle_records,
        AVG(co2_emissions_g_km) AS average_co2_g_km,
        AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km,
        AVG(engine_size_l) AS average_engine_size_l,
        AVG(co2_gap_to_class_p25) AS average_peer_gap_g_km
    FROM vehicle_ratings
    GROUP BY model_year
), trend AS (
    SELECT
        yearly.*,
        LAG(average_co2_g_km) OVER (ORDER BY model_year) AS previous_year_average_co2
    FROM yearly
), baseline AS (
    SELECT average_co2_g_km AS baseline_co2
    FROM yearly
    WHERE model_year = 1995
)
SELECT
    trend.*,
    average_co2_g_km / NULLIF(previous_year_average_co2, 0) - 1 AS co2_yoy_change_pct,
    average_co2_g_km / NULLIF(baseline.baseline_co2, 0) - 1 AS co2_change_vs_1995_pct
FROM trend
CROSS JOIN baseline;

CREATE OR REPLACE VIEW vw_dashboard_class_benchmark AS
SELECT
    model_year,
    vehicle_class,
    COUNT(*) AS vehicle_records,
    AVG(co2_emissions_g_km) AS average_co2_g_km,
    AVG(class_year_co2_median) AS median_co2_g_km,
    AVG(class_year_co2_p25) AS p25_co2_g_km,
    AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km,
    AVG(engine_size_l) AS average_engine_size_l,
    AVG(co2_gap_to_class_p25) AS average_peer_gap_g_km,
    RANK() OVER (
        PARTITION BY model_year
        ORDER BY AVG(co2_emissions_g_km) DESC
    ) AS high_to_low_emission_rank
FROM vehicle_ratings
GROUP BY model_year, vehicle_class;

CREATE OR REPLACE VIEW vw_dashboard_make_benchmark AS
SELECT
    model_year,
    make,
    COUNT(*) AS vehicle_records,
    AVG(co2_emissions_g_km) AS average_co2_g_km,
    AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km,
    AVG(engine_size_l) AS average_engine_size_l,
    AVG(co2_gap_to_class_p25) AS average_peer_gap_g_km,
    RANK() OVER (
        PARTITION BY model_year
        ORDER BY AVG(co2_emissions_g_km)
    ) AS low_to_high_emission_rank
FROM vehicle_ratings
GROUP BY model_year, make;

CREATE OR REPLACE VIEW vw_dashboard_model_performance AS
SELECT
    metric_id,
    model_name,
    model_scope,
    split,
    eligible_for_selection,
    fit_period,
    mae,
    rmse,
    mape,
    r_squared,
    mean_error_pred_minus_actual,
    p90_absolute_error
FROM model_metrics;

CREATE OR REPLACE VIEW vw_dashboard_feature_importance AS
SELECT
    importance_id,
    model_name,
    feature,
    importance_mean_mae_increase,
    importance_std,
    RANK() OVER (
        PARTITION BY model_name
        ORDER BY importance_mean_mae_increase DESC
    ) AS importance_rank
FROM feature_importance;

CREATE OR REPLACE VIEW vw_dashboard_high_emission_opportunities AS
SELECT
    d.*,
    RANK() OVER (
        PARTITION BY d.model_year, d.vehicle_class
        ORDER BY d.co2_gap_to_class_p25 DESC, d.co2_emissions_g_km DESC
    ) AS within_class_opportunity_rank
FROM vw_dashboard_vehicle_detail AS d
WHERE d.model_year >= 2022
  AND d.co2_gap_to_class_p25 > 0;

CREATE OR REPLACE VIEW vw_dashboard_test_segment_errors AS
SELECT
    segment_error_id,
    segment_type,
    segment_value,
    vehicle_records,
    average_actual_co2_g_km,
    average_predicted_co2_g_km,
    mae,
    rmse,
    mape,
    r_squared,
    mean_error_pred_minus_actual,
    p90_absolute_error
FROM model_segment_errors;

CREATE OR REPLACE VIEW vw_dashboard_kpis AS
WITH year_bounds AS (
    SELECT MIN(model_year) AS first_year, MAX(model_year) AS latest_year
    FROM vehicle_ratings
), first_year AS (
    SELECT AVG(v.co2_emissions_g_km) AS average_co2
    FROM vehicle_ratings AS v
    CROSS JOIN year_bounds AS y
    WHERE v.model_year = y.first_year
), latest_year AS (
    SELECT
        COUNT(*) AS vehicle_records,
        AVG(v.co2_emissions_g_km) AS average_co2,
        AVG(v.fuel_cons_comb_l_100km) AS average_fuel_consumption,
        AVG(v.co2_gap_to_class_p25) AS average_peer_gap
    FROM vehicle_ratings AS v
    CROSS JOIN year_bounds AS y
    WHERE v.model_year = y.latest_year
), selected_test AS (
    SELECT *
    FROM model_metrics
    WHERE model_scope = 'early_specification'
      AND split = 'test'
      AND eligible_for_selection = 1
    LIMIT 1
)
SELECT
    (SELECT COUNT(*) FROM vehicle_ratings) AS vehicle_records,
    y.first_year AS first_model_year,
    y.latest_year AS latest_model_year,
    (SELECT COUNT(DISTINCT model_year) FROM vehicle_ratings) AS years_covered,
    l.vehicle_records AS latest_year_records,
    l.average_co2 AS latest_average_co2_g_km,
    l.average_fuel_consumption AS latest_average_combined_l_100km,
    l.average_co2 / NULLIF(f.average_co2, 0) - 1 AS co2_change_first_to_latest_pct,
    l.average_peer_gap AS latest_average_peer_gap_g_km,
    s.model_name AS selected_model,
    (SELECT COUNT(*) FROM model_predictions WHERE data_split = 'test') AS test_records,
    s.mae AS test_mae_g_km,
    s.rmse AS test_rmse_g_km,
    s.mape AS test_mape,
    s.r_squared AS test_r_squared,
    s.p90_absolute_error AS test_p90_absolute_error_g_km
FROM year_bounds AS y
CROSS JOIN first_year AS f
CROSS JOIN latest_year AS l
CROSS JOIN selected_test AS s;
