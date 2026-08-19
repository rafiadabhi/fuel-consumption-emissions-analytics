"""Cached MySQL queries used by the Streamlit dashboard."""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.db import get_engine  # noqa: E402


@st.cache_data(ttl=300, show_spinner=False)
def query_frame(query: str) -> pd.DataFrame:
    return pd.read_sql(query, get_engine())


def load_kpis() -> pd.DataFrame:
    return query_frame("SELECT * FROM vw_dashboard_kpis")


def load_yearly_trend() -> pd.DataFrame:
    return query_frame("SELECT * FROM vw_dashboard_yearly_trend ORDER BY model_year")


def load_class_benchmark() -> pd.DataFrame:
    return query_frame(
        "SELECT * FROM vw_dashboard_class_benchmark "
        "ORDER BY model_year, average_co2_g_km DESC"
    )


def load_segment_summary() -> pd.DataFrame:
    return query_frame(
        """
        SELECT
            model_year,
            vehicle_class,
            make,
            fuel_type,
            COUNT(*) AS vehicle_records,
            AVG(co2_emissions_g_km) AS average_co2_g_km,
            AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km,
            AVG(engine_size_l) AS average_engine_size_l,
            AVG(co2_gap_to_class_p25) AS average_peer_gap_g_km
        FROM vw_dashboard_vehicle_detail
        GROUP BY model_year, vehicle_class, make, fuel_type
        """
    )


def load_engine_band_summary() -> pd.DataFrame:
    return query_frame(
        """
        SELECT
            model_year,
            vehicle_class,
            fuel_type,
            engine_size_band,
            COUNT(*) AS vehicle_records,
            AVG(fuel_cons_comb_l_100km) AS average_combined_l_100km,
            AVG(co2_emissions_g_km) AS average_co2_g_km
        FROM vw_dashboard_vehicle_detail
        GROUP BY model_year, vehicle_class, fuel_type, engine_size_band
        """
    )


def load_model_metrics() -> pd.DataFrame:
    return query_frame(
        "SELECT * FROM vw_dashboard_model_performance ORDER BY metric_id"
    )


def load_feature_importance() -> pd.DataFrame:
    return query_frame(
        "SELECT * FROM vw_dashboard_feature_importance ORDER BY importance_rank"
    )


def load_segment_errors() -> pd.DataFrame:
    return query_frame(
        "SELECT * FROM vw_dashboard_test_segment_errors ORDER BY mae DESC"
    )


def load_test_predictions() -> pd.DataFrame:
    return query_frame(
        """
        SELECT
            vehicle_id,
            model_year,
            make,
            model,
            vehicle_class,
            fuel_type,
            actual_co2_g_km,
            predicted_co2_g_km,
            prediction_error_g_km,
            absolute_error_g_km
        FROM vw_dashboard_vehicle_detail
        WHERE model_split = 'test'
        ORDER BY vehicle_id
        """
    )


def load_opportunities() -> pd.DataFrame:
    return query_frame(
        """
        SELECT *
        FROM vw_dashboard_high_emission_opportunities
        ORDER BY co2_gap_to_class_p25 DESC
        LIMIT 500
        """
    )
