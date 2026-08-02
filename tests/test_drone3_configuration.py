from __future__ import annotations

import unittest
from pathlib import Path

from scripts.drone_model.run_build import load_model_config, validate_and_resolve


REPO = Path(__file__).resolve().parents[1]


class Drone3ConfigurationTests(unittest.TestCase):
    def test_drone3_layout_and_primary_dimensions(self) -> None:
        config = validate_and_resolve(load_model_config(REPO / "config" / "drone3_model.yaml"))
        derived = config["derived"]
        positions = list(derived["motor_positions_mm"].values())

        self.assertEqual(derived["rotor_count"], 8)
        self.assertAlmostEqual(max(item[0] for item in positions) - min(item[0] for item in positions), 2560.0)
        self.assertAlmostEqual(max(item[1] for item in positions) - min(item[1] for item in positions), 2445.0)
        self.assertEqual(config["propeller"]["diameter_mm"], 863.6)
        self.assertEqual(len(config["structure"]["members"]), 16)
        self.assertEqual(config["wing"]["span_mm"], 2500.0)
        positions_by_id = derived["motor_positions_mm"]
        self.assertEqual(positions_by_id["front_outer_left"], [-1280.0, -722.5, -148.0])
        self.assertEqual(positions_by_id["front_inner_left"], [-440.0, -1222.5, 148.0])
        self.assertEqual(
            abs(positions_by_id["front_inner_left"][1] - positions_by_id["front_outer_left"][1]),
            500.0,
        )
        members = {member["id"]: member for member in config["structure"]["members"]}
        self.assertEqual(members["front_cross"]["location_mm"][1], -722.5)
        self.assertEqual(config["equipment"]["masts"][0]["height_mm"], 500.0)


if __name__ == "__main__":
    unittest.main()
