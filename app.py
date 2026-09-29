"""Streamlit interface for the Hydrogen Shipping Cost Model."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from model import calculate_case, metadata, sensitivity_analysis
from presentation import (
    DELIVERED_COST_LABEL,
    SHIPPING_COST_LABEL,
    annual_quantity_metric_values,
    build_cost_comparison_rows,
    build_summary_rows,
    lowest_delivered_cost,
)


st.set_page_config(page_title="Hydrogen Shipping Cost Model", page_icon="H₂", layout="wide")
st.markdown(
    """
    <style>
    #MainMenu, header, footer {visibility: hidden;}
    .stApp {background: #ffffff; color: #142329;}
    .block-container {max-width: 1500px; padding: 0.7rem 1.8rem 2.5rem;}
    .nav {display:grid;grid-template-columns:1fr auto;align-items:center;min-height:64px;
          margin:-0.7rem -1.8rem 1rem;padding:0 2rem;border-bottom:1px solid #dce5e1;background:#fff;}
    .brand {display:flex;align-items:center;gap:10px;color:#0b6b55;font-size:1.35rem;font-weight:800;}
    .brand-mark {display:inline-grid;place-items:center;width:42px;height:42px;border-radius:50%;background:#075646;color:white;}
    .nav-status {color:#617079;font-size:.9rem;}.dot {display:inline-block;width:9px;height:9px;margin-right:7px;border-radius:50%;background:#19ae59;}
    div[data-testid="stForm"] {border:1px solid #dce5e1;border-radius:12px;padding:1.1rem;}
    div[data-testid="stMetric"] {border:1px solid #d7e5df;border-radius:10px;padding:1rem;background:#f8fcfa;min-height:125px;}
    div[data-testid="stMetricValue"] {
        color:#075c4b;font-weight:750;
        font-size:clamp(1.05rem,1.55vw,1.75rem);
        line-height:1.2;white-space:normal;overflow:visible;text-overflow:clip;
    }
    div[data-testid="stMetric"] div[data-testid="stMarkdownContainer"] p {
        white-space:normal!important;overflow:visible!important;text-overflow:clip!important;
        overflow-wrap:anywhere;line-height:1.2;
    }
    div[data-testid="stMetricValue"] p {
        font-size:clamp(.9rem,1.35vw,1.65rem)!important;
        white-space:normal!important;overflow-wrap:anywhere;
    }
    .section-title {font-size:1.4rem;font-weight:800;margin:0 0 .8rem;color:#142329;}
    .section-number {color:#0b7a59;margin-right:.55rem;}
    .scope {padding:.7rem 1rem;border-left:4px solid #0b7a59;background:#f5faf8;color:#42545c;margin-bottom:1rem;}
    @media (max-width:800px){.block-container{padding-left:1rem;padding-right:1rem}.brand{font-size:1.08rem}}
    </style>
    <nav class="nav">
      <div class="brand"><span class="brand-mark">H₂</span>Hydrogen Shipping Cost Model</div>
      <div class="nav-status"><span class="dot"></span>Model ready</div>
    </nav>
    """,
    unsafe_allow_html=True,
)

INFO = metadata()
D = INFO["defaults"]
C = INFO["carrier_defaults"]


def by_carrier(output: dict) -> dict[str, dict]:
    return {item["carrier"]: item for item in output["results"]}


def cost_groups(result: dict, delivered: bool) -> dict[str, float]:
    values = result["breakdown"]["delivered_transport_chain_aud_per_kg_h2" if delivered else "shipping_aud_per_kg_h2"]
    capex = {"Ship CAPEX", "Storage CAPEX", "Additional CAPEX"}
    losses = {"Fuel", "Carbon", "Shipping BOG", "Storage BOG", "Cracking carbon"}
    groups = {"CAPEX": 0.0, "OPEX": 0.0, "Fuel, losses & carbon": 0.0, "Cracking": 0.0}
    for key, value in values.items():
        if key in capex:
            groups["CAPEX"] += value
        elif key == "Ammonia cracking":
            groups["Cracking"] += value
        elif key in losses:
            groups["Fuel, losses & carbon"] += value
        else:
            groups["OPEX"] += value
    return groups


left, right = st.columns([0.36, 0.64], gap="medium")
with left:
    st.markdown('<div class="section-title"><span class="section-number">01</span>Scenario inputs</div>', unsafe_allow_html=True)
    with st.form("inputs"):
        route_name = st.selectbox("Route", INFO["routes"], disabled=True)
        departure = st.selectbox("Departure port", INFO["departures"], disabled=True)
        arrival = st.selectbox("Arrival port", INFO["arrivals"], disabled=True)
        voyage_factor = st.number_input("Voyage time adjustment factor", 1.0, 3.0, D["voyage_time_adjustment_factor"], 0.05,
            help="1.00 uses the distance-derived duration; increase for weather or operational delays.")
        base_days = 7148.72 / (20.0 * 1.852 * 24.0)
        st.caption(f"Effective one-way voyage duration: {base_days * voyage_factor:.2f} days")

        a, b = st.columns(2)
        operating_days = a.number_input("Operating days/year", 1.0, 366.0, D["operating_days_year"], 1.0)
        port_round_trip = b.number_input("Port days/round trip", 0.0, 200.0, D["port_days_each_end"] * 2, 0.5)
        carriers = st.multiselect("Carrier type", INFO["carriers"], default=INFO["carriers"])

        with st.expander("Economic assumptions"):
            a, b = st.columns(2)
            interest = a.number_input("Interest rate (%)", 0.0, 100.0, D["interest_rate_pct"], 0.5)
            life = b.number_input("Economic life (years)", 1.0, 100.0, D["economic_life_years"], 1.0)
            a, b = st.columns(2)
            aud_usd = a.number_input("AUD–USD rate", 0.01, 10.0, D["aud_usd"], 0.01)
            carbon_price = b.number_input("Carbon price (USD/tCO₂e)", 0.0, 10000.0, D["carbon_price_usd_tonne"], 10.0)
            include_h2_carbon = st.checkbox("Include supplementary H₂ leakage impact in carbon cost", D["include_h2_leakage_in_carbon_cost"])

        with st.expander("Ammonia cracking"):
            cracker_conversion = st.number_input("Cracker conversion (%)", 95.0, 99.9, D["cracker_conversion_pct"], 0.1)
            psa_recovery = st.number_input("PSA recovery (%)", 65.0, 90.0, D["psa_recovery_pct"], 1.0)
            cracking_cost = st.number_input("Cracking cost (USD/kg H₂)", 0.20, 0.80, D["cracking_cost_usd_per_kg_h2"], 0.05)
            heat_source = st.selectbox("Cracking heat source", ["Electric heating", "Process hydrogen/off-gas", "Natural gas"])
            a, b = st.columns(2)
            cracking_electricity = a.number_input("Electricity (kWh/kg H₂)", 0.0, 20.0, D["cracking_electricity_kwh_kg_h2"], 0.1)
            cracking_thermal = b.number_input("Thermal energy (kWhth/kg H₂)", 0.0, 30.0, D["cracking_thermal_kwhth_kg_h2"], 0.1)
            heater_efficiency = st.number_input("Electric heater efficiency (%)", 85.0, 100.0, D["heater_efficiency_pct"], 1.0)

        with st.expander("Storage, fill and heel"):
            a, b = st.columns(2)
            export_days = a.number_input("Export storage (days)", 1.0, 7.0, D["export_storage_days"], 1.0)
            import_days = b.number_input("Import storage (days)", 3.0, 30.0, D["import_storage_days"], 1.0)
            st.caption("Ammonia")
            a, b = st.columns(2)
            nh3_storage = a.number_input("NH₃ storage loss (%/day)", 0.0, 0.025, C["Ammonia"]["storage_bog_pct_day"], 0.001, format="%.3f")
            nh3_bog = b.number_input("NH₃ shipping BOG (%/day)", 0.025, 0.10, C["Ammonia"]["transport_bog_pct_day"], 0.005, format="%.3f")
            a, b = st.columns(2)
            nh3_fill = a.number_input("NH₃ fill fraction (%)", 95.0, 98.0, C["Ammonia"]["fill_fraction_pct"], 0.5)
            nh3_heel = b.number_input("NH₃ heel (%)", 2.0, 10.0, C["Ammonia"]["heel_fraction_pct"], 0.5)
            st.caption("Liquid hydrogen")
            a, b = st.columns(2)
            h2_storage = a.number_input("LH₂ storage BOG (%/day)", 0.01, 0.30, C["Hydrogen"]["storage_bog_pct_day"], 0.01)
            h2_bog = b.number_input("LH₂ shipping BOG (%/day)", 0.10, 0.50, C["Hydrogen"]["transport_bog_pct_day"], 0.05)
            a, b = st.columns(2)
            h2_fill = a.number_input("LH₂ fill fraction (%)", 90.0, 95.0, C["Hydrogen"]["fill_fraction_pct"], 0.5)
            h2_heel = b.number_input("LH₂ heel (%)", 2.0, 10.0, C["Hydrogen"]["heel_fraction_pct"], 0.5)

        with st.expander("Emissions and terminal energy"):
            a, b = st.columns(2)
            qld_grid = a.number_input("Queensland grid (kg CO₂e/kWh)", 0.0, 2.0, D["queensland_grid_kgco2e_kwh"], 0.01)
            japan_grid = b.number_input("Japan grid (kg CO₂e/kWh)", 0.0, 2.0, D["japan_grid_kgco2e_kwh"], 0.01)
            a, b = st.columns(2)
            nh3_terminal = a.number_input("NH₃ terminal electricity (kWh/kg)", 0.0, 2.0, C["Ammonia"]["terminal_electricity_kwh_kg"], 0.001, format="%.3f")
            h2_terminal = b.number_input("LH₂ terminal electricity (kWh/kg)", 0.0, 3.0, C["Hydrogen"]["terminal_electricity_kwh_kg"], 0.01)
            st.caption("Import terminal values use the same editable proxy assumption; they are not Tokyo measurements.")
            a, b = st.columns(2)
            n2o_intensity = a.number_input("NH₃-engine N₂O (g CO₂e/MJ)", 0.0, 41.0, D["ammonia_engine_n2o_gco2e_mj"], 0.5)
            h2_gwp = b.number_input("Hydrogen GWP100", 0.0, 30.0, D["hydrogen_gwp100"], 0.1)
            bog_managed = st.number_input("BOG controlled/utilised (%)", 0.0, 100.0, 100.0, 1.0)
            st.caption(f"BOG vented to atmosphere: {100.0 - bog_managed:.1f}%")
            nh3_slip = st.number_input("NH₃ fuel slip (%)", 0.0, 10.0, 0.0, 0.01)

        submitted = st.form_submit_button("Calculate", type="primary", width="stretch")

payload = {
    "route": route_name, "departure": departure, "arrival": arrival,
    "voyage_time_adjustment_factor": voyage_factor, "operating_days_year": operating_days,
    "port_days_each_end": port_round_trip / 2.0, "carriers": carriers,
    "interest_rate_pct": interest, "economic_life_years": life, "aud_usd": aud_usd,
    "carbon_price_usd_tonne": carbon_price, "include_h2_leakage_in_carbon_cost": include_h2_carbon,
    "export_storage_days": export_days, "import_storage_days": import_days,
    "cracker_conversion_pct": cracker_conversion, "psa_recovery_pct": psa_recovery,
    "cracking_cost_usd_per_kg_h2": cracking_cost, "cracking_heat_source": heat_source,
    "cracking_electricity_kwh_kg_h2": cracking_electricity,
    "cracking_thermal_kwhth_kg_h2": cracking_thermal, "heater_efficiency_pct": heater_efficiency,
    "queensland_grid_kgco2e_kwh": qld_grid, "japan_grid_kgco2e_kwh": japan_grid,
    "ammonia_engine_n2o_gco2e_mj": n2o_intensity, "hydrogen_gwp100": h2_gwp,
    "carrier_overrides": {
        "Ammonia": {"transport_bog_pct_day": nh3_bog, "storage_bog_pct_day": nh3_storage,
            "fill_fraction_pct": nh3_fill, "heel_fraction_pct": nh3_heel,
            "bog_managed_pct": bog_managed, "bog_vented_pct": 100.0 - bog_managed,
            "terminal_electricity_kwh_kg": nh3_terminal, "import_terminal_electricity_kwh_kg": nh3_terminal,
            "nh3_slip_pct_fuel": nh3_slip},
        "Hydrogen": {"transport_bog_pct_day": h2_bog, "storage_bog_pct_day": h2_storage,
            "fill_fraction_pct": h2_fill, "heel_fraction_pct": h2_heel,
            "bog_managed_pct": bog_managed, "bog_vented_pct": 100.0 - bog_managed,
            "terminal_electricity_kwh_kg": h2_terminal, "import_terminal_electricity_kwh_kg": h2_terminal},
    },
}

try:
    output = calculate_case(payload)
except ValueError as error:
    with right:
        st.error(str(error))
    st.stop()

with right:
    results = by_carrier(output)
    st.markdown('<div class="section-title"><span class="section-number">02</span>Model outputs</div>', unsafe_allow_html=True)
    st.markdown('<div class="scope"><b>Transport-chain boundary:</b> Australian export terminal → ocean shipping → Japanese import terminal → ammonia cracking. Hydrogen and ammonia production are excluded.</div>', unsafe_allow_html=True)
    first = next(iter(results.values()))
    cheapest = lowest_delivered_cost(results.values())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Lowest delivered cost",
        f"A${cheapest['totals']['delivered_transport_chain_cost_aud_per_kg_h2']:.2f}/kg H₂",
        cheapest["carrier"],
    )
    m2.metric("Route distance", f"{first['route']['distance_km']:,.0f} km", "one way")
    m3.metric("Effective voyage", f"{first['route']['one_way_days']:.2f} days", "one way")
    m4.metric("Annual sailings", f"{first['operations']['trips_per_year']:.2f}", "round trips/year")

    summary = pd.DataFrame(build_summary_rows(results))
    st.dataframe(summary.style.format(precision=3, thousands=","), hide_index=True, width="stretch")
    st.download_button("Download result summary (CSV)", summary.to_csv(index=False).encode("utf-8-sig"), "hydrogen_shipping_results.csv", "text/csv")

    with st.container(border=True):
        st.subheader("Shipping and delivered transport-chain cost")
        cost_chart = pd.DataFrame(build_cost_comparison_rows(results)).set_index("Carrier")
        st.bar_chart(
            cost_chart[[SHIPPING_COST_LABEL, DELIVERED_COST_LABEL]],
            height=280,
            width="stretch",
            stack=False,
        )

    with st.container(border=True):
        st.subheader("Cost breakdown")
        delivered_view = st.toggle("Show delivered-cost breakdown", value=True)
        groups = pd.DataFrame([{"Carrier": name, **cost_groups(result, delivered_view)} for name, result in results.items()]).set_index("Carrier")
        st.bar_chart(groups, height=290, width="stretch")

    carrier_tabs = st.tabs(list(results))
    for tab, (name, result) in zip(carrier_tabs, results.items()):
        with tab:
            t = result["totals"]
            a, b, c = st.columns(3)
            medium_value, h2_value = annual_quantity_metric_values(result)
            a.metric("Usable transported medium", medium_value)
            b.metric("Delivered H₂", h2_value)
            c.metric("GHG intensity", f"{t['emissions_kgco2e_per_kg_delivered_h2']:.3f} kgCO₂e/kgH₂")
            st.caption(f"NH₃ slip: {t['nh3_slip_kg_year']:,.1f} kg/year · Supplementary H₂ leakage impact: {t['supplementary_h2_leakage_tco2e_year']:,.1f} t CO₂e/year")
            emissions = pd.DataFrame([{"Stage": k, "t CO₂e/year": v} for k, v in result["emissions_breakdown_tco2e"].items()])
            st.bar_chart(emissions, x="Stage", y="t CO₂e/year", height=240, width="stretch")
            with st.expander("Mass-balance audit"):
                mass = pd.DataFrame([{"Flow": k.replace("_", " ").title(), "kg/trip": v} for k, v in result["mass_balance_per_trip_kg"].items()])
                st.dataframe(mass.style.format({"kg/trip": "{:,.0f}"}), hide_index=True, width="stretch")

st.caption("All results are estimates based on the selected assumptions.")

with st.expander("Sensitivity analysis"):
    st.write("One-at-a-time scenario analysis. Ranges are scenarios, not statistical confidence intervals.")
    sensitivity_carrier = st.selectbox("Carrier for sensitivity analysis", carriers or INFO["carriers"], key="sensitivity_carrier")
    try:
        sensitivity = pd.DataFrame(sensitivity_analysis(payload, sensitivity_carrier))
        metric = st.selectbox("Rank by", ["Delivered cost", "Shipping cost", "Emissions"])
        metric_columns = {
            "Delivered cost": ["Delivered cost @ low input", "Delivered cost @ base input", "Delivered cost @ high input"],
            "Shipping cost": ["Shipping cost @ low input", "Shipping cost @ base input", "Shipping cost @ high input"],
            "Emissions": ["Emissions @ low input", "Emissions @ base input", "Emissions @ high input"],
        }
        selected_columns = metric_columns[metric]
        sensitivity["Impact span"] = (sensitivity[selected_columns[2]] - sensitivity[selected_columns[0]]).abs()
        sensitivity = sensitivity.sort_values("Impact span", ascending=False)
        chart = sensitivity.head(15).set_index("Parameter")[selected_columns].rename(columns={
            selected_columns[0]: "Low input scenario",
            selected_columns[1]: "Base scenario",
            selected_columns[2]: "High input scenario",
        })
        st.bar_chart(chart, height=430, width="stretch")
        st.dataframe(sensitivity, hide_index=True, width="stretch")
        st.download_button("Download sensitivity results (CSV)", sensitivity.to_csv(index=False).encode("utf-8-sig"), f"sensitivity_{sensitivity_carrier.lower()}.csv", "text/csv")
    except ValueError as error:
        st.warning(str(error))

with st.expander("Parameter sources"):
    sources = pd.DataFrame(INFO["parameter_sources"])
    sources["base_value"] = sources["base_value"].astype(str)
    st.dataframe(sources, hide_index=True, width="stretch")
    st.download_button("Download sources (CSV)", sources.to_csv(index=False).encode("utf-8-sig"), "parameter_sources.csv", "text/csv")
