import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.config import MODEL_DIR, OUTPUT_DIR, ensure_directories
from src.db import get_engine


TARGET = "co2_emissions_g_km"
NUMERIC_FEATURES = ["model_year", "engine_size_l", "cylinders", "gear_count"]
CATEGORICAL_FEATURES = [
    "make",
    "vehicle_class",
    "transmission_family",
    "fuel_type",
]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

MEASUREMENT_FEATURES = NUMERIC_FEATURES + [
    "fuel_cons_city_l_100km",
    "fuel_cons_hwy_l_100km",
    "fuel_cons_comb_l_100km",
    "fuel_economy_comb_mpg",
] + CATEGORICAL_FEATURES

RF_GRID = [
    {"max_depth": 14, "min_samples_leaf": 1, "max_features": 0.7},
    {"max_depth": 18, "min_samples_leaf": 1, "max_features": 0.7},
    {"max_depth": None, "min_samples_leaf": 1, "max_features": 0.7},
    {"max_depth": None, "min_samples_leaf": 1, "max_features": 1.0},
]


def load_vehicles() -> pd.DataFrame:
    """Read the modeling table from MySQL; there is no CSV fallback by design."""
    query = """
        SELECT
            v.*,
            f.fuel_type_name AS fuel_type,
            t.transmission_family_name AS transmission_family
        FROM vehicle_ratings AS v
        JOIN fuel_type_lookup AS f USING (fuel_type_code)
        JOIN transmission_family_lookup AS t USING (transmission_family_code)
    """
    frame = pd.read_sql(query, get_engine())

    numeric_columns = [
        "vehicle_id",
        "model_year",
        "engine_size_l",
        "cylinders",
        "gear_count",
        "fuel_cons_city_l_100km",
        "fuel_cons_hwy_l_100km",
        "fuel_cons_comb_l_100km",
        "fuel_economy_comb_mpg",
        "co2_emissions_g_km",
        "co2_gap_to_class_p25",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    return frame


def split_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "train": frame["model_year"] <= 2019,
        "validation": frame["model_year"].between(2020, 2021),
        "development": frame["model_year"] <= 2021,
        "test": frame["model_year"] >= 2022,
    }


def build_preprocessor(numeric_features=None, categorical_features=None) -> ColumnTransformer:
    numeric_features = numeric_features or NUMERIC_FEATURES
    categorical_features = categorical_features or CATEGORICAL_FEATURES
    numeric = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "one_hot",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )
    return ColumnTransformer(
        [
            ("numeric", numeric, numeric_features),
            ("categorical", categorical, categorical_features),
        ]
    )


def regression_metrics(actual, predicted) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    errors = predicted - actual
    absolute_errors = np.abs(errors)
    return {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "mape": float(mean_absolute_percentage_error(actual, predicted)),
        "r_squared": float(r2_score(actual, predicted)),
        "mean_error_pred_minus_actual": float(errors.mean()),
        "p90_absolute_error": float(np.quantile(absolute_errors, 0.90)),
    }


def metric_row(
    model_name: str,
    model_scope: str,
    split: str,
    actual,
    predicted,
    eligible_for_selection: bool,
    fit_period: str,
) -> dict:
    return {
        "model_name": model_name,
        "model_scope": model_scope,
        "split": split,
        "eligible_for_selection": int(eligible_for_selection),
        "fit_period": fit_period,
        **regression_metrics(actual, predicted),
    }


def build_standard_candidates() -> dict[str, Pipeline]:
    return {
        "Median Baseline": Pipeline(
            [
                ("preprocessor", build_preprocessor()),
                ("model", DummyRegressor(strategy="median")),
            ]
        ),
        "Ridge Regression": Pipeline(
            [
                ("preprocessor", build_preprocessor()),
                ("model", Ridge(alpha=10.0)),
            ]
        ),
        "Hist Gradient Boosting": Pipeline(
            [
                ("preprocessor", build_preprocessor()),
                (
                    "model",
                    HistGradientBoostingRegressor(
                        max_iter=250,
                        learning_rate=0.05,
                        max_leaf_nodes=31,
                        min_samples_leaf=20,
                        l2_regularization=1.0,
                        random_state=42,
                    ),
                ),
            ]
        ),
    }


