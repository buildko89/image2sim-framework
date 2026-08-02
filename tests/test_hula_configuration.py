from __future__ import annotations

import unittest
from pathlib import Path

from scripts.drone_model.run_build import load_model_config, validate_and_resolve


REPO = Path(__file__).resolve().parents[1]


class HulaConfigurationTests(unittest.TestCase):
    def test_hula_dimensions_components_and_public_specs(self) -> None:
        config = validate_and_resolve(load_model_config(REPO / "config" / "hula_model.yaml"))
        derived = config["derived"]
        positions = list(derived["motor_positions_mm"].values())
        span_x = max(item[0] for item in positions) - min(item[0] for item in positions)
        span_y = max(item[1] for item in positions) - min(item[1] for item in positions)

        self.assertEqual(derived["rotor_count"], 4)
        self.assertAlmostEqual(config["measurements"]["motor_center_diagonal_mm"]["value"], 128.0)
        self.assertAlmostEqual(span_x + derived["guard_outer_width_mm"], 184.6)
        self.assertAlmostEqual(span_y + derived["guard_outer_length_mm"], 189.3)
        self.assertEqual(config["propeller"]["diameter_mm"], 75.0)
        self.assertLess(config["propeller"]["opacity"], 1.0)
        self.assertEqual(config["body"]["length_mm"], 90.0)
        self.assertEqual(config["body"]["height_mm"], 35.0)
        self.assertEqual(config["body"]["width_mm"], 40.0)
        self.assertEqual(config["body"]["shape"], "bulged_box")
        self.assertEqual(config["arm"]["style"], "measured_triangle")
        self.assertEqual(config["arm"]["front_member_lengths_mm"], {"outer": 30.0, "inner": 25.0})
        self.assertEqual(config["arm"]["rear_member_lengths_mm"], {"outer": 40.0, "inner": 35.0})
        self.assertEqual(config["arm"]["vertical_member_roles"], ["upper", "lower"])
        self.assertEqual(config["arm"]["vertical_root_spacing_mm"], 11.5)
        self.assertEqual(config["motor"]["housing_diameter_mm"], 10.0)
        self.assertEqual(config["motor"]["published_specification"], "L8.5 20")
        self.assertEqual(config["guard"]["mount_tube_diameter_mm"], 15.0)
        self.assertEqual(config["guard"]["shape"], "outward_semicircle")
        self.assertEqual(config["guard"]["outer_diameter_mm"], 100.0)
        self.assertEqual(config["guard"]["published_specification"], "75 mm / 3 in")
        self.assertEqual(config["guard"]["sweep_deg"], 180.0)
        self.assertEqual(config["guard"]["tube_diameter_mm"], 3.0)
        self.assertEqual(config["guard"]["center_z_mm"], 16.0)
        self.assertEqual(config["guard"]["height_above_motor_pod_mm"], 20.0)
        self.assertEqual(config["guard"]["strut_start_z_mm"], 5.0)
        self.assertEqual(config["guard"]["strut_end_z_mm"], 16.0)
        self.assertEqual(config["guard"]["strut_angle_offsets_deg"], [-90.0, 0.0, 90.0])

        cameras = {item["id"]: item for item in config["equipment"]["cameras"]}
        self.assertEqual(set(cameras), {"front", "downward"})
        self.assertTrue(cameras["front"]["movable"])
        self.assertEqual(cameras["front"]["tilt_range_deg"], 120.0)
        self.assertEqual(cameras["front"]["shape"], "hemisphere")
        self.assertEqual(cameras["front"]["diameter_mm"], 25.0)
        self.assertEqual(cameras["front"]["body_protrusion_mm"], 20.0)
        self.assertEqual(cameras["front"]["location_mm"], [0.0, -52.5, -6.0])
        self.assertEqual(config["specifications"]["camera"]["field_of_view_deg"], 71.0)
        self.assertEqual(config["specifications"]["official_size_mm"], [189.3, 184.6, 50.0])
        self.assertEqual(config["specifications"]["official_size_tolerance_mm"], 3.0)
        self.assertEqual(config["specifications"]["wheelbase_mm"], 128.0)
        self.assertEqual(config["specifications"]["wheelbase_tolerance_mm"], 1.0)
        self.assertEqual(config["specifications"]["camera"]["video_modes"], ["720p_30fps"])
        self.assertEqual(config["specifications"]["camera"]["patrol_video_mode"], "360p_30fps")
        self.assertEqual(config["specifications"]["battery"]["weight_g"], 31.0)
        self.assertEqual(
            config["specifications"]["battery"]["storage_temperature_as_published"][1]["maximum_period"],
            "3_months",
        )
        self.assertFalse(config["specifications"]["japan_variant_5_8_ghz_available"])
        self.assertEqual(config["specifications"]["laser"]["wavelength_nm"], 640.0)
        self.assertTrue(config["specifications"]["laser"]["japan_variant_restricted"])
        self.assertEqual(config["specifications"]["software_requirements"]["mac"]["macos_minimum"], 11.0)
        self.assertEqual(config["specifications"]["software_requirements"]["mac"]["chip_minimum"], "Apple_M1")
        self.assertEqual(config["specifications"]["weight_with_guard_g"]["tolerance"], 3.0)
        self.assertEqual(config["specifications"]["manual"]["version"], "V12")
        self.assertEqual(config["specifications"]["manual"]["revision_date"], "2025-12-12")
        self.assertEqual(config["specifications"]["operating_temperature_c"], [0.0, 40.0])
        self.assertEqual(config["physics"]["mass_g"], 100.0)


if __name__ == "__main__":
    unittest.main()
