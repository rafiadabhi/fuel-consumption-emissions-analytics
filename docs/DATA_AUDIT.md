# Dataset Audit

## Audit conclusion

The supplied dataset supports descriptive vehicle-efficiency analysis and regression of **published rated tailpipe CO₂ emissions**. It does not support an energy-company fleet claim, actual fuel savings, lifecycle emissions, sales-weighted market estimates, or causal engineering conclusions.

Final project title: **Fuel Consumption & Emissions Analytics**.

## Source identity

| Attribute | Value |
|---|---|
| File | `MY1995-2023-Fuel-Consumption-Ratings.csv` |
| SHA-256 | `2cc4a0100c582286f2be6f53927a7bf3fe07b4c4cc9d878f2b3e6a746c08fcd1` |
| Raw rows | 27,001 |
| Raw columns | 15 |
| Model years | 1995–2023 |
| Unit of analysis | One published vehicle configuration/model-year rating |
| Target | `CO2Emission_g_km` |
| Natural primary key | None supplied |
| Implemented key | Deterministic surrogate `vehicle_id` after exact duplicate removal |

## Source schema

| Source field | Inferred type | Meaning / use |
|---|---|---|
| `ModelYear` | Integer | Model year and time split |
| `Make` | Text | Manufacturer |
| `Model` | Text | Vehicle model/configuration label |
| `VehicleClass` | Text | Historical vehicle class label |
| `EngineSize_L` | Decimal | Engine displacement in litres |
| `Cylinders` | Integer | Cylinder count |
| `Transmission` | Text | Transmission code |
| `FuelType` | Text | X, Z, D, E, or N fuel code |
| `FuelConsCity_L100km` | Decimal | Rated city consumption |
| `FuelConsHwy_L100km` | Decimal | Rated highway consumption |
| `Comb_L100km` | Decimal | Rated combined consumption |
| `Comb_mpg` | Integer | Rated combined MPG |
| `CO2Emission_g_km` | Integer | Regression target |
| `CO2Rating` | Nullable decimal | Rating present from MY2016 |
| `SmogRating` | Nullable decimal | Rating present from MY2017 |

## Missing values

| Field | Missing rows | Interpretation | Treatment |
|---|---:|---|---|
| `CO2Rating` | 18,991 | Structural historical absence; first available MY2016 | Retain null; do not impute backward |
| `SmogRating` | 20,101 | Structural historical absence; first available MY2017 | Retain null; do not impute backward |
| All other source fields | 0 | Complete | No imputation |

## Duplicate rows

Three fully identical records were removed. Original source row numbers are retained for audit:

| Source row | Year | Make | Model | Class | Transmission | Fuel | CO₂ g/km |
|---:|---:|---|---|---|---|---|---:|
| 592 | 1995 | Nissan | Axxess | Minivan | A4 | X | 281 |
| 594 | 1995 | Nissan | Axxess | Minivan | M5 | X | 262 |
| 3,899 | 2000 | Land Rover | Discovery Series II 4x4 | SUV | A4 | Z | 403 |

The output `removed_exact_duplicates.csv` preserves all original columns.

## Invalid-value checks

| Validation | Invalid rows |
|---|---:|
| Model year outside 1995–2023 | 0 |
| Engine size ≤ 0 | 0 |
| Cylinders ≤ 0 | 0 |
| City/highway/combined consumption ≤ 0 | 0 |
| CO₂ ≤ 0 | 0 |
| CO₂ rating outside 1–10 when present | 0 |
| Smog rating outside 1–10 when present | 0 |
| Unmapped fuel code | 0 |
| Unmapped transmission family | 0 |
| Combined consumption outside city/highway range ±0.11 | 0 |

There are 258 records where rated city consumption is lower than highway consumption. They are flagged but retained because the values pass all other checks and can occur for particular technologies/configurations. Treating them as automatically invalid would be an unsupported assumption.

## Standardization

- Manufacturer and model text: trimmed, whitespace-normalized, uppercased.
- Manufacturer labels: 90 raw case-sensitive values → 55 canonical makes.
- Vehicle class: 33 raw historical labels → 18 canonical classes; raw label retained.
- Transmission: parsed into A, AS, AM, AV, or M family plus gear count.
- Fuel codes mapped using NRCan definitions:
  - X: Regular Gasoline
  - Z: Premium Gasoline
  - D: Diesel
  - E: E85
  - N: Natural Gas

## Outlier assessment

IQR flags are descriptive only. No rows were deleted solely for being statistically extreme.

| Field | IQR-flagged rows | Observed range | Decision |
|---|---:|---:|---|
| Engine size | 51 | 0.8–8.4 L | Retain |
| Cylinders | 15 | 2–16 | Retain |
| City consumption | 615 | 4.0–33.3 L/100 km | Retain |
| Highway consumption | 591 | 3.9–22.1 L/100 km | Retain |
| Combined consumption | 558 | 4.0–27.5 L/100 km | Retain |
| Combined MPG | 411 | 10–71 | Retain |
| CO₂ | 342 | 94–633 g/km | Retain |

These extremes are plausible high-performance, large-engine, or unusually efficient configurations. Deleting them would narrow the business problem and distort model evaluation.

## Leakage and target circularity

- Pearson correlation between combined L/100 km and CO₂: **0.9335**.
- Fuel-specific linear R²:
  - Diesel: 0.9989
  - E85: 0.9919
  - Natural Gas: 0.9946
  - Regular Gasoline: 0.9990
  - Premium Gasoline: 0.9982
- 99.674% of combined-consumption values are within 0.11 of a 55% city / 45% highway weighted value.

Because measured consumption nearly determines the target within fuel type, it is excluded from the primary early-specification model. MPG and CO₂ ratings are also excluded. Class/year benchmark fields are derived from the target and cannot enter training.

`Model` is omitted from the model because 4,275 unique labels create high-cardinality memorization risk and weaken interpretation.

## Class imbalance

Not applicable: the task is regression. Segment sizes are still reviewed because small classes can create unstable averages and error estimates.

## Table relationships

The source contains one flat table. The MySQL layer introduces normalized lookups:

- `vehicle_ratings.fuel_type_code` → `fuel_type_lookup.fuel_type_code`
- `vehicle_ratings.transmission_family_code` → `transmission_family_lookup.transmission_family_code`
- `model_predictions.vehicle_id` → `vehicle_ratings.vehicle_id`

There is no defensible source-level foreign key beyond these engineered relationships.

## Suitability and limits

Supported:

- model-year trends;
- class/fuel/engine/make descriptive benchmarks;
- class-year peer screening;
- temporal holdout regression of rated CO₂.

Not supported:

- sales-weighted or fleet-weighted estimates;
- actual energy-company savings;
- fuel-cost analysis;
- real-world driving or lifecycle emissions;
- production deployment or real-time prediction;
- causal claims about manufacturers, transmission, fuel, or engine design.

Machine-readable audit: `data/outputs/data_audit_report.json`.
