"""Pure presentation helpers shared by the Streamlit app and regression tests."""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from model import kg_year_to_kt_year, kg_year_to_t_year


SHIPPING_COST_LABEL = "Shipping cost (A$/kg H₂-eq)"
DELIVERED_COST_LABEL = "Delivered transport-chain cost (A$/kg H2)"
DELIVERED_H2_LABEL = "Delivered H₂ (t/year)"


def lowest_delivered_cost(results: Iterable[Mapping[str, Any]]) -> Mapping[str, Any]:
    """Return the carrier result with the lowest final delivered cost."""
    return min(
        results,
        key=lambda item: item["totals"]["delivered_transport_chain_cost_aud_per_kg_h2"],
    )


def build_summary_rows(results: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Build the main table and CSV rows with explicit presentation units."""
    rows: list[dict[str, Any]] = []
    for name, result in results.items():
        totals = result["totals"]
        rows.append(
            {
                "Carrier": name,
                SHIPPING_COST_LABEL: totals["shipping_cost_aud_per_kg_h2"],
                DELIVERED_COST_LABEL: totals["delivered_transport_chain_cost_aud_per_kg_h2"],
                DELIVERED_H2_LABEL: kg_year_to_t_year(totals["delivered_h2_kg_year"]),
                "Transport-chain emissions (t CO₂e/year)": totals["transport_chain_emissions_tco2e_year"],
                "Intensity (kg CO₂e/kg H₂)": totals["emissions_kgco2e_per_kg_delivered_h2"],
                "Supplementary H₂ leakage (t CO₂e/year)": totals["supplementary_h2_leakage_tco2e_year"],
            }
        )
    return rows


def build_cost_comparison_rows(results: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return independent side-by-side series; values are never added together."""
    return [
        {
            "Carrier": name,
            SHIPPING_COST_LABEL: result["totals"]["shipping_cost_aud_per_kg_h2"],
            DELIVERED_COST_LABEL: result["totals"]["delivered_transport_chain_cost_aud_per_kg_h2"],
        }
        for name, result in results.items()
    ]


def annual_quantity_metric_values(result: Mapping[str, Any]) -> tuple[str, str]:
    """Format annual mass cards in kt/year without losing their units."""
    totals = result["totals"]
    return (
        f"{kg_year_to_kt_year(totals['delivered_medium_kg_year']):,.2f} kt/year",
        f"{kg_year_to_kt_year(totals['delivered_h2_kg_year']):,.2f} kt/year",
    )
