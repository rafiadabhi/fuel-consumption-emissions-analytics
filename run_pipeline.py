"""Run the complete source-to-dashboard data pipeline."""

import subprocess
import sys
import time


STEPS = [
    ("1/6 Audit and clean the raw CSV", "src.01_audit_clean"),
    ("2/6 Create MySQL tables and load clean data", "src.03_load_mysql"),
    ("3/6 Train and evaluate leakage-aware models", "src.02_train_models"),
    ("4/6 Create MySQL dashboard views", "src.04_build_dashboard_views"),
    ("5/6 Export compact result evidence", "src.05_export_results"),
    ("6/6 Validate files and MySQL objects", "src.06_validate_outputs"),
]


def run_step(label: str, module: str) -> None:
    print(f"\n{'=' * 76}\n{label}\n{'=' * 76}")
    subprocess.run([sys.executable, "-m", module], check=True)


def main() -> None:
    started = time.time()
    for label, module in STEPS:
        run_step(label, module)
    print(f"\nPipeline completed in {time.time() - started:.1f} seconds.")
    print("Start the dashboard with: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
