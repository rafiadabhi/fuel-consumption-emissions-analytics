"""Create the MySQL analytical layer and load the Python-cleaned vehicle table."""

import json
import time

import pandas as pd
from sqlalchemy import text

from src.config import PROCESSED_FILE, SQL_DIR, ensure_directories
from src.db import create_database_if_needed, execute_sql_file, get_engine, test_connection


FACT_COLUMNS = [
    "vehicle_id",
    "source_row_number",
    "model_year",
    "make",
    "model",
    "vehicle_class_raw",
    "vehicle_class",
    "engine_size_l",
    "cylinders",
    "transmission",
    "transmission_family_code",
    "gear_count",
    "fuel_type_code",
    "fuel_cons_city_l_100km",
    "fuel_cons_hwy_l_100km",
    "fuel_cons_comb_l_100km",
    "fuel_economy_comb_mpg",
    "co2_emissions_g_km",
    "co2_rating",
    "smog_rating",
    "city_hwy_gap_l_100km",
    "city_hwy_ratio",
    "co2_per_comb_l",
    "engine_size_band",
    "class_year_co2_median",
    "class_year_co2_p25",
    "co2_vs_class_year_median",
    "co2_gap_to_class_p25",
    "above_class_year_median",
    "city_below_highway_flag",
    "emission_band",
    "model_split",
]


def main() -> None:
    ensure_directories()
    started = time.time()
    if not PROCESSED_FILE.exists():
        raise FileNotFoundError(
            f"Missing cleaned data: {PROCESSED_FILE}. Run python -m src.01_audit_clean first."
        )

    create_database_if_needed()
    version = test_connection()
    print(f"Connected to MySQL {version}")
    execute_sql_file(SQL_DIR / "01_schema.sql")

    frame = pd.read_csv(PROCESSED_FILE)
    missing_columns = sorted(set(FACT_COLUMNS) - set(frame.columns))
    if missing_columns:
        raise ValueError(f"Cleaned data is missing MySQL columns: {missing_columns}")

    fact = frame[FACT_COLUMNS].copy()
    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        connection.execute(text("TRUNCATE TABLE model_predictions"))
        connection.execute(text("TRUNCATE TABLE model_metrics"))
        connection.execute(text("TRUNCATE TABLE model_tuning_results"))
        connection.execute(text("TRUNCATE TABLE feature_importance"))
        connection.execute(text("TRUNCATE TABLE model_segment_errors"))
        connection.execute(text("TRUNCATE TABLE vehicle_ratings"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    fact.to_sql(
        "vehicle_ratings",
        engine,
        if_exists="append",
        index=False,
        chunksize=750,
        method="multi",
    )

    with engine.connect() as connection:
        database_rows = connection.execute(
            text("SELECT COUNT(*) FROM vehicle_ratings")
        ).scalar_one()
        unique_ids = connection.execute(
            text("SELECT COUNT(DISTINCT vehicle_id) FROM vehicle_ratings")
        ).scalar_one()
        invalid_rows = connection.execute(
            text(
                "SELECT COUNT(*) FROM vehicle_ratings "
                "WHERE co2_emissions_g_km <= 0 OR engine_size_l <= 0 OR cylinders <= 0"
            )
        ).scalar_one()

    if database_rows != len(fact) or unique_ids != len(fact) or invalid_rows != 0:
        raise AssertionError(
            "MySQL load validation failed: "
            f"source={len(fact)}, rows={database_rows}, ids={unique_ids}, invalid={invalid_rows}"
        )

    result = {
        "mysql_version": version,
        "loaded_rows": int(database_rows),
        "unique_vehicle_ids": int(unique_ids),
        "invalid_required_rows": int(invalid_rows),
        "elapsed_seconds": round(time.time() - started, 2),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
