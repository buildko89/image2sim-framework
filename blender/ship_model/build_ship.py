"""build_ship.py - パラメトリック船舶モデルを Blender 5.2 で自動生成する。

実行方法:
    blender --background --factory-startup --python blender/ship_model/build_ship.py -- --config-json <resolved.json>

出力:
    - <subject>.blend (Blender シーン正本)
    - <subject>.glb (描画用 glTF 2.0)
    - renders/*.png (6方向正投影レンダリング)
    - build_report.json (検証レポート)

階層構造:
    <subject_id> (ルート: 水線面 z=0, 船体中央 y=0)
    ├─ Hull/ (船殻ロフトメッシュ)
    ├─ Superstructure/ (船橋・マスト・煙突)
    ├─ Cargo/ (コンテナスタック / 甲板装備)
    ├─ Actuators/ (プロペラ spin, 舵 hinge, レーダ spin)
    ├─ BUOYANCY_SITES/ (40点波面浮力計測サイト)
    ├─ COLLISION/ (凸コライダ + RCS属性)
    ├─ MOUNTS/ (センサ取付点)
    └─ NAV_LIGHTS/ (COLREG航海灯)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import bmesh
import bpy
from mathutils import Matrix, Vector


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="build_ship.py")
    p.add_argument("--config-json", required=True)
    return p.parse_args(argv)


# --- シーンおよびマテリアルのセットアップ --------------------------------------

MATS: Dict[str, bpy.types.Material] = {}


def setup_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.world = bpy.data.worlds.new("ShipWorld")
    scene.world.color = (0.04, 0.05, 0.07)


def make_material(name: str, color: Tuple[float, float, float, float], metallic: float = 0.0,
                  roughness: float = 0.5, emission: float = 0.0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = color
                bsdf.inputs["Emission Strength"].default_value = emission
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = color
    return mat


def init_materials() -> None:
    specs = {
        "hull_dark": ((0.12, 0.13, 0.15, 1.0), 0.2, 0.6, 0.0),      # 水線上の黒色外板
        "hull_bottom": ((0.55, 0.12, 0.10, 1.0), 0.1, 0.7, 0.0),    # 水線下の赤色船底塗料
        "deck_green": ((0.15, 0.28, 0.18, 1.0), 0.1, 0.7, 0.0),     # 甲板の濃緑色
        "deck_gray": ((0.35, 0.36, 0.38, 1.0), 0.2, 0.6, 0.0),      # 甲板の鋼板色
        "white_structure": ((0.88, 0.89, 0.90, 1.0), 0.0, 0.4, 0.0),# 船橋・白色構造物
        "glass_dark": ((0.08, 0.12, 0.16, 1.0), 0.8, 0.1, 0.0),     # 窓ガラス
        "metal_steel": ((0.65, 0.66, 0.68, 1.0), 0.85, 0.3, 0.0),    # プロペラ・舵・マスト
        "container_blue": ((0.08, 0.22, 0.55, 1.0), 0.2, 0.5, 0.0),
        "container_red": ((0.65, 0.15, 0.12, 1.0), 0.2, 0.5, 0.0),
        "container_green": ((0.12, 0.45, 0.20, 1.0), 0.2, 0.5, 0.0),
        "container_orange": ((0.80, 0.38, 0.08, 1.0), 0.2, 0.5, 0.0),
        "light_white": ((1.0, 1.0, 0.95, 1.0), 0.0, 0.1, 10.0),
        "light_red": ((1.0, 0.1, 0.1, 1.0), 0.0, 0.1, 8.0),
        "light_green": ((0.1, 1.0, 0.2, 1.0), 0.0, 0.1, 8.0),
    }
    for name, (col, metal, rough, emis) in specs.items():
        MATS[name] = make_material(f"ship_{name}", col, metallic=metal, roughness=rough, emission=emis)


def get_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


# --- メッシュ生成ヘルパー -----------------------------------------------------

def obj_from_bmesh(name: str, bm: bmesh.types.BMesh, coll: bpy.types.Collection,
                   mat_name: str, parent: bpy.types.Object = None,
                   loc: Tuple[float, float, float] = (0.0, 0.0, 0.0),
                   **props) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if mat_name in MATS:
        ob.data.materials.append(MATS[mat_name])
    if parent is not None:
        ob.parent = parent
    ob.location = loc
    for k, v in props.items():
        ob[k] = v
    return ob


def make_box(name: str, size: Tuple[float, float, float], loc: Tuple[float, float, float],
             coll: bpy.types.Collection, mat_name: str, parent: bpy.types.Object = None,
             **props) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    return obj_from_bmesh(name, bm, coll, mat_name, parent, loc, **props)


def make_cylinder(name: str, radius: float, depth: float, loc: Tuple[float, float, float],
                  coll: bpy.types.Collection, mat_name: str, axis: str = "Z",
                  parent: bpy.types.Object = None, segments: int = 32, **props) -> bpy.types.Object:
    bm = bmesh.new()
    rot = {"Z": Matrix.Identity(4),
           "Y": Matrix.Rotation(math.pi / 2, 4, "X"),
           "X": Matrix.Rotation(math.pi / 2, 4, "Y")}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius,
                          depth=depth, matrix=rot)
    return obj_from_bmesh(name, bm, coll, mat_name, parent, loc, **props)


def make_empty(name: str, loc: Tuple[float, float, float], coll: bpy.types.Collection,
               parent: bpy.types.Object = None, size: float = 1.0, **props) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "ARROWS"
    ob.empty_display_size = size
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    ob.location = loc
    for k, v in props.items():
        ob[k] = v
    return ob


# --- 船殻（Hull）ロフト生成 ---------------------------------------------------

def build_hull(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> bpy.types.Object:
    """Station 0 (AP) 〜 Station 20 (FP) の21断面からなるロフト船殻を生成する。"""
    dim = cfg["dimensions"]
    hull_cfg = cfg["hull"]

    Lpp = float(dim["length_pp_m"])
    B = float(dim["beam_m"])
    d = float(dim["draft_m"])
    D = float(dim["depth_m"])
    Cb = float(dim["block_coefficient"])

    transom_w_ratio = float(hull_cfg.get("transom_width_ratio", 0.75))
    transom_d_ratio = float(hull_cfg.get("transom_depth_ratio", 0.82))
    sheer_fore = float(hull_cfg.get("sheer_fore_m", 1.8))
    sheer_aft = float(hull_cfg.get("sheer_aft_m", 0.6))
    flare_angle = math.radians(float(hull_cfg.get("flare_angle_deg", 25.0)))

    n_stations = 21  # Station 0..20
    sections = []

    for i in range(n_stations):
        t = i / (n_stations - 1)  # 0.0 (AP) .. 1.0 (FP)
        y = -Lpp / 2.0 + t * Lpp
        xi = (y / (Lpp / 2.0))    # -1.0 .. +1.0

        # 水線面半幅 b(y) の推算 (超楕円曲線補間)
        if xi < 0.0:
            # 船尾部: トランサム幅から平行中体へ
            u = (xi + 1.0)        # 0.0 at AP, 1.0 at Midship
            b_ratio = transom_w_ratio + (1.0 - transom_w_ratio) * (1.0 - (1.0 - u) ** 2.5)
        else:
            # 船首部: 平行中体から船首端へ絞り込み
            u = xi                # 0.0 at Midship, 1.0 at FP
            exponent = 2.0 + 4.0 * Cb
            b_ratio = max(0.02, (1.0 - u ** exponent) ** (1.0 / 2.0))
        b = (B / 2.0) * b_ratio

        # キール深さと甲板高さ
        if xi < 0.0:
            z_keel = -d * (1.0 - (1.0 - transom_d_ratio) * (-xi) ** 2)
            z_deck = (D - d) + sheer_aft * (-xi) ** 1.5
        else:
            z_keel = -d
            z_deck = (D - d) + sheer_fore * (xi) ** 1.8

        # 断面プロファイル点の生成 (左舷側 + 右舷側)
        # キール底 (z_keel) -> ビルジ -> 喫水線 (z=0) -> 甲板 (z_deck)
        # [ (-b, z_deck), (-b, 0), (-0.8b, z_keel), (0, z_keel), (0.8b, z_keel), (b, 0), (b, z_deck) ]
        flare_offset = (z_deck - 0.0) * math.tan(flare_angle) * (max(0.0, xi) ** 2)
        b_deck = b + flare_offset

        pts = [
            (-b_deck, z_deck),
            (-b, 0.0),
            (-b * 0.85, z_keel * 0.92),
            (-b * 0.40, z_keel),
            (0.0, z_keel),
            (b * 0.40, z_keel),
            (b * 0.85, z_keel * 0.92),
            (b, 0.0),
            (b_deck, z_deck),
        ]
        sections.append((y, pts))

    # BMesh によるロフト面の構築
    bm = bmesh.new()
    rings = []
    for y, pts in sections:
        ring = [bm.verts.new((x, y, z)) for x, z in pts]
        rings.append(ring)

    n_pts = len(sections[0][1])
    for s in range(len(rings) - 1):
        r1, r2 = rings[s], rings[s + 1]
        for p in range(n_pts - 1):
            bm.faces.new((r1[p], r1[p + 1], r2[p + 1], r2[p]))

    # 甲板上面 (Deck) を閉じる
    for s in range(len(rings) - 1):
        r1, r2 = rings[s], rings[s + 1]
        bm.faces.new((r1[-1], r1[0], r2[0], r2[-1]))

    # 船尾トランサム端面を閉じる (Station 0)
    bm.faces.new(rings[0])
    # 船首端面を閉じる (Station 20)
    bm.faces.new(list(reversed(rings[-1])))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    hull_obj = obj_from_bmesh("ship_hull", bm, coll, "hull_dark", parent=parent, part_type="hull")

    # バルバスバウ (Bulbous Bow) の追加
    bb_cfg = hull_cfg.get("bulbous_bow", {})
    if bb_cfg.get("enabled", False):
        protrusion = float(bb_cfg.get("protrusion_m", 2.0))
        radius = float(bb_cfg.get("radius_m", 1.2))
        center_z = float(bb_cfg.get("center_z_m", -2.0))
        fp_y = Lpp / 2.0
        bb_loc = (0.0, fp_y + protrusion * 0.5, center_z)
        make_cylinder("bulbous_bow", radius, protrusion, bb_loc, coll, "hull_bottom",
                      axis="Y", parent=hull_obj, part_type="bulbous_bow")

    return hull_obj


# --- 上部構造物・船橋（Superstructure & Bridge） ------------------------------

def build_superstructure(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> bpy.types.Object:
    sup_cfg = cfg.get("superstructure", {})
    if not sup_cfg.get("enabled", True):
        return None

    dim = cfg["dimensions"]
    Lpp = float(dim["length_pp_m"])
    D = float(dim["depth_m"])
    d = float(dim["draft_m"])
    deck_z = D - d

    L_s = float(sup_cfg.get("length_m", 14.0))
    W_s = float(sup_cfg.get("width_m", 12.0))
    H_s = float(sup_cfg.get("height_m", 11.0))
    W_wing = float(sup_cfg.get("bridge_wing_width_m", W_s + 2.0))

    stype = sup_cfg.get("type", "aft_bridge")
    if stype == "aft_bridge":
        y_center = -Lpp * 0.38
    elif stype == "forward_wheelhouse":
        y_center = Lpp * 0.15
    else:
        y_center = 0.0

    # 居住区・船橋基部 (Deckhouse)
    base_loc = (0.0, y_center, deck_z + H_s * 0.45)
    base_obj = make_box("superstructure_base", (W_s, L_s, H_s * 0.9), base_loc, coll,
                        "white_structure", parent=parent, part_type="superstructure")

    # 操舵室ブリッジウイング (Bridge Wing Deck)
    wing_z = deck_z + H_s * 0.88
    wing_loc = (0.0, y_center, wing_z)
    make_box("bridge_wing", (W_wing, L_s * 0.6, H_s * 0.22), wing_loc, coll,
             "white_structure", parent=base_obj, part_type="bridge_wing")

    # 船橋フロント窓 (Glass Windows)
    win_loc = (0.0, y_center + L_s * 0.31, wing_z + 0.3)
    make_box("bridge_windows", (W_s * 0.85, 0.2, H_s * 0.12), win_loc, coll,
             "glass_dark", parent=base_obj, part_type="window")

    # レーダマスト (Radar Mast)
    mast_cfg = sup_cfg.get("mast", {})
    H_m = float(mast_cfg.get("height_m", 8.0))
    mast_loc = (0.0, y_center, deck_z + H_s + H_m * 0.5)
    make_cylinder("mast_main", 0.25, H_m, mast_loc, coll, "metal_steel",
                  axis="Z", parent=base_obj, part_type="mast")

    # 煙突 (Funnel)
    funnel_cfg = sup_cfg.get("funnel", {})
    if funnel_cfg:
        H_f = float(funnel_cfg.get("height_m", 4.0))
        D_f = float(funnel_cfg.get("diameter_m", 1.8))
        f_pos = funnel_cfg.get("pos_m", [0.0, y_center - L_s * 0.4, deck_z + H_s + H_f * 0.5])
        make_cylinder("funnel", D_f * 0.5, H_f, tuple(f_pos), coll, "white_structure",
                      axis="Z", parent=base_obj, part_type="funnel")

    return base_obj


# --- 貨物・コンテナベイ（Cargo / Containers） ----------------------------------

def build_cargo(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> None:
    cargo_cfg = cfg.get("hull", {}).get("cargo_hold", {})
    ctype = cargo_cfg.get("type", "")
    if ctype != "container_bays":
        return

    dim = cfg["dimensions"]
    Lpp = float(dim["length_pp_m"])
    D = float(dim["depth_m"])
    d = float(dim["draft_m"])
    B = float(dim["beam_m"])
    deck_z = D - d

    bays = int(cargo_cfg.get("bays", 4))
    stacks = int(cargo_cfg.get("stacks", 5))
    tiers = int(cargo_cfg.get("tiers", 3))

    c_len = 6.06   # 20ft コンテナ長 [m]
    c_w = 2.44     # コンテナ幅 [m]
    c_h = 2.59     # コンテナ高 [m]

    container_colors = ["container_blue", "container_red", "container_green", "container_orange"]
    start_y = -Lpp * 0.20
    spacing_y = c_len + 0.8
    spacing_x = c_w + 0.3

    for bay in range(bays):
        by = start_y + bay * spacing_y
        for st in range(stacks):
            bx = (st - (stacks - 1) / 2.0) * spacing_x
            # 船幅に収まるかチェック
            if abs(bx) + c_w * 0.5 > B * 0.45:
                continue
            for tr in range(tiers):
                bz = deck_z + tr * c_h + c_h * 0.5
                mat_idx = (bay * 7 + st * 3 + tr) % len(container_colors)
                make_box(f"container_b{bay}_s{st}_t{tr}", (c_w, c_len, c_h), (bx, by, bz),
                         coll, container_colors[mat_idx], parent=parent, part_type="cargo_container")


# --- アクチュエータ（Actuators: プロペラ・舵・レーダ） ------------------------

def build_actuators(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> None:
    act_cfg = cfg.get("actuators", {})

    # 1. プロペラ (Propellers: 回転関節 spin, ローカルY軸)
    for p in act_cfg.get("propellers", []):
        pid = p["id"]
        dia = float(p.get("diameter_m", 3.0))
        pos = tuple(p.get("shaft_pos_m", [0.0, -40.0, -2.0]))
        # プロペラハブ (Empty またはシリンダ)
        hub = make_cylinder(f"propeller_{pid}", dia * 0.15, dia * 0.25, pos, coll,
                            "metal_steel", axis="Y", parent=parent,
                            joint_type="spin", joint_axis=[0.0, 1.0, 0.0],
                            part_type="propeller", propeller_dia_m=dia)
        # プロペラブレード (4枚)
        n_blades = int(p.get("blades", 4))
        for b in range(n_blades):
            ang = 2.0 * math.pi * b / n_blades
            bx = (dia * 0.35) * math.sin(ang)
            bz = (dia * 0.35) * math.cos(ang)
            blade = make_box(f"propeller_{pid}_b{b}", (dia * 0.15, 0.06, dia * 0.45),
                             (bx, 0.0, bz), coll, "metal_steel", parent=hub, part_type="blade")
            blade.rotation_euler = (ang, 0.2, 0.0)

    # 2. 舵 (Rudders: 操舵関節 hinge, ローカルZ軸)
    for r in act_cfg.get("rudders", []):
        rid = r["id"]
        area = float(r.get("area_m2", 7.0))
        ar = float(r.get("aspect_ratio", 1.6))
        pos = tuple(r.get("pos_m", [0.0, -43.0, -2.0]))
        h_rudder = (area * ar) ** 0.5
        chord = area / h_rudder
        rudder_obj = make_box(f"rudder_{rid}", (0.25, chord, h_rudder), pos, coll,
                              "metal_steel", parent=parent,
                              joint_type="hinge", joint_axis=[0.0, 0.0, 1.0],
                              part_type="rudder", rudder_area_m2=area)

    # 3. レーダマスト回転アンテナ (Radar Antenna spin)
    for m in cfg.get("mounts", []):
        if m.get("type") == "marine_radar":
            mid = m["id"]
            pos = tuple(m.get("pos_m", [0.0, -35.0, 20.0]))
            # 2.4m のスキャナバー
            make_box(f"radar_mast_{mid}", (2.4, 0.22, 0.28), pos, coll,
                     "white_structure", parent=parent,
                     joint_type="spin", joint_axis=[0.0, 0.0, 1.0],
                     part_type="radar_antenna")


# --- 40点浮力計算サイト（BUOYANCY_SITES） --------------------------------------

def build_buoyancy_sites(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> List[dict]:
    """船長方向20ステーション × 左右舷 = 40点の水面標高計測サイトを生成する。"""
    dim = cfg["dimensions"]
    Lpp = float(dim["length_pp_m"])
    B = float(dim["beam_m"])
    d = float(dim["draft_m"])

    b_cfg = cfg.get("buoyancy", {})
    n_st = int(b_cfg.get("stations_count", 20))
    offset_ratio = float(b_cfg.get("transverse_offset_ratio", 0.70))

    sites = []
    dx = Lpp / n_st

    for i in range(n_st):
        y = -Lpp / 2.0 + (i + 0.5) * dx
        xi = y / (Lpp / 2.0)
        # ステーション局所半幅
        b_st = (B / 2.0) * max(0.15, (1.0 - abs(xi) ** 2.2) ** 0.5)
        transverse_dist = b_st * offset_ratio

        # 左舷 (Port: -X Blender, +Y FLU)
        port_name = f"buoyancy_st{i:02d}_port"
        port_pos = (-transverse_dist, y, 0.0)
        make_empty(port_name, port_pos, coll, parent=parent, size=0.8,
                   station_idx=i, side="port", baseline_z=-d, part_type="buoyancy_site")
        sites.append({"name": port_name, "station": i, "side": "port", "pos": port_pos})

        # 右舷 (Starboard: +X Blender, -Y FLU)
        stbd_name = f"buoyancy_st{i:02d}_stbd"
        stbd_pos = (transverse_dist, y, 0.0)
        make_empty(stbd_name, stbd_pos, coll, parent=parent, size=0.8,
                   station_idx=i, side="stbd", baseline_z=-d, part_type="buoyancy_site")
        sites.append({"name": stbd_name, "station": i, "side": "stbd", "pos": stbd_pos})

    return sites


# --- 当たり判定（COLLISION）と RCS 属性 ----------------------------------------

def build_collision(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> None:
    dim = cfg["dimensions"]
    Lpp = float(dim["length_pp_m"])
    B = float(dim["beam_m"])
    D = float(dim["depth_m"])
    d = float(dim["draft_m"])
    total_rcs = float(cfg.get("signatures", {}).get("radar_cross_section_m2", 2500.0))

    # 1. 主船体コライダ (中前部)
    hull_box = make_box("collision_hull_main", (B * 0.95, Lpp * 0.65, D),
                        (0.0, 0.0, (D - 2.0 * d) * 0.5), coll, "hull_dark",
                        parent=parent, part_type="collision",
                        rcs_sigma=total_rcs * 0.45)
    hull_box.display_type = "WIRE"

    # 2. 船首部コライダ
    bow_box = make_box("collision_hull_bow", (B * 0.70, Lpp * 0.25, D * 1.1),
                       (0.0, Lpp * 0.38, (D - 2.0 * d) * 0.5), coll, "hull_dark",
                       parent=parent, part_type="collision",
                       rcs_sigma=total_rcs * 0.20)
    bow_box.display_type = "WIRE"

    # 3. 船尾・上部構造物コライダ
    sup = cfg.get("superstructure", {})
    if sup.get("enabled", True):
        L_s = float(sup.get("length_m", 14.0))
        W_s = float(sup.get("width_m", 12.0))
        H_s = float(sup.get("height_m", 11.0))
        y_c = -Lpp * 0.38 if sup.get("type") == "aft_bridge" else 0.0
        bridge_box = make_box("collision_superstructure", (W_s, L_s, H_s),
                              (0.0, y_c, (D - d) + H_s * 0.5), coll, "white_structure",
                              parent=parent, part_type="collision",
                              rcs_sigma=total_rcs * 0.35)
        bridge_box.display_type = "WIRE"


# --- センサマウント（MOUNTS）＆ 航海灯（NAV_LIGHTS） ---------------------------

def build_mounts_and_lights(cfg: dict, coll_mount: bpy.types.Collection,
                            coll_light: bpy.types.Collection, parent: bpy.types.Object) -> None:
    # センサマウント
    for m in cfg.get("mounts", []):
        mid = m["id"]
        mtype = m.get("type", "sensor")
        pos = tuple(m.get("pos_m", [0.0, 0.0, 0.0]))
        make_empty(f"mount_{mid}", pos, coll_mount, parent=parent, size=0.6,
                   mount_type=mtype, part_type="mount")

    # 航海灯
    light_mat_map = {"white": "light_white", "red": "light_red", "green": "light_green"}
    for l in cfg.get("nav_lights", []):
        lid = l["id"]
        col = l.get("color", "white")
        pos = tuple(l.get("pos_m", [0.0, 0.0, 0.0]))
        mat = light_mat_map.get(col, "light_white")
        make_cylinder(f"navlight_{lid}", 0.12, 0.20, pos, coll_light, mat, axis="Z",
                      parent=parent, part_type="nav_light", light_color=col,
                      arc_deg=float(l.get("arc_deg", 225.0)))


# --- 6方向レンダリング --------------------------------------------------------

def render_views(root_obj: bpy.types.Object, out_dir: Path, resolution: int = 800) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    renders_dir = out_dir / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = "PNG"

    # カメラコレクション
    cams_coll = get_collection("Cameras")
    cam_data = bpy.data.cameras.new("OrthoCam")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("Camera_Ortho", cam_data)
    cams_coll.objects.link(cam_obj)
    scene.camera = cam_obj

    # バウンディングボックス計測
    dim = root_obj.dimensions
    max_dim = max(dim.x, dim.y, dim.z, 20.0)
    cam_data.ortho_scale = max_dim * 1.25

    views = {
        "front": (Vector((0.0, max_dim * 2.0, 0.0)), Vector((math.pi / 2, 0.0, math.pi))),
        "back": (Vector((0.0, -max_dim * 2.0, 0.0)), Vector((math.pi / 2, 0.0, 0.0))),
        "port": (Vector((-max_dim * 2.0, 0.0, 0.0)), Vector((math.pi / 2, 0.0, -math.pi / 2))),
        "starboard": (Vector((max_dim * 2.0, 0.0, 0.0)), Vector((math.pi / 2, 0.0, math.pi / 2))),
        "top": (Vector((0.0, 0.0, max_dim * 2.0)), Vector((0.0, 0.0, 0.0))),
        "iso": (Vector((max_dim * 1.5, -max_dim * 1.5, max_dim * 1.2)), Vector((math.radians(60), 0.0, math.radians(45)))),
    }

    results = {}
    for name, (loc, rot) in views.items():
        cam_obj.location = loc
        cam_obj.rotation_euler = rot
        img_path = renders_dir / f"{name}.png"
        scene.render.filepath = str(img_path)
        bpy.ops.render.render(write_still=True)
        results[name] = str(img_path)

    return results


# --- メイン実行 ---------------------------------------------------------------

def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config_json)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    subject = cfg.get("template_id", "vessel")
    out_dir = cfg_path.parent

    setup_scene()
    init_materials()

    # コレクション階層の作成
    coll_hull = get_collection("Hull")
    coll_sup = get_collection("Superstructure")
    coll_cargo = get_collection("Cargo")
    coll_act = get_collection("Actuators")
    coll_buoy = get_collection("BUOYANCY_SITES")
    coll_coll = get_collection("COLLISION")
    coll_mount = get_collection("MOUNTS")
    coll_light = get_collection("NAV_LIGHTS")

    # ルートオブジェクト (水線面 z=0, 船体中央 y=0)
    root = make_empty(subject, (0.0, 0.0, 0.0), bpy.context.scene.collection,
                      part_type="root", vehicle_type="vessel", subject_id=subject)

    # 各コンポーネントの構築
    build_hull(cfg, coll_hull, root)
    build_superstructure(cfg, coll_sup, root)
    build_cargo(cfg, coll_cargo, root)
    build_actuators(cfg, coll_act, root)
    buoy_sites = build_buoyancy_sites(cfg, coll_buoy, root)
    build_collision(cfg, coll_coll, root)
    build_mounts_and_lights(cfg, coll_mount, coll_light, root)

    # .blend の保存
    blend_path = out_dir / f"{subject}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # .glb のエクスポート
    glb_path = out_dir / f"{subject}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB",
                             use_selection=False, export_cameras=False)

    # 6方向レンダリング
    renders = render_views(root, out_dir)

    # build_report.json の生成
    report = {
        "subject": subject,
        "blend_file": str(blend_path),
        "glb_file": str(glb_path),
        "renders": renders,
        "buoyancy_sites_count": len(buoy_sites),
        "total_objects": len(bpy.data.objects),
        "total_meshes": len(bpy.data.meshes),
    }
    report_path = out_dir / "build_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"[build_ship.py] Successfully built {subject}: {blend_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
