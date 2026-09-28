"""Headless Streamlit regression tests."""
from __future__ import annotations

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
