# Streamlit Dashboard Guide

I built the dashboard in `dashboard/app.py` with Streamlit and Plotly. Every page
queries the MySQL reporting views through `dashboard/data_access.py`; there is no
local CSV fallback.

## Start the Dashboard

Run the pipeline first, then start Streamlit from the project root:

```bash
python run_pipeline.py
streamlit run dashboard/app.py
```

## Dashboard Pages

### 1. Executive Overview

- filters: model year, vehicle class, and fuel type;
- KPIs: configurations, average CO₂, average fuel use, and model years;
- charts: yearly CO₂ trend, fuel-type mix, class comparison, and engine-band fuel use.

### 2. Segment Benchmark

- filters: model year, vehicle class, manufacturer, and fuel type;
- KPIs: configurations, average CO₂, average fuel use, and average peer gap;
- charts: fuel use versus CO₂, class peer gaps, manufacturer ranking, and class mix.

### 3. Model Performance

- controls: evaluation split and error segment;
- KPIs: selected model, MAE, R², and P90 absolute error;
- charts: actual versus predicted CO₂, validation MAE, permutation importance,
  and test MAE by segment.

### 4. Opportunity Scenario

- filters: model year, vehicle class, and fuel type;
- controls: annual distance and scenario vehicle count;
- KPIs: configurations screened, average peer gap, annual distance, and scenario gap;
- charts: largest peer gaps, opportunity mix, scenario sensitivity, and gap distribution.

The scenario is a class-year peer benchmark, not a forecast or a claim of achieved
emissions savings. The modeling assumptions and leakage controls are documented in
`docs/MODEL_CARD.md` instead of being displayed as text panels in the dashboard.

## Design Preview

The approved layout references are stored in `dashboard/mockups/`. Their values are
for layout review only. The running dashboard replaces them with MySQL results.

## GitHub Evidence

After the dashboard is running, capture one screenshot per page in:

```text
dashboard/screenshots/
```

Use these names:

```text
01_executive_overview.png
02_segment_benchmark.png
03_model_performance.png
04_opportunity_scenario.png
```

The source-only package leaves this folder empty. Add the screenshots only after
reviewing the dashboard generated from your own pipeline run.
