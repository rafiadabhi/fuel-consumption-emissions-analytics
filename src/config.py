"""Shared paths and MySQL configuration."""

from pathlib import Path
import os
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"
MODEL_DIR = PROJECT_ROOT / "models"
SQL_DIR = PROJECT_ROOT / "sql"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"
SCREENSHOT_DIR = DASHBOARD_DIR / "screenshots"

RAW_FILE = RAW_DIR / "MY1995-2023-Fuel-Consumption-Ratings.csv"
PROCESSED_FILE = PROCESSED_DIR / "vehicle_ratings_clean.csv"


def _load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_local_env(PROJECT_ROOT / ".env")


def ensure_directories() -> None:
    for directory in (
        RAW_DIR,
        PROCESSED_DIR,
        OUTPUT_DIR,
        MODEL_DIR,
        DASHBOARD_DIR,
        SCREENSHOT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def mysql_database_name() -> str:
    name = os.getenv("MYSQL_DATABASE", "fuel_emissions_db")
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError("MYSQL_DATABASE may contain only letters, numbers, and underscores.")
    return name


def mysql_url(include_database: bool = True):
    from sqlalchemy import URL

    return URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=mysql_database_name() if include_database else None,
        query={"charset": "utf8mb4"},
    )
