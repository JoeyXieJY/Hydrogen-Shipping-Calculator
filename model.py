"""Auditable shipping-cost, mass-balance and transport-chain emissions model.

The calculation layer is intentionally independent of Streamlit. Monetary
components are stored as million USD/year and converted only for presentation.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).with_name("model_data.json")
REFERENCE = json.loads(DATA_PATH.read_text(encoding="utf-8"))
KNOT_TO_KM_PER_HOUR = 1.852
GWP100_CH4 = 28.0
GWP100_N2O = 265.0
KG_PER_TONNE = 1_000.0
KG_PER_KILOTONNE = 1_000_000.0
KG_PER_MEGATONNE = 1_000_000_000.0


def kg_year_to_t_year(value: float) -> float:
    """Convert an annual mass flow from kg/year to t/year."""
    return value / KG_PER_TONNE


def kg_year_to_kt_year(value: float) -> float:
    """Convert an annual mass flow from kg/year to kt/year."""
    return value / KG_PER_KILOTONNE


def kg_year_to_mt_year(value: float) -> float:
    """Convert an annual mass flow from kg/year to Mt/year."""
    return value / KG_PER_MEGATONNE


def _num(value: Any, name: str, low: float | None = None, high: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    if low is not None and number < low:
        raise ValueError(f"{name} cannot be below {low}")
    if high is not None and number > high:
        raise ValueError(f"{name} cannot exceed {high}")
    return number


def capital_recovery_factor(rate_pct: float, years: float) -> float:
    rate = rate_pct / 100.0
    if years <= 0:
        raise ValueError("Economic life must be greater than zero")
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def exponential_remaining(initial_mass: float, rate_pct_day: float, days: float) -> float:
    """Return remaining mass after a discrete daily loss rate."""
    if initial_mass < 0 or days < 0 or not 0 <= rate_pct_day <= 100:
        raise ValueError("Invalid mass, duration or daily loss rate")
    return initial_mass * (1.0 - rate_pct_day / 100.0) ** days


def _deep_update(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_update(result[key], value)
        else:
            result[key] = value
    return result


def _validated_inputs(payload: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    payload = copy.deepcopy(payload or {})
    overrides = payload.pop("carrier_overrides", {})
    raw = {**REFERENCE["workbook_case"], **payload}
    route = REFERENCE["route"]
    for key, expected in (("departure", route["departure"]), ("arrival", route["arrival"]), ("route", route["name"])):
        if key in raw and raw[key] != expected:
            raise ValueError(f"{key} is fixed to {expected}")

    bounds = {
        "aud_usd": (0.01, None), "interest_rate_pct": (0, 100),
        "economic_life_years": (1, 100), "fuel_cost_usd_tonne": (0, None),
        "voyage_time_adjustment_factor": (1.0, 3.0), "operating_days_year": (0.1, 366),
        "maintenance_pct_capex": (0, 100), "misc_pct_opex": (0, 100),
        "insurance_pct_opex": (0, 100), "labour_musd_year": (0, None),
        "carbon_price_usd_tonne": (0, None), "port_days_each_end": (0, 100),
        "port_charge_musd_day": (0, None), "export_storage_days": (0, 365),
        "import_storage_days": (0, 365), "cracker_conversion_pct": (0, 100),
        "psa_recovery_pct": (0, 100), "cracking_cost_usd_per_kg_h2": (0, None),
        "queensland_grid_kgco2e_kwh": (0, None), "japan_grid_kgco2e_kwh": (0, None),
        "hydrogen_gwp100": (0, None), "ammonia_engine_n2o_gco2e_mj": (0, None),
        "cracking_electricity_kwh_kg_h2": (0, None),
        "cracking_thermal_kwhth_kg_h2": (0, None), "heater_efficiency_pct": (0.01, 100)
    }
    p = copy.deepcopy(raw)
    for field, (low, high) in bounds.items():
        p[field] = _num(raw[field], field, low, high)
    p["include_h2_leakage_in_carbon_cost"] = bool(raw["include_h2_leakage_in_carbon_cost"])
    if p["cracking_heat_source"] not in {"Electric heating", "Process hydrogen/off-gas", "Natural gas"}:
        raise ValueError("Unsupported cracking heat source")

    carrier_data: dict[str, dict[str, Any]] = {}
    for name, defaults in REFERENCE["carrier_defaults"].items():
        carrier_data[name] = _deep_update(defaults, overrides.get(name, {}))
        c = carrier_data[name]
        positive = ["lhv_mj_kg", "density_kg_m3", "ship_capacity_m3", "engine_mw", "engine_efficiency_pct"]
        for field in positive:
            c[field] = _num(c[field], f"{name}.{field}", 0.000001)
        for field in ["transport_bog_pct_day", "storage_bog_pct_day", "fill_fraction_pct", "heel_fraction_pct", "bog_managed_pct", "bog_vented_pct"]:
            c[field] = _num(c[field], f"{name}.{field}", 0, 100)
        if c["fill_fraction_pct"] <= c["heel_fraction_pct"]:
            raise ValueError(f"{name}: fill fraction must be greater than heel fraction")
        if not math.isclose(c["bog_managed_pct"] + c["bog_vented_pct"], 100.0, abs_tol=1e-9):
            raise ValueError(f"{name}: BOG managed and vented fractions must total 100%")
    return p, carrier_data


def _route(p: dict[str, Any]) -> dict[str, Any]:
    data = REFERENCE["route"]
    base_days = data["distance_km"] / (data["reference_speed_knots"] * KNOT_TO_KM_PER_HOUR * 24.0)
    return {
        **data,
        "calculated_one_way_days": base_days,
        "voyage_time_adjustment_factor": p["voyage_time_adjustment_factor"],
        "one_way_days": base_days * p["voyage_time_adjustment_factor"],
    }


def _fuel_combustion_emissions_tonnes(fuel_name: str, fuel_kg: float, fuel_energy_mj: float, p: dict[str, Any]) -> float:
    props = REFERENCE["fuel_properties"][fuel_name]
    co2 = fuel_kg / 1000.0 * props["co2_t_per_t"]
    ch4_co2e = fuel_kg * props.get("ch4_g_per_kg", 0.0) * GWP100_CH4 / 1_000_000.0
    n2o_co2e = fuel_kg * props.get("n2o_g_per_kg", 0.0) * GWP100_N2O / 1_000_000.0
    if fuel_name == "Ammonia":
        n2o_co2e = fuel_energy_mj * p["ammonia_engine_n2o_gco2e_mj"] / 1_000_000.0
    return co2 + ch4_co2e + n2o_co2e


def _carrier_result(name: str, p: dict[str, Any], c: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    crf = capital_recovery_factor(p["interest_rate_pct"], p["economic_life_years"])
    voyage_days = route["one_way_days"]
    trip_days = 2.0 * voyage_days + 2.0 * p["port_days_each_end"]
    trips = p["operating_days_year"] / trip_days

    nominal_mass = c["ship_capacity_m3"] * c["density_kg_m3"]
    departure_mass = nominal_mass * c["fill_fraction_pct"] / 100.0
    target_heel = nominal_mass * c["heel_fraction_pct"] / 100.0

    export_after_fraction = (1.0 - c["storage_bog_pct_day"] / 100.0) ** p["export_storage_days"]
    if export_after_fraction <= 0:
        raise ValueError(f"{name}: export storage loss leaves no cargo")
    export_feed = departure_mass / export_after_fraction
    export_storage_loss = export_feed - departure_mass

    mass_after_outbound_bog = exponential_remaining(departure_mass, c["transport_bog_pct_day"], voyage_days)
    outbound_bog = departure_mass - mass_after_outbound_bog

    input_energy_mj_day = c["engine_mw"] * 24.0 * 3600.0 / (c["engine_efficiency_pct"] / 100.0)
    fuel_lhv = REFERENCE["fuel_properties"][c["ship_fuel_source"]]["lhv_mj_kg"]
    fuel_demand_leg = input_energy_mj_day * voyage_days / fuel_lhv
    managed_outbound_bog = outbound_bog * c["bog_managed_pct"] / 100.0
    fuel_from_outbound_bog = min(managed_outbound_bog, fuel_demand_leg)
    outbound_fuel_gap = fuel_demand_leg - fuel_from_outbound_bog
    # The remaining propulsion demand is treated as separately bunkered fuel.
    # It is priced and emitted, but is not deducted from the cargo a second time.
    arrival_mass = mass_after_outbound_bog
    if arrival_mass <= target_heel:
        raise ValueError(f"{name}: arrival mass does not exceed the target heel")
    unloaded_mass = arrival_mass - target_heel

    heel_after_return_bog = exponential_remaining(target_heel, c["transport_bog_pct_day"], voyage_days)
    return_heel_bog = target_heel - heel_after_return_bog
    managed_return_bog = return_heel_bog * c["bog_managed_pct"] / 100.0
    fuel_from_return_bog = min(managed_return_bog, fuel_demand_leg)
    return_fuel_gap = fuel_demand_leg - fuel_from_return_bog
    heel_after_return = heel_after_return_bog
    heel_makeup = target_heel - heel_after_return

    usable_medium_trip = exponential_remaining(unloaded_mass, c["storage_bog_pct_day"], p["import_storage_days"])
    import_storage_loss = unloaded_mass - usable_medium_trip

    export_feed_year = export_feed * trips
    departure_mass_year = departure_mass * trips
    unloaded_mass_year = unloaded_mass * trips
    usable_medium_year = usable_medium_trip * trips
    outbound_bog_year = outbound_bog * trips
    return_bog_year = return_heel_bog * trips
    export_storage_loss_year = export_storage_loss * trips
    import_storage_loss_year = import_storage_loss * trips
    heel_makeup_year = heel_makeup * trips
    fuel_required_year = 2.0 * fuel_demand_leg * trips
    fuel_gap_year = (outbound_fuel_gap + return_fuel_gap) * trips

    average_export_daily = export_feed_year / p["operating_days_year"]
    average_import_daily = unloaded_mass_year / p["operating_days_year"]
    export_storage_mass = max(departure_mass, average_export_daily * p["export_storage_days"])
    import_storage_mass = max(unloaded_mass, average_import_daily * p["import_storage_days"])
    export_storage_m3 = export_storage_mass / c["density_kg_m3"]
    import_storage_m3 = import_storage_mass / c["density_kg_m3"]
    export_storage_capex = c["export_reference_cost_musd"] * (export_storage_m3 / c["export_reference_capacity_m3"]) ** c["export_scale_coefficient"]
    import_storage_capex = c["import_reference_cost_musd"] * (import_storage_m3 / c["import_reference_capacity_m3"]) ** c["import_scale_coefficient"]

    theoretical_h2_year = usable_medium_year * c["theoretical_h2_kg_per_kg"]
    recovered_h2_year = theoretical_h2_year
    cracking_h2_energy_use = 0.0
    cracking_natural_gas_kg = 0.0
    cracking_electricity_kwh = 0.0
    if name == "Ammonia":
        recovered_h2_year *= p["cracker_conversion_pct"] / 100.0 * p["psa_recovery_pct"] / 100.0
        cracking_electricity_kwh = recovered_h2_year * p["cracking_electricity_kwh_kg_h2"]
        thermal_kwh = recovered_h2_year * p["cracking_thermal_kwhth_kg_h2"]
        if p["cracking_heat_source"] == "Electric heating":
            cracking_electricity_kwh += thermal_kwh / (p["heater_efficiency_pct"] / 100.0)
        elif p["cracking_heat_source"] == "Process hydrogen/off-gas":
            cracking_h2_energy_use = thermal_kwh * 3.6 / REFERENCE["fuel_properties"]["Hydrogen"]["lhv_mj_kg"]
        else:
            cracking_natural_gas_kg = thermal_kwh * 3.6 / REFERENCE["fuel_properties"]["Natural gas"]["lhv_mj_kg"]
    delivered_h2_year = recovered_h2_year - cracking_h2_energy_use
    if min(usable_medium_year, theoretical_h2_year, recovered_h2_year, delivered_h2_year) <= 0:
        raise ValueError(f"{name}: calculated delivery is not positive")

    export_terminal_kwh = export_feed_year * c["terminal_electricity_kwh_kg"]
    import_terminal_kwh = unloaded_mass_year * c["import_terminal_electricity_kwh_kg"]
    export_emissions = export_terminal_kwh * p["queensland_grid_kgco2e_kwh"] / 1000.0
    import_emissions = import_terminal_kwh * p["japan_grid_kgco2e_kwh"] / 1000.0
    fuel_energy_year_mj = fuel_required_year * fuel_lhv
    shipping_emissions = _fuel_combustion_emissions_tonnes(c["ship_fuel_source"], fuel_required_year, fuel_energy_year_mj, p)
    cracking_emissions = cracking_electricity_kwh * p["japan_grid_kgco2e_kwh"] / 1000.0
    cracking_emissions += cracking_natural_gas_kg / 1000.0 * REFERENCE["fuel_properties"]["Natural gas"]["co2_t_per_t"]
    transport_chain_emissions = export_emissions + shipping_emissions + import_emissions + cracking_emissions
    shipping_chain_emissions = export_emissions + shipping_emissions + import_emissions

    vented_transport = (outbound_bog_year + return_bog_year) * c["bog_vented_pct"] / 100.0
    leaked_h2 = 0.0
    if name == "Hydrogen":
        leaked_h2 = vented_transport + export_storage_loss_year + import_storage_loss_year
    h2_leakage_tco2e = leaked_h2 * p["hydrogen_gwp100"] / 1000.0
    nh3_slip_kg = fuel_required_year * c.get("nh3_slip_pct_fuel", 0.0) / 100.0 if name == "Ammonia" else 0.0

    ship_capital = crf * c["ship_capex_musd"]
    storage_capital = crf * (export_storage_capex + import_storage_capex)
    additional_capital = crf * c["additional_capex_musd"]
    maintenance = p["maintenance_pct_capex"] / 100.0 * c["ship_capex_musd"]
    storage_opex = c["import_om_pct"] / 100.0 * import_storage_capex + c["export_om_pct"] / 100.0 * export_storage_capex
    port = p["port_charge_musd_day"] * p["port_days_each_end"] * trips * 2.0
    base_opex = p["labour_musd_year"] + port + maintenance + storage_opex + c["additional_opex_musd_year"]
    miscellaneous = base_opex * p["misc_pct_opex"] / 100.0
    insurance = base_opex * p["insurance_pct_opex"] / 100.0
    fuel_cost = fuel_gap_year * c["lhv_mj_kg"] / 1000.0 * c["market_price_usd_gj"] / 1_000_000.0
    shipping_bog_cost = (outbound_bog_year + return_bog_year) * c["lhv_mj_kg"] / 1000.0 * c["market_price_usd_gj"] / 1_000_000.0
    storage_bog_cost = (export_storage_loss_year + import_storage_loss_year) * c["lhv_mj_kg"] / 1000.0 * c["market_price_usd_gj"] / 1_000_000.0
    carbon_base = shipping_chain_emissions
    if p["include_h2_leakage_in_carbon_cost"]:
        carbon_base += h2_leakage_tco2e
    shipping_carbon_cost = carbon_base * p["carbon_price_usd_tonne"] / 1_000_000.0

    shipping_components = {
        "Ship CAPEX": ship_capital, "Storage CAPEX": storage_capital,
        "Additional CAPEX": additional_capital, "Labour": p["labour_musd_year"],
        "Port": port, "Maintenance": maintenance, "Miscellaneous": miscellaneous,
        "Insurance": insurance, "Storage OPEX": storage_opex,
        "Additional OPEX": c["additional_opex_musd_year"], "Fuel": fuel_cost,
        "Carbon": shipping_carbon_cost, "Shipping BOG": shipping_bog_cost,
        "Storage BOG": storage_bog_cost,
    }
    delivered_components = copy.deepcopy(shipping_components)
    if name == "Ammonia":
        delivered_components["Ammonia cracking"] = recovered_h2_year * p["cracking_cost_usd_per_kg_h2"] / 1_000_000.0
        delivered_components["Cracking carbon"] = cracking_emissions * p["carbon_price_usd_tonne"] / 1_000_000.0

    shipping_total = sum(shipping_components.values())
    delivered_total = sum(delivered_components.values())
    aud_per_usd = 1.0 / p["aud_usd"]
    shipping_per_kg_h2 = shipping_total * 1_000_000.0 / theoretical_h2_year * aud_per_usd
    delivered_cost_per_kg_h2 = delivered_total * 1_000_000.0 / delivered_h2_year * aud_per_usd
    shipping_breakdown = {k: v * 1_000_000.0 / theoretical_h2_year * aud_per_usd for k, v in shipping_components.items()}
    delivered_breakdown = {k: v * 1_000_000.0 / delivered_h2_year * aud_per_usd for k, v in delivered_components.items()}

    return {
        "carrier": name,
        "route": route,
        "operations": {
            "trip_days": trip_days, "trips_per_year": trips,
            "sailing_days": trips * voyage_days * 2.0,
            "fuel_required_kg_year": fuel_required_year, "fuel_gap_kg_year": fuel_gap_year,
            "outbound_bog_kg_year": outbound_bog_year, "return_heel_bog_kg_year": return_bog_year,
            "heel_makeup_kg_year": heel_makeup_year,
        },
        "mass_balance_per_trip_kg": {
            "nominal_mass": nominal_mass, "departure_mass": departure_mass,
            "export_feed": export_feed, "export_storage_loss": export_storage_loss,
            "outbound_bog": outbound_bog, "outbound_fuel_gap": outbound_fuel_gap,
            "arrival_mass": arrival_mass, "target_heel": target_heel,
            "unloaded_mass": unloaded_mass, "import_storage_loss": import_storage_loss,
            "usable_medium": usable_medium_trip, "return_heel_bog": return_heel_bog,
            "heel_after_return": heel_after_return, "heel_makeup": heel_makeup,
        },
        "storage": {
            "export_required_mass_kg": export_storage_mass, "import_required_mass_kg": import_storage_mass,
            "export_required_m3": export_storage_m3, "import_required_m3": import_storage_m3,
            "export_capex_musd": export_storage_capex, "import_capex_musd": import_storage_capex,
        },
        "annual_musd": delivered_components,
        "annual_musd_shipping": shipping_components,
        "totals": {
            "capital_musd_year": ship_capital + storage_capital + additional_capital,
            "shipping_total_musd_year": shipping_total,
            "delivered_transport_chain_total_musd_year": delivered_total,
            "landed_total_musd_year": delivered_total,
            "delivered_medium_kg_year": usable_medium_year,
            "theoretical_h2_kg_year": theoretical_h2_year,
            "recovered_h2_kg_year": recovered_h2_year, "delivered_h2_kg_year": delivered_h2_year,
            "shipping_cost_aud_per_kg_h2": shipping_per_kg_h2,
            "delivered_transport_chain_cost_aud_per_kg_h2": delivered_cost_per_kg_h2,
            "landed_cost_aud_per_kg_h2": delivered_cost_per_kg_h2,
            "aud_per_kg_h2_graph": shipping_per_kg_h2,
            "delivered_energy_gj_year": usable_medium_year * c["lhv_mj_kg"] / 1000.0,
            "aud_per_tonne_medium": shipping_total * 1_000_000.0 / usable_medium_year * 1000.0 * aud_per_usd,
            "aud_per_gj_medium": shipping_total * 1_000_000.0 / (usable_medium_year * c["lhv_mj_kg"] / 1000.0) * aud_per_usd,
            "transport_chain_emissions_tco2e_year": transport_chain_emissions,
            "emissions_kgco2e_per_kg_delivered_h2": transport_chain_emissions * 1000.0 / delivered_h2_year,
            "supplementary_h2_leakage_tco2e_year": h2_leakage_tco2e,
            "nh3_slip_kg_year": nh3_slip_kg,
        },
        "emissions_breakdown_tco2e": {
            "Export terminal": export_emissions, "Shipping": shipping_emissions,
            "Import terminal": import_emissions, "Ammonia cracking": cracking_emissions,
        },
        "breakdown": {
            "shipping_aud_per_kg_h2": shipping_breakdown,
            "delivered_transport_chain_aud_per_kg_h2": delivered_breakdown,
            "landed_aud_per_kg_h2": delivered_breakdown,
            "aud_per_kg_h2_graph": shipping_breakdown,
        },
    }


def calculate_case(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    p, carriers = _validated_inputs(payload)
    route = _route(p)
    requested = (payload or {}).get("carriers", list(carriers))
    if not isinstance(requested, list) or not requested:
        raise ValueError("Select at least one carrier")
    if any(name not in carriers for name in requested):
        raise ValueError("Only Ammonia and Hydrogen are supported")
    results = [_carrier_result(name, p, carriers[name], route) for name in requested]
    return {
        "inputs": p, "results": results, "currency": "AUD",
        "model_version": REFERENCE["model_version"],
        "scope": "Australian export terminal to Japanese import terminal and ammonia cracking; production excluded",
    }


def sensitivity_analysis(payload: dict[str, Any] | None = None, carrier: str = "Ammonia") -> list[dict[str, Any]]:
    """Run one-at-a-time low/base/high scenarios through the core model."""
    if carrier not in REFERENCE["carrier_defaults"]:
        raise ValueError("Unsupported carrier for sensitivity analysis")
    base_payload = copy.deepcopy(payload or {})
    base_payload["carriers"] = [carrier]
    base_result = calculate_case(base_payload)["results"][0]
    specs = list(REFERENCE["sensitivity_parameters"])
    specs.extend(REFERENCE.get("carrier_sensitivity_parameters", {}).get(carrier, []))
    if carrier == "Hydrogen":
        excluded = {"cracker_conversion_pct", "psa_recovery_pct", "cracking_cost_usd_per_kg_h2", "ammonia_engine_n2o_gco2e_mj", "cracking_electricity_kwh_kg_h2", "cracking_thermal_kwhth_kg_h2", "heater_efficiency_pct"}
        specs = [spec for spec in specs if spec["key"] not in excluded]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        outcomes: dict[str, dict[str, float]] = {}
        for level, value in (("Low", spec["low"]), ("High", spec["high"])):
            scenario = copy.deepcopy(base_payload)
            if spec.get("carrier_field"):
                scenario.setdefault("carrier_overrides", {}).setdefault(carrier, {})[spec["carrier_field"]] = value
            else:
                scenario[spec["key"]] = value
            result = calculate_case(scenario)["results"][0]["totals"]
            outcomes[level] = {
                "shipping": result["shipping_cost_aud_per_kg_h2"],
                "delivered_cost": result["delivered_transport_chain_cost_aud_per_kg_h2"],
                "delivered_h2_t_year": kg_year_to_t_year(result["delivered_h2_kg_year"]),
                "emissions": result["transport_chain_emissions_tco2e_year"],
            }
        totals = base_result["totals"]
        rows.append({
            "Parameter": spec["label"], "Low input": spec["low"], "Base input": spec["base"], "High input": spec["high"],
            "Shipping cost @ low input": outcomes["Low"]["shipping"],
            "Shipping cost @ base input": totals["shipping_cost_aud_per_kg_h2"],
            "Shipping cost @ high input": outcomes["High"]["shipping"],
            "Delivered cost @ low input": outcomes["Low"]["delivered_cost"],
            "Delivered cost @ base input": totals["delivered_transport_chain_cost_aud_per_kg_h2"],
            "Delivered cost @ high input": outcomes["High"]["delivered_cost"],
            "Delivered H2 (t/year) @ low input": outcomes["Low"]["delivered_h2_t_year"],
            "Delivered H2 (t/year) @ base input": kg_year_to_t_year(totals["delivered_h2_kg_year"]),
            "Delivered H2 (t/year) @ high input": outcomes["High"]["delivered_h2_t_year"],
            "Emissions @ low input": outcomes["Low"]["emissions"],
            "Emissions @ base input": totals["transport_chain_emissions_tco2e_year"],
            "Emissions @ high input": outcomes["High"]["emissions"],
        })
    return rows


def metadata() -> dict[str, Any]:
    route = REFERENCE["route"]
    parameter_sources = copy.deepcopy(REFERENCE["parameter_sources"])
    for row in parameter_sources:
        source_text = str(row.get("source", ""))
        if "doi.org" in source_text.lower() or "http://" in source_text.lower() or "https://" in source_text.lower():
            row["citation_status"] = "Citation recorded"
        elif row.get("type") in {"Literature value", "Official data"}:
            row["citation_status"] = "Full citation to be verified"
        elif row.get("type") == "Legacy workbook value":
            row["citation_status"] = "Source details to be verified"
        else:
            row["citation_status"] = "Not applicable (assumption or derived value)"
    return {
        "routes": [route["name"]], "departures": [route["departure"]],
        "arrivals": [route["arrival"]], "carriers": list(REFERENCE["carrier_defaults"]),
        "defaults": copy.deepcopy(REFERENCE["workbook_case"]),
        "carrier_defaults": copy.deepcopy(REFERENCE["carrier_defaults"]),
        "parameter_sources": parameter_sources,
        "sensitivity_parameters": copy.deepcopy(REFERENCE["sensitivity_parameters"]),
        "scope_note": "Transport-chain boundary; hydrogen and ammonia production are excluded.",
    }
