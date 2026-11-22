"""camera_geometry.py - カメラ（iRVision 2D など）の形と光学を 1 か所で計算する。

Blender（見た目）・USD の組み立て・QA が同じ値を使う。Blender・pxr には依存しない（pytest で試せる）。

入力:
    テンプレート YAML（config/camera_templates/<id>.yaml）
    センサーの設定 JSON（hakoniwa-mujoco-sensor の config/irvision/*.json。光学・外形・質量の正本）
出力:
    resolve() の辞書（resolved_config.json に書く）。部品は本体の座標（原点 = 光学中心、+x = 光軸）の箱・円柱。
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parents[1]
TEMPLATES_DIR = REPO_DIR / "config" / "camera_templates"


def list_templates() -> List[str]:
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml"))


def load_template(template_id: str) -> Dict[str, Any]:
    path = TEMPLATES_DIR / f"{template_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"camera template not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data.get("template_id") != template_id:
        raise ValueError(f"{path}: template_id must be {template_id!r}")
    return data


def sensor_config_path(template: Dict[str, Any], override: Optional[str] = None) -> Path:
    """既定はこのリポジトリの親フォルダ（兄弟のリポジトリが並ぶ作業場所）からの相対。"""
    p = Path(override) if override else REPO_DIR.parent / template["sensor_config"]
    if not p.is_file():
        raise FileNotFoundError(
            f"sensor config not found: {p}\n"
            "  hakoniwa-mujoco-sensor を兄弟フォルダに置くか、--sensor-config で場所を指定してください。")
    return p


def optics_from_sensor(sensor: Dict[str, Any]) -> Dict[str, Any]:
    spec, irv = sensor["spec"], sensor["irvision"]
    w, h = spec["image"]["width"], spec["image"]["height"]
    sw, sh = irv["sensor_size_mm"]
    f = irv["focal_length_mm"]
    hfov = 2 * math.atan(sw / (2 * f))
    vfov = 2 * math.atan(sh / (2 * f))
    if abs(hfov - spec["horizontal_fov"]) > 1e-9:
        raise ValueError(f"sensor config is inconsistent: horizontal_fov {spec['horizontal_fov']} != {hfov}")
    return {
        "focal_length_mm": f,
        "sensor_size_mm": [sw, sh],
        "image_size": [w, h],
        "image_format": spec["image"]["format"],
        "horizontal_fov_rad": hfov,
        "vertical_fov_rad": vfov,
        "intrinsics": spec.get("intrinsics", {}),
        "clip_m": [spec["clip"]["near"], spec["clip"]["far"]],
        "update_rate_hz": spec["update_rate"],
        "frame_id": spec["frame_id"],
        "camera_name": sensor.get("mjcf_binding", {}).get("camera_name", ""),
        "led_color": irv["led"]["color"],
        "led_rgb": irv["led"]["rgb"],
    }


def _box(name: str, role: str, x0: float, x1: float, hy: float, hz: float, cy: float = 0.0, cz: float = 0.0,
         **extra: Any) -> Dict[str, Any]:
    return {"name": name, "role": role, "shape": "box", "center": [(x0 + x1) / 2, cy, cz],
            "half": [(x1 - x0) / 2, hy, hz], **extra}


def _cyl_x(name: str, role: str, x0: float, x1: float, radius: float, cy: float = 0.0, cz: float = 0.0,
           **extra: Any) -> Dict[str, Any]:
    """光軸（x）向きの円柱。"""
    return {"name": name, "role": role, "shape": "cylinder", "axis": "x", "center": [(x0 + x1) / 2, cy, cz],
            "radius": radius, "half_length": (x1 - x0) / 2, **extra}


def build_parts(housing_mm: Dict[str, float], visual: Dict[str, Any]) -> List[Dict[str, Any]]:
    L, W, H = housing_mm["length"] / 1000, housing_mm["width"] / 1000, housing_mm["height"] / 1000
    fl = visual["front_layer_m"]
    parts: List[Dict[str, Any]] = [
        _box("housing", "housing", -L, -fl, W / 2, H / 2, bevel=visual["bevel_m"]),
    ]
    # 前面の層（後ろから レンズ → 窓 → LED）
    lens = visual["lens"]
    parts.append(_cyl_x("lens_barrel", "lens", -fl, -0.75 * fl, lens["barrel_radius_m"]))
    parts.append(_cyl_x("lens_glass", "lens", -0.75 * fl, -0.6 * fl, lens["radius_m"]))
    win = visual["window"]
    parts.append(_box("window", "window", -0.6 * fl, -0.6 * fl + win["thickness_m"],
                      W / 2 - win["inset_m"], H / 2 - win["inset_m"]))
    led = visual["led_layout"]
    n, (ry, rz), s = led["per_side"], led["ring_half_m"], led["size_m"]
    x0, x1 = -0.35 * fl, 0.0  # LED の前面 = 光学中心（本体の最前面）
    k = 0
    for i in range(n):  # 上下の辺
        y = -ry + 2 * ry * i / (n - 1)
        for z in (rz, -rz):
            parts.append(_box(f"led_{k:02d}", "led", x0, x1, s / 2, s / 2, cy=y, cz=z)); k += 1
    for i in range(1, n - 1):  # 左右の辺（角は上下で置いた）
        z = -rz + 2 * rz * i / (n - 1)
        for y in (ry, -ry):
            parts.append(_box(f"led_{k:02d}", "led", x0, x1, s / 2, s / 2, cy=y, cz=z)); k += 1
    lab = visual["label"]
    if lab["face"] != "+y":
        raise ValueError("label.face は +y だけ対応")
    lx, lz = lab["size_m"]
    parts.append(_box("label", "label", lab["center_x_m"] - lx / 2, lab["center_x_m"] + lx / 2,
                      0.0002, lz / 2, cy=W / 2 + 0.0002))
    con = visual["connector"]
    if con["face"] != "-z":
        raise ValueError("connector.face は -z だけ対応")
    parts.append({"name": "connector", "role": "connector", "shape": "cylinder", "axis": "z",
                  "center": [con["center_x_m"], 0.0, -H / 2 - con["length_m"] / 2],
                  "radius": con["radius_m"], "half_length": con["length_m"] / 2})
    return parts


def envelope(parts: List[Dict[str, Any]], roles: Optional[set] = None) -> Dict[str, List[float]]:
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for p in parts:
        if roles and p["role"] not in roles:
            continue
        c = p["center"]
        if p["shape"] == "box":
            h = p["half"]
        else:
            r, hl = p["radius"], p["half_length"]
            h = [hl, r, r] if p["axis"] == "x" else [r, r, hl]
        for i in range(3):
            lo[i] = min(lo[i], c[i] - h[i])
            hi[i] = max(hi[i], c[i] + h[i])
    return {"min": lo, "max": hi, "size": [hi[i] - lo[i] for i in range(3)]}


def resolve(template_id: str, sensor_config: Optional[str] = None) -> Dict[str, Any]:
    tpl = load_template(template_id)
    spath = sensor_config_path(tpl, sensor_config)
    sensor = json.loads(spath.read_text(encoding="utf-8"))
    irv = sensor["irvision"]
    housing = irv["housing_mm"]
    parts = build_parts(housing, tpl["visual"])
    body = envelope(parts, {"housing", "lens", "window", "led"})
    return {
        "template_id": template_id,
        "display_name": tpl["display_name"],
        "root_prim": tpl["root_prim"],
        "model": irv["model"],
        "sensor_config": str(spath),
        "sensor_mjcf": str(spath.with_name(irv["mjcf"])) if irv.get("mjcf") else "",
        "housing_mm": housing,
        "mass_kg": irv["mass_kg"],
        "optics": optics_from_sensor(sensor),
        "visual": tpl["visual"],
        "usd": tpl["usd"],
        "provenance": tpl["provenance"],
        "parts": parts,
        "envelope_body": body,
        "frame": {"origin": "front window centre = optical centre", "x": "optical axis (forward)",
                  "y": "left", "z": "up", "unit": "m"},
    }
