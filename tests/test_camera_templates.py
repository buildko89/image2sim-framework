"""test_camera_templates.py - カメラテンプレートの読み込み・センサー設定との照合・形の計算の回帰試験（Blender 不要）。

センサーの設定 JSON（hakoniwa-mujoco-sensor）が兄弟フォルダに無い環境では、同じ形の JSON を一時フォルダに作って試す。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "camera_model"))

import camera_geometry as cg  # noqa: E402

SENSOR_JSON = {
    "spec": {
        "frame_id": "irvision_optical", "update_rate": 10.0, "horizontal_fov": 2 * math.atan(7.2 / 16),
        "image": {"width": 1280, "height": 1024, "format": "L8"}, "clip": {"near": 0.03, "far": 3.0},
        "intrinsics": {"fx": 1422.2222222222222, "fy": 1422.2222222222222, "cx": 640.0, "cy": 512.0},
    },
    "mjcf_binding": {"camera_name": "irvision_cam"},
    "irvision": {
        "model": "FANUC iRVision 2D", "image_type": "grayscale", "focal_length_mm": 8.0, "pixel_pitch_um": 5.625,
        "sensor_size_mm": [7.2, 5.76], "vertical_fov": 2 * math.atan(5.76 / 16),
        "led": {"color": "red", "rgb": [1.0, 0.08, 0.02]},
        "housing_mm": {"width": 80.0, "height": 74.0, "length": 131.8}, "mass_kg": 0.6, "mjcf": "irvision_2d.xml",
    },
}


@pytest.fixture()
def sensor_json(tmp_path) -> str:
    sibling = REPO.parent / "hakoniwa-mujoco-sensor" / "config" / "irvision" / "irvision_2d_gray_8mm.json"
    if sibling.is_file():
        return str(sibling)
    p = tmp_path / "irvision_2d_gray_8mm.json"
    p.write_text(json.dumps(SENSOR_JSON), encoding="utf-8")
    return str(p)


def test_template_found():
    assert "irvision_2d" in cg.list_templates()


def test_resolve_takes_optics_from_sensor(sensor_json):
    cfg = cg.resolve("irvision_2d", sensor_json)
    o = cfg["optics"]
    assert o["image_size"] == [1280, 1024]
    assert o["image_format"] == "L8"
    assert o["focal_length_mm"] == 8.0
    assert math.degrees(o["horizontal_fov_rad"]) == pytest.approx(48.4555, abs=1e-3)
    assert math.degrees(o["vertical_fov_rad"]) == pytest.approx(39.5978, abs=1e-3)
    assert o["camera_name"] == "irvision_cam"
    assert o["led_color"] == "red"
    assert cfg["mass_kg"] == 0.6


def test_body_envelope_is_the_housing(sensor_json):
    cfg = cg.resolve("irvision_2d", sensor_json)
    env = cfg["envelope_body"]
    assert env["size"] == pytest.approx([0.1318, 0.080, 0.074], abs=1e-9)
    assert env["max"][0] == pytest.approx(0.0, abs=1e-9)      # 前面 = 光学中心
    assert env["min"][0] == pytest.approx(-0.1318, abs=1e-9)  # 後ろへ伸びる


def test_parts_inside_the_front_layer_and_led_count(sensor_json):
    cfg = cg.resolve("irvision_2d", sensor_json)
    fl = cfg["visual"]["front_layer_m"]
    front = [p for p in cfg["parts"] if p["role"] in {"lens", "window", "led"}]
    for p in front:
        hx = p["half"][0] if p["shape"] == "box" else p["half_length"]
        assert -fl - 1e-12 <= p["center"][0] - hx and p["center"][0] + hx <= 1e-12, p["name"]
    n = cfg["visual"]["led_layout"]["per_side"]
    assert sum(p["role"] == "led" for p in cfg["parts"]) == 4 * n - 4
    housing = next(p for p in cfg["parts"] if p["name"] == "housing")
    assert housing["center"][0] + housing["half"][0] == pytest.approx(-fl)


def test_inconsistent_sensor_config_is_rejected(tmp_path):
    bad = json.loads(json.dumps(SENSOR_JSON))
    bad["spec"]["horizontal_fov"] = 0.9
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        cg.resolve("irvision_2d", str(p))


def test_missing_sensor_config_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError):
        cg.resolve("irvision_2d", str(tmp_path / "nope.json"))
