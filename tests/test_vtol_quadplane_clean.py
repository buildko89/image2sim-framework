from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path


class VtolQuadplaneCleanTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[1]
        self.glb_path = self.repo / "output" / "vtol_quadplane" / "vtol_quadplane.glb"

    def test_glb_exists(self):
        self.assertTrue(self.glb_path.is_file(), "vtol_quadplane.glb does not exist")

    def test_no_codrone_parts(self):
        with self.glb_path.open("rb") as f:
            f.seek(12)
            chunk_len, chunk_type = struct.unpack("<II", f.read(8))
            gltf = json.loads(f.read(chunk_len).decode("utf-8"))

        nodes = [n.get("name", "") for n in gltf.get("nodes", [])]

        banned_keywords = [
            "codrone",
            "canopy_cap",
            "ir_sensor",
            "bottom_ir",
            "bottom_optical_flow",
            "tail_light_panel",
            "front_center_port",
            "front_eye",
            "rear_chassis_hole",
        ]
        found_banned = []
        for node_name in nodes:
            for kw in banned_keywords:
                if kw in node_name.lower():
                    found_banned.append(node_name)

        self.assertEqual(
            found_banned,
            [],
            f"Found CoDrone parts in vtol_quadplane.glb: {found_banned}",
        )


if __name__ == "__main__":
    unittest.main()
