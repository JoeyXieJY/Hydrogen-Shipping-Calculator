"""Headless Streamlit regression tests."""
from __future__ import annotations

import json

import pyarrow as pa
from streamlit.testing.v1 import AppTest

from presentation import DELIVERED_COST_LABEL, DELIVERED_H2_LABEL, SHIPPING_COST_LABEL


def test_default_app_outputs_and_labels() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()

    assert not app.exception
    assert app.metric[0].label == "Lowest delivered cost"
    assert app.metric[0].value == "A$0.79/kg H₂"
    assert app.metric[0].delta == "Hydrogen"

    summary = app.dataframe[0].value
    assert [SHIPPING_COST_LABEL, DELIVERED_COST_LABEL, DELIVERED_H2_LABEL] == [
        column for column in summary.columns if column in {SHIPPING_COST_LABEL, DELIVERED_COST_LABEL, DELIVERED_H2_LABEL}
    ]
    ammonia = summary.loc[summary["Carrier"] == "Ammonia"].iloc[0]
    assert round(ammonia[DELIVERED_H2_LABEL], 2) == 243_780.14
    assert round(ammonia[SHIPPING_COST_LABEL], 3) == 0.355
    assert round(ammonia[DELIVERED_COST_LABEL], 3) == 0.978

    medium_values = [metric.value for metric in app.metric if metric.label == "Usable transported medium"]
    delivered_values = [metric.value for metric in app.metric if metric.label == "Delivered H₂"]
    assert medium_values == ["1,854.93 kt/year", "182.15 kt/year"]
    assert delivered_values == ["243.78 kt/year", "182.15 kt/year"]
    assert any(button.label == "Calculate" for button in app.button)


def _chart_data(chart):
    return pa.ipc.open_stream(chart.proto.datasets[0].data.data).read_all().to_pandas()


def test_cost_chart_is_side_by_side_with_independent_values() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception

    chart = app.get("vega_lite_chart")[0]
    spec = json.loads(chart.proto.spec)
    assert spec["encoding"]["y"]["stack"] is False
    assert "xOffset" in spec["encoding"]

    values = _chart_data(chart)
    series = values.pivot(index="Carrier", columns="color -- streamlit-generated", values="value -- streamlit-generated")
    assert round(series.loc["Ammonia", SHIPPING_COST_LABEL], 3) == 0.355
    assert round(series.loc["Ammonia", DELIVERED_COST_LABEL], 3) == 0.978
    assert round(series.loc["Hydrogen", SHIPPING_COST_LABEL], 3) == 0.792
    assert round(series.loc["Hydrogen", DELIVERED_COST_LABEL], 3) == 0.792


def test_sensitivity_chart_uses_input_scenario_labels() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()
    assert not app.exception
    labels = set(_chart_data(app.get("vega_lite_chart")[-1])["color -- streamlit-generated"])
    assert labels == {"Low input scenario", "Base scenario", "High input scenario"}


def test_voyage_factor_updates_effective_voyage_and_sailings() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()
    factor = next(widget for widget in app.number_input if widget.label == "Voyage time adjustment factor")
    factor.set_value(1.05)
    next(button for button in app.button if button.label == "Calculate").click()
    app.run()
    assert not app.exception
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Effective voyage"] == "8.44 days"
    assert metrics["Annual sailings"] == "17.60"


def test_edited_cracking_cost_updates_sensitivity_base_input_and_scenario() -> None:
    app = AppTest.from_file("app.py", default_timeout=30).run()
    cost = next(widget for widget in app.number_input if widget.label == "Cracking cost (USD/kg H₂)")
    cost.set_value(0.50)
    next(button for button in app.button if button.label == "Calculate").click()
    app.run()
    assert not app.exception

    summary = app.dataframe[0].value
    ammonia_cost = summary.loc[summary["Carrier"] == "Ammonia", DELIVERED_COST_LABEL].iloc[0]
    sensitivity = next(frame.value for frame in app.dataframe if "Base input" in frame.value.columns)
    row = sensitivity.loc[sensitivity["Parameter"] == "Cracking cost"].iloc[0]
    assert row["Base input"] == 0.50
    assert abs(row["Delivered cost @ base input"] - ammonia_cost) < 1e-10

    sources = next(frame.value for frame in app.dataframe if "base_value" in frame.value.columns)
    source = sources.loc[sources["parameter"] == "Cracking cost"].iloc[0]
    assert source["base_value"] == "0.35"
    assert source["range"] == "0.20–0.80"
