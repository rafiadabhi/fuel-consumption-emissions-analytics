"""Validate generated files, model reproducibility, MySQL tables, and views."""

import json
import math

import joblib
import pandas as pd
from sqlalchemy import text

from src.config import (
    DASHBOARD_DIR,
    MODEL_DIR,
    OUTPUT_DIR,
    PROCESSED_FILE,
    RAW_FILE,
    ensure_directories,
)
from src.db import get_engine


REQUIRED_OUTPUTS = [
    PROCESSED_FILE,
    OUTPUT_DIR / "data_audit_report.json",
    OUTPUT_DIR / "model_metadata.json",
    OUTPUT_DIR / "model_metrics.csv",
    OUTPUT_DIR / "model_predictions.csv",
    OUTPUT_DIR / "feature_importance.csv",
    OUTPUT_DIR / "dashboard_kpis.csv",
    OUTPUT_DIR / "results_manifest.csv",
    MODEL_DIR / "selected_co2_model.joblib",
    DASHBOARD_DIR / "app.py",
]


def check(name: str, passed: bool, actual, expected, details: str = "") -> dict:
    return {
        "check": name,
        "status": "PASS" if passed else "FAIL",
        "actual": actual,
        "expected": expected,
        "details": details,
    }


def main() -> None:
    ensure_directories()
    rows = []

    for path in REQUIRED_OUTPUTS:
        rows.append(check(f"file exists: {path.name}", path.exists(), path.exists(), True))

    missing = [str(path) for path in REQUIRED_OUTPUTS if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required outputs: {missing}")

    raw = pd.read_csv(RAW_FILE)
    clean = pd.read_csv(PROCESSED_FILE)
    predictions = pd.read_csv(OUTPUT_DIR / "model_predictions.csv")
    metrics = pd.read_csv(OUTPUT_DIR / "model_metrics.csv")
    kpis = pd.read_csv(OUTPUT_DIR / "dashboard_kpis.csv")
    metadata = json.loads((OUTPUT_DIR / "model_metadata.json").read_text(encoding="utf-8"))

    required_clean = [
        "vehicle_id",
        "model_year",
        "make",
        "vehicle_class",
        "engine_size_l",
        "cylinders",
        "fuel_type",
        "co2_emissions_g_km",
    ]
    rows.extend(
        [
            check("raw rows", len(raw) == 27001, len(raw), 27001),
            check("clean rows", len(clean) == 26998, len(clean), 26998),
            check(
                "exact duplicates removed",
                len(raw) - len(clean) == 3,
                len(raw) - len(clean),
                3,
            ),
            check(
                "unique vehicle IDs",
                clean["vehicle_id"].nunique() == len(clean),
                clean["vehicle_id"].nunique(),
                len(clean),
            ),
            check(
                "required clean values",
                clean[required_clean].isna().sum().sum() == 0,
                int(clean[required_clean].isna().sum().sum()),
                0,
            ),
            check(
                "model years",
                (clean["model_year"].min(), clean["model_year"].max()) == (1995, 2023),
                f"{clean['model_year'].min()}-{clean['model_year'].max()}",
                "1995-2023",
            ),
            check("prediction rows", len(predictions) == len(clean), len(predictions), len(clean)),
            check(
                "prediction IDs",
                predictions["vehicle_id"].nunique() == len(clean),
                predictions["vehicle_id"].nunique(),
                len(clean),
            ),
            check(
                "test rows",
                int((predictions["data_split"] == "test").sum()) == 1758,
                int((predictions["data_split"] == "test").sum()),
                1758,
            ),
            check(
                "finite predictions",
                predictions["predicted_co2_g_km"].map(math.isfinite).all(),
                int(predictions["predicted_co2_g_km"].map(math.isfinite).sum()),
                len(predictions),
            ),
            check("single KPI row", len(kpis) == 1, len(kpis), 1),
        ]
    )

    selected_name = metadata["selected_model"]
    selected_test = metrics.loc[
        (metrics["model_name"] == selected_name)
        & (metrics["model_scope"] == "early_specification")
        & (metrics["split"] == "test")
    ]
    rows.append(check("one selected test metric", len(selected_test) == 1, len(selected_test), 1))
    if len(selected_test) == 1:
        metric = selected_test.iloc[0]
        rows.extend(
            [
                check(
                    "test MAE is better than baseline threshold",
                    float(metric["mae"]) < 50,
                    float(metric["mae"]),
                    "< 50 g/km",
                ),
                check(
                    "test R-squared bounded",
                    -1 <= float(metric["r_squared"]) <= 1,
                    float(metric["r_squared"]),
                    "between -1 and 1",
                ),
                check(
                    "KPI MAE matches metrics",
                    abs(float(kpis.iloc[0]["test_mae_g_km"]) - float(metric["mae"])) < 1e-8,
                    float(kpis.iloc[0]["test_mae_g_km"]),
                    float(metric["mae"]),
                ),
            ]
        )

    model = joblib.load(MODEL_DIR / "selected_co2_model.joblib")
    sample = clean.head(25)
    reconstructed = model.predict(sample[metadata["model_features"]])
    stored = (
        predictions.set_index("vehicle_id")
        .loc[sample["vehicle_id"], "predicted_co2_g_km"]
        .to_numpy()
    )
    max_difference = float(abs(reconstructed - stored).max())
    rows.append(
        check(
            "serialized model reproduces predictions",
            max_difference <= 0.00051,
            max_difference,
            "<= 0.00051 g/km (CSV rounding)",
        )
    )

    with get_engine().connect() as connection:
        mysql_summary = {
            "vehicle_ratings": int(
                connection.execute(text("SELECT COUNT(*) FROM vehicle_ratings")).scalar_one()
            ),
            "model_predictions": int(
                connection.execute(text("SELECT COUNT(*) FROM model_predictions")).scalar_one()
            ),
            "model_segment_errors": int(
                connection.execute(text("SELECT COUNT(*) FROM model_segment_errors")).scalar_one()
            ),
            "detail_view": int(
                connection.execute(
                    text("SELECT COUNT(*) FROM vw_dashboard_vehicle_detail")
                ).scalar_one()
            ),
            "yearly_view": int(
                connection.execute(
                    text("SELECT COUNT(*) FROM vw_dashboard_yearly_trend")
                ).scalar_one()
            ),
            "kpi_view": int(
                connection.execute(text("SELECT COUNT(*) FROM vw_dashboard_kpis")).scalar_one()
            ),
            "dashboard_prediction_sample": int(
                connection.execute(
                    text(
                        "SELECT co2_emissions_g_km AS actual_co2_g_km, "
                        "predicted_co2_g_km, absolute_error_g_km "
                        "FROM vw_dashboard_vehicle_detail "
                        "WHERE model_split = 'test' LIMIT 1"
                    )
                ).first()
                is not None
            ),
        }
    rows.extend(
        [
            check(
                "MySQL vehicle rows",
                mysql_summary["vehicle_ratings"] == len(clean),
                mysql_summary["vehicle_ratings"],
                len(clean),
            ),
            check(
                "MySQL prediction rows",
                mysql_summary["model_predictions"] == len(clean),
                mysql_summary["model_predictions"],
                len(clean),
            ),
            check(
                "MySQL segment-error rows",
                mysql_summary["model_segment_errors"] > 0,
                mysql_summary["model_segment_errors"],
                "> 0",
            ),
            check(
                "MySQL detail view rows",
                mysql_summary["detail_view"] == len(clean),
                mysql_summary["detail_view"],
                len(clean),
            ),
            check("MySQL yearly rows", mysql_summary["yearly_view"] == 29, mysql_summary["yearly_view"], 29),
            check("MySQL KPI rows", mysql_summary["kpi_view"] == 1, mysql_summary["kpi_view"], 1),
            check(
                "dashboard prediction query",
                mysql_summary["dashboard_prediction_sample"] == 1,
                mysql_summary["dashboard_prediction_sample"],
                1,
            ),
        ]
    )

    report = pd.DataFrame(rows)
    report.to_csv(OUTPUT_DIR / "validation_checks.csv", index=False)
    failures = report.loc[report["status"] == "FAIL", "check"].tolist()
    payload = {
        "status": "PASS" if not failures else "FAIL",
        "checks_run": int(len(report)),
        "checks_passed": int((report["status"] == "PASS").sum()),
        "checks_failed": int(len(failures)),
        "failed_checks": failures,
        "mysql_summary": mysql_summary,
        "note": "Generated files, model reproduction, MySQL tables, and dashboard views were validated.",
    }
    (OUTPUT_DIR / "validation_report.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    print(report.to_string(index=False))
    print(json.dumps(payload, indent=2))
    if failures:
        raise AssertionError(f"Validation failed: {failures}")


if __name__ == "__main__":
    main()
