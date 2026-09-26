"""不启动网页，直接检查底层计算结果。"""

import math
import unittest

from model import REFERENCE, calculate_case


class ModelTests(unittest.TestCase):
    def test_excel_default_case(self):
        result = calculate_case()
        by_carrier = {item["carrier"]: item for item in result["results"]}

        for carrier, expected in REFERENCE["validation_targets"].items():
            actual = by_carrier[carrier]["totals"]
            self.assertTrue(
                math.isclose(
                    actual["aud_per_kg_h2_graph"],
                    expected["cost_aud_kg_h2_graph"],
                    rel_tol=1e-9,
                )
            )

    def test_requires_a_carrier(self):
        with self.assertRaises(ValueError):
            calculate_case({"carriers": []})


if __name__ == "__main__":
    unittest.main()
