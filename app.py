"""HySupply Shipping Calculator — 初学者版 Streamlit 网页。

运行命令：streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from model import calculate_case, metadata


# 1. 页面基础设置
st.set_page_config(
    page_title="HySupply Shipping Calculator",
    page_icon="H₂",
    layout="wide",
)


# 2. 简单样式：只负责颜色、边距和顶部导航
st.markdown(
    """
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp {background: #ffffff; color: #142329;}
    .block-container {max-width: 1500px; padding: 0.7rem 1.8rem 2.5rem;}
    .nav {
        display: grid; grid-template-columns: 1fr auto 1fr; align-items: center;
        min-height: 64px; margin: -0.7rem -1.8rem 1rem; padding: 0 2rem;
        border-bottom: 1px solid #dce5e1; background: #ffffff;
    }
    .brand {display: flex; align-items: center; gap: 10px; color: #0b6b55; font-size: 1.45rem; font-weight: 800;}
    .brand-mark {display: inline-grid; place-items: center; width: 42px; height: 42px; border-radius: 50%; background: #075646; color: white; font-size: 1rem;}
    .nav-links {display: flex; gap: 2.2rem;}
    .nav-links a {color: #52616b; text-decoration: none; font-size: 1rem; padding: 21px 0 17px;}
    .nav-links a.active {color: #086c55; border-bottom: 2px solid #118865; font-weight: 700;}
    .nav-status {justify-self: end; color: #617079; font-size: 0.9rem;}
    .dot {display: inline-block; width: 9px; height: 9px; margin-right: 7px; border-radius: 50%; background: #19ae59;}
    div[data-testid="stForm"] {border: 1px solid #dce5e1; border-radius: 12px; padding: 1.1rem;}
    div[data-testid="stMetric"] {border: 1px solid #d7e5df; border-radius: 10px; padding: 1rem; background: #f8fcfa; min-height: 130px;}
    div[data-testid="stMetricValue"] {color: #075c4b; font-weight: 750;}
    div[data-testid="stVerticalBlockBorderWrapper"] {border-color: #dce5e1; border-radius: 12px;}
    .section-title {font-size: 1.45rem; font-weight: 800; margin: 0 0 0.8rem; color: #142329;}
    .section-number {color: #0b7a59; margin-right: 0.55rem;}
    .note {font-size: 0.86rem; color: #68767e;}
    @media (max-width: 800px) {
        .nav {grid-template-columns: 1fr auto;}
        .nav-links {display: none;}
        .block-container {padding-left: 1rem; padding-right: 1rem;}
    }
    </style>

    <nav class="nav">
      <div class="brand"><span class="brand-mark">H₂</span>Hydrogen Shipping Cost Model</div>
      <div class="nav-links">
        <a class="active" href="#calculator">Calculator</a>
      </div>
      <div class="nav-status"><span class="dot"></span>Model ready</div>
    </nav>
    <div id="calculator"></div>
    """,
    unsafe_allow_html=True,
)


MODEL_INFO = metadata()
DEFAULTS = MODEL_INFO["defaults"]


def result_by_carrier(output: dict) -> dict:
    """把结果列表转换为按运输介质名称索引的字典。"""
    return {item["carrier"]: item for item in output["results"]}


def cost_groups(result: dict) -> dict[str, float]:
    """把详细成本合并成三组，用于堆叠柱状图。"""
    values = result["breakdown"]["aud_per_kg_h2_graph"]
    capex_names = {"Ship CAPEX", "Storage CAPEX", "Additional CAPEX"}
    loss_names = {"Fuel", "Carbon", "Shipping BOG", "Storage BOG"}
    groups = {"CAPEX": 0.0, "OPEX": 0.0, "Fuel & losses": 0.0}
    for name, value in values.items():
        if name in capex_names:
            groups["CAPEX"] += value
        elif name in loss_names:
            groups["Fuel & losses"] += value
        else:
            groups["OPEX"] += value
    return groups


# 3. 左侧输入、右侧输出
input_column, output_column = st.columns([0.34, 0.66], gap="medium")

with input_column:
    st.markdown('<div class="section-title"><span class="section-number">01</span>Scenario inputs</div>', unsafe_allow_html=True)

    with st.form("shipping_inputs"):
        route_name = st.selectbox("Route", ["Australia – Japan (Base case)"])
        departure = st.selectbox("Departure port", ["Gladstone (QLD)"])
        arrival = st.selectbox("Arrival port", ["Tokyo (Japan)"])

        day_col, speed_col = st.columns(2)
        with day_col:
            one_way_days = st.number_input("One-way days", min_value=0.1, value=11.0, step=0.1)
        with speed_col:
            ship_speed = st.number_input("Ship speed (knots)", min_value=0.1, value=20.0, step=0.5)

        operation_col, port_col = st.columns(2)
        with operation_col:
            operating_days = st.number_input("Operating days (per year)", min_value=1.0, max_value=366.0, value=25.0, step=1.0)
        with port_col:
            port_days = st.number_input("Port days (per round trip)", min_value=0.0, value=3.0, step=0.5)

        carriers = st.multiselect(
            "Carrier type",
            options=["Ammonia", "Hydrogen"],
            default=["Ammonia", "Hydrogen"],
            help="可以选择一种，也可以同时比较两种运输介质。",
        )

        rate_col, life_col = st.columns(2)
        with rate_col:
            interest_rate = st.number_input("Interest rate (%)", min_value=0.0, value=5.0, step=0.5)
        with life_col:
            economic_life = st.number_input("Economic life (years)", min_value=1.0, value=20.0, step=1.0)

        exchange_col, carbon_col = st.columns(2)
        with exchange_col:
            aud_usd = st.number_input("AUD – USD rate", min_value=0.01, value=0.70, step=0.01)
        with carbon_col:
            carbon_price = st.number_input("Carbon price (USD/tCO₂e)", min_value=0.0, value=0.0, step=10.0)

        submitted = st.form_submit_button("Calculate", type="primary", width="stretch")


# 4. 调用 model.py；业务公式不会写在页面文件里
payload = {
    "departure": departure,
    "arrival": arrival,
    "one_way_days": one_way_days,
    "ship_speed_knots": ship_speed,
    "operating_days_year": operating_days,
    "port_days_each_end": port_days / 2,
    "interest_rate_pct": interest_rate,
    "economic_life_years": economic_life,
    "aud_usd": aud_usd,
    "carbon_price_usd_tonne": carbon_price,
    "carriers": carriers,
}

try:
    output = calculate_case(payload)
except ValueError as error:
    with output_column:
        st.error(str(error))
    st.stop()


with output_column:
    results = result_by_carrier(output)
    st.markdown('<div class="section-title"><span class="section-number">02</span>Model outputs</div>', unsafe_allow_html=True)
    st.caption(f"{route_name}: {departure} → {arrival}")

    cheapest = min(results.values(), key=lambda item: item["totals"]["aud_per_kg_h2_graph"])
    first_result = next(iter(results.values()))

    metric_1, metric_2, metric_3 = st.columns(3)
    with metric_1:
        st.metric(
            "Lowest shipping cost",
            f"A$ {cheapest['totals']['aud_per_kg_h2_graph']:.2f}",
            f"per kg H₂ delivered · {cheapest['carrier']}",
        )
    with metric_2:
        st.metric("Route distance", f"{first_result['route']['distance_nm']:,.0f} nm", "one way")
    with metric_3:
        st.metric("Annual sailings", f"{first_result['operations']['trips_per_year']:.2f}", "round trips per year")

    with st.container(border=True):
        st.subheader("Total shipping cost")
        total_rows = [
            {"Carrier": name, "A$ per kg H₂": result["totals"]["aud_per_kg_h2_graph"]}
            for name, result in results.items()
        ]
        total_chart = pd.DataFrame(total_rows)
        st.bar_chart(
            total_chart,
            x="Carrier",
            y="A$ per kg H₂",
            color="#0b665c",
            height=270,
            width="stretch",
        )

    with st.container(border=True):
        st.subheader("Cost breakdown")
        breakdown_rows = []
        for name, result in results.items():
            breakdown_rows.append({"Carrier": name, **cost_groups(result)})
        breakdown_chart = pd.DataFrame(breakdown_rows)
        st.bar_chart(
            breakdown_chart,
            x="Carrier",
            y=["CAPEX", "OPEX", "Fuel & losses"],
            color=["#0b5d58", "#37c84a", "#f58a3a"],
            height=290,
            width="stretch",
        )

    st.caption("All results are estimates based on the selected assumptions.")
