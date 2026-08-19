import hashlib
import json
import re
import time

import numpy as np
import pandas as pd

from src.config import OUTPUT_DIR, PROCESSED_FILE, RAW_FILE, ensure_directories


COLUMN_MAP = {
    "ModelYear": "model_year",
    "Make": "make",
    "Model": "model",
    "VehicleClass": "vehicle_class_raw",
    "EngineSize_L": "engine_size_l",
    "Cylinders": "cylinders",
    "Transmission": "transmission",
    "FuelType": "fuel_type_code",
    "FuelConsCity_L100km": "fuel_cons_city_l_100km",
    "FuelConsHwy_L100km": "fuel_cons_hwy_l_100km",
    "Comb_L100km": "fuel_cons_comb_l_100km",
    "Comb_mpg": "fuel_economy_comb_mpg",
    "CO2Emission_g_km": "co2_emissions_g_km",
    "CO2Rating": "co2_rating",
    "SmogRating": "smog_rating",
}

FUEL_TYPES = {
    "X": "Regular Gasoline",
    "Z": "Premium Gasoline",
    "D": "Diesel",
    "E": "E85",
    "N": "Natural Gas",
}

TRANSMISSION_FAMILIES = {
    "A": "Automatic",
    "AS": "Automatic with Select Shift",
    "AM": "Automated Manual",
    "AV": "Continuously Variable",
    "M": "Manual",
}

VEHICLE_CLASS_MAP = {
    "COMPACT": "COMPACT",
    "FULL SIZE": "FULL-SIZE",
    "MID SIZE": "MID-SIZE",
    "MINICOMPACT": "MINICOMPACT",
    "MINIVAN": "MINIVAN",
    "PICKUP TRUCK SMALL": "PICKUP TRUCK - SMALL",
    "PICKUP TRUCK STANDARD": "PICKUP TRUCK - STANDARD",
    "SPECIAL PURPOSE VEHICLE": "SPECIAL PURPOSE VEHICLE",
    "STATION WAGON MID SIZE": "STATION WAGON - MID-SIZE",
    "STATION WAGON SMALL": "STATION WAGON - SMALL",
    "SUBCOMPACT": "SUBCOMPACT",
    "SUV": "SUV - UNSPECIFIED",
    "SUV SMALL": "SUV - SMALL",
    "SUV STANDARD": "SUV - STANDARD",
    "TWO SEATER": "TWO-SEATER",
    "VAN CARGO": "VAN - CARGO",
    "VAN PASSENGER": "VAN - PASSENGER",
    "UL": "OTHER / UNCLASSIFIED",
}


def normalize_text(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
        .str.upper()
    )


def normalize_vehicle_class(value: str) -> str:
    key = re.sub(r"[^A-Z0-9]+", " ", str(value).strip().upper()).strip()
    if key not in VEHICLE_CLASS_MAP:
        raise ValueError(f"Unmapped vehicle class: {value!r} (normalized key {key!r})")
    return VEHICLE_CLASS_MAP[key]


