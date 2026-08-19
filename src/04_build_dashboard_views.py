"""Create and validate the MySQL views used by Streamlit."""

import json

from sqlalchemy import text

from src.config import SQL_DIR
from src.db import execute_sql_file, get_engine


EXPECTED_VIEWS = {
    "vw_dashboard_vehicle_detail": 26998,
    "vw_dashboard_yearly_trend": 29,
    "vw_dashboard_class_benchmark": None,
    "vw_dashboard_make_benchmark": None,
    "vw_dashboard_model_performance": None,
    "vw_dashboard_feature_importance": None,
    "vw_dashboard_high_emission_opportunities": None,
    "vw_dashboard_test_segment_errors": None,
    "vw_dashboard_kpis": 1,
}


def main() -> None:
    execute_sql_file(SQL_DIR / "02_reporting_views.sql")
    counts = {}
    with get_engine().connect() as connection:
        for view_name, exact_expected in EXPECTED_VIEWS.items():
            count = int(
                connection.execute(text(f"SELECT COUNT(*) FROM `{view_name}`")).scalar_one()
            )
            if exact_expected is not None and count != exact_expected:
                raise AssertionError(
                    f"{view_name} has {count} rows; expected {exact_expected}."
                )
            counts[view_name] = count

        missing_predictions = int(
            connection.execute(
                text(
                    "SELECT COUNT(*) FROM vw_dashboard_vehicle_detail "
                    "WHERE predicted_co2_g_km IS NULL"
                )
            ).scalar_one()
        )

    if missing_predictions:
        raise AssertionError(
            f"Dashboard detail view has {missing_predictions} rows without predictions."
        )
    if counts["vw_dashboard_test_segment_errors"] == 0:
        raise AssertionError("Dashboard segment-error view is empty.")

    print(json.dumps({"view_rows": counts, "missing_predictions": 0}, indent=2))


if __name__ == "__main__":
    main()
