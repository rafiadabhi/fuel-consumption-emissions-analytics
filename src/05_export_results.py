"""Export compact, reviewable result evidence from MySQL for GitHub."""

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.config import OUTPUT_DIR, ensure_directories
from src.db import get_engine


QUERIES = {
    "dashboard_kpis.csv": "SELECT * FROM vw_dashboard_kpis",
    "yearly_trend.csv": (
        "SELECT * FROM vw_dashboard_yearly_trend ORDER BY model_year"
    ),
    "class_year_benchmark.csv": (
        "SELECT * FROM vw_dashboard_class_benchmark "
        "ORDER BY model_year, average_co2_g_km DESC"
    ),
    "make_year_summary.csv": (
        "SELECT * FROM vw_dashboard_make_benchmark "
        "ORDER BY model_year, average_co2_g_km"
    ),
    "model_metrics.csv": (
        "SELECT * FROM vw_dashboard_model_performance ORDER BY metric_id"
    ),
    "model_tuning_results.csv": (
        "SELECT * FROM model_tuning_results ORDER BY mae, rmse"
    ),
    "feature_importance.csv": (
        "SELECT * FROM vw_dashboard_feature_importance ORDER BY importance_rank"
    ),
    "high_emission_opportunities.csv": (
        "SELECT * FROM vw_dashboard_high_emission_opportunities "
        "ORDER BY co2_gap_to_class_p25 DESC LIMIT 500"
    ),
    "model_segment_errors.csv": (
        "SELECT * FROM vw_dashboard_test_segment_errors ORDER BY mae DESC"
    ),
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    ensure_directories()
    engine = get_engine()
    manifest_rows = []

    for file_name, query in QUERIES.items():
        frame = pd.read_sql(query, engine)
        path = OUTPUT_DIR / file_name
        frame.to_csv(path, index=False)
        manifest_rows.append(
            {
                "file": file_name,
                "rows": int(len(frame)),
                "columns": int(len(frame.columns)),
                "bytes": int(path.stat().st_size),
                "sha256": file_sha256(path),
                "source": "MySQL",
            }
        )

    manifest = pd.DataFrame(manifest_rows).sort_values("file")
    manifest.to_csv(OUTPUT_DIR / "results_manifest.csv", index=False)
    summary = {
        "files_exported": int(len(manifest)),
        "output_directory": str(OUTPUT_DIR),
    }
    print(json.dumps(summary, indent=2))
    print(manifest.to_string(index=False))


if __name__ == "__main__":
    main()