def tune_random_forest(
    frame: pd.DataFrame,
    train_mask: pd.Series,
    validation_mask: pd.Series,
) -> tuple[dict, pd.DataFrame, np.ndarray]:
    preprocessor = build_preprocessor()
    train_x = preprocessor.fit_transform(frame.loc[train_mask, MODEL_FEATURES])
    validation_x = preprocessor.transform(frame.loc[validation_mask, MODEL_FEATURES])
    train_y = frame.loc[train_mask, TARGET]
    validation_y = frame.loc[validation_mask, TARGET]
    rows = []
    predictions = {}

    for tuning_id, parameters in enumerate(RF_GRID, start=1):
        started = time.time()
        model = RandomForestRegressor(
            n_estimators=300,
            n_jobs=-1,
            random_state=42,
            **parameters,
        )
        model.fit(train_x, train_y)
        predicted = model.predict(validation_x)
        metrics = regression_metrics(validation_y, predicted)
        rows.append(
            {
                "tuning_id": tuning_id,
                "model_name": "Random Forest",
                "max_depth": parameters["max_depth"],
                "min_samples_leaf": parameters["min_samples_leaf"],
                "max_features": parameters["max_features"],
                "n_estimators": 300,
                **metrics,
                "elapsed_seconds": round(time.time() - started, 3),
            }
        )
        predictions[tuning_id] = predicted

    tuning = pd.DataFrame(rows).sort_values(["mae", "rmse"]).reset_index(drop=True)
    best_id = int(tuning.iloc[0]["tuning_id"])
    best_parameters = RF_GRID[best_id - 1].copy()
    best_parameters["n_estimators"] = 300
    return best_parameters, tuning, predictions[best_id]


def build_selected_pipeline(model_name: str, best_rf_parameters: dict) -> Pipeline:
    if model_name == "Random Forest (Tuned)":
        model = RandomForestRegressor(
            n_jobs=-1,
            random_state=42,
            **best_rf_parameters,
        )
    elif model_name == "Ridge Regression":
        model = Ridge(alpha=10.0)
    elif model_name == "Hist Gradient Boosting":
        model = HistGradientBoostingRegressor(
            max_iter=250,
            learning_rate=0.05,
            max_leaf_nodes=31,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=42,
        )
    else:
        model = DummyRegressor(strategy="median")
    return Pipeline([("preprocessor", build_preprocessor()), ("model", model)])


