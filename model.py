"""Pure-Python port of the active HySupply shipping calculations.

The workbook is treated as the audit reference. This module has no Excel or
web-framework dependency, which makes the model testable and easy to extend.
All monetary build-up values are in million USD/year until presentation.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).with_name("model_data.json")
REFERENCE = json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _num(value: Any, name: str, low: float | None = None, high: float | None = None) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if low is not None and number < low:
        raise ValueError(f"{name} 不能小于 {low}")
    if high is not None and number > high:
        raise ValueError(f"{name} 不能大于 {high}")
    return number


def capital_recovery_factor(rate_pct: float, years: float) -> float:
    rate = rate_pct / 100.0
    if years <= 0:
        raise ValueError("经济寿命必须大于 0")
    if rate == 0:
        return 1.0 / years
    return rate * (1 + rate) ** years / ((1 + rate) ** years - 1)


def _route_value(table: str, departure: str, arrival: str, custom: Any) -> Any:
    if departure == "Custom" or arrival == "Custom":
        return custom
    try:
        return REFERENCE["routes"][table][departure][arrival]
    except KeyError as exc:
        raise ValueError("未找到所选港口组合的航线数据") from exc


def _carrier_result(name: str, p: dict[str, Any], carrier: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    crf = capital_recovery_factor(p["interest_rate_pct"], p["economic_life_years"])
    trip_days = route["one_way_days"] * 2 + p["port_days_each_end"] * 2
    trips = p["operating_days_year"] / trip_days
    sailing_days = trips * route["one_way_days"] * 2

    nominal_capacity = 2 * carrier["ship_capacity_m3"]
    export_storage_capex = round(
        carrier["export_reference_cost_musd"]
        * (nominal_capacity / carrier["export_reference_capacity_m3"]) ** carrier["export_scale_coefficient"], 2
    )
    import_storage_capex = round(
        carrier["import_reference_cost_musd"]
        * (nominal_capacity / carrier["import_reference_capacity_m3"]) ** carrier["import_scale_coefficient"], 2
    )

    ship_capital = crf * carrier["ship_capex_musd"]
    storage_capital = crf * (export_storage_capex + import_storage_capex)
    additional_capital = crf * carrier["additional_capex_musd"]

    energy_mwh_day = round(carrier["engine_mw"] * 24 / (carrier["engine_efficiency_pct"] / 100), 2)
    fuel_lhv = REFERENCE["fuel_properties"][carrier["ship_fuel_source"]]["lhv_mj_kg"]
    fuel_use_t_day = round(energy_mwh_day * 3.6 / fuel_lhv, 2)
    required_fuel = fuel_use_t_day * sailing_days

    transport_bog = carrier["transport_bog_pct_day"] / 100 * carrier["ship_capacity_kg"] * sailing_days / 1000
    fuel_source = carrier["ship_fuel_source"]
    fossil_fuels = {"Heavy Fuel Oil (HFO)", "Marine Gas Oil (MGO)", "Very Low Sulfur Fuel Oil (VLSFO)", "Custom"}
    if fuel_source in fossil_fuels:
        forced_bog = 0.0
    elif fuel_source == name or (name == "Ammonia" and fuel_source == "Hydrogen"):
        required_medium = required_fuel / carrier["mass_conversion_s1_kg_h2_per_kg"] if name == "Ammonia" else required_fuel
        forced_bog = max(required_medium - transport_bog, 0.0)
    else:
        forced_bog = 0.0
    total_bog = transport_bog + forced_bog if forced_bog > 0 else transport_bog
    bog_per_trip = total_bog / trips

    export_storage_bog = carrier["export_bog_pct_day"] / 100 * nominal_capacity / 2 * carrier["density_kg_m3"] * 365 / 1000
    import_storage_bog = carrier["import_bog_pct_day"] / 100 * nominal_capacity / 2 * carrier["density_kg_m3"] * 365 / 1000

    suez_cost = p["suez_cost_musd_one_way"] if route["suez"] == "YES" else 0.0
    panama_cost = p["panama_cost_musd_one_way"] if route["panama"] == "YES" else 0.0
    labour = p["labour_musd_year"]
    canal = (suez_cost + panama_cost) * 2 * trips
    port = p["port_charge_musd_day"] * p["port_days_each_end"] * trips * 2
    maintenance = p["maintenance_pct_capex"] / 100 * carrier["ship_capex_musd"]
    storage_opex = carrier["import_om_pct"] / 100 * import_storage_capex + carrier["export_om_pct"] / 100 * export_storage_capex
    base_opex = labour + canal + port + maintenance + storage_opex + carrier["additional_opex_musd_year"]
    miscellaneous = base_opex * p["misc_pct_opex"] / 100
    insurance = base_opex * p["insurance_pct_opex"] / 100

    if fuel_source in {"Hydrogen", "Ammonia"}:
        fuel_cost = carrier["market_price_usd_gj"] * total_bog * carrier["lhv_mj_kg"] / 1_000_000
    else:
        fuel_cost = required_fuel * p["fuel_cost_usd_tonne"] / 1_000_000
    emission_factor = REFERENCE["fuel_properties"][fuel_source]["co2_t_per_t"]
    emissions = (total_bog if fuel_source == name and name == "Hydrogen" else required_fuel) * emission_factor
    carbon_cost = emissions * p["carbon_price_usd_tonne"] / 1_000_000
    shipping_bog_cost = 0.0 if fuel_source in {"Hydrogen", "Ammonia"} else carrier["market_price_usd_gj"] * transport_bog * carrier["lhv_mj_kg"] / 1_000_000
    storage_bog_cost = carrier["market_price_usd_gj"] * (export_storage_bog + import_storage_bog) * carrier["lhv_mj_kg"] / 1_000_000

    components = {
        "Ship CAPEX": ship_capital,
        "Storage CAPEX": storage_capital,
        "Additional CAPEX": additional_capital,
        "Labour": labour,
        "Canal": canal,
        "Port": port,
        "Maintenance": maintenance,
        "Miscellaneous": miscellaneous,
        "Insurance": insurance,
        "Storage OPEX": storage_opex,
        "Additional OPEX": carrier["additional_opex_musd_year"],
        "Fuel": fuel_cost,
        "Carbon": carbon_cost,
        "Shipping BOG": shipping_bog_cost,
        "Storage BOG": storage_bog_cost,
    }
    total_annual = sum(components.values())
    delivered_medium_kg = (carrier["ship_capacity_kg"] - bog_per_trip * 1000) * trips
    delivered_h2e_graph_kg = delivered_medium_kg * carrier["graph_h2_conversion"]
    delivered_energy_gj = delivered_medium_kg * carrier["lhv_mj_kg"] / 1000
    if min(delivered_medium_kg, delivered_h2e_graph_kg, delivered_energy_gj) <= 0:
        raise ValueError(f"{name} 的损耗超过运载量；请检查航程、BOG 和运营天数")

    aud_factor = 1 / p["aud_usd"]
    per_kg_h2 = {key: value * 1_000_000 / delivered_h2e_graph_kg * aud_factor for key, value in components.items()}
    per_tonne_medium = {key: value * 1_000_000 / delivered_medium_kg * 1000 * aud_factor for key, value in components.items()}
    per_gj_medium = {key: value * 1_000_000 / delivered_energy_gj * aud_factor for key, value in components.items()}
    return {
        "carrier": name,
        "route": route,
        "operations": {
            "trip_days": trip_days,
            "trips_per_year": trips,
            "sailing_days": sailing_days,
            "fuel_use_tonnes_year": required_fuel,
            "transport_bog_tonnes_year": transport_bog,
            "total_bog_tonnes_year": total_bog,
        },
        "annual_musd": components,
        "totals": {
            "capital_musd_year": ship_capital + storage_capital + additional_capital,
            "operating_musd_year": total_annual - ship_capital - storage_capital - additional_capital,
            "total_musd_year": total_annual,
            "delivered_medium_kg_year": delivered_medium_kg,
            "delivered_h2e_graph_kg_year": delivered_h2e_graph_kg,
            "delivered_energy_gj_year": delivered_energy_gj,
            "aud_per_kg_h2_graph": sum(per_kg_h2.values()),
            "aud_per_tonne_medium": sum(per_tonne_medium.values()),
            "aud_per_gj_medium": sum(per_gj_medium.values()),
        },
        "breakdown": {
            "aud_per_kg_h2_graph": per_kg_h2,
            "aud_per_tonne_medium": per_tonne_medium,
            "aud_per_gj_medium": per_gj_medium,
        },
    }


def calculate_case(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = {**REFERENCE["workbook_case"], **(payload or {})}
    numeric_fields = {
        "aud_usd": (0.01, None), "interest_rate_pct": (0, 100), "economic_life_years": (1, 100),
        "fuel_cost_usd_tonne": (0, None), "ship_speed_knots": (0.1, 100), "operating_days_year": (0.1, 366),
        "maintenance_pct_capex": (0, 100), "misc_pct_opex": (0, 100), "insurance_pct_opex": (0, 100),
        "labour_musd_year": (0, None), "carbon_price_usd_tonne": (0, None), "suez_cost_musd_one_way": (0, None),
        "panama_cost_musd_one_way": (0, None), "port_days_each_end": (0, 100), "port_charge_musd_day": (0, None),
    }
    p = copy.deepcopy(raw)
    for field, (low, high) in numeric_fields.items():
        p[field] = _num(raw[field], field, low, high)

    departure, arrival = str(raw["departure"]), str(raw["arrival"])
    custom_distance = _num(raw.get("custom_distance_nm", raw.get("distance_nm", 3619)), "custom_distance_nm", 1)
    distance = _num(_route_value("distance_nm", departure, arrival, custom_distance), "distance_nm", 1)
    suez = str(_route_value("suez", departure, arrival, raw.get("custom_suez", "NO"))).upper()
    panama = str(_route_value("panama", departure, arrival, raw.get("custom_panama", "NO"))).upper()
    calculated_days = distance / (p["ship_speed_knots"] * 24)
    override = raw.get("one_way_days")
    one_way_days = _num(override, "one_way_days", 0.01) if override not in (None, "", 0, "0") else calculated_days
    route = {"departure": departure, "arrival": arrival, "distance_nm": distance, "suez": suez, "panama": panama,
             "one_way_days": one_way_days, "calculated_days": calculated_days, "days_overridden": override not in (None, "", 0, "0")}

    names = raw.get("carriers", ["Ammonia", "Hydrogen"])
    if not isinstance(names, list) or not names:
        raise ValueError("至少选择一种运输介质")
    results = []
    for name in names:
        if name not in REFERENCE["carrier_defaults"]:
            raise ValueError(f"当前版本尚未配置运输介质：{name}")
        results.append(_carrier_result(name, p, copy.deepcopy(REFERENCE["carrier_defaults"][name]), route))
    return {"inputs": p, "results": results, "currency": "AUD", "model_version": "1.0.0-web-port"}


def metadata() -> dict[str, Any]:
    return {
        "departures": REFERENCE["departures"], "arrivals": REFERENCE["arrivals"],
        "carriers": list(REFERENCE["carrier_defaults"]), "defaults": REFERENCE["workbook_case"],
        "scope_note": "Attached workbook has complete active calculations for Ammonia and Hydrogen; other carrier columns are incomplete.",
    }
