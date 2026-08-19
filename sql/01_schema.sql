-- MySQL 8.0+ schema for Vehicle Fuel Efficiency Analytics.
-- Run automatically by: python -m src.03_load_mysql
-- Manual alternative: open this file in MySQL Workbench after creating/selecting
-- the database configured in .env.

CREATE TABLE IF NOT EXISTS fuel_type_lookup (
    fuel_type_code CHAR(1) PRIMARY KEY,
    fuel_type_name VARCHAR(40) NOT NULL UNIQUE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS transmission_family_lookup (
    transmission_family_code VARCHAR(2) PRIMARY KEY,
    transmission_family_name VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

REPLACE INTO fuel_type_lookup (fuel_type_code, fuel_type_name) VALUES
    ('X', 'Regular Gasoline'),
    ('Z', 'Premium Gasoline'),
    ('D', 'Diesel'),
    ('E', 'E85'),
    ('N', 'Natural Gas');

REPLACE INTO transmission_family_lookup
    (transmission_family_code, transmission_family_name) VALUES
    ('A',  'Automatic'),
    ('AS', 'Automatic with Select Shift'),
    ('AM', 'Automated Manual'),
    ('AV', 'Continuously Variable'),
    ('M',  'Manual');

CREATE TABLE IF NOT EXISTS vehicle_ratings (
    vehicle_id INT PRIMARY KEY,
    source_row_number INT NOT NULL,
    model_year SMALLINT NOT NULL,
    make VARCHAR(60) NOT NULL,
    model VARCHAR(180) NOT NULL,
    vehicle_class_raw VARCHAR(80) NOT NULL,
    vehicle_class VARCHAR(80) NOT NULL,
    engine_size_l DECIMAL(4,1) NOT NULL,
    cylinders TINYINT UNSIGNED NOT NULL,
    transmission VARCHAR(8) NOT NULL,
    transmission_family_code VARCHAR(2) NOT NULL,
    gear_count TINYINT UNSIGNED NOT NULL,
    fuel_type_code CHAR(1) NOT NULL,
    fuel_cons_city_l_100km DECIMAL(5,1) NOT NULL,
    fuel_cons_hwy_l_100km DECIMAL(5,1) NOT NULL,
    fuel_cons_comb_l_100km DECIMAL(5,1) NOT NULL,
    fuel_economy_comb_mpg SMALLINT UNSIGNED NOT NULL,
    co2_emissions_g_km SMALLINT UNSIGNED NOT NULL,
    co2_rating TINYINT UNSIGNED NULL,
    smog_rating TINYINT UNSIGNED NULL,
    city_hwy_gap_l_100km DECIMAL(6,3) NOT NULL,
    city_hwy_ratio DECIMAL(10,6) NOT NULL,
    co2_per_comb_l DECIMAL(10,6) NOT NULL,
    engine_size_band VARCHAR(20) NOT NULL,
    class_year_co2_median DECIMAL(7,3) NOT NULL,
    class_year_co2_p25 DECIMAL(7,3) NOT NULL,
    co2_vs_class_year_median DECIMAL(8,3) NOT NULL,
    co2_gap_to_class_p25 DECIMAL(8,3) NOT NULL,
    above_class_year_median TINYINT(1) NOT NULL,
    city_below_highway_flag TINYINT(1) NOT NULL,
    emission_band VARCHAR(12) NOT NULL,
    model_split ENUM('train', 'validation', 'test') NOT NULL,
    CONSTRAINT fk_vehicle_fuel_type
        FOREIGN KEY (fuel_type_code) REFERENCES fuel_type_lookup(fuel_type_code),
    CONSTRAINT fk_vehicle_transmission_family
        FOREIGN KEY (transmission_family_code)
        REFERENCES transmission_family_lookup(transmission_family_code),
    CONSTRAINT chk_vehicle_year CHECK (model_year BETWEEN 1995 AND 2023),
    CONSTRAINT chk_engine_size CHECK (engine_size_l > 0),
    CONSTRAINT chk_cylinders CHECK (cylinders > 0),
    CONSTRAINT chk_consumption CHECK (
        fuel_cons_city_l_100km > 0
        AND fuel_cons_hwy_l_100km > 0
        AND fuel_cons_comb_l_100km > 0
    ),
    CONSTRAINT chk_co2 CHECK (co2_emissions_g_km > 0),
    CONSTRAINT chk_co2_rating CHECK (co2_rating IS NULL OR co2_rating BETWEEN 1 AND 10),
    CONSTRAINT chk_smog_rating CHECK (smog_rating IS NULL OR smog_rating BETWEEN 1 AND 10),
    INDEX idx_vehicle_year (model_year),
    INDEX idx_vehicle_make_year (make, model_year),
    INDEX idx_vehicle_class_year (vehicle_class, model_year),
    INDEX idx_vehicle_fuel_year (fuel_type_code, model_year),
    INDEX idx_vehicle_co2 (co2_emissions_g_km),
    INDEX idx_vehicle_split (model_split)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS model_predictions (
    vehicle_id INT PRIMARY KEY,
    data_split ENUM('train', 'validation', 'test') NOT NULL,
    model_name VARCHAR(80) NOT NULL,
    actual_co2_g_km DECIMAL(8,3) NOT NULL,
    predicted_co2_g_km DECIMAL(8,3) NOT NULL,
    prediction_error_g_km DECIMAL(9,3) NOT NULL,
    absolute_error_g_km DECIMAL(9,3) NOT NULL,
    absolute_percentage_error DECIMAL(10,6) NOT NULL,
    predicted_emission_band VARCHAR(12) NOT NULL,
    high_error_flag TINYINT(1) NOT NULL,
    CONSTRAINT fk_prediction_vehicle
        FOREIGN KEY (vehicle_id) REFERENCES vehicle_ratings(vehicle_id)
        ON DELETE CASCADE,
    INDEX idx_prediction_split (data_split),
    INDEX idx_prediction_error (absolute_error_g_km),
    INDEX idx_prediction_model (model_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS model_metrics (
    metric_id INT PRIMARY KEY,
    model_name VARCHAR(80) NOT NULL,
    model_scope VARCHAR(80) NOT NULL,
    split VARCHAR(20) NOT NULL,
    eligible_for_selection TINYINT(1) NOT NULL,
    fit_period VARCHAR(40) NOT NULL,
    mae DECIMAL(12,6) NOT NULL,
    rmse DECIMAL(12,6) NOT NULL,
    mape DECIMAL(12,8) NOT NULL,
    r_squared DECIMAL(12,8) NOT NULL,
    mean_error_pred_minus_actual DECIMAL(12,6) NOT NULL,
    p90_absolute_error DECIMAL(12,6) NOT NULL,
    INDEX idx_metric_scope_split (model_scope, split)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS model_tuning_results (
    tuning_id INT PRIMARY KEY,
    model_name VARCHAR(80) NOT NULL,
    max_depth SMALLINT NULL,
    min_samples_leaf SMALLINT NOT NULL,
    max_features DECIMAL(5,3) NOT NULL,
    n_estimators SMALLINT NOT NULL,
    mae DECIMAL(12,6) NOT NULL,
    rmse DECIMAL(12,6) NOT NULL,
    mape DECIMAL(12,8) NOT NULL,
    r_squared DECIMAL(12,8) NOT NULL,
    mean_error_pred_minus_actual DECIMAL(12,6) NOT NULL,
    p90_absolute_error DECIMAL(12,6) NOT NULL,
    elapsed_seconds DECIMAL(12,3) NOT NULL,
    selected_configuration TINYINT(1) NOT NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS feature_importance (
    importance_id INT PRIMARY KEY,
    model_name VARCHAR(80) NOT NULL,
    feature VARCHAR(80) NOT NULL,
    importance_mean_mae_increase DECIMAL(14,8) NOT NULL,
    importance_std DECIMAL(14,8) NOT NULL,
    UNIQUE KEY uq_feature_model (model_name, feature)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS model_segment_errors (
    segment_error_id INT PRIMARY KEY,
    segment_type VARCHAR(40) NOT NULL,
    segment_value VARCHAR(100) NOT NULL,
    vehicle_records INT NOT NULL,
    average_actual_co2_g_km DECIMAL(12,6) NOT NULL,
    average_predicted_co2_g_km DECIMAL(12,6) NOT NULL,
    mae DECIMAL(12,6) NOT NULL,
    rmse DECIMAL(12,6) NOT NULL,
    mape DECIMAL(12,8) NOT NULL,
    r_squared DECIMAL(12,8) NOT NULL,
    mean_error_pred_minus_actual DECIMAL(12,6) NOT NULL,
    p90_absolute_error DECIMAL(12,6) NOT NULL,
    INDEX idx_segment_error_type (segment_type),
    UNIQUE KEY uq_segment_error (segment_type, segment_value)
) ENGINE=InnoDB;