def build_segment_errors(test_frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for segment_type, column in {
        "Model Year": "model_year",
        "Vehicle Class": "vehicle_class",
        "Fuel Type": "fuel_type",
        "Engine Size Band": "engine_size_band",
    }.items():
        for segment_value, group in test_frame.groupby(column, observed=True):
            metrics = regression_metrics(
                group["actual_co2_g_km"], group["predicted_co2_g_km"]
            )
            rows.append(
                {
                    "segment_type": segment_type,
                    "segment_value": str(segment_value),
                    "vehicle_records": int(len(group)),
                    "average_actual_co2_g_km": float(group["actual_co2_g_km"].mean()),
                    "average_predicted_co2_g_km": float(group["predicted_co2_g_km"].mean()),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def write_model_tables_to_mysql(
    predictions: pd.DataFrame,
    metrics: pd.DataFrame,
    tuning: pd.DataFrame,
    feature_importance: pd.DataFrame,
    segment_errors: pd.DataFrame,
) -> None:
    from sqlalchemy import text

    engine = get_engine()
    with engine.begin() as connection:
        connection.execute(
            text(
                "SET FOREIGN_KEY_CHECKS=0;"
            )
        )
        connection.execute(text("TRUNCATE TABLE model_predictions"))
        connection.execute(text("TRUNCATE TABLE model_metrics"))
        connection.execute(text("TRUNCATE TABLE model_tuning_results"))
        connection.execute(text("TRUNCATE TABLE feature_importance"))
        connection.execute(text("TRUNCATE TABLE model_segment_errors"))
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    predictions.to_sql(
        "model_predictions",
        engine,
        if_exists="append",
        index=False,
        chunksize=1000,
        method="multi",
    )
    metrics.to_sql("model_metrics", engine, if_exists="append", index=False, method="multi")
    tuning.to_sql(
        "model_tuning_results", engine, if_exists="append", index=False, method="multi"
    )
    feature_importance.to_sql(
        "feature_importance", engine, if_exists="append", index=False, method="multi"
    )
    mysql_segment_errors = segment_errors.copy()
    mysql_segment_errors.insert(
        0, "segment_error_id", np.arange(1, len(mysql_segment_errors) + 1)
    )
    mysql_segment_errors.to_sql(
        "model_segment_errors", engine, if_exists="append", index=False, method="multi"
    )


def main() -> None:
    ensure_directories()
    started = time.time()

    frame = load_vehicles()
    masks = split_masks(frame)
    split_summary = {
        name: {
            "rows": int(mask.sum()),
            "year_min": int(frame.loc[mask, "model_year"].min()),
            "year_max": int(frame.loc[mask, "model_year"].max()),
            "average_target": float(frame.loc[mask, TARGET].mean()),
        }
        for name, mask in masks.items()
    }

    metrics_rows = []
    validation_predictions = {}
    for model_name, model in build_standard_candidates().items():
        print(f"Training {model_name}...")
        model.fit(frame.loc[masks["train"], MODEL_FEATURES], frame.loc[masks["train"], TARGET])
        predicted = model.predict(frame.loc[masks["validation"], MODEL_FEATURES])
        validation_predictions[model_name] = predicted
        metrics_rows.append(
            metric_row(
                model_name,
                "early_specification",
                "validation",
                frame.loc[masks["validation"], TARGET],
                predicted,
                True,
                "1995-2019",
            )
        )

    print("Tuning Random Forest on the 2020-2021 validation period...")
    best_rf_parameters, tuning, rf_validation_prediction = tune_random_forest(
        frame, masks["train"], masks["validation"]
    )
    metrics_rows.append(
        metric_row(
            "Random Forest (Tuned)",
            "early_specification",
            "validation",
            frame.loc[masks["validation"], TARGET],
            rf_validation_prediction,
            True,
            "1995-2019",
        )
    )

    validation_metrics = pd.DataFrame(metrics_rows)
    selected_model_name = validation_metrics.sort_values(["mae", "rmse"]).iloc[0][
        "model_name"
    ]
    print(f"Selected by validation MAE: {selected_model_name}")

    selected_model = build_selected_pipeline(selected_model_name, best_rf_parameters)
    selected_model.fit(
        frame.loc[masks["development"], MODEL_FEATURES],
        frame.loc[masks["development"], TARGET],
    )
    test_prediction = selected_model.predict(frame.loc[masks["test"], MODEL_FEATURES])
    metrics_rows.append(
        metric_row(
            selected_model_name,
            "early_specification",
            "test",
            frame.loc[masks["test"], TARGET],
            test_prediction,
            True,
            "1995-2021 refit",
        )
    )

    baseline_test = Pipeline(
        [
            ("preprocessor", build_preprocessor()),
            ("model", DummyRegressor(strategy="median")),
        ]
    )
    baseline_test.fit(
        frame.loc[masks["development"], MODEL_FEATURES],
        frame.loc[masks["development"], TARGET],
    )
    baseline_test_prediction = baseline_test.predict(frame.loc[masks["test"], MODEL_FEATURES])
    metrics_rows.append(
        metric_row(
            "Median Baseline",
            "early_specification",
            "test",
            frame.loc[masks["test"], TARGET],
            baseline_test_prediction,
            False,
            "1995-2021 refit",
        )
    )

    print("Training measurement-rich diagnostic model (not eligible for selection)...")
    rich_numeric = NUMERIC_FEATURES + [
        "fuel_cons_city_l_100km",
        "fuel_cons_hwy_l_100km",
        "fuel_cons_comb_l_100km",
        "fuel_economy_comb_mpg",
    ]
    rich_model = Pipeline(
        [
            (
                "preprocessor",
                build_preprocessor(rich_numeric, CATEGORICAL_FEATURES),
            ),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=300,
                    max_depth=18,
                    min_samples_leaf=1,
                    max_features=0.9,
                    n_jobs=-1,
                    random_state=42,
                ),
            ),
        ]
    )
    rich_model.fit(
        frame.loc[masks["development"], MEASUREMENT_FEATURES],
        frame.loc[masks["development"], TARGET],
    )
    rich_test_prediction = rich_model.predict(frame.loc[masks["test"], MEASUREMENT_FEATURES])
    metrics_rows.append(
        metric_row(
            "Measurement-Rich RF (Diagnostic)",
            "measurement_rich_circular_diagnostic",
            "test",
            frame.loc[masks["test"], TARGET],
            rich_test_prediction,
            False,
            "1995-2021 refit",
        )
    )

    metrics = pd.DataFrame(metrics_rows)
    metrics.insert(0, "metric_id", np.arange(1, len(metrics) + 1))
    tuning = tuning.copy()
    tuning["selected_configuration"] = (
        tuning["tuning_id"] == tuning.iloc[0]["tuning_id"]
    ).astype("int8")

    all_prediction = selected_model.predict(frame[MODEL_FEATURES])
    predictions = frame[
        [
            "vehicle_id",
            "model_year",
            "make",
            "model",
            "vehicle_class",
            "engine_size_band",
            "fuel_type",
            "model_split",
            TARGET,
        ]
    ].copy()
    predictions = predictions.rename(
        columns={TARGET: "actual_co2_g_km", "model_split": "data_split"}
    )
    predictions["model_name"] = selected_model_name
    predictions["predicted_co2_g_km"] = np.round(all_prediction, 3)
    predictions["prediction_error_g_km"] = np.round(
        predictions["predicted_co2_g_km"] - predictions["actual_co2_g_km"], 3
    )
    predictions["absolute_error_g_km"] = predictions["prediction_error_g_km"].abs()
    predictions["absolute_percentage_error"] = np.round(
        predictions["absolute_error_g_km"] / predictions["actual_co2_g_km"], 6
    )
    predictions["predicted_emission_band"] = pd.cut(
        predictions["predicted_co2_g_km"],
        bins=[-np.inf, 200, 250, 300, 350, np.inf],
        right=False,
        labels=["<200", "200-249", "250-299", "300-349", "350+"],
    ).astype("string")
    test_p90 = float(
        predictions.loc[predictions["data_split"] == "test", "absolute_error_g_km"].quantile(0.90)
    )
    predictions["high_error_flag"] = (
        predictions["absolute_error_g_km"] >= test_p90
    ).astype("int8")

    test_frame = predictions.loc[predictions["data_split"] == "test"].copy()
    importance = permutation_importance(
        selected_model,
        frame.loc[masks["test"], MODEL_FEATURES],
        frame.loc[masks["test"], TARGET],
        scoring="neg_mean_absolute_error",
        n_repeats=8,
        random_state=42,
        # Keep the diagnostic single-process on Windows to avoid Joblib
        # memmapping the test matrix into a space-constrained temp directory.
        n_jobs=1,
    )
    feature_importance = pd.DataFrame(
        {
            "feature": MODEL_FEATURES,
            "importance_mean_mae_increase": importance.importances_mean,
            "importance_std": importance.importances_std,
        }
    ).sort_values("importance_mean_mae_increase", ascending=False)
    feature_importance.insert(0, "model_name", selected_model_name)
    feature_importance.insert(0, "importance_id", np.arange(1, len(feature_importance) + 1))

    segment_errors = build_segment_errors(test_frame)
    test_metrics = metrics.loc[
        (metrics["model_name"] == selected_model_name)
        & (metrics["split"] == "test")
        & (metrics["model_scope"] == "early_specification")
    ].iloc[0]
    diagnostic_metrics = metrics.loc[
        metrics["model_name"] == "Measurement-Rich RF (Diagnostic)"
    ].iloc[0]

    metadata = {
        "final_title": "Fuel Consumption & Emissions Analytics",
        "target": "rated tailpipe CO2 emissions (g/km)",
        "primary_use_case": "early-specification prediction without measured fuel-consumption outputs",
        "selected_model": selected_model_name,
        "selection_rule": "minimum 2020-2021 validation MAE, RMSE as tie-breaker",
        "selected_random_forest_parameters": best_rf_parameters,
        "model_features": MODEL_FEATURES,
        "excluded_measurement_and_target_derived_features": [
            "fuel_cons_city_l_100km",
            "fuel_cons_hwy_l_100km",
            "fuel_cons_comb_l_100km",
            "fuel_economy_comb_mpg",
            "co2_rating",
            "smog_rating",
            "class-year CO2 benchmarks",
        ],
        "split_summary": split_summary,
        "test_metrics": {
            key: float(test_metrics[key])
            for key in [
                "mae",
                "rmse",
                "mape",
                "r_squared",
                "mean_error_pred_minus_actual",
                "p90_absolute_error",
            ]
        },
        "test_prediction_range": {
            "minimum": float(test_frame["predicted_co2_g_km"].min()),
            "maximum": float(test_frame["predicted_co2_g_km"].max()),
        },
        "measurement_rich_diagnostic": {
            "mae": float(diagnostic_metrics["mae"]),
            "r_squared": float(diagnostic_metrics["r_squared"]),
            "interpretation": "Near-perfect performance is circular for the early-specification use case and is not the selected model.",
        },
        "limitations": [
            "Predictions estimate published rated tailpipe CO2, not real-world or lifecycle emissions.",
            "Manufacturer effects may reflect historical product mix rather than causal engineering quality.",
            "No vehicle weight, power, drivetrain, electrification flag, sales count, or distance field is supplied.",
            "The 2022-2023 test set measures temporal generalization only for the supplied Canadian ratings data.",
        ],
        "elapsed_seconds": round(time.time() - started, 2),
    }

    predictions.to_csv(OUTPUT_DIR / "model_predictions.csv", index=False)
    metrics.to_csv(OUTPUT_DIR / "model_metrics.csv", index=False)
    tuning.to_csv(OUTPUT_DIR / "model_tuning_results.csv", index=False)
    feature_importance.to_csv(OUTPUT_DIR / "feature_importance.csv", index=False)
    segment_errors.to_csv(OUTPUT_DIR / "model_segment_errors.csv", index=False)
    (OUTPUT_DIR / "model_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    joblib.dump(
        selected_model,
        MODEL_DIR / "selected_co2_model.joblib",
        compress=3,
    )

    mysql_prediction_columns = [
        "vehicle_id",
        "data_split",
        "model_name",
        "actual_co2_g_km",
        "predicted_co2_g_km",
        "prediction_error_g_km",
        "absolute_error_g_km",
        "absolute_percentage_error",
        "predicted_emission_band",
        "high_error_flag",
    ]
    write_model_tables_to_mysql(
        predictions[mysql_prediction_columns],
        metrics,
        tuning,
        feature_importance,
        segment_errors,
    )

    print(json.dumps(metadata, indent=2))
    print(metrics.to_string(index=False))
    print(f"Saved model outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
