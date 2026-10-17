"""パラメトリックローバモデルを Blender で組み立てる（vehicle_type: rover）。

scripts/rover_model/run_build.py から呼ばれる:
    blender --background --factory-startup --python blender/rover_model/build_rover.py -- --config-json <resolved.json>

出力: .blend / .glb / 6 方向レンダ / build_report.json

階層（GLB でもこのまま。各ノードは読込先で動かせる）:
    <subject_id>（ルート・地面の高さ）
    ├─ body_*（車体の各部品）、equip_*（装備）
    ├─ susp_<軸><左右>（懸架の関節の印・slide z）
    │   └─ steer_<軸><左右>（操舵の関節の印・hinge z。操舵しない軸は無い）
    │       └─ wheel_<軸><左右>（車輪・hinge x。タイヤ・ハブ・スポークを子に持つ）
    ├─ deploy_*（動く外装：太陽電池パネル・パラボラ・階段）
    └─ mount_*（取付点：カメラ・ライダ・太陽センサ・IMU）
関節の種類・軸はカスタムプロパティ joint_type / joint_axis に書く（blend2mjcf_rover.py が読む）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "blender" / "drone_model"))
from build_drone import look_at, make_material, mesh_objects, world_bounds  # noqa: E402


def mm(v: float) -> float:
    return float(v) / 1000.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--config-json", required=True)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return p.parse_args(argv)


# --- シーン・コレクション・マテリアル ---------------------------------------------

def setup_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.world = bpy.data.worlds.new("RoverWorld")
    scene.world.color = (0.05, 0.05, 0.06)


def collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


MATS: dict[str, bpy.types.Material] = {}


def init_materials() -> None:
    spec = {
        "white": ((0.86, 0.87, 0.88, 1.0), 0.0, 0.45),
        "panel_gray": ((0.62, 0.63, 0.64, 1.0), 0.2, 0.5),
        "dark": ((0.16, 0.16, 0.17, 1.0), 0.3, 0.6),
        "metal": ((0.70, 0.71, 0.73, 1.0), 0.9, 0.25),
        "tire": ((0.10, 0.10, 0.11, 1.0), 0.4, 0.7),
        "glass": ((0.22, 0.16, 0.09, 1.0), 0.0, 0.08),
        "solar": ((0.30, 0.06, 0.05, 1.0), 0.2, 0.3),
        "dish": ((0.90, 0.90, 0.90, 1.0), 0.1, 0.4),
    }
    for name, (col, metal, rough) in spec.items():
        MATS[name] = make_material(f"rover_{name}", col, metallic=metal, roughness=rough)
    MATS["light"] = make_material("rover_light", (1.0, 1.0, 0.97, 1.0), emission_color=(1.0, 1.0, 0.95, 1.0),
                                  emission_strength=5.0)


# --- メッシュの部品 ---------------------------------------------------------------

def _obj_from_bm(name: str, bm: bmesh.types.BMesh, coll, mat: str, parent=None,
                 loc=(0.0, 0.0, 0.0), part_type: str = "") -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.data.materials.append(MATS[mat])
    if parent is not None:
        ob.parent = parent
    ob.location = loc
    if part_type:
        ob["part_type"] = part_type
    return ob


def box(name, size, loc, coll, mat, parent=None, bevel=0.0, part_type="") -> bpy.types.Object:
    """size = (x, y, z) の全長 [m]。loc は中心。"""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(bevel, min(size) * 0.45), segments=3,
                        affect="EDGES", profile=0.5)
    return _obj_from_bm(name, bm, coll, mat, parent, loc, part_type)


def cylinder(name, radius, depth, loc, coll, mat, axis="Z", parent=None, segments=40, part_type="",
             radius_top=None) -> bpy.types.Object:
    bm = bmesh.new()
    rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
           "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius,
                          radius2=radius if radius_top is None else radius_top, depth=depth, matrix=rot)
    return _obj_from_bm(name, bm, coll, mat, parent, loc, part_type)


def empty(name, loc, coll, parent=None, size=0.15, **props) -> bpy.types.Object:
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


def render_views(visual, cams, out_dir: Path, resolution: int) -> dict[str, str]:
    """6 方向の正投影レンダ（ローバは +Y が前）。"""
    lo, hi = world_bounds(mesh_objects(visual))
    center = (lo + hi) / 2.0
    longest = max(hi - lo)
    dirs = {"front": Vector((0, 1, 0)), "back": Vector((0, -1, 0)), "left": Vector((-1, 0, 0)),
            "right": Vector((1, 0, 0)), "top": Vector((0, 0, 1)), "bottom": Vector((0, 0, -1))}
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = "PNG"
    (out_dir / "renders").mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, d in dirs.items():
        cd = bpy.data.cameras.new(f"camera_{name}_data")
        cd.type = "ORTHO"
        cd.ortho_scale = longest * 1.12
        cam = bpy.data.objects.new(f"camera_{name}", cd)
        cams.objects.link(cam)
        cam.location = center + d * longest * 4.0
        look_at(cam, center)
        if name in ("top", "bottom"):
            cam.rotation_euler = (Vector((0, 0, 0)) if name == "top" else Vector((math.pi, 0, 0)))
        scene.camera = cam
        path = out_dir / "renders" / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs[name] = str(path)
    return outputs


def render_comparison(visual, cams, out_dir: Path, views: list[dict]) -> dict[str, str]:
    """公式 CG に近い向き・画角の透視レンダ（形の目視比較用）。
    azimuth_deg：前（+Y）から左（−X）へ測った方位（例：65 = 左前方、140 = 左後方）、elevation_deg：仰角、hfov_deg：水平画角。"""
    lo, hi = world_bounds(mesh_objects(visual))
    center = (lo + hi) / 2.0
    size = max(hi - lo)
    scene = bpy.context.scene
    outputs = {}
    for v in views:
        scene.render.resolution_x, scene.render.resolution_y = int(v.get("width", 1600)), int(v.get("height", 900))
        az, el = math.radians(v["azimuth_deg"]), math.radians(v["elevation_deg"])
        hfov = math.radians(v["hfov_deg"])
        d = Vector((-math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
        dist = size * float(v.get("fill", 0.62)) ** -1 / 2.0 / math.tan(hfov / 2.0)
        cd = bpy.data.cameras.new(f"cmp_{v['name']}_data")
        cd.sensor_fit = "HORIZONTAL"
        cd.angle = hfov
        cam = bpy.data.objects.new(f"cmp_{v['name']}", cd)
        cams.objects.link(cam)
        target = center + Vector((0, 0, float(v.get("target_dz_m", 0.0))))
        cam.location = target + d * dist
        look_at(cam, target)
        scene.camera = cam
        path = out_dir / "renders" / f"cmp_{v['name']}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs[v["name"]] = str(path)
    return outputs


# --- 車輪 -------------------------------------------------------------------------

def build_wheel(name: str, cfg: dict, coll, parent, outer_sign: float) -> bpy.types.Object:
    """車輪 1 つ。原点は車輪の中心、回転軸はローカル X。outer_sign は外側（+X / −X）。"""
    w = cfg["wheels"]
    t = w["tire"]
    r, b = mm(w["radius_mm"]), mm(w["width_mm"])
    gh = mm(t["tread_height_mm"])
    # タイヤの芯（トレッドの下）
    tire = cylinder(name, r - gh, b, (0, 0, 0), coll, "tire", axis="X", parent=parent, segments=48,
                    part_type="wheel")
    # 分割トレッド（ブロックを 1 つのメッシュに）
    bm = bmesh.new()
    n = int(t["tread_blocks"])
    arc = 2 * math.pi * r / n * float(t["tread_fill"])
    for i in range(n):
        a = 2 * math.pi * i / n
        m = Matrix.Rotation(a, 4, "X") @ Matrix.Translation((0, 0, r - gh / 2)) @ \
            Matrix.Diagonal((b * 0.96, arc, gh, 1.0))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    _obj_from_bm(f"{name}_tread", bm, coll, "tire", tire, part_type="tread")
    # 外側の面：金属のリング・ハブ・スポーク
    face_x = outer_sign * (b / 2 + 0.004)
    ring = cylinder(f"{name}_rim", r * 0.97, 0.02, (face_x, 0, 0), coll, "metal", axis="X", parent=tire,
                    part_type="rim")
    ring["radius_ratio"] = float(t["rim_radius_ratio"])
    disc = cylinder(f"{name}_face", r * float(t["rim_radius_ratio"]), 0.024, (face_x * 1.02, 0, 0), coll, "dark",
                    axis="X", parent=tire, part_type="wheel_face")
    hub_r = r * float(t["hub_radius_ratio"])
    cylinder(f"{name}_hub", hub_r * 0.55, 0.14, (face_x + outer_sign * 0.07, 0, 0), coll, "metal", axis="X",
             parent=tire, part_type="hub")
    bm = bmesh.new()
    k = int(t["spokes"])
    for i in range(k):
        a = 2 * math.pi * i / k
        span = r * float(t["rim_radius_ratio"]) - hub_r
        m = Matrix.Rotation(a, 4, "X") @ Matrix.Translation((0, 0, hub_r + span / 2)) @ \
            Matrix.Diagonal((0.02, 0.035, span, 1.0))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    _obj_from_bm(f"{name}_spokes", bm, coll, "metal", disc, loc=(outer_sign * 0.015, 0, 0), part_type="spokes")
    tire["joint_type"] = "hinge"
    tire["joint_axis"] = [1.0, 0.0, 0.0]
    tire["radius_mm"] = float(w["radius_mm"])
    tire["width_mm"] = float(w["width_mm"])
    return tire


# --- 車体 -------------------------------------------------------------------------

def build_body(cfg: dict, coll, coll_col, root) -> dict[str, Any]:
    bd = cfg["body"]
    L, W = mm(bd["length_mm"]), mm(bd["width_mm"])
    tub, band, up, nose = bd["tub"], bd["side_band"], bd["upper"], bd["nose"]
    z_tb, z_tt = mm(tub["z_bottom_mm"]), mm(tub["z_top_mm"])
    z_bb, z_bt = mm(band["z_bottom_mm"]), mm(band["z_top_mm"])
    z_top = mm(up["z_top_mm"])
    bev = mm(up["roof_bevel_mm"])

    # 下部の胴（車輪の間）
    tub_len = L * float(tub["length_ratio"])
    box("body_tub", (mm(tub["width_mm"]), tub_len, z_tt - z_tb), (0, 0, (z_tb + z_tt) / 2), coll, "dark",
        root, bevel=0.05, part_type="body_tub")
    # 側面の帯（全幅・収納した太陽電池パネルの高さ）
    box("body_side_band", (W * 0.98, L * 0.94, z_bt - z_bb), (0, -L * 0.02, (z_bb + z_bt) / 2), coll,
        "panel_gray", root, bevel=0.04, part_type="body_side_band")
    # 上部：前の白いキャビンと後ろの荷室の箱
    cab_len = L * float(up["cabin_length_ratio"])
    box_len = L - cab_len
    cab_y = L / 2 - cab_len / 2
    box_y = -L / 2 + box_len / 2
    box("body_cabin", (W, cab_len, z_top - 0.08 - z_bt), (0, cab_y, (z_bt + z_top - 0.08) / 2), coll, "white",
        root, bevel=bev, part_type="body_cabin")
    box("body_cargo", (W * 0.96, box_len, z_top - z_bt), (0, box_y, (z_bt + z_top) / 2), coll, "panel_gray",
        root, bevel=bev * 0.6, part_type="body_cargo")
    # 前面の張り出し（中央のバンパー）
    zb0, zb1 = (mm(v) for v in nose["bumper_z_mm"])
    pr = mm(nose["bumper_protrusion_mm"])
    box("body_bumper", (W * float(nose["bumper_width_ratio"]), pr + 0.3, zb1 - zb0),
        (0, L / 2 + pr / 2 - 0.15, (zb0 + zb1) / 2), coll, "white", root, bevel=0.05, part_type="body_bumper")
    # 前輪の上の張り出し（左右）
    fp = bd["fender_pods"]
    front_y = max(a["y_mm"] for a in cfg["wheels"]["axles"])
    for side, sx in (("L", -1.0), ("R", 1.0)):
        box(f"body_fender_{side}", (0.55, mm(fp["length_mm"]), mm(fp["height_mm"])),
            (sx * (W / 2 - 0.2), mm(front_y) + 0.15, mm(fp["z_bottom_mm"]) + mm(fp["height_mm"]) / 2),
            coll, "metal", root, bevel=0.06, part_type="body_fender")
    # 当たり判定（簡単な箱。GLB には出さない）
    box("collision_tub", (mm(tub["width_mm"]), tub_len, z_tt - z_tb), (0, 0, (z_tb + z_tt) / 2), coll_col,
        "dark", root, part_type="collision")
    box("collision_upper", (W, L, z_top - z_bb), (0, 0, (z_bb + z_top) / 2), coll_col, "dark", root,
        part_type="collision")
    return {"L": L, "W": W, "z_top": z_top, "z_bt": z_bt, "cab_y": cab_y, "cab_len": cab_len}


def build_equipment(cfg: dict, geo: dict, coll, root) -> None:
    eq = cfg["equipment"]
    L, W, z_top = geo["L"], geo["W"], geo["z_top"]
    front = L / 2
    # 前の窓（2 段 × 2 枚）
    win = eq["windows"]
    z0, z1 = (mm(v) for v in win["z_mm"])
    rows, cols = int(win["rows"]), int(win["cols"])
    ww = W * float(win["width_ratio"])
    for i in range(rows):
        for j in range(cols):
            h = (z1 - z0) / rows
            w = ww / cols
            box(f"equip_window_{i}{j}", (w * 0.94, 0.04, h * 0.86),
                (-ww / 2 + w * (j + 0.5), front + 0.005, z0 + h * (i + 0.5)), coll, "glass", root,
                part_type="window")
    # 前照灯（上段 左右 3 灯ずつ・下段 2 灯）
    hu = eq["headlights_upper"]
    for side, sx in (("L", -1.0), ("R", 1.0)):
        for k in range(int(hu["count_per_side"])):
            x = sx * (W / 2 - 0.35 - k * 0.42)
            cylinder(f"equip_headlight_{side}{k}", mm(hu["radius_mm"]), 0.2, (x, front + 0.08, mm(hu["z_mm"])),
                     coll, "light", axis="Y", parent=root, segments=24, part_type="headlight")
    hl = eq["headlights_lower"]
    for k, sx in enumerate((-1.0, 1.0)):
        cylinder(f"equip_lowlight_{k}", mm(hl["radius_mm"]), 0.12,
                 (sx * W * 0.22, front + mm(cfg["body"]["nose"]["bumper_protrusion_mm"]) + 0.02, mm(hl["z_mm"])),
                 coll, "light", axis="Y", parent=root, segments=20, part_type="headlight")
    # 屋根：センサ筐体・パラボラ（展開物として関節つき）・排熱の筒・ホイップアンテナ
    box("equip_roof_sensor_housing", (1.1, 0.7, 0.28), (0, geo["cab_y"] + 0.2, z_top + 0.06), coll, "white",
        root, bevel=0.06, part_type="sensor_housing")
    for k, st in enumerate(eq["roof_stacks"]):
        cylinder(f"equip_stack_{k}", mm(st["radius_mm"]), mm(st["height_mm"]),
                 (mm(st["x_mm"]), L / 2 * float(st["y_ratio"]), z_top + mm(st["height_mm"]) / 2), coll, "white",
                 parent=root, segments=24, part_type="stack")
    for k, an in enumerate(eq["whip_antennas"]):
        cylinder(f"equip_whip_{k}", 0.02, mm(an["height_mm"]),
                 (mm(an["x_mm"]), L / 2 * float(an["y_ratio"]), z_top + mm(an["height_mm"]) / 2 - 0.25),
                 coll, "metal", parent=root, segments=12, part_type="antenna")
    # 後面：ハッチの枠・デッキ
    hat = eq["rear_hatch"]
    box("equip_rear_hatch", (mm(hat["width_mm"]), 0.12, mm(hat["height_mm"])),
        (0, -L / 2 - 0.05, mm(hat["z_bottom_mm"]) + mm(hat["height_mm"]) / 2), coll, "metal", root, bevel=0.08,
        part_type="hatch")
    dk = eq["rear_deck"]
    box("equip_rear_deck", (W * 0.7, mm(dk["depth_mm"]), 0.06), (0, -L / 2 - mm(dk["depth_mm"]) / 2,
                                                                  mm(dk["z_mm"])), coll, "metal", root,
        part_type="deck")


def build_deployables(cfg: dict, geo: dict, coll, root) -> list[dict]:
    out = []
    L, W, z_bt = geo["L"], geo["W"], geo["z_bt"]
    band = cfg["body"]["side_band"]
    zb, zt = mm(band["z_bottom_mm"]), mm(band["z_top_mm"])
    for d in cfg.get("deployables", []):
        did = d["id"]
        if d["type"] == "panel":
            sx = -1.0 if d.get("side") == "L" else 1.0
            node = empty(f"deploy_{did}", (sx * (W / 2 + 0.02), -L * 0.02, zb), coll, root,
                         joint_type="slide", joint_axis=[0.0, 0.0, 1.0], stroke_mm=float(d.get("stroke_mm", 0.0)),
                         part_type="deployable")
            box(f"{did}_panel", (0.04, L * 0.8, zt - zb), (0, 0, (zt - zb) / 2), coll, "solar", node,
                part_type="solar_panel")
        elif d["type"] == "antenna":
            eq = cfg["equipment"]["roof_dish"]
            y = L / 2 * float(eq["y_ratio"])
            node = empty(f"deploy_{did}", (0, y, geo["z_top"]), coll, root, joint_type="hinge",
                         joint_axis=[0.0, 0.0, 1.0], part_type="deployable")
            cylinder(f"{did}_mast", 0.07, mm(eq["mast_height_mm"]), (0, 0, mm(eq["mast_height_mm"]) / 2), coll,
                     "white", parent=node, segments=16, part_type="mast")
            dish = cylinder(f"{did}_dish", mm(eq["diameter_mm"]) / 2, 0.12,
                            (0, 0.15, mm(eq["mast_height_mm"]) + mm(eq["diameter_mm"]) / 2), coll, "dish",
                            axis="Y", parent=node, segments=36, part_type="dish", radius_top=0.06)
            dish.rotation_euler = Euler((math.radians(-15), 0, 0))
        elif d["type"] == "stairs":
            st = cfg["equipment"]["rear_stairs"]
            dk = cfg["equipment"]["rear_deck"]
            node = empty(f"deploy_{did}", (0, -L / 2 - mm(dk["depth_mm"]), mm(dk["z_mm"])), coll, root,
                         joint_type="hinge", joint_axis=[1.0, 0.0, 0.0], part_type="deployable")
            n = int(st["steps"])
            for k in range(n):
                z = -(k + 1) * mm(dk["z_mm"]) / (n + 1)
                box(f"{did}_step{k}", (mm(st["width_mm"]), 0.28, 0.04), (0, -mm(st.get("pitch_mm", 220.0)) * (k + 1), z), coll, "metal", node,
                    part_type="step")
        else:
            continue
        out.append({"id": did, "type": d["type"], "joint": d.get("joint", "")})
    return out


def main() -> int:
    args = parse_args()
    cfg = json.loads(Path(args.config_json).read_text(encoding="utf-8"))
    out_cfg = cfg["output"]
    out_dir = Path(out_cfg["directory"])
    setup_scene()
    init_materials()
    visual = collection("VISUAL")
    joints = collection("JOINTS")
    mounts_c = collection("MOUNTS")
    coll_col = collection("COLLISION")
    cams = collection("CAMERAS")
    coll_col.hide_render = True

    root = empty(cfg["subject_id"], (0, 0, 0), joints, size=0.5, part_type="root")
    root["vehicle_type"] = "rover"
    root["front_axis"] = cfg["coordinate_system"]["front_axis"]
    root["up_axis"] = cfg["coordinate_system"]["up_axis"]
    root["dimensions_provisional"] = bool(cfg.get("dimensions_provisional", True))

    geo = build_body(cfg, visual, coll_col, root)
    build_equipment(cfg, geo, visual, root)

    w = cfg["wheels"]
    r = mm(w["radius_mm"])
    half_track = mm(w["track_mm"]) / 2
    wheels_report = []
    for ax in w["axles"]:
        for side, sx in (("L", -1.0), ("R", 1.0)):
            wid = f"{ax['id']}{side}"
            loc = (sx * half_track, mm(ax["y_mm"]), r)
            susp = empty(f"susp_{wid}", loc, joints, root, joint_type="slide", joint_axis=[0.0, 0.0, 1.0],
                         travel_mm=float(w["suspension"]["travel_mm"]), part_type="suspension")
            parent = susp
            if ax.get("steer"):
                parent = empty(f"steer_{wid}", (0, 0, 0), joints, susp, joint_type="hinge",
                               joint_axis=[0.0, 0.0, 1.0], part_type="steering")
            tire = build_wheel(f"wheel_{wid}", cfg, visual, parent, outer_sign=sx)
            cylinder(f"collision_wheel_{wid}", r, mm(w["width_mm"]), (0, 0, 0), coll_col, "tire", axis="X",
                     parent=tire, segments=24, part_type="collision")
            wheels_report.append({"id": wid, "location_mm": [round(v * 1000.0, 1) for v in loc],
                                  "steer": bool(ax.get("steer")), "outer_sign": sx})

    deploy_report = build_deployables(cfg, geo, visual, root)

    mounts_report = []
    for m in cfg.get("mounts", []):
        loc = tuple(mm(v) for v in m["location_mm"])
        ob = empty(f"mount_{m['id']}", loc, mounts_c, root, size=0.25, part_type="mount", mount_type=m["type"])
        if "euler_deg" in m:
            ob.rotation_euler = Euler(tuple(math.radians(v) for v in m["euler_deg"]))
        for k in ("hfov_deg",):
            if k in m:
                ob[k] = float(m[k])
        mounts_report.append({"id": m["id"], "type": m["type"], "location_mm": m["location_mm"]})

    bpy.context.view_layer.update()
    vis_objs = mesh_objects(visual)
    lo, hi = world_bounds(vis_objs)
    body_objs = [o for o in vis_objs if o.name.startswith("body_")]
    blo, bhi = world_bounds(body_objs)
    renders = render_views(visual, cams, out_dir, int(out_cfg.get("render_resolution", 900)))
    renders.update(render_comparison(visual, cams, out_dir, out_cfg.get("comparison_views", [])))

    out_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for c in (visual, joints, mounts_c):
        for ob in c.all_objects:
            ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out_dir / out_cfg["glb"]), export_format="GLB", use_selection=True,
                              export_extras=True, export_cameras=False, export_lights=False, export_apply=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_dir / out_cfg["blend"]))

    report = {
        "subject_id": cfg["subject_id"],
        "bounds_all_mm": {"min": [round(v * 1000, 1) for v in lo], "max": [round(v * 1000, 1) for v in hi]},
        "bounds_body_mm": {"min": [round(v * 1000, 1) for v in blo], "max": [round(v * 1000, 1) for v in bhi]},
        "wheels": wheels_report,
        "deployables": deploy_report,
        "mounts": mounts_report,
        "object_count": len(bpy.data.objects),
        "mesh_count": len(vis_objs),
        "renders": renders,
    }
    (out_dir / out_cfg["build_report"]).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[build_rover] done", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
