"""Regression and engineering-invariant tests for the Stage 2 model."""
from __future__ import annotations

import math
import subprocess
import sys
import unittest
from pathlib import Path

from model import (
    REFERENCE,
    calculate_case,
    exponential_remaining,
    kg_year_to_kt_year,
    kg_year_to_mt_year,
    kg_year_to_t_year,
    metadata,
    sensitivity_analysis,
)
from presentation import (
    DELIVERED_COST_LABEL,
    DELIVERED_H2_LABEL,
    SHIPPING_COST_LABEL,
    annual_quantity_metric_values,
    build_cost_comparison_rows,
    build_summary_rows,
    lowest_delivered_cost,
)


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.default = calculate_case()
        self.results = {item["carrier"]: item for item in self.default["results"]}

    def test_fixed_route_and_distance_conversion(self):
        route = self.results["Ammonia"]["route"]
        self.assertAlmostEqual(3860 * 1.852, 7148.72, places=10)
        self.assertAlmostEqual(route["distance_km"], 7148.72, places=10)
        self.assertEqual(route["departure"], "Gladstone (QLD)")
        self.assertEqual(route["arrival"], "Tokyo (Japan)")

    def test_voyage_duration_uses_distance_reference_speed_and_factor(self):
        route = self.results["Hydrogen"]["route"]
        expected = 7148.72 / (20 * 1.852 * 24)
        self.assertAlmostEqual(route["calculated_one_way_days"], expected)
        adjusted = calculate_case({"carriers": ["Hydrogen"], "voyage_time_adjustment_factor": 1.25})["results"][0]
        self.assertAlmostEqual(adjusted["route"]["one_way_days"], expected * 1.25)

    def test_voyage_adjustment_105_regression(self):
        adjusted = calculate_case({"voyage_time_adjustment_factor": 1.05})["results"][0]
        self.assertAlmostEqual(adjusted["route"]["one_way_days"], 8.44375, places=5)
        self.assertAlmostEqual(adjusted["operations"]["trips_per_year"], 17.59899434318039)

    def test_longer_voyage_does_not_reduce_fuel_or_bog(self):
        base = self.results["Hydrogen"]
        longer = calculate_case({"carriers": ["Hydrogen"], "voyage_time_adjustment_factor": 1.35})["results"][0]
        self.assertGreater(longer["operations"]["fuel_required_kg_year"], base["operations"]["fuel_required_kg_year"])
        self.assertGreater(longer["operations"]["outbound_bog_kg_year"], base["operations"]["outbound_bog_kg_year"])

    def test_nominal_capacity_comes_only_from_volume_and_density(self):
        self.assertNotIn("ship_capacity_kg", REFERENCE["carrier_defaults"]["Ammonia"])
        self.assertEqual(self.results["Ammonia"]["mass_balance_per_trip_kg"]["nominal_mass"], 109_120_000)
        self.assertEqual(self.results["Hydrogen"]["mass_balance_per_trip_kg"]["nominal_mass"], 11_360_000)

    def test_default_fill_and_heel(self):
        nh3 = self.results["Ammonia"]["mass_balance_per_trip_kg"]
        h2 = self.results["Hydrogen"]["mass_balance_per_trip_kg"]
        self.assertEqual(nh3["departure_mass"], 109_120_000 * 0.98)
        self.assertEqual(h2["departure_mass"], 11_360_000 * 0.95)
        self.assertEqual(nh3["target_heel"], 109_120_000 * 0.05)
        self.assertEqual(h2["target_heel"], 11_360_000 * 0.05)

    def test_exponential_bog_formula(self):
        initial, rate, days = 1_000_000.0, 0.2, 8.5
        self.assertAlmostEqual(exponential_remaining(initial, rate, days), initial * (1 - rate / 100) ** days)

    def test_main_bog_is_outbound_and_return_loss_is_heel_only(self):
        h2 = self.results["Hydrogen"]
        mass = h2["mass_balance_per_trip_kg"]
        expected_outbound = mass["departure_mass"] - exponential_remaining(mass["departure_mass"], 0.2, h2["route"]["one_way_days"])
        expected_return = mass["target_heel"] - exponential_remaining(mass["target_heel"], 0.2, h2["route"]["one_way_days"])
        self.assertAlmostEqual(mass["outbound_bog"], expected_outbound)
        self.assertAlmostEqual(mass["return_heel_bog"], expected_return)

    def test_storage_loss_uses_dwell_time_not_365_days(self):
        h2 = self.results["Hydrogen"]
        mass = h2["mass_balance_per_trip_kg"]
        expected_import = mass["unloaded_mass"] - exponential_remaining(mass["unloaded_mass"], 0.06, 20)
        self.assertAlmostEqual(mass["import_storage_loss"], expected_import)
        self.assertLess(mass["import_storage_loss"], mass["unloaded_mass"] * 0.006 * 365)

    def test_storage_capacity_uses_shipload_or_daily_throughput(self):
        for result in self.results.values():
            mass = result["mass_balance_per_trip_kg"]
            storage = result["storage"]
            self.assertGreaterEqual(storage["export_required_mass_kg"], mass["departure_mass"])
            self.assertGreaterEqual(storage["import_required_mass_kg"], mass["unloaded_mass"])

    def test_ammonia_cracking_yield(self):
        nh3 = self.results["Ammonia"]["totals"]
        self.assertAlmostEqual(0.177 * 0.99 * 0.75, 0.1314225)
        self.assertAlmostEqual(nh3["recovered_h2_kg_year"] / nh3["delivered_medium_kg_year"], 0.1314225)

    def test_lower_psa_recovery_reduces_h2_and_increases_landed_cost(self):
        base = self.results["Ammonia"]["totals"]
        low = calculate_case({"carriers": ["Ammonia"], "psa_recovery_pct": 65})["results"][0]["totals"]
        self.assertLess(low["delivered_h2_kg_year"], base["delivered_h2_kg_year"])
        self.assertGreater(low["landed_cost_aud_per_kg_h2"], base["landed_cost_aud_per_kg_h2"])

    def test_shipping_cost_excludes_cracking_cost(self):
        low = calculate_case({"carriers": ["Ammonia"], "cracking_cost_usd_per_kg_h2": 0.2})["results"][0]["totals"]
        high = calculate_case({"carriers": ["Ammonia"], "cracking_cost_usd_per_kg_h2": 0.8})["results"][0]["totals"]
        self.assertAlmostEqual(low["shipping_cost_aud_per_kg_h2"], high["shipping_cost_aud_per_kg_h2"])
        self.assertGreater(high["landed_cost_aud_per_kg_h2"], low["landed_cost_aud_per_kg_h2"])

    def test_carbon_price_changes_cost(self):
        zero = self.results["Ammonia"]
        priced = calculate_case({"carriers": ["Ammonia"], "carbon_price_usd_tonne": 100})["results"][0]
        self.assertEqual(zero["annual_musd"]["Carbon"], 0)
        self.assertGreater(priced["annual_musd"]["Carbon"], 0)
        self.assertGreater(priced["totals"]["landed_cost_aud_per_kg_h2"], zero["totals"]["landed_cost_aud_per_kg_h2"])

    def test_zero_hydrogen_release_has_zero_supplementary_impact(self):
        result = calculate_case({"carriers": ["Hydrogen"], "carrier_overrides": {"Hydrogen": {
            "storage_bog_pct_day": 0, "bog_managed_pct": 100, "bog_vented_pct": 0
        }}})["results"][0]
        self.assertEqual(result["totals"]["supplementary_h2_leakage_tco2e_year"], 0)

    def test_bog_management_does_not_double_deduct_delivery(self):
        managed = calculate_case({"carriers": ["Hydrogen"], "carrier_overrides": {"Hydrogen": {"bog_managed_pct": 100, "bog_vented_pct": 0}}})["results"][0]
        vented = calculate_case({"carriers": ["Hydrogen"], "carrier_overrides": {"Hydrogen": {"bog_managed_pct": 0, "bog_vented_pct": 100}}})["results"][0]
        self.assertAlmostEqual(managed["totals"]["delivered_h2_kg_year"], vented["totals"]["delivered_h2_kg_year"])
        self.assertGreater(vented["operations"]["fuel_gap_kg_year"], managed["operations"]["fuel_gap_kg_year"])

    def test_invalid_percentages_and_mass_balance_raise(self):
        with self.assertRaises(ValueError):
            calculate_case({"carrier_overrides": {"Hydrogen": {"fill_fraction_pct": 5, "heel_fraction_pct": 5}}})
        with self.assertRaises(ValueError):
            calculate_case({"carrier_overrides": {"Hydrogen": {"bog_managed_pct": 60, "bog_vented_pct": 30}}})
        with self.assertRaises(ValueError):
            calculate_case({"carrier_overrides": {"Hydrogen": {"transport_bog_pct_day": 100}}})

    def test_only_confirmed_route_choices_are_exposed(self):
        info = metadata()
        self.assertEqual(info["routes"], ["Australia – Japan (Base case)"])
        self.assertEqual(info["departures"], ["Gladstone (QLD)"])
        self.assertEqual(info["arrivals"], ["Tokyo (Japan)"])
        with self.assertRaises(ValueError):
            calculate_case({"departure": "Custom"})

    def test_removed_interface_labels(self):
        app = Path(__file__).with_name("app.py").read_text(encoding="utf-8")
        self.assertNotIn(">HySupply<", app)
        self.assertNotIn("Run model", app)
        self.assertNotIn("Methodology", app)
        self.assertNotIn("About", app)
        self.assertNotIn("Ship speed", app)
        self.assertIn("Calculate", app)
        self.assertIn("All results are estimates based on the selected assumptions.", app)
        self.assertIn("Lowest delivered cost", app)
        self.assertNotIn("Lowest shipping cost", app)
        self.assertNotIn("Post-cracking landed cost", app)
        self.assertIn("stack=False", app)

    def test_annual_mass_unit_conversions(self):
        self.assertEqual(kg_year_to_t_year(1_000.0), 1.0)
        self.assertEqual(kg_year_to_kt_year(1_000_000.0), 1.0)

        value = 243_780_143.985
        self.assertAlmostEqual(kg_year_to_t_year(value), 243_780.144, places=3)
        self.assertAlmostEqual(kg_year_to_kt_year(value), 243.780, places=3)

        self.assertEqual(kg_year_to_mt_year(1_000_000_000.0), 1.0)

    def _assert_module_imports(self, module_name: str) -> None:
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module_name}"],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"import {module_name} failed:\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )

    def test_model_imports_in_fresh_interpreter(self):
        self._assert_module_imports("model")

    def test_presentation_imports_in_fresh_interpreter(self):
        self._assert_module_imports("presentation")

    def test_app_imports_in_fresh_interpreter(self):
        self._assert_module_imports("app")

    def test_default_delivered_h2_card_is_kilotonne_per_year(self):
        medium, delivered_h2 = annual_quantity_metric_values(self.results["Ammonia"])
        self.assertEqual(medium, "1,854.93 kt/year")
        self.assertEqual(delivered_h2, "243.78 kt/year")

    def test_default_main_table_delivered_h2_is_tonnes_per_year(self):
        rows = build_summary_rows(self.results)
        ammonia = next(row for row in rows if row["Carrier"] == "Ammonia")
        self.assertAlmostEqual(ammonia[DELIVERED_H2_LABEL], 243_780.1439852848)
        self.assertAlmostEqual(ammonia[DELIVERED_COST_LABEL], 0.9783449698528076)

    def test_cost_comparison_uses_independent_not_summed_values(self):
        rows = {row["Carrier"]: row for row in build_cost_comparison_rows(self.results)}
        self.assertAlmostEqual(rows["Ammonia"][SHIPPING_COST_LABEL], 0.35517114011570955)
        self.assertAlmostEqual(rows["Ammonia"][DELIVERED_COST_LABEL], 0.9783449698528076)
        self.assertNotAlmostEqual(rows["Ammonia"][DELIVERED_COST_LABEL], 0.35517114011570955 + 0.9783449698528076)
        self.assertAlmostEqual(rows["Hydrogen"][SHIPPING_COST_LABEL], 0.7917431998583839)
        self.assertAlmostEqual(rows["Hydrogen"][DELIVERED_COST_LABEL], 0.7917431998583839)

    def test_lowest_delivered_cost_is_hydrogen(self):
        cheapest = lowest_delivered_cost(self.results.values())
        self.assertEqual(cheapest["carrier"], "Hydrogen")
        self.assertAlmostEqual(cheapest["totals"]["delivered_transport_chain_cost_aud_per_kg_h2"], 0.7917431998583839)

    def test_sensitivity_ranges_are_ordered(self):
        specs = list(REFERENCE["sensitivity_parameters"])
        for carrier_specs in REFERENCE["carrier_sensitivity_parameters"].values():
            specs.extend(carrier_specs)
        for spec in specs:
            self.assertLessEqual(spec["low"], spec["base"], spec["label"])
            self.assertLessEqual(spec["base"], spec["high"], spec["label"])

    def test_sensitivity_uses_core_model(self):
        ammonia = sensitivity_analysis(carrier="Ammonia")
        hydrogen = sensitivity_analysis(carrier="Hydrogen")
        self.assertGreaterEqual(len(ammonia), 20)
        self.assertGreaterEqual(len(hydrogen), 15)
        expected = {
            "Shipping cost @ low input", "Shipping cost @ base input", "Shipping cost @ high input",
            "Delivered cost @ low input", "Delivered cost @ base input", "Delivered cost @ high input",
            "Delivered H2 (t/year) @ low input", "Delivered H2 (t/year) @ base input",
            "Delivered H2 (t/year) @ high input",
        }
        self.assertTrue(all(expected.issubset(row) for row in ammonia))
        self.assertTrue(all(not any("landed cost" in key.lower() for key in row) for row in ammonia))

    def test_sensitivity_delivered_h2_is_tonnes_per_year(self):
        rows = sensitivity_analysis(carrier="Ammonia")
        aud_usd = next(row for row in rows if row["Parameter"] == "AUD/USD")
        self.assertAlmostEqual(aud_usd["Delivered H2 (t/year) @ base input"], 243_780.1439852848)
        self.assertLess(aud_usd["Delivered cost @ high input"], aud_usd["Delivered cost @ low input"])

    def test_heat_source_enters_energy_or_mass_balance(self):
        electric = self.results["Ammonia"]
        process_h2 = calculate_case({"carriers": ["Ammonia"], "cracking_heat_source": "Process hydrogen/off-gas"})["results"][0]
        gas = calculate_case({"carriers": ["Ammonia"], "cracking_heat_source": "Natural gas"})["results"][0]
        self.assertLess(process_h2["totals"]["delivered_h2_kg_year"], electric["totals"]["delivered_h2_kg_year"])
        self.assertGreater(gas["emissions_breakdown_tco2e"]["Ammonia cracking"], 0)

    def test_parameter_sources_have_required_metadata(self):
        required = {"parameter", "base_value", "unit", "source", "year", "type", "range", "notes", "citation_status"}
        allowed = {"Official data", "Literature value", "Engineering assumption", "Derived value", "Legacy workbook value"}
        for row in metadata()["parameter_sources"]:
            self.assertTrue(required.issubset(row))
            self.assertIn(row["type"], allowed)
        vague = [row for row in metadata()["parameter_sources"] if row["source"].startswith("Published ")]
        self.assertTrue(vague)
        self.assertTrue(all(row["citation_status"] == "Full citation to be verified" for row in vague))

    def test_default_regression_targets(self):
        for carrier, expected in REFERENCE["validation_targets"].items():
            actual = self.results[carrier]["totals"]
            for key, value in expected.items():
                self.assertTrue(math.isclose(actual[key], value, rel_tol=1e-10), f"{carrier}: {key}")

    def test_requires_carrier(self):
        with self.assertRaises(ValueError):
            calculate_case({"carriers": []})


if __name__ == "__main__":
    unittest.main()
