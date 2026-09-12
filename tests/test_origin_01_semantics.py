from __future__ import annotations

import json
import os
import struct
import unittest
from pathlib import Path


def read_glb_json(path: Path) -> dict:
    with path.open("rb") as f:
        magic, ver, length = struct.unpack("<III", f.read(12))
        if magic != 0x46546C67:
            raise ValueError(f"Not a GLB: {path}")
        chunk_len, chunk_type = struct.unpack("<II", f.read(8))
        return json.loads(f.read(chunk_len).decode("utf-8"))


class TestOrigin01Semantics(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[1]
        self.generated_dir = self.repo / "output" / "origin_01_parametric"
        self.original_dir = Path(r"D:\work_godot\hakoniwa-godot-drone\Models\origin-01")

    def test_files_exist(self):
        expected_files = [
            "origin-01.glb",
            "origin_01_body.glb",
            "origin_01_transporter.glb",
            "propeller_origin_01.glb",
            "origin_01_camera.glb",
            "origin_01_lidar.glb",
            "origin_01_lidar2.glb",
            "parts_param.json",
        ]
        for f in expected_files:
            gen_path = self.generated_dir / f
            self.assertTrue(gen_path.is_file(), f"Generated file missing: {f}")

    def test_parts_param_json(self):
        gen_path = self.generated_dir / "parts_param.json"
        orig_path = self.original_dir / "parts_param.json"
        with gen_path.open("r", encoding="utf-8") as f:
            gen_data = json.load(f)
        with orig_path.open("r", encoding="utf-8") as f:
            orig_data = json.load(f)

        # プロペラ座標のチェック
        orig_props = {p["name"]: p["pos"] for p in orig_data["propellers"]}
        gen_props = {p["name"]: p["pos"] for p in gen_data["propellers"]}
        for name, pos in orig_props.items():
            self.assertIn(name, gen_props)
            self.assertEqual(pos, gen_props[name])

        self.assertEqual(orig_data.get("DRONE_SCALE"), gen_data.get("DRONE_SCALE"))
        self.assertEqual(orig_data.get("CAMERA_POSITIONS"), gen_data.get("CAMERA_POSITIONS"))

    def test_sub_glb_node_names(self):
        sub_glbs = [
            "origin_01_body.glb",
            "origin_01_transporter.glb",
            "origin_01_camera.glb",
            "origin_01_lidar.glb",
            "origin_01_lidar2.glb",
            "propeller_origin_01.glb",
        ]
        for glb_name in sub_glbs:
            with self.subTest(glb=glb_name):
                gen_data = read_glb_json(self.generated_dir / glb_name)
                orig_data = read_glb_json(self.original_dir / glb_name)

                gen_nodes = sorted(n.get("name") for n in gen_data.get("nodes", []))
                orig_nodes = sorted(n.get("name") for n in orig_data.get("nodes", []))
                self.assertEqual(orig_nodes, gen_nodes, f"Node names mismatch in {glb_name}")

    def test_sub_glb_materials(self):
        sub_glbs = [
            "origin_01_body.glb",
            "origin_01_transporter.glb",
            "origin_01_camera.glb",
            "origin_01_lidar.glb",
            "origin_01_lidar2.glb",
            "propeller_origin_01.glb",
        ]
        for glb_name in sub_glbs:
            with self.subTest(glb=glb_name):
                gen_data = read_glb_json(self.generated_dir / glb_name)
                orig_data = read_glb_json(self.original_dir / glb_name)

                gen_mats = sorted(m.get("name") for m in gen_data.get("materials", []))
                orig_mats = sorted(m.get("name") for m in orig_data.get("materials", []))
                self.assertEqual(orig_mats, gen_mats, f"Material names mismatch in {glb_name}")


if __name__ == "__main__":
    unittest.main()
