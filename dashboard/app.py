"""Visual-first Streamlit dashboard backed directly by MySQL reporting views."""

from html import escape

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data_access import (
    load_engine_band_summary,
    load_feature_importance,
    load_kpis,
    load_model_metrics,
    load_opportunities,
    load_segment_errors,
    load_segment_summary,
    load_test_predictions,
)


st.set_page_config(
    page_title="Fuel Consumption & Emissions Analytics",
    page_icon="🚘",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG = "#F1F2EF"
CARD = "#FFFFFF"
TEXT = "#141A17"
MUTED = "#88928C"
LINE = "#E4E8E4"
DARK_GREEN = "#075B3A"
GREEN = "#0B7A4D"
MID_GREEN = "#299966"
LIGHT_GREEN = "#63BD91"
PALE_GREEN = "#DCECE3"
GREEN_SCALE = [DARK_GREEN, GREEN, MID_GREEN, LIGHT_GREEN, PALE_GREEN]

st.markdown(
    f"""
    <style>
    :root {{
        --bg: {BG};
        --card: {CARD};
        --text: {TEXT};
        --muted: {MUTED};
        --line: {LINE};
        --green: {GREEN};
        --dark-green: {DARK_GREEN};
    }}
    html, body {{
        color-scheme: light !important;
        background: #E9ECE8 !important;
    }}
    #MainMenu,
    footer,
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    [data-testid="stStatusWidget"] {{
        display: none !important;
    }}
    .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"] {{
        background: var(--bg) !important;
        color: var(--text) !important;
    }}
    .block-container {{
        max-width: 1480px;
        padding: 1rem 2rem 2.2rem;
    }}
    [data-testid="stSidebar"] {{
        background: #F8F9F7 !important;
        border-right: 1px solid var(--line);
        min-width: 270px !important;
        max-width: 270px !important;
    }}
    [data-testid="stSidebar"] .block-container {{
        padding: 1.75rem 1.15rem 1.4rem;
    }}
    [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {{
        display: none !important;
    }}
    h1, h2, h3, p, label, div, input, button {{
        font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .brand {{
        display: flex;
        align-items: center;
        gap: 0.7rem;
        margin: 0.2rem 0 2.1rem;
        font-weight: 800;
        font-size: 1.08rem;
        color: var(--text);
    }}
    .brand-mark {{
        width: 30px;
        height: 30px;
        border: 3px solid {GREEN};
        border-radius: 50%;
        display: grid;
        place-items: center;
        color: {GREEN};
        font-size: 0.82rem;
        box-sizing: border-box;
    }}
    .menu-label {{
        color: var(--muted);
        font-size: 0.68rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0 0 0.55rem;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] {{
        gap: 0.25rem;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label {{
        position: relative;
        min-height: 44px;
        border-radius: 12px;
        padding: 0.68rem 0.65rem 0.68rem 2.55rem;
        margin-bottom: 0.12rem;
        color: #819087 !important;
        transition: background 120ms ease, color 120ms ease;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {{
        position: absolute;
        width: 1px;
        height: 1px;
        opacity: 0;
        overflow: hidden;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label::before {{
        content: "▦";
        position: absolute;
        left: 0.8rem;
        top: 50%;
        transform: translateY(-50%);
        color: #A9B7B0;
        font-size: 1.24rem;
        line-height: 1;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label p {{
        color: inherit !important;
        font-size: 0.78rem !important;
        font-weight: 500;
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {{
        background: #FFFFFF !important;
        color: var(--text) !important;
        font-weight: 700 !important;
        box-shadow: 0 5px 16px rgba(20, 26, 23, 0.055);
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)::before {{
        color: var(--green);
    }}
    [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)::after {{
        content: "";
        position: absolute;
        left: -1.15rem;
        top: 7px;
        bottom: 7px;
        width: 5px;
        border-radius: 999px;
        background: var(--green);
    }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{
        color: inherit;
    }}
    .general-links {{
        margin-top: 2.4rem;
        color: #91A097;
        font-size: 0.76rem;
        line-height: 2.8;
    }}
    .general-links span {{
        display: block;
    }}
    .general-links i {{
        display: inline-block;
        width: 13px;
        height: 13px;
        border: 1px solid #91A097;
        border-radius: 50%;
        margin-right: 0.72rem;
        vertical-align: -2px;
    }}
    .top-meta {{
        text-align: right;
        line-height: 1.16;
        padding-top: 0.2rem;
    }}
    .top-meta strong {{
        color: var(--text);
        display: block;
        font-size: 0.76rem;
        white-space: nowrap;
    }}
    .top-meta span {{
        color: var(--muted);
        display: block;
        font-size: 0.62rem;
        margin-top: 0.18rem;
        white-space: nowrap;
    }}
    .page-head {{
        margin: 0.25rem 0 0.65rem;
    }}
    .page-title {{
        color: var(--text);
        font-size: clamp(1.8rem, 2.4vw, 2.55rem);
        line-height: 1.08;
        font-weight: 800;
        letter-spacing: -0.035em;
        margin: 0;
    }}
    .page-subtitle {{
        color: var(--muted);
        margin-top: 0.38rem;
        font-size: 0.88rem;
    }}
    .filter-label {{
        color: var(--muted);
        font-size: 0.66rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin: 0.25rem 0 -0.18rem;
    }}
    div[data-testid="stMetric"],
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--card) !important;
        border: 1px solid rgba(228, 232, 228, 0.92) !important;
        border-radius: 17px !important;
        box-shadow: 0 7px 20px rgba(20, 26, 23, 0.045);
    }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        padding: 0.1rem 0.25rem 0.2rem;
        overflow: hidden;
    }}
    .kpi-card {{
        background: var(--card);
        border: 1px solid rgba(228, 232, 228, 0.92);
        border-radius: 17px;
        box-shadow: 0 7px 20px rgba(20, 26, 23, 0.045);
        min-height: 112px;
        padding: 0.95rem 1.05rem 0.82rem;
        box-sizing: border-box;
        position: relative;
        overflow: hidden;
    }}
    .kpi-card.featured {{
        background: linear-gradient(145deg, {DARK_GREEN}, {MID_GREEN});
        color: white;
        border-color: transparent;
    }}
    .kpi-label {{
        color: var(--text);
        font-size: 0.74rem;
        line-height: 1.2;
        padding-right: 1.6rem;
    }}
    .featured .kpi-label {{ color: rgba(255,255,255,0.93); }}
    .kpi-value {{
        color: var(--text);
        font-size: clamp(1.55rem, 2.1vw, 2.12rem);
        line-height: 1;
        font-weight: 500;
        margin-top: 0.85rem;
        letter-spacing: -0.03em;
        white-space: nowrap;
    }}
    .kpi-value.compact {{
        font-size: clamp(1.02rem, 1.45vw, 1.45rem);
        white-space: normal;
        line-height: 1.08;
    }}
    .featured .kpi-value {{ color: white; }}
    .kpi-note {{
        color: {GREEN};
        font-size: 0.63rem;
        margin-top: 0.38rem;
        white-space: nowrap;
    }}
    .featured .kpi-note {{ color: rgba(255,255,255,0.76); }}
    .kpi-arrow {{
        position: absolute;
        right: 0.92rem;
        top: 0.86rem;
        width: 27px;
        height: 27px;
        border: 1px solid currentColor;
        border-radius: 50%;
        display: grid;
        place-items: center;
        font-size: 0.78rem;
    }}
    .db-card {{
        position: fixed;
        left: 1.15rem;
        bottom: 1.5rem;
        width: 232px;
        box-sizing: border-box;
        background: {DARK_GREEN};
        color: white;
        border-radius: 16px;
        padding: 1rem;
        font-size: 0.74rem;
        line-height: 1.65;
    }}
    .db-card strong {{ display: block; font-size: 0.82rem; margin-bottom: 0.12rem; }}
    .db-card span {{ color: #9DE0BD; }}
    [data-testid="stButton"] > button,
    [data-testid="stDownloadButton"] > button {{
        border-radius: 999px !important;
        border: 1px solid {GREEN} !important;
        background: #FFFFFF !important;
        color: {DARK_GREEN} !important;
        font-weight: 700 !important;
        min-height: 42px;
    }}
    [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stBaseButton-primary"] {{
        background: {GREEN} !important;
        color: #FFFFFF !important;
    }}
    [data-testid="stButton"] > button:hover,
    [data-testid="stDownloadButton"] > button:hover {{
        border-color: {DARK_GREEN} !important;
        background: #E6F1EB !important;
        color: {DARK_GREEN} !important;
    }}
    [data-testid="stButton"] > button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {{
        background: {DARK_GREEN} !important;
        color: #FFFFFF !important;
    }}
    [data-testid="stTextInput"] input,
    [data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input {{
        background: #FFFFFF !important;
        color: var(--text) !important;
        -webkit-text-fill-color: var(--text) !important;
        border-color: var(--line) !important;
        border-radius: 12px !important;
        box-shadow: none !important;
    }}
    [data-testid="stTextInput"] input {{
        min-height: 42px;
    }}
    [data-baseweb="select"] > div {{
        min-height: 44px;
    }}
    [data-baseweb="select"] span,
    [data-baseweb="select"] svg,
    [data-testid="stNumberInput"] button,
    [data-testid="stNumberInput"] button svg {{
        color: var(--text) !important;
        fill: var(--text) !important;
    }}
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [role="listbox"],
    [role="option"] {{
        background: #FFFFFF !important;
        color: var(--text) !important;
    }}
    [data-testid="stWidgetLabel"] p,
    [data-testid="stSlider"] p,
    [data-testid="stNumberInput"] p {{
        color: #65736C !important;
        font-size: 0.72rem !important;
    }}
    [data-testid="stSlider"] [role="slider"] {{
        background: {GREEN} !important;
        border-color: {GREEN} !important;
        color: {GREEN} !important;
    }}
    [data-testid="stPlotlyChart"] {{
        border-radius: 16px;
        overflow: hidden;
    }}
    hr {{ border-color: var(--line); }}
    @media (max-width: 900px) {{
        [data-testid="stSidebar"] {{ min-width: 235px !important; max-width: 235px !important; }}
        .block-container {{ padding-left: 1rem; padding-right: 1rem; }}
        .kpi-card {{ min-height: 108px; }}
        .db-card {{ width: 197px; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


def weighted_average(frame: pd.DataFrame, value: str) -> float:
    valid = frame[[value, "vehicle_records"]].dropna()
    total_weight = float(valid["vehicle_records"].sum())
    if valid.empty or total_weight == 0:
        return float("nan")
    return float((valid[value] * valid["vehicle_records"]).sum() / total_weight)


def aggregate_weighted(
    frame: pd.DataFrame,
    group_columns: str | list[str],
    value_columns: list[str],
) -> pd.DataFrame:
    groups = [group_columns] if isinstance(group_columns, str) else group_columns
    work = frame.copy()
    weighted_columns = []
    for value in value_columns:
        weighted_name = f"__weighted_{value}"
        work[weighted_name] = work[value] * work["vehicle_records"]
        weighted_columns.append(weighted_name)

    aggregations = {"vehicle_records": "sum"}
    aggregations.update({name: "sum" for name in weighted_columns})
    result = work.groupby(groups, as_index=False, dropna=False).agg(aggregations)
    for value, weighted_name in zip(value_columns, weighted_columns):
        result[value] = result[weighted_name] / result["vehicle_records"]
    return result.drop(columns=weighted_columns)


def render_top_toolbar(first_year: int, latest_year: int) -> str:
    search_col, spacer, refresh_col, meta_col = st.columns(
        [2.35, 4.5, 0.42, 0.78], vertical_alignment="center"
    )
    with search_col:
        search_query = st.text_input(
            "Search make or model",
            placeholder="Search make or model",
            label_visibility="collapsed",
            key="global_vehicle_search",
        )
    with refresh_col:
        if st.button(
            "↻",
            key="top_refresh",
            help="Refresh MySQL data",
            use_container_width=True,
        ):
            st.cache_data.clear()
            st.rerun()
    with meta_col:
        st.markdown(
            f"""
            <div class="top-meta">
              <strong>MY{first_year}–{latest_year}</strong>
              <span>All vehicle ratings</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    return search_query.strip()


def page_header(
    title: str,
    subtitle: str,
    export_frame: pd.DataFrame,
    page_key: str,
) -> None:
    title_col, refresh_col, export_col = st.columns(
        [5.9, 0.78, 0.88], vertical_alignment="center"
    )
    with title_col:
        st.markdown(
            f"""
            <div class="page-head">
              <h1 class="page-title">{escape(title)}</h1>
              <div class="page-subtitle">{escape(subtitle)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with refresh_col:
        if st.button(
            "↻ Refresh",
            type="primary",
            key=f"refresh_{page_key}",
            use_container_width=True,
        ):
            st.cache_data.clear()
            st.rerun()
    with export_col:
        st.download_button(
            "Export Data",
            data=export_frame.to_csv(index=False).encode("utf-8"),
            file_name=f"{page_key}.csv",
            mime="text/csv",
            key=f"export_{page_key}",
            use_container_width=True,
        )


def apply_search(frame: pd.DataFrame, search_query: str) -> pd.DataFrame:
    if not search_query:
        return frame
    searchable = [column for column in ("make", "model") if column in frame.columns]
    if not searchable:
        return frame
    matched = pd.Series(False, index=frame.index)
    for column in searchable:
        matched |= frame[column].fillna("").astype(str).str.contains(
            search_query, case=False, regex=False
        )
    return frame.loc[matched].copy()


def render_kpis(items: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(items))
    for index, (label, value, note) in enumerate(items):
        featured = " featured" if index == 0 else ""
        compact = " compact" if len(value) > 15 else ""
        columns[index].markdown(
            f"""
            <div class="kpi-card{featured}">
              <div class="kpi-label">{escape(label)}</div>
              <div class="kpi-arrow">↗</div>
              <div class="kpi-value{compact}">{escape(value)}</div>
              <div class="kpi-note">{escape(note)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def style_figure(
    figure: go.Figure,
    title: str,
    *,
    height: int = 335,
    show_grid: bool = True,
) -> go.Figure:
    figure.update_layout(
        title={
            "text": f"<b>{escape(title)}</b>",
            "x": 0.02,
            "xanchor": "left",
            "font": {"size": 15, "color": TEXT},
        },
        height=height,
        margin={"l": 26, "r": 22, "t": 62, "b": 34},
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font={"family": "Inter, Segoe UI, sans-serif", "color": TEXT, "size": 11},
        hoverlabel={"bgcolor": CARD, "font": {"color": TEXT}, "bordercolor": LINE},
        legend={"title": None, "font": {"size": 10}, "orientation": "h", "y": -0.16},
        coloraxis_showscale=False,
    )
    figure.update_xaxes(
        showgrid=show_grid,
        gridcolor=LINE,
        zeroline=False,
        linecolor=LINE,
        tickfont={"color": MUTED},
        title_font={"color": MUTED},
    )
    figure.update_yaxes(
        showgrid=show_grid,
        gridcolor=LINE,
        zeroline=False,
        linecolor=LINE,
        tickfont={"color": MUTED},
        title_font={"color": MUTED},
    )
    return figure


def chart_card(figure: go.Figure) -> None:
    with st.container(border=True):
        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
        )


def filter_segment_frame(
    frame: pd.DataFrame,
    year_range: tuple[int, int],
    classes: list[str],
    fuels: list[str],
    makes: list[str] | None = None,
) -> pd.DataFrame:
    filtered = frame.loc[frame["model_year"].between(*year_range)].copy()
    if classes:
        filtered = filtered.loc[filtered["vehicle_class"].isin(classes)]
    if fuels:
        filtered = filtered.loc[filtered["fuel_type"].isin(fuels)]
    if makes:
        filtered = filtered.loc[filtered["make"].isin(makes)]
    return filtered


def category_mix(
    frame: pd.DataFrame,
    category: str,
    value: str,
    *,
    limit: int = 6,
) -> pd.DataFrame:
    grouped = frame.groupby(category, as_index=False)[value].sum().sort_values(value, ascending=False)
    if len(grouped) <= limit:
        return grouped
    visible = grouped.head(limit - 1).copy()
    other = pd.DataFrame({category: ["Other"], value: [grouped.iloc[limit - 1 :][value].sum()]})
    return pd.concat([visible, other], ignore_index=True)


def empty_selection() -> None:
    st.warning("No records match the selected filters.")


def executive_overview(kpis: pd.Series, search_query: str) -> None:
    all_data = load_segment_summary()
    all_engine_data = load_engine_band_summary()
    first_year = int(all_data["model_year"].min())
    latest_year = int(all_data["model_year"].max())
    data = apply_search(all_data, search_query)
    engine_data = apply_search(all_engine_data, search_query)

    page_header(
        "Executive Overview",
        "Vehicle efficiency and emissions performance across model years.",
        data,
        "executive_overview",
    )
    if data.empty:
        empty_selection()
        return
    st.markdown('<div class="filter-label">Filters</div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1.05, 1.3, 1.1])
    year_range = f1.slider(
        "Model year",
        first_year,
        latest_year,
        (first_year, latest_year),
        key="overview_year",
    )
    classes = f2.multiselect(
        "Vehicle class",
        sorted(data["vehicle_class"].dropna().unique()),
        placeholder="All classes",
        key="overview_class",
    )
    fuels = f3.multiselect(
        "Fuel type",
        sorted(data["fuel_type"].dropna().unique()),
        placeholder="All fuel types",
        key="overview_fuel",
    )
    filtered = filter_segment_frame(data, year_range, classes, fuels)
    if filtered.empty:
        empty_selection()
        return

    total_records = int(filtered["vehicle_records"].sum())
    average_co2 = weighted_average(filtered, "average_co2_g_km")
    average_fuel = weighted_average(filtered, "average_combined_l_100km")
    render_kpis(
        [
            ("Vehicle Configurations", f"{total_records:,}", "audited records"),
            ("Average CO₂", f"{average_co2:.1f}", "g/km"),
            ("Average Fuel Use", f"{average_fuel:.1f}", "combined L/100 km"),
            ("Model Years", f"{filtered['model_year'].nunique():,}", f"{year_range[0]}–{year_range[1]}"),
        ]
    )

    trend = aggregate_weighted(filtered, "model_year", ["average_co2_g_km"])
    trend = trend.sort_values("model_year")
    fuel_mix = category_mix(filtered, "fuel_type", "vehicle_records", limit=6)

    left, right = st.columns([1.4, 1])
    with left:
        figure = go.Figure(
            go.Scatter(
                x=trend["model_year"],
                y=trend["average_co2_g_km"],
                mode="lines+markers",
                line={"color": GREEN, "width": 3},
                marker={"size": 6, "color": CARD, "line": {"color": GREEN, "width": 2}},
                fill="tozeroy",
                fillcolor="rgba(41, 153, 102, 0.10)",
                hovertemplate="MY%{x}<br>%{y:.1f} g/km<extra></extra>",
            )
        )
        figure.update_yaxes(title="Average CO₂ (g/km)", rangemode="tozero")
        figure.update_xaxes(title="Model year")
        chart_card(style_figure(figure, "CO₂ Trend by Model Year", height=350))
    with right:
        figure = px.pie(
            fuel_mix,
            names="fuel_type",
            values="vehicle_records",
            hole=0.60,
            color_discrete_sequence=GREEN_SCALE,
        )
        figure.update_traces(
            textinfo="percent",
            textposition="inside",
            marker={"line": {"color": CARD, "width": 2}},
            hovertemplate="%{label}<br>%{value:,} ratings<br>%{percent}<extra></extra>",
        )
        figure = style_figure(figure, "Fuel Type Mix", height=350, show_grid=False)
        figure.add_annotation(
            x=0.5,
            y=0.5,
            text=f"<b>{total_records:,}</b><br><span style='font-size:10px'>ratings</span>",
            showarrow=False,
            font={"size": 18, "color": TEXT},
        )
        figure.update_layout(
            legend={"orientation": "v", "x": 1.02, "xanchor": "left", "y": 0.52},
            margin={"l": 20, "r": 92, "t": 62, "b": 24},
        )
        chart_card(figure)

    class_summary = aggregate_weighted(filtered, "vehicle_class", ["average_co2_g_km"])
    class_summary = class_summary.nlargest(8, "average_co2_g_km").sort_values("average_co2_g_km")
    filtered_engine = filter_segment_frame(engine_data, year_range, classes, fuels)
    engine_summary = aggregate_weighted(
        filtered_engine,
        "engine_size_band",
        ["average_combined_l_100km"],
    )
    engine_order = ["<=2.0L", "2.1-3.0L", "3.1-4.0L", ">4.0L"]
    engine_summary["engine_size_band"] = pd.Categorical(
        engine_summary["engine_size_band"], categories=engine_order, ordered=True
    )
    engine_summary = engine_summary.sort_values("engine_size_band")

    left, right = st.columns([1.4, 1])
    with left:
        figure = go.Figure(
            go.Bar(
                x=class_summary["average_co2_g_km"],
                y=class_summary["vehicle_class"],
                orientation="h",
                marker={"color": [LIGHT_GREEN] * len(class_summary), "cornerradius": 7},
                hovertemplate="%{y}<br>%{x:.1f} g/km<extra></extra>",
            )
        )
        figure.update_xaxes(title="Average CO₂ (g/km)")
        chart_card(style_figure(figure, "Average CO₂ by Vehicle Class", height=350, show_grid=False))
    with right:
        bubble_sizes = 34 + (
            engine_summary["average_combined_l_100km"]
            / engine_summary["average_combined_l_100km"].max()
            * 46
        )
        figure = go.Figure(
            go.Scatter(
                x=engine_summary["engine_size_band"].astype(str),
                y=[0] * len(engine_summary),
                mode="markers",
                marker={
                    "size": bubble_sizes,
                    "color": GREEN_SCALE[: len(engine_summary)],
                    "line": {"color": CARD, "width": 2},
                },
                customdata=engine_summary[["average_combined_l_100km"]],
                hovertemplate="%{x}<br>%{customdata[0]:.1f} L/100 km<extra></extra>",
            )
        )
        figure.update_yaxes(visible=False, range=[-0.8, 0.8])
        figure.update_xaxes(title=None, showgrid=False)
        chart_card(style_figure(figure, "Fuel Use by Engine Band", height=350, show_grid=False))


def segment_benchmark(kpis: pd.Series, search_query: str) -> None:
    all_data = load_segment_summary()
    first_year = int(all_data["model_year"].min())
    latest_year = int(all_data["model_year"].max())
    data = apply_search(all_data, search_query)
    page_header(
        "Segment Benchmark",
        "Compare vehicle classes, manufacturers, fuel types, and peer gaps.",
        data,
        "segment_benchmark",
    )
    if data.empty:
        empty_selection()
        return

    st.markdown('<div class="filter-label">Filters</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1, 1.18, 1.18, 1.05])
    year_range = f1.slider(
        "Model year",
        first_year,
        latest_year,
        (max(first_year, 2018), latest_year),
        key="segment_year",
    )
    classes = f2.multiselect(
        "Vehicle class",
        sorted(data["vehicle_class"].dropna().unique()),
        placeholder="All classes",
        key="segment_class",
    )
    makes = f3.multiselect(
        "Manufacturer",
        sorted(data["make"].dropna().unique()),
        placeholder="All manufacturers",
        key="segment_make",
    )
    fuels = f4.multiselect(
        "Fuel type",
        sorted(data["fuel_type"].dropna().unique()),
        placeholder="All fuel types",
        key="segment_fuel",
    )
    filtered = filter_segment_frame(data, year_range, classes, fuels, makes)
    if filtered.empty:
        empty_selection()
        return

    total_records = int(filtered["vehicle_records"].sum())
    average_co2 = weighted_average(filtered, "average_co2_g_km")
    average_fuel = weighted_average(filtered, "average_combined_l_100km")
    average_gap = weighted_average(filtered, "average_peer_gap_g_km")
    render_kpis(
        [
            ("Configurations", f"{total_records:,}", "filtered ratings"),
            ("Average CO₂", f"{average_co2:.1f}", "g/km"),
            ("Average Fuel Use", f"{average_fuel:.1f}", "combined L/100 km"),
            ("Average Peer Gap", f"{average_gap:.1f}", "g/km to class-year P25"),
        ]
    )

    make_summary = aggregate_weighted(
        filtered,
        "make",
        ["average_co2_g_km", "average_combined_l_100km", "average_peer_gap_g_km"],
    )
    scatter_data = make_summary.loc[make_summary["vehicle_records"] >= 5].nlargest(
        40, "vehicle_records"
    )
    if scatter_data.empty:
        scatter_data = make_summary

    class_summary = aggregate_weighted(
        filtered,
        "vehicle_class",
        ["average_co2_g_km", "average_peer_gap_g_km"],
    )
    gap_summary = class_summary.nlargest(10, "average_peer_gap_g_km").sort_values(
        "average_peer_gap_g_km"
    )

    left, right = st.columns([1.35, 1])
    with left:
        figure = px.scatter(
            scatter_data,
            x="average_combined_l_100km",
            y="average_co2_g_km",
            size="vehicle_records",
            color="average_co2_g_km",
            hover_name="make",
            color_continuous_scale=[PALE_GREEN, LIGHT_GREEN, GREEN, DARK_GREEN],
            labels={
                "average_combined_l_100km": "Combined L/100 km",
                "average_co2_g_km": "Average CO₂ (g/km)",
                "vehicle_records": "Ratings",
            },
        )
        figure.update_traces(marker={"line": {"color": CARD, "width": 1}, "opacity": 0.82})
        chart_card(style_figure(figure, "Fuel Consumption vs Rated CO₂", height=360))
    with right:
        figure = go.Figure(
            go.Bar(
                x=gap_summary["average_peer_gap_g_km"],
                y=gap_summary["vehicle_class"],
                orientation="h",
                marker={"color": MID_GREEN, "cornerradius": 7},
                hovertemplate="%{y}<br>%{x:.1f} g/km<extra></extra>",
            )
        )
        figure.update_xaxes(title="Average peer gap (g/km)")
        chart_card(style_figure(figure, "Peer Gap by Vehicle Class", height=360, show_grid=False))

    qualified_makes = make_summary.loc[make_summary["vehicle_records"] >= 5]
    if qualified_makes.empty:
        qualified_makes = make_summary
    ranking = qualified_makes.nsmallest(10, "average_co2_g_km").sort_values(
        "average_co2_g_km", ascending=False
    )
    class_mix = category_mix(filtered, "vehicle_class", "vehicle_records", limit=6)

    left, right = st.columns([1.35, 1])
    with left:
        figure = go.Figure(
            go.Bar(
                x=ranking["average_co2_g_km"],
                y=ranking["make"],
                orientation="h",
                marker={"color": LIGHT_GREEN, "cornerradius": 7},
                customdata=ranking[["vehicle_records"]],
                hovertemplate="%{y}<br>%{x:.1f} g/km<br>%{customdata[0]:,} ratings<extra></extra>",
            )
        )
        figure.update_xaxes(title="Average CO₂ (g/km)")
        chart_card(style_figure(figure, "Manufacturer CO₂ Ranking", height=350, show_grid=False))
    with right:
        figure = px.pie(
            class_mix,
            names="vehicle_class",
            values="vehicle_records",
            hole=0.60,
            color_discrete_sequence=GREEN_SCALE,
        )
        figure.update_traces(
            textinfo="percent",
            textposition="inside",
            marker={"line": {"color": CARD, "width": 2}},
            hovertemplate="%{label}<br>%{value:,} ratings<br>%{percent}<extra></extra>",
        )
        figure = style_figure(figure, "Class Composition", height=350, show_grid=False)
        figure.add_annotation(
            x=0.5,
            y=0.5,
            text=(
                f"<b>{filtered['vehicle_class'].nunique():,}</b>"
                "<br><span style='font-size:10px'>classes</span>"
            ),
            showarrow=False,
            font={"size": 18, "color": TEXT},
        )
        figure.update_layout(
            legend={"orientation": "v", "x": 1.02, "xanchor": "left", "y": 0.52},
            margin={"l": 20, "r": 104, "t": 62, "b": 24},
        )
        chart_card(figure)


def model_performance(kpis: pd.Series, search_query: str) -> None:
    metrics = load_model_metrics()
    importance = load_feature_importance()
    predictions = apply_search(load_test_predictions(), search_query)
    segment_errors = load_segment_errors()
    page_header(
        "Model Performance",
        "Temporal evaluation of the selected early-specification CO₂ model.",
        predictions,
        "model_performance",
    )
    if predictions.empty:
        empty_selection()
        return

    selected_test = metrics.loc[
        (metrics["model_scope"] == "early_specification")
        & (metrics["split"] == "test")
        & (metrics["eligible_for_selection"] == 1)
    ]
    if selected_test.empty:
        raise ValueError("Selected test-model metrics are missing.")
    selected_model_name = str(selected_test.iloc[0]["model_name"])

    st.markdown('<div class="filter-label">Filters</div>', unsafe_allow_html=True)
    f1, f2 = st.columns([1, 1.5])
    split_periods = {
        "test": "Test · 2022–2023",
        "validation": "Validation · 2020–2021",
    }
    available_splits = [
        split_periods[split]
        for split in ["test", "validation"]
        if not metrics.loc[
            (metrics["model_name"] == selected_model_name) & (metrics["split"] == split)
        ].empty
    ]
    selected_split_label = f1.selectbox(
        "Evaluation split",
        available_splits,
        key="model_split",
    )
    segment_types = segment_errors["segment_type"].drop_duplicates().tolist()
    segment_labels = {
        segment_type: str(segment_type).replace("_", " ").title()
        for segment_type in segment_types
    }
    selected_segment_label = f2.selectbox(
        "Error segment",
        ["All segments", *segment_labels.values()],
        key="error_segment",
    )
    selected_split = next(
        split for split, label in split_periods.items() if label == selected_split_label
    )

    selected_metric = metrics.loc[
        (metrics["model_name"] == selected_model_name)
        & (metrics["split"] == selected_split)
    ].iloc[0]
    render_kpis(
        [
            ("Selected Model", selected_model_name, "validation MAE selection"),
            ("MAE", f"{float(selected_metric['mae']):.2f}", "g/km"),
            ("R²", f"{float(selected_metric['r_squared']):.3f}", selected_split),
            (
                "P90 Absolute Error",
                f"{float(selected_metric['p90_absolute_error']):.2f}",
                "g/km",
            ),
        ]
    )

    plot_predictions = predictions
    if len(plot_predictions) > 3500:
        plot_predictions = plot_predictions.sample(3500, random_state=42)
    figure = px.scatter(
        plot_predictions,
        x="actual_co2_g_km",
        y="predicted_co2_g_km",
        color="vehicle_class",
        hover_data=["model_year", "make", "model", "absolute_error_g_km"],
        color_discrete_sequence=GREEN_SCALE,
        opacity=0.62,
        labels={
            "actual_co2_g_km": "Actual CO₂ (g/km)",
            "predicted_co2_g_km": "Predicted CO₂ (g/km)",
        },
    )
    low = float(
        min(predictions["actual_co2_g_km"].min(), predictions["predicted_co2_g_km"].min())
    )
    high = float(
        max(predictions["actual_co2_g_km"].max(), predictions["predicted_co2_g_km"].max())
    )
    figure.add_shape(
        type="line",
        x0=low,
        y0=low,
        x1=high,
        y1=high,
        line={"color": MUTED, "dash": "dash", "width": 1.5},
    )
    figure.update_layout(showlegend=False)

    validation = metrics.loc[
        (metrics["split"] == "validation")
        & (metrics["model_scope"] == "early_specification")
        & (metrics["eligible_for_selection"] == 1)
    ].sort_values("mae", ascending=False)
    validation_figure = go.Figure(
        go.Bar(
            x=validation["mae"],
            y=validation["model_name"],
            orientation="h",
            marker={"color": LIGHT_GREEN, "cornerradius": 7},
            hovertemplate="%{y}<br>MAE %{x:.2f} g/km<extra></extra>",
        )
    )
    validation_figure.update_xaxes(title="MAE (g/km)")

    left, right = st.columns([1.3, 1])
    with left:
        chart_card(style_figure(figure, "Actual vs Predicted CO₂", height=365))
    with right:
        chart_card(
            style_figure(
                validation_figure,
                "Validation MAE",
                height=365,
                show_grid=False,
            )
        )

    importance_plot = importance.nlargest(10, "importance_mean_mae_increase").sort_values(
        "importance_mean_mae_increase"
    )
    importance_figure = go.Figure(
        go.Bar(
            x=importance_plot["importance_mean_mae_increase"],
            y=importance_plot["feature"],
            orientation="h",
            marker={"color": MID_GREEN, "cornerradius": 7},
            hovertemplate="%{y}<br>MAE increase %{x:.3f}<extra></extra>",
        )
    )
    importance_figure.update_xaxes(title="MAE increase after shuffle")

    if selected_segment_label == "All segments":
        selected_errors = segment_errors.copy()
    else:
        selected_segment = next(
            value for value, label in segment_labels.items() if label == selected_segment_label
        )
        selected_errors = segment_errors.loc[
            segment_errors["segment_type"] == selected_segment
        ].copy()
    selected_errors = selected_errors.nlargest(6, "mae").sort_values("mae")
    error_figure = go.Figure(
        go.Bar(
            x=selected_errors["mae"],
            y=selected_errors["segment_value"],
            orientation="h",
            marker={"color": LIGHT_GREEN, "cornerradius": 7},
            customdata=selected_errors[["vehicle_records"]],
            hovertemplate="%{y}<br>MAE %{x:.2f} g/km<br>%{customdata[0]:,} ratings<extra></extra>",
        )
    )
    error_figure.update_xaxes(title="MAE (g/km)")

    left, right = st.columns(2)
    with left:
        chart_card(
            style_figure(
                importance_figure,
                "Permutation Feature Importance",
                height=355,
                show_grid=False,
            )
        )
    with right:
        chart_card(
            style_figure(
                error_figure,
                "MAE by Vehicle Segment",
                height=355,
                show_grid=False,
            )
        )


def opportunity_scenario(kpis: pd.Series, search_query: str) -> None:
    data = apply_search(load_opportunities(), search_query)
    page_header(
        "Opportunity Scenario",
        "Explore the class-year peer gap under an adjustable distance scenario.",
        data,
        "opportunity_scenario",
    )
    if data.empty:
        empty_selection()
        return

    opportunity_first_year = int(data["model_year"].min())
    opportunity_latest_year = int(data["model_year"].max())
    st.markdown('<div class="filter-label">Filters and scenario controls</div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1, 1.2, 1.05])
    year_range = f1.slider(
        "Model year",
        opportunity_first_year,
        opportunity_latest_year,
        (opportunity_first_year, opportunity_latest_year),
        key="opportunity_year",
    )
    classes = f2.multiselect(
        "Vehicle class",
        sorted(data["vehicle_class"].dropna().unique()),
        placeholder="All classes",
        key="opportunity_class",
    )
    fuels = f3.multiselect(
        "Fuel type",
        sorted(data["fuel_type"].dropna().unique()),
        placeholder="All fuel types",
        key="opportunity_fuel",
    )
    c1, c2 = st.columns(2)
    annual_km = c1.slider(
        "Annual distance per vehicle (km)",
        5_000,
        50_000,
        20_000,
        1_000,
        key="annual_distance",
    )
    vehicle_count = c2.number_input(
        "Scenario vehicle count",
        min_value=1,
        max_value=1_000_000,
        value=1_000,
        step=100,
        key="scenario_count",
    )

    filtered = data.loc[data["model_year"].between(*year_range)].copy()
    if classes:
        filtered = filtered.loc[filtered["vehicle_class"].isin(classes)]
    if fuels:
        filtered = filtered.loc[filtered["fuel_type"].isin(fuels)]
    if filtered.empty:
        empty_selection()
        return

    average_gap = float(filtered["co2_gap_to_class_p25"].mean())
    scenario_tonnes = average_gap * annual_km * int(vehicle_count) / 1_000_000
    render_kpis(
        [
            ("Configurations Screened", f"{len(filtered):,}", "positive peer-gap ratings"),
            ("Average Peer Gap", f"{average_gap:.1f}", "g/km to class-year P25"),
            ("Annual Distance", f"{annual_km:,}", "km per vehicle"),
            ("Scenario Gap", f"{scenario_tonnes:,.1f}", "tCO₂ per year"),
        ]
    )

    top = filtered.nlargest(6, "co2_gap_to_class_p25").copy()
    top["vehicle_label"] = top["make"] + " — " + top["model"]
    top = top.sort_values("co2_gap_to_class_p25")
    largest_figure = go.Figure(
        go.Bar(
            x=top["co2_gap_to_class_p25"],
            y=top["vehicle_label"],
            orientation="h",
            marker={"color": MID_GREEN, "cornerradius": 7},
            hovertemplate="%{y}<br>%{x:.1f} g/km<extra></extra>",
        )
    )
    largest_figure.update_xaxes(title="Gap to class-year P25 (g/km)")

    mix_source = (
        filtered.groupby("vehicle_class", as_index=False)
        .size()
        .rename(columns={"size": "configurations"})
    )
    mix = category_mix(mix_source, "vehicle_class", "configurations", limit=6)
    mix_figure = px.pie(
        mix,
        names="vehicle_class",
        values="configurations",
        hole=0.60,
        color_discrete_sequence=GREEN_SCALE,
    )
    mix_figure.update_traces(
        textinfo="percent",
        textposition="inside",
        marker={"line": {"color": CARD, "width": 2}},
        hovertemplate="%{label}<br>%{value:,} configurations<br>%{percent}<extra></extra>",
    )

    left, right = st.columns([1.35, 1])
    with left:
        chart_card(
            style_figure(
                largest_figure,
                "Largest Gaps to Class-Year P25",
                height=375,
                show_grid=False,
            )
        )
    with right:
        mix_figure = style_figure(
            mix_figure,
            "Opportunity Mix by Vehicle Class",
            height=375,
            show_grid=False,
        )
        mix_figure.add_annotation(
            x=0.5,
            y=0.5,
            text=f"<b>{len(filtered):,}</b><br><span style='font-size:10px'>screened</span>",
            showarrow=False,
            font={"size": 18, "color": TEXT},
        )
        mix_figure.update_layout(
            legend={"orientation": "v", "x": 1.02, "xanchor": "left", "y": 0.52},
            margin={"l": 20, "r": 112, "t": 62, "b": 24},
        )
        chart_card(mix_figure)

    distances = list(range(5_000, 50_001, 5_000))
    scenario_values = [
        average_gap * distance * int(vehicle_count) / 1_000_000 for distance in distances
    ]
    sensitivity_figure = go.Figure(
        go.Scatter(
            x=distances,
            y=scenario_values,
            mode="lines+markers",
            line={"color": GREEN, "width": 3},
            marker={"size": 6, "color": CARD, "line": {"color": GREEN, "width": 2}},
            fill="tozeroy",
            fillcolor="rgba(41, 153, 102, 0.10)",
            hovertemplate="%{x:,} km<br>%{y:,.1f} tCO₂<extra></extra>",
        )
    )
    sensitivity_figure.update_xaxes(title="Annual distance per vehicle (km)")
    sensitivity_figure.update_yaxes(title="Scenario gap (tCO₂/year)", rangemode="tozero")

    distribution_figure = go.Figure(
        go.Histogram(
            x=filtered["co2_gap_to_class_p25"],
            nbinsx=18,
            marker={"color": LIGHT_GREEN, "line": {"color": CARD, "width": 1}},
            hovertemplate="Peer gap %{x:.1f} g/km<br>%{y} configurations<extra></extra>",
        )
    )
    distribution_figure.update_xaxes(title="Gap to class-year P25 (g/km)")
    distribution_figure.update_yaxes(title="Configurations")

    left, right = st.columns([1.35, 1])
    with left:
        chart_card(style_figure(sensitivity_figure, "Scenario Sensitivity", height=350))
    with right:
        chart_card(style_figure(distribution_figure, "Peer Gap Distribution", height=350))


with st.sidebar:
    st.markdown(
        '<div class="brand"><span class="brand-mark">●</span>Fuel Analytics</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="menu-label">Menu</div>', unsafe_allow_html=True)
    page = st.radio(
        "Dashboard page",
        [
            "Executive Overview",
            "Segment Benchmark",
            "Model Performance",
            "Opportunity Scenario",
        ],
        label_visibility="collapsed",
    )
    st.markdown(
        """
        <div class="general-links">
          <div class="menu-label">General</div>
          <span><i></i>Data Quality</span>
          <span><i></i>Documentation</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


try:
    dashboard_kpi_frame = load_kpis()
    dashboard_kpis = dashboard_kpi_frame.iloc[0]
    search_query = render_top_toolbar(
        int(dashboard_kpis["first_model_year"]),
        int(dashboard_kpis["latest_model_year"]),
    )
    if page == "Executive Overview":
        executive_overview(dashboard_kpis, search_query)
    elif page == "Segment Benchmark":
        segment_benchmark(dashboard_kpis, search_query)
    elif page == "Model Performance":
        model_performance(dashboard_kpis, search_query)
    else:
        opportunity_scenario(dashboard_kpis, search_query)

    with st.sidebar:
        st.markdown(
            """
            <div class="db-card">
              <strong>MySQL</strong>
              fuel_emissions_db<br>
              <span>● Connected</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
except Exception as exc:
    st.error(
        "The dashboard could not complete its MySQL query. Confirm that the pipeline "
        "finished successfully and that `.env` contains the correct credentials."
    )
    with st.expander("Technical details"):
        st.code(f"{type(exc).__name__}: {exc}")
