"""blend2mjcf_nc.py - 加工機・台車・パレットの MJCF・同期プロファイル・ロボット用インタフェースを書き出す。

使用法:
    python scripts/nc_machine/blend2mjcf_nc.py --config-json <resolved_config.json> --out-dir <出力フォルダ>

形は nc_geometry.describe() の結果（Blender の見た目と同じ値）から作る。名前には接頭辞を付けない
（hakoniwa-cobot の gen_cell.py が mjSpec の attach でインスタンス名 NC1/ などを付ける）。
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import nc_geometry as ncg  # noqa: E402


def fmt(v) -> str:
    return " ".join(f"{float(x):.6g}" for x in v)


def generate_mjcf(desc: Dict[str, Any]) -> str:
    root = ET.Element("mujoco", model=desc["template_id"])
    ET.SubElement(root, "compiler", angle="radian", autolimits="true")
    # 単体で動かすとき（preview・試験）の刻み。hakoniwa-cobot のセルに取り込むときはセルの値が使われる
    ET.SubElement(root, "option", timestep="0.001")
    default = ET.SubElement(root, "default")
    col = ET.SubElement(default, "default", {"class": "nc_collision"})
    ET.SubElement(col, "geom", contype="1", conaffinity="1", group="2")
    vis = ET.SubElement(default, "default", {"class": "nc_visual"})
    ET.SubElement(vis, "geom", contype="0", conaffinity="0", group="1", mass="0")
    site_def = ET.SubElement(default, "default", {"class": "nc_site"})
    ET.SubElement(site_def, "site", group="4", rgba="1 0.5 0 0.3")

    asset = ET.SubElement(root, "asset")
    for name, c in desc["materials"].items():
        ET.SubElement(asset, "material", name=name, rgba=fmt(c))

    world = ET.SubElement(root, "worldbody")
    elems = {}
    sites_by_body: Dict[str, list] = {}
    for s in desc["sites"]:
        sites_by_body.setdefault(s["body"], []).append(s)
    for bd in desc["bodies"]:
        parent = elems[bd["parent"]] if bd["parent"] else world
        b = ET.SubElement(parent, "body", name=bd["name"], pos=fmt(bd["pos"]))
        elems[bd["name"]] = b
        if bd["joint"]:
            j = bd["joint"]
            attrs = {"name": j["name"], "type": j["type"], "axis": fmt(j["axis"])}
            if j.get("range") is not None:
                attrs["range"] = fmt(j["range"])
            for key in ("armature", "damping"):
                if j.get(key) is not None:
                    attrs[key] = f"{float(j[key]):.6g}"
            ET.SubElement(b, "joint", attrs)
        for g in bd["geoms"]:
            attrs = {"name": g["name"], "type": g["type"], "size": fmt(g["size"]), "pos": fmt(g["pos"]),
                     "material": g["material"], "class": "nc_collision" if g["collide"] else "nc_visual"}
            if g["quat"] != ncg.Q_ID:
                attrs["quat"] = fmt(g["quat"])
            ET.SubElement(b, "geom", attrs)
        for s in sites_by_body.get(bd["name"], []):
            attrs = {"name": s["name"], "type": s["type"], "pos": fmt(s["pos"]), "size": fmt(s["size"]),
                     "class": "nc_site"}
            ET.SubElement(b, "site", attrs)
    acts = desc.get("actuators") or []
    if acts:
        # LOD1：プラントが目標を入れて動かす。position は kp・kv、velocity は kv。力の上限を付ける
        act_el = ET.SubElement(root, "actuator")
        for a in acts:
            attrs = {"name": a["name"], "joint": a["joint"], "kv": f"{a['kv']:.6g}",
                     "ctrlrange": fmt(a["ctrlrange"]), "forcerange": fmt(a["forcerange"])}
            if a["kind"] == "position":
                attrs["kp"] = f"{a['kp']:.6g}"
            ET.SubElement(act_el, a["kind"], attrs)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode") + "\n"


def generate_sync_profile(desc: Dict[str, Any]) -> Dict[str, Any]:
    """箱庭ビューア向け。ノード名＝MJCF のボディ名。LOD0 は関節なし（全ボディ固定）。"""
    joints = []
    for bd in desc["bodies"]:
        if bd["joint"]:
            joints.append({"name": bd["joint"]["name"], "type": bd["joint"]["type"], "node_name": bd["name"]})
    return {
        "robot_name": desc["template_id"],
        "root_body": desc["bodies"][0]["name"],
        "coordinate_conversion": {"source": "Z-up (MuJoCo)", "target": "Unreal_and_Godot", "scale": 1.0},
        "nodes": [bd["name"] for bd in desc["bodies"]],
        "joints": joints,
    }


def write_all(cfg: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    desc = ncg.describe(cfg)
    out_dir.mkdir(parents=True, exist_ok=True)
    subject = desc["template_id"]
    paths = {
        "mjcf": out_dir / f"{subject}.xml",
        "profile": out_dir / ("machine_sync.profile.json" if desc["kind"] == "machine" else "sync.profile.json"),
        "interface": out_dir / ("robot_interface.json" if desc["kind"] == "machine" else f"{desc['kind']}_interface.json"),
    }
    paths["mjcf"].write_text(generate_mjcf(desc), encoding="utf-8")
    paths["profile"].write_text(json.dumps(generate_sync_profile(desc), indent=2, ensure_ascii=False), encoding="utf-8")
    paths["interface"].write_text(json.dumps(desc["interface"], indent=2, ensure_ascii=False), encoding="utf-8")
    if desc.get("plant"):
        # LOD1：加工機の物理モジュール（hakoniwa-ncmachine の plant/）が読む関節・アクチュエータの名前と動きの値
        paths["plant"] = out_dir / "machine_plant.json"
        paths["plant"].write_text(json.dumps(desc["plant"], indent=2, ensure_ascii=False), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}


def main() -> int:
    p = argparse.ArgumentParser(prog="blend2mjcf_nc.py")
    p.add_argument("--config-json", required=True)
    p.add_argument("--out-dir", required=True)
    a = p.parse_args()
    cfg = json.loads(Path(a.config_json).read_text(encoding="utf-8"))
    for k, v in write_all(cfg, Path(a.out_dir)).items():
        print(f"[blend2mjcf_nc.py] {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
