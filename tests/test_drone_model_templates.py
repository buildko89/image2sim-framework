from __future__ import annotations

import math
import unittest

from scripts.drone_model.run_build import deep_merge, validate_and_resolve


def base_config() -> dict:
    return {
        "measurements": {},
        "layout": {"motor_axis_z_mm": 4.0},
        "propeller": {"diameter_mm": 30.0, "direction_pattern": ["ccw", "cw"]},
        "guard": {"enabled": False},
    }


class TemplateResolutionTests(unittest.TestCase):
    def test_deep_merge_preserves_nested_template_values(self) -> None:
        merged = deep_merge(
            {"body": {"width_mm": 40.0, "height_mm": 20.0}, "count": 4},
            {"body": {"width_mm": 55.0}},
        )
        self.assertEqual(merged["body"], {"width_mm": 55.0, "height_mm": 20.0})
        self.assertEqual(merged["count"], 4)

    def test_square_diagonal_keeps_legacy_rotor_ids(self) -> None:
        config = base_config()
        config["measurements"]["motor_center_diagonal_mm"] = {"value": 100.0}
        config["layout"]["mode"] = "square_diagonal"
        resolved = validate_and_resolve(config)["derived"]
        self.assertEqual(resolved["rotor_ids"], ["fl", "fr", "rl", "rr"])
        spacing = 100.0 / math.sqrt(2.0)
        self.assertAlmostEqual(resolved["motor_center_spacing_x_mm"], spacing)

    def test_radial_layout_supports_six_rotors(self) -> None:
        config = base_config()
        config["layout"].update({"mode": "radial", "rotor_count": 6, "radius_mm": 55.0, "id_prefix": "r"})
        resolved = validate_and_resolve(config)["derived"]
        self.assertEqual(resolved["rotor_ids"], ["r1", "r2", "r3", "r4", "r5", "r6"])
        self.assertEqual(resolved["rotor_count"], 6)

    def test_explicit_layout_accepts_individual_positions(self) -> None:
        config = base_config()
        config["layout"].update({
            "mode": "explicit",
            "motor_positions_mm": {"front": [0.0, -40.0], "rear_left": [-35.0, 30.0, 6.0]},
        })
        resolved = validate_and_resolve(config)["derived"]
        self.assertEqual(resolved["motor_positions_mm"]["front"], [0.0, -40.0, 4.0])
        self.assertEqual(resolved["motor_positions_mm"]["rear_left"], [-35.0, 30.0, 6.0])


if __name__ == "__main__":
    unittest.main()