def sha256(path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_profile(frame: pd.DataFrame) -> dict:
    result = {}
    for column in frame.select_dtypes(include="number"):
        values = frame[column].dropna()
        result[column] = {
            "count": int(values.size),
            "min": float(values.min()) if not values.empty else None,
            "max": float(values.max()) if not values.empty else None,
            "mean": float(values.mean()) if not values.empty else None,
            "median": float(values.median()) if not values.empty else None,
        }
    return result


def iqr_outlier_profile(frame: pd.DataFrame, columns: list[str]) -> dict:
    result = {}
    for column in columns:
        values = frame[column].dropna()
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        result[column] = {
            "count": int(((values < lower) | (values > upper)).sum()),
            "lower_bound": float(lower),
            "upper_bound": float(upper),
        }
    return result


def fuel_relationships(frame: pd.DataFrame) -> dict:
    relationships = {}
    for fuel_code, group in frame.groupby("fuel_type_code"):
        x = group["fuel_cons_comb_l_100km"].to_numpy(dtype=float)
        y = group["co2_emissions_g_km"].to_numpy(dtype=float)
        slope, intercept = np.polyfit(x, y, 1)
        prediction = slope * x + intercept
        r_squared = 1 - np.square(y - prediction).sum() / np.square(y - y.mean()).sum()
        relationships[str(fuel_code)] = {
            "rows": int(len(group)),
            "slope": float(slope),
            "intercept": float(intercept),
            "r_squared": float(r_squared),
        }
    return relationships


def make_data_dictionary() -> pd.DataFrame:
    rows = [
        ("vehicle_id", "Integer", "Deterministic surrogate key after duplicate removal", "Identifier"),
        ("source_row_number", "Integer", "Original CSV row number including the header offset", "Audit"),
        ("model_year", "Integer", "Vehicle model year", "Feature / time split"),
        ("make", "Text", "Uppercase manufacturer name", "Feature / segment"),
        ("model", "Text", "Uppercase vehicle model/configuration label", "Reporting only"),
        ("vehicle_class_raw", "Text", "Vehicle class exactly as supplied", "Audit"),
        ("vehicle_class", "Category", "Canonical vehicle class across historical naming changes", "Feature / segment"),
        ("engine_size_l", "Decimal", "Engine displacement in litres", "Feature"),
        ("cylinders", "Integer", "Number of engine cylinders", "Feature"),
        ("transmission", "Text", "Original transmission code", "Source field"),
        ("transmission_family_code", "Category", "A, AS, AM, AV, or M code family", "Database key / feature"),
        ("transmission_family", "Category", "Readable transmission family", "Feature / segment"),
        ("gear_count", "Integer", "Number of gears; 0 means no discrete count for CVT", "Feature"),
        ("fuel_type_code", "Category", "X, Z, D, E, or N fuel code", "Database key"),
        ("fuel_type", "Category", "Readable fuel type", "Feature / segment"),
        ("fuel_cons_city_l_100km", "Decimal", "Rated city fuel consumption, L/100 km", "Measured outcome / analysis"),
        ("fuel_cons_hwy_l_100km", "Decimal", "Rated highway fuel consumption, L/100 km", "Measured outcome / analysis"),
        ("fuel_cons_comb_l_100km", "Decimal", "Rated combined fuel consumption, L/100 km", "Measured outcome / leakage-excluded"),
        ("fuel_economy_comb_mpg", "Integer", "Rated combined fuel economy, miles per gallon", "Derived source measure / leakage-excluded"),
        ("co2_emissions_g_km", "Integer", "Rated tailpipe CO2 emissions in grams per kilometre", "Regression target"),
        ("co2_rating", "Nullable integer", "CO2 rating supplied from model year 2016 onward", "Reporting only"),
        ("smog_rating", "Nullable integer", "Smog rating supplied from model year 2017 onward", "Reporting only"),
        ("city_hwy_gap_l_100km", "Decimal", "City minus highway fuel consumption", "Engineered analysis"),
        ("city_hwy_ratio", "Decimal", "City divided by highway fuel consumption", "Engineered analysis"),
        ("co2_per_comb_l", "Decimal", "CO2 g/km divided by combined L/100 km", "Diagnostic only"),
        ("engine_size_band", "Category", "Readable engine-displacement band", "Dashboard segment"),
        ("class_year_co2_median", "Decimal", "Median CO2 for the same model year and class", "Peer benchmark"),
        ("class_year_co2_p25", "Decimal", "25th percentile CO2 for the same model year and class", "Peer benchmark"),
        ("co2_vs_class_year_median", "Decimal", "Vehicle CO2 minus class-year median", "Peer benchmark"),
        ("co2_gap_to_class_p25", "Decimal", "Positive gap to class-year 25th percentile", "Scenario input; not guaranteed reduction"),
        ("above_class_year_median", "Binary", "1 when CO2 exceeds the class-year median", "Dashboard flag"),
        ("city_below_highway_flag", "Binary", "1 when rated city use is below highway use", "Data-quality/technology flag"),
        ("emission_band", "Category", "Descriptive CO2 band; not a regulatory rating", "Dashboard segment"),
        ("model_split", "Category", "Train, validation, or test period", "Evaluation"),
    ]
    return pd.DataFrame(rows, columns=["field", "data_type", "definition", "analytical_role"])


def build_aggregates(clean: pd.DataFrame) -> None:
    yearly = (
        clean.groupby("model_year", as_index=False)
        .agg(
            vehicle_records=("vehicle_id", "count"),
            average_co2_g_km=("co2_emissions_g_km", "mean"),
            median_co2_g_km=("co2_emissions_g_km", "median"),
            average_combined_l_100km=("fuel_cons_comb_l_100km", "mean"),
            average_engine_size_l=("engine_size_l", "mean"),
            average_peer_gap_g_km=("co2_gap_to_class_p25", "mean"),
        )
        .sort_values("model_year")
    )
    yearly["co2_yoy_change_pct"] = yearly["average_co2_g_km"].pct_change()
    yearly["co2_change_vs_1995_pct"] = (
        yearly["average_co2_g_km"] / yearly.loc[yearly["model_year"] == 1995, "average_co2_g_km"].iloc[0] - 1
    )
    yearly.to_csv(OUTPUT_DIR / "yearly_trend.csv", index=False)

    class_year = (
        clean.groupby(["model_year", "vehicle_class"], as_index=False)
        .agg(
            vehicle_records=("vehicle_id", "count"),
            average_co2_g_km=("co2_emissions_g_km", "mean"),
            median_co2_g_km=("co2_emissions_g_km", "median"),
            p25_co2_g_km=("co2_emissions_g_km", lambda values: values.quantile(0.25)),
            average_combined_l_100km=("fuel_cons_comb_l_100km", "mean"),
            average_engine_size_l=("engine_size_l", "mean"),
            average_peer_gap_g_km=("co2_gap_to_class_p25", "mean"),
        )
        .sort_values(["model_year", "average_co2_g_km"], ascending=[True, False])
    )
    class_year.to_csv(OUTPUT_DIR / "class_year_benchmark.csv", index=False)

    make_year = (
        clean.groupby(["model_year", "make"], as_index=False)
        .agg(
            vehicle_records=("vehicle_id", "count"),
            average_co2_g_km=("co2_emissions_g_km", "mean"),
            average_combined_l_100km=("fuel_cons_comb_l_100km", "mean"),
            average_engine_size_l=("engine_size_l", "mean"),
            average_peer_gap_g_km=("co2_gap_to_class_p25", "mean"),
        )
    )
    make_year.to_csv(OUTPUT_DIR / "make_year_summary.csv", index=False)

    for file_name, group_columns in {
        "fuel_type_year_summary.csv": ["model_year", "fuel_type_code", "fuel_type"],
        "engine_band_year_summary.csv": ["model_year", "engine_size_band"],
        "transmission_year_summary.csv": ["model_year", "transmission_family_code", "transmission_family"],
    }.items():
        summary = (
            clean.groupby(group_columns, as_index=False, observed=True)
            .agg(
                vehicle_records=("vehicle_id", "count"),
                average_co2_g_km=("co2_emissions_g_km", "mean"),
                average_combined_l_100km=("fuel_cons_comb_l_100km", "mean"),
                average_engine_size_l=("engine_size_l", "mean"),
            )
        )
        summary.to_csv(OUTPUT_DIR / file_name, index=False)

    opportunities = (
        clean.loc[clean["model_year"] >= 2022]
        .sort_values(["co2_gap_to_class_p25", "co2_emissions_g_km"], ascending=False)
        .head(500)
    )
    opportunities.to_csv(OUTPUT_DIR / "high_emission_opportunities.csv", index=False)
    make_data_dictionary().to_csv(OUTPUT_DIR / "data_dictionary.csv", index=False)


def main() -> None:
    ensure_directories()
    started = time.time()
    if not RAW_FILE.exists():
        raise FileNotFoundError(f"Missing raw dataset: {RAW_FILE}")

    raw = pd.read_csv(RAW_FILE)
    expected_columns = list(COLUMN_MAP)
    if list(raw.columns) != expected_columns:
        raise ValueError(
            "Unexpected source columns. Expected exactly: " + ", ".join(expected_columns)
        )

    raw.insert(0, "source_row_number", np.arange(2, len(raw) + 2))
    duplicate_mask = raw.drop(columns="source_row_number").duplicated(keep="first")
    removed_duplicates = raw.loc[duplicate_mask].copy()
    removed_duplicates.to_csv(OUTPUT_DIR / "removed_exact_duplicates.csv", index=False)

    clean = raw.loc[~duplicate_mask].rename(columns=COLUMN_MAP).reset_index(drop=True)
    clean["make"] = normalize_text(clean["make"])
    clean["model"] = normalize_text(clean["model"])
    clean["vehicle_class_raw"] = clean["vehicle_class_raw"].astype("string").str.strip()
    clean["vehicle_class"] = clean["vehicle_class_raw"].map(normalize_vehicle_class)
    clean["transmission"] = normalize_text(clean["transmission"])
    clean["transmission_family_code"] = clean["transmission"].str.extract(
        r"^([A-Z]+)", expand=False
    )
    clean["transmission_family"] = clean["transmission_family_code"].map(
        TRANSMISSION_FAMILIES
    )
    clean["gear_count"] = (
        pd.to_numeric(
            clean["transmission"].str.extract(r"(\d+)$", expand=False), errors="coerce"
        )
        .fillna(0)
        .astype("int8")
    )
    clean["fuel_type_code"] = normalize_text(clean["fuel_type_code"])
    clean["fuel_type"] = clean["fuel_type_code"].map(FUEL_TYPES)

    clean["city_hwy_gap_l_100km"] = (
        clean["fuel_cons_city_l_100km"] - clean["fuel_cons_hwy_l_100km"]
    ).round(3)
    clean["city_hwy_ratio"] = (
        clean["fuel_cons_city_l_100km"] / clean["fuel_cons_hwy_l_100km"]
    ).round(6)
    clean["co2_per_comb_l"] = (
        clean["co2_emissions_g_km"] / clean["fuel_cons_comb_l_100km"]
    ).round(6)
    clean["engine_size_band"] = pd.cut(
        clean["engine_size_l"],
        bins=[-np.inf, 2.0, 3.0, 4.0, np.inf],
        labels=["<=2.0L", "2.1-3.0L", "3.1-4.0L", ">4.0L"],
    ).astype("string")
    peer_group = clean.groupby(["model_year", "vehicle_class"])["co2_emissions_g_km"]
    clean["class_year_co2_median"] = peer_group.transform("median").round(3)
    clean["class_year_co2_p25"] = peer_group.transform(
        lambda values: values.quantile(0.25)
    ).round(3)
    clean["co2_vs_class_year_median"] = (
        clean["co2_emissions_g_km"] - clean["class_year_co2_median"]
    ).round(3)
    clean["co2_gap_to_class_p25"] = (
        clean["co2_emissions_g_km"] - clean["class_year_co2_p25"]
    ).clip(lower=0).round(3)
    clean["above_class_year_median"] = (
        clean["co2_emissions_g_km"] > clean["class_year_co2_median"]
    ).astype("int8")
    clean["city_below_highway_flag"] = (
        clean["fuel_cons_city_l_100km"] < clean["fuel_cons_hwy_l_100km"]
    ).astype("int8")
    clean["emission_band"] = pd.cut(
        clean["co2_emissions_g_km"],
        bins=[-np.inf, 200, 250, 300, 350, np.inf],
        right=False,
        labels=["<200", "200-249", "250-299", "300-349", "350+"],
    ).astype("string")
    clean["model_split"] = np.select(
        [clean["model_year"] <= 2019, clean["model_year"].between(2020, 2021)],
        ["train", "validation"],
        default="test",
    )
    clean.insert(0, "vehicle_id", np.arange(1, len(clean) + 1))

    required = [
        "vehicle_id",
        "model_year",
        "make",
        "model",
        "vehicle_class",
        "engine_size_l",
        "cylinders",
        "transmission_family_code",
        "transmission_family",
        "fuel_type_code",
        "fuel_type",
        "fuel_cons_city_l_100km",
        "fuel_cons_hwy_l_100km",
        "fuel_cons_comb_l_100km",
        "co2_emissions_g_km",
    ]
    checks = {
        "clean_rows": int(len(clean)),
        "unique_vehicle_ids": int(clean["vehicle_id"].nunique()),
        "missing_required_values": int(clean[required].isna().sum().sum()),
        "invalid_model_year": int((~clean["model_year"].between(1995, 2023)).sum()),
        "invalid_engine_size": int((clean["engine_size_l"] <= 0).sum()),
        "invalid_cylinders": int((clean["cylinders"] <= 0).sum()),
        "invalid_consumption": int(
            (
                clean[
                    [
                        "fuel_cons_city_l_100km",
                        "fuel_cons_hwy_l_100km",
                        "fuel_cons_comb_l_100km",
                    ]
                ]
                <= 0
            ).any(axis=1).sum()
        ),
        "invalid_co2": int((clean["co2_emissions_g_km"] <= 0).sum()),
        "invalid_co2_rating": int(
            (clean["co2_rating"].notna() & ~clean["co2_rating"].between(1, 10)).sum()
        ),
        "invalid_smog_rating": int(
            (clean["smog_rating"].notna() & ~clean["smog_rating"].between(1, 10)).sum()
        ),
        "unmapped_fuel_codes": int(clean["fuel_type"].isna().sum()),
        "unmapped_transmission_codes": int(clean["transmission_family"].isna().sum()),
        "combined_outside_city_highway_range": int(
            (~clean["fuel_cons_comb_l_100km"].between(
                clean[["fuel_cons_city_l_100km", "fuel_cons_hwy_l_100km"]].min(axis=1) - 0.11,
                clean[["fuel_cons_city_l_100km", "fuel_cons_hwy_l_100km"]].max(axis=1) + 0.11,
            )).sum()
        ),
        "city_below_highway_rows": int(clean["city_below_highway_flag"].sum()),
    }
    failing = {
        key: value
        for key, value in checks.items()
        if key
        not in {"clean_rows", "unique_vehicle_ids", "city_below_highway_rows"}
        and value != 0
    }
    if checks["unique_vehicle_ids"] != checks["clean_rows"] or failing:
        raise AssertionError(f"Cleaning validation failed: {failing}")

    output_columns = [
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
        "transmission_family",
        "gear_count",
        "fuel_type_code",
        "fuel_type",
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
    clean = clean[output_columns]
    clean.to_csv(PROCESSED_FILE, index=False)
    build_aggregates(clean)

    weighted_combined = (
        0.55 * clean["fuel_cons_city_l_100km"]
        + 0.45 * clean["fuel_cons_hwy_l_100km"]
    )
    audit = {
        "source_file": RAW_FILE.name,
        "source_sha256": sha256(RAW_FILE),
        "source_rows": int(len(raw)),
        "source_columns": int(len(COLUMN_MAP)),
        "clean_rows": int(len(clean)),
        "rows_removed_as_exact_duplicates": int(duplicate_mask.sum()),
        "source_missing_values": {
            column: int(value)
            for column, value in raw.drop(columns="source_row_number").isna().sum().items()
        },
        "source_data_types": {
            column: str(dtype)
            for column, dtype in raw.drop(columns="source_row_number").dtypes.items()
        },
        "numeric_profile": numeric_profile(clean),
        "date_range": {"min_model_year": int(clean["model_year"].min()), "max_model_year": int(clean["model_year"].max())},
        "unique_values": {
            "raw_make": int(raw["Make"].nunique()),
            "canonical_make": int(clean["make"].nunique()),
            "model": int(clean["model"].nunique()),
            "raw_vehicle_class": int(raw["VehicleClass"].nunique()),
            "canonical_vehicle_class": int(clean["vehicle_class"].nunique()),
            "transmission": int(clean["transmission"].nunique()),
            "fuel_type": int(clean["fuel_type_code"].nunique()),
        },
        "rating_availability": {
            "co2_rating_nonmissing": int(clean["co2_rating"].notna().sum()),
            "co2_rating_first_year": int(clean.loc[clean["co2_rating"].notna(), "model_year"].min()),
            "smog_rating_nonmissing": int(clean["smog_rating"].notna().sum()),
            "smog_rating_first_year": int(clean.loc[clean["smog_rating"].notna(), "model_year"].min()),
        },
        "validation_checks": checks,
        "iqr_outlier_counts_descriptive_only": iqr_outlier_profile(
            clean,
            [
                "engine_size_l",
                "cylinders",
                "fuel_cons_city_l_100km",
                "fuel_cons_hwy_l_100km",
                "fuel_cons_comb_l_100km",
                "fuel_economy_comb_mpg",
                "co2_emissions_g_km",
            ],
        ),
        "leakage_diagnostics": {
            "co2_combined_consumption_correlation": float(
                clean[["co2_emissions_g_km", "fuel_cons_comb_l_100km"]].corr().iloc[0, 1]
            ),
            "fuel_specific_linear_relationships": fuel_relationships(clean),
            "share_within_0_11_of_55_45_weighted_consumption": float(
                ((clean["fuel_cons_comb_l_100km"] - weighted_combined).abs() <= 0.11).mean()
            ),
            "excluded_from_primary_model": [
                "fuel_cons_city_l_100km",
                "fuel_cons_hwy_l_100km",
                "fuel_cons_comb_l_100km",
                "fuel_economy_comb_mpg",
                "co2_rating",
                "smog_rating",
                "all peer benchmark fields derived from the target",
            ],
        },
        "modeling_scope": {
            "unit_of_analysis": "one published vehicle configuration/model-year rating",
            "target": "rated tailpipe CO2 emissions in g/km",
            "primary_use_case": "early-specification ranking before fuel-consumption test outputs are used",
            "class_imbalance": "not applicable to regression",
            "split": "train 1995-2019; validation 2020-2021; test 2022-2023",
        },
        "limitations": [
            "One row is a rated vehicle configuration, not a sold vehicle or fleet unit; averages are not sales-weighted.",
            "The data contains rated laboratory values, not real-world driving outcomes, fuel cost, distance, or fleet utilization.",
            "CO2 and smog rating fields were introduced later and must not be imputed backward.",
            "Vehicle-class labels changed historically and are canonicalized while the raw label is retained.",
            "Combined fuel consumption and CO2 are nearly deterministic within fuel type, so measured consumption is excluded from the primary early-specification model.",
            "No weight, horsepower, drivetrain, electrification flag, or lifecycle-emissions field is supplied.",
            "Results are descriptive and predictive; they do not establish causal engineering effects or guaranteed emission reductions.",
        ],
        "elapsed_seconds": round(time.time() - started, 2),
    }
    (OUTPUT_DIR / "data_audit_report.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    pd.DataFrame(
        [
            {"step": "source ingestion", "rows_before": len(raw), "rows_after": len(raw), "rows_removed": 0, "reason": "Read supplied CSV without modifying it"},
            {"step": "exact duplicate removal", "rows_before": len(raw), "rows_after": len(clean), "rows_removed": int(duplicate_mask.sum()), "reason": "Remove only fully identical records"},
            {"step": "canonicalization and feature engineering", "rows_before": len(clean), "rows_after": len(clean), "rows_removed": 0, "reason": "Standardize names and create auditable peer benchmarks"},
        ]
    ).to_csv(OUTPUT_DIR / "cleaning_log.csv", index=False)

    print(json.dumps(audit, indent=2))
    print(f"Saved clean data: {PROCESSED_FILE}")


if __name__ == "__main__":
    main()
