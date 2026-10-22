"""blend2mjcf_ship.py - 船舶モデルからマルチボディMJCFと同期プロファイルを自動生成する。

機能:
  1. Blender .blend または resolved_config.json から船舶マルチボディMJCF (XML) を生成。
  2. geom_user[0] にレーダ反射断面積 RCS σ [m^2] を埋め込む (RadarSensor 契約)。
  3. 40点波面浮力計測サイト (BUOYANCY_SITES) を <site> として配置。
  4. 操舵 (Rudder hinge)・推進 (Propeller spin)・レーダ (Radar spin) のアクチュエータと関節ツリーを構築。
  5. 貴島 (1990) 推定式により hydro_mmg.json を自動算出・出力。
  6. 箱庭ビューア (Unreal / Godot) 用の同期プロファイル ship_sync.profile.json を出力。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List

# 同一ディレクトリの kijima_mmg をインポート
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
from kijima_mmg import estimate_mmg_coefficients


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="blend2mjcf_ship.py")
    p.add_argument("--config-json", required=True, help="解決済み船舶設定JSON")
    p.add_argument("--out-mjcf", required=True, help="出力MJCF XMLパス")
    p.add_argument("--out-hydro", required=True, help="出力MMG係数JSONパス")
    p.add_argument("--out-profile", required=True, help="出力同期プロファイルJSONパス")
    return p.parse_args()


# 可動部質量の基準（749GT: 舵面積 7.2 m^2 で 3,500 kg、プロペラ直径 3.2 m で 2,200 kg）。
# 舵は面積^1.5（寸法^3）、プロペラは直径^3 で換算する。
REF_RUDDER_AREA_M2 = 7.2
REF_RUDDER_MASS_KG = 3500.0
REF_PROPELLER_DIA_M = 3.2
REF_PROPELLER_MASS_KG = 2200.0
RADAR_ANTENNA_MASS_KG = 45.0


def rudder_mass_kg(area_m2: float) -> float:
    return REF_RUDDER_MASS_KG * (area_m2 / REF_RUDDER_AREA_M2) ** 1.5


def propeller_mass_kg(diameter_m: float) -> float:
    return REF_PROPELLER_MASS_KG * (diameter_m / REF_PROPELLER_DIA_M) ** 3


def to_flu(v: List[float] | tuple) -> List[float]:
    """Blender座標系 (+X: 右, +Y: 前, +Z: 上) から MuJoCo FLU (x: 前, y: 左, z: 上) へ変換。"""
    # x_flu = y_blender, y_flu = -x_blender, z_flu = z_blender
    return [round(float(v[1]), 4), round(-float(v[0]), 4), round(float(v[2]), 4)]


def vec_str(v: List[float]) -> str:
    return f"{v[0]:.4f} {v[1]:.4f} {v[2]:.4f}"


def generate_mjcf(cfg: Dict[str, Any], hydro: Dict[str, Any]) -> str:
    subject = cfg.get("template_id", "vessel")
    dim = cfg["dimensions"]
    Lpp = float(dim["length_pp_m"])
    B = float(dim["beam_m"])
    d = float(dim["draft_m"])
    D = float(dim["depth_m"])
    displacement_kg = float(hydro["mass_and_inertia"]["mass_kg"])
    # 可動部（舵・プロペラ・レーダ）の質量は船の大きさで換算し、船体質量から差し引いて
    # 全質量 = 排水量（計画喫水で浮く）にする。固定値のままだと小型船（漁船 16 t に 5.7 t）で
    # 過積載・船尾トリムになる。
    appendage_kg = (
        sum(rudder_mass_kg(float(r.get("area_m2", 7.0))) for r in cfg.get("actuators", {}).get("rudders", []))
        + sum(propeller_mass_kg(float(p.get("diameter_m", 3.2))) for p in cfg.get("actuators", {}).get("propellers", []))
        + RADAR_ANTENNA_MASS_KG * sum(1 for m in cfg.get("mounts", []) if m.get("type") == "marine_radar")
    )
    mass_kg = displacement_kg - appendage_kg
    Izz = float(hydro["mass_and_inertia"]["Izz_kgm2"])
    # Ixx (ロール慣性モーメント) ≈ mass * (0.38 * B)^2
    Ixx = mass_kg * ((0.38 * B) ** 2)
    # Iyy (ピッチ慣性モーメント) ≈ mass * (0.25 * Lpp)^2
    Iyy = mass_kg * ((0.25 * Lpp) ** 2)

    total_rcs = float(cfg.get("signatures", {}).get("radar_cross_section_m2", 2500.0))

    xml = [
        f'<?xml version="1.0" encoding="utf-8"?>',
        f'<!-- 自動生成: blend2mjcf_ship.py (image2sim-ship) -->',
        f'<!-- 船舶モデル: {subject} ({cfg.get("name", "")}) -->',
        f'<!-- 座標系: MuJoCo FLU (x: 前方, y: 左舷, z: 上方) -->',
        f'<mujoco model="{subject}">',
        f'  <compiler angle="degree" coordinate="local"/>',
        f'  <option timestep="0.002" gravity="0 0 -9.80665"/>',
        f'',
        f'  <default>',
        f'    <default class="hull_geom">',
        f'      <geom type="box" group="3" contype="1" conaffinity="1" rgba="0.15 0.16 0.18 1.0" user="{total_rcs * 0.45:.1f}"/>',
        f'    </default>',
        f'    <default class="rudder_joint">',
        f'      <joint type="hinge" axis="0 0 1" range="-35 35" damping="50000" armature="1000"/>',
        f'    </default>',
        f'    <default class="propeller_joint">',
        f'      <joint type="hinge" axis="1 0 0" damping="500" armature="50"/>',
        f'    </default>',
        f'    <default class="radar_joint">',
        f'      <joint type="hinge" axis="0 0 1" damping="10" armature="5"/>',
        f'    </default>',
        f'    <default class="buoyancy_site">',
        f'      <site type="sphere" size="0.25" group="4" rgba="0.2 0.8 1.0 0.5"/>',
        f'    </default>',
        f'    <default class="mount_site">',
        f'      <site type="sphere" size="0.20" group="2" rgba="1.0 0.8 0.2 0.8"/>',
        f'    </default>',
        f'    <default class="light_site">',
        f'      <site type="sphere" size="0.15" group="2" rgba="1.0 1.0 1.0 0.9"/>',
        f'    </default>',
        f'  </default>',
        f'',
        f'  <worldbody>',
        f'    <!-- 自船メインボディ (水線面 z=0, 船体中央 x=0, 竜骨 z=-d) -->',
        f'    <body name="vessel" pos="0 0 0">',
        f'      <freejoint name="vessel_free"/>',
        f'      <inertial pos="0 0 {-d * 0.35:.3f}" mass="{mass_kg:.1f}" diaginertia="{Ixx:.1e} {Iyy:.1e} {Izz:.1e}"/>',
        f'',
        f'      <!-- 船体コライダ (geom_user[0] に RCS σ を埋め込み) -->',
        f'      <geom class="hull_geom" name="geom_hull_main" pos="0 0 {(D - 2.0*d)*0.5:.3f}" size="{Lpp*0.325:.3f} {B*0.475:.3f} {D*0.5:.3f}" user="{total_rcs * 0.45:.1f}"/>',
        f'      <geom class="hull_geom" name="geom_hull_bow" pos="{Lpp*0.38:.3f} 0 {(D - 2.0*d)*0.5:.3f}" size="{Lpp*0.125:.3f} {B*0.35:.3f} {D*0.55:.3f}" user="{total_rcs * 0.20:.1f}"/>',
        f'      <geom class="hull_geom" name="geom_superstructure" pos="{-Lpp*0.38:.3f} 0 {(D - d) + 5.5:.3f}" size="7.0 {B*0.42:.3f} 5.5" user="{total_rcs * 0.35:.1f}"/>',
        f'',
        f'      <!-- 40点波面浮力計測サイト (BUOYANCY_SITES: 20 Station x 左右舷) -->',
    ]

    # 40点浮力サイトの配置 (FLU系: x 前後, y 左右, z 上下)
    n_st = int(cfg.get("buoyancy", {}).get("stations_count", 20))
    offset_ratio = float(cfg.get("buoyancy", {}).get("transverse_offset_ratio", 0.70))
    dx = Lpp / n_st

    for i in range(n_st):
        x_st = -Lpp / 2.0 + (i + 0.5) * dx
        xi = x_st / (Lpp / 2.0)
        b_st = (B / 2.0) * max(0.15, (1.0 - abs(xi) ** 2.2) ** 0.5)
        y_offset = b_st * offset_ratio

        # 左舷 (Port: +y in FLU)
        xml.append(f'      <site class="buoyancy_site" name="buoyancy_st{i:02d}_port" pos="{x_st:.3f} {y_offset:.3f} 0.000"/>')
        # 右舷 (Starboard: -y in FLU)
        xml.append(f'      <site class="buoyancy_site" name="buoyancy_st{i:02d}_stbd" pos="{x_st:.3f} {-y_offset:.3f} 0.000"/>')

    # センサ取付点 (MOUNTS)
    xml.append(f'')
    xml.append(f'      <!-- センサ取付点 (MOUNTS) -->')
    for m in cfg.get("mounts", []):
        mid = m["id"]
        pos_flu = to_flu(m.get("pos_m", [0.0, 0.0, 0.0]))
        xml.append(f'      <site class="mount_site" name="mount_{mid}" pos="{vec_str(pos_flu)}"/>')

    # 航海灯 (NAV_LIGHTS)
    xml.append(f'')
    xml.append(f'      <!-- 航海灯 (NAV_LIGHTS) -->')
    for l in cfg.get("nav_lights", []):
        lid = l["id"]
        pos_flu = to_flu(l.get("pos_m", [0.0, 0.0, 0.0]))
        xml.append(f'      <site class="light_site" name="navlight_{lid}" pos="{vec_str(pos_flu)}"/>')

    # アクチュエータ・サブボディ (舵・プロペラ・レーダ)
    xml.append(f'')
    xml.append(f'      <!-- 可動部: 舵 (Rudder) -->')
    for r in cfg.get("actuators", {}).get("rudders", []):
        rid = r["id"]
        pos_flu = to_flu(r.get("pos_m", [0.0, -44.0, -2.0]))
        area = float(r.get("area_m2", 7.0))
        ar = float(r.get("aspect_ratio", 1.6))
        hr = (area * ar) ** 0.5
        chord = area / hr
        xml.append(f'      <body name="body_rudder_{rid}" pos="{vec_str(pos_flu)}">')
        xml.append(f'        <joint class="rudder_joint" name="joint_rudder_{rid}"/>')
        mr = rudder_mass_kg(area)
        ir = (mr / REF_RUDDER_MASS_KG) * (area / REF_RUDDER_AREA_M2)
        xml.append(f'        <inertial pos="0 0 0" mass="{mr:.1f}" diaginertia="{500 * ir:.4g} {1200 * ir:.4g} {800 * ir:.4g}"/>')
        xml.append(f'        <geom type="box" size="{chord*0.5:.3f} 0.12 {hr*0.5:.3f}" rgba="0.3 0.35 0.4 1.0"/>')
        xml.append(f'      </body>')

    xml.append(f'')
    xml.append(f'      <!-- 可動部: プロペラ (Propeller) -->')
    for p in cfg.get("actuators", {}).get("propellers", []):
        pid = p["id"]
        pos_flu = to_flu(p.get("shaft_pos_m", [0.0, -42.0, -2.2]))
        dia = float(p.get("diameter_m", 3.2))
        xml.append(f'      <body name="body_propeller_{pid}" pos="{vec_str(pos_flu)}">')
        xml.append(f'        <joint class="propeller_joint" name="joint_propeller_{pid}"/>')
        mp = propeller_mass_kg(dia)
        ip = (mp / REF_PROPELLER_MASS_KG) * (dia / REF_PROPELLER_DIA_M) ** 2
        xml.append(f'        <inertial pos="0 0 0" mass="{mp:.1f}" diaginertia="{800 * ip:.4g} {500 * ip:.4g} {500 * ip:.4g}"/>')
        xml.append(f'        <geom type="cylinder" size="{dia*0.15:.3f} {dia*0.15:.3f}" euler="0 90 0" rgba="0.8 0.6 0.2 1.0"/>')
        xml.append(f'      </body>')

    xml.append(f'')
    xml.append(f'      <!-- 可動部: レーダアンテナ (Radar Antenna) -->')
    for m in cfg.get("mounts", []):
        if m.get("type") == "marine_radar":
            mid = m["id"]
            pos_flu = to_flu(m.get("pos_m", [0.0, -36.0, 20.0]))
            xml.append(f'      <body name="body_radar_{mid}" pos="{vec_str(pos_flu)}">')
            xml.append(f'        <joint class="radar_joint" name="joint_radar_{mid}"/>')
            xml.append(f'        <inertial pos="0 0 0" mass="{RADAR_ANTENNA_MASS_KG:.1f}" diaginertia="5 20 20"/>')
            xml.append(f'        <geom type="box" size="0.12 1.20 0.14" rgba="0.9 0.9 0.95 1.0"/>')
            xml.append(f'      </body>')

    xml.append(f'    </body>')
    xml.append(f'  </worldbody>')
    xml.append(f'')

    # アクチュエータ制御部
    xml.append(f'  <actuator>')
    for r in cfg.get("actuators", {}).get("rudders", []):
        rid = r["id"]
        max_deg = float(r.get("max_angle_deg", 35.0))
        max_rad = math.radians(max_deg)
        xml.append(f'    <position name="act_rudder_{rid}" joint="joint_rudder_{rid}" kp="200000" ctrlrange="{-max_rad:.4f} {max_rad:.4f}"/>')

    for p in cfg.get("actuators", {}).get("propellers", []):
        pid = p["id"]
        xml.append(f'    <motor name="act_propeller_{pid}" joint="joint_propeller_{pid}" ctrlrange="-500000 500000"/>')

    for m in cfg.get("mounts", []):
        if m.get("type") == "marine_radar":
            mid = m["id"]
            rpm = float(m.get("rpm", 24.0))
            rad_s = rpm * 2.0 * math.pi / 60.0
            xml.append(f'    <velocity name="act_radar_{mid}" joint="joint_radar_{mid}" kv="1000" ctrlrange="0 {rad_s*1.5:.2f}"/>')
    xml.append(f'  </actuator>')
    xml.append(f'')

    # センサ群 (IMU / 速度)
    xml.append(f'  <sensor>')
    xml.append(f'    <framepos name="ship_pos" objtype="body" objname="vessel"/>')
    xml.append(f'    <framequat name="ship_quat" objtype="body" objname="vessel"/>')
    xml.append(f'    <framelinvel name="ship_linvel" objtype="body" objname="vessel"/>')
    xml.append(f'    <frameangvel name="ship_angvel" objtype="body" objname="vessel"/>')
    for m in cfg.get("mounts", []):
        if m.get("type") == "gyro_compass":
            mid = m["id"]
            xml.append(f'    <gyro name="gyro_{mid}" site="mount_{mid}"/>')
            xml.append(f'    <accelerometer name="acc_{mid}" site="mount_{mid}"/>')
    xml.append(f'  </sensor>')
    xml.append(f'</mujoco>')

    return "\n".join(xml) + "\n"


def generate_sync_profile(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """箱庭ビューア (Unreal Engine 5.8 / Godot 4.6) 向けロボット同期プロファイルを生成する。"""
    subject = cfg.get("template_id", "vessel")
    joints = []

    # 舵関節
    for r in cfg.get("actuators", {}).get("rudders", []):
        rid = r["id"]
        joints.append({
            "name": f"joint_rudder_{rid}",
            "type": "hinge",
            "axis": "Z",
            "node_name": f"rudder_{rid}",
        })

    # プロペラ回転関節
    for p in cfg.get("actuators", {}).get("propellers", []):
        pid = p["id"]
        joints.append({
            "name": f"joint_propeller_{pid}",
            "type": "spin",
            "axis": "X_FLU_Y_BLENDER",
            "node_name": f"propeller_{pid}",
        })

    # レーダアンテナ関節
    for m in cfg.get("mounts", []):
        if m.get("type") == "marine_radar":
            mid = m["id"]
            joints.append({
                "name": f"joint_radar_{mid}",
                "type": "spin",
                "axis": "Z",
                "node_name": f"radar_mast_{mid}",
            })

    return {
        "robot_name": subject,
        "root_body": "vessel",
        "coordinate_conversion": {
            "source": "FLU",
            "target": "Unreal_and_Godot",
            "scale": 1.0,
        },
        "joints": joints,
        "buoyancy_sites_prefix": "buoyancy_st",
        "mounts_prefix": "mount_",
        "nav_lights_prefix": "navlight_",
    }


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config_json)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    dim = cfg["dimensions"]
    act = cfg.get("actuators", {})
    rudders = act.get("rudders", [{}])
    propellers = act.get("propellers", [{}])

    rudder_area = float(rudders[0].get("area_m2", 7.0))
    prop_dia = float(propellers[0].get("diameter_m", 3.2))

    # 1. 貴島推定式による初期MMGパラメータ算出
    hydro = estimate_mmg_coefficients(
        length_pp_m=float(dim["length_pp_m"]),
        beam_m=float(dim["beam_m"]),
        draft_m=float(dim["draft_m"]),
        block_coefficient=float(dim["block_coefficient"]),
        rudder_area_m2=rudder_area,
        propeller_dia_m=prop_dia,
        water_density_kg_m3=float(dim.get("water_density_kg_m3", 1025.0)),
    )

    # 自航平衡の設計点（航海速力・常用回転数 = 最大回転数 × 0.9^(1/3)、出力 90 % MCR 相当）と推進器・舵の基数。
    # MmgModel はこの点で直進抵抗を較正する（無いと全船 14 kt・210 rpm とみなし、小型船で K_T < 0 になる）
    service_speed_kt = float(dim.get("service_speed_kt", 14.0))
    max_rpm = float(propellers[0].get("max_rpm", 250.0))
    hydro["design_point"] = {
        "service_speed_kt": service_speed_kt,
        "service_speed_mps": service_speed_kt * 0.514444,
        "service_rpm": max_rpm * 0.9 ** (1.0 / 3.0),
    }
    hydro["propeller_and_rudder"]["propeller_count"] = len(act.get("propellers", [])) or 1
    hydro["propeller_and_rudder"]["rudder_count"] = len(act.get("rudders", [])) or 1

    # 2. hydro_mmg.json 出力
    out_hydro = Path(args.out_hydro)
    out_hydro.parent.mkdir(parents=True, exist_ok=True)
    with out_hydro.open("w", encoding="utf-8") as f:
        json.dump(hydro, f, indent=2, ensure_ascii=False)
    print(f"[blend2mjcf_ship.py] Generated hydro MMG JSON: {out_hydro}")

    # 3. MJCF XML 出力
    mjcf_xml = generate_mjcf(cfg, hydro)
    out_mjcf = Path(args.out_mjcf)
    out_mjcf.parent.mkdir(parents=True, exist_ok=True)
    out_mjcf.write_text(mjcf_xml, encoding="utf-8")
    print(f"[blend2mjcf_ship.py] Generated MJCF XML: {out_mjcf}")

    # 4. 同期プロファイル JSON 出力
    profile = generate_sync_profile(cfg)
    out_prof = Path(args.out_profile)
    out_prof.parent.mkdir(parents=True, exist_ok=True)
    with out_prof.open("w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    print(f"[blend2mjcf_ship.py] Generated sync profile JSON: {out_prof}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
