"""build_ship.py - パラメトリック船舶モデルを Blender 5.2 で自動生成する。

実行方法:
    blender --background --factory-startup --python blender/ship_model/build_ship.py -- --config-json <resolved.json>

出力:
    - <subject>.blend (Blender シーン正本)
    - <subject>.glb (描画用 glTF 2.0。COLLISION の箱は物理専用なので含めない)
    - renders/*.png (6方向正投影 ＋ 斜め俯瞰 hero / 水面付き hero_water)
    - build_report.json (検証レポート)

階層構造（ルート直下。ビューアの関節同期は rudder_* / propeller_* / radar_mast_* の名前・原点・無回転を前提とする）:
    <subject_id> (ルート: 水線面 z=0, 船体中央 y=0)
    ├─ hull            船殻（hull_form.py の断面ロフト、塗装の境界で分割）＋ バルバスバウ・スケグ・スラスタ口
    ├─ deck_fittings   ブルワーク・手すり・係船設備・ハッチカバー
    ├─ superstructure  居住区・船橋・窓・煙突・マスト・レーダ台座（種類: aft_bridge / passenger_decks / forward_wheelhouse）
    ├─ cargo           コンテナ（40 ft）
    ├─ rudder_<id>     舵（翼形断面、原点 = 舵軸、Z まわり hinge）
    ├─ propeller_<id>  プロペラ（ボス＋翼、原点 = 軸心、Y まわり spin）
    ├─ radar_mast_<id> レーダ空中線（原点 = 回転中心、Z まわり spin）
    ├─ BUOYANCY_SITES / MOUNTS（Empty）、NAV_LIGHTS
    └─ COLLISION（物理用の凸箱。glb には出力しない）

寸法の正本は設定 JSON（物理の MJCF も同じ値から生成される）。見た目の船体の水線下体積は排水容積に一致させる。
塗装色は設定の paint（一般的な配色で、実船の塗装の再現ではない）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import bmesh
import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hull_form as hf  # noqa: E402

Vec3 = Tuple[float, float, float]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="build_ship.py")
    p.add_argument("--config-json", required=True)
    return p.parse_args(argv)


# --- シーン・マテリアル ---------------------------------------------------------

MATS: Dict[str, bpy.types.Material] = {}

CONTAINER_COLORS = [
    (0.08, 0.22, 0.55), (0.62, 0.13, 0.11), (0.12, 0.42, 0.22), (0.82, 0.40, 0.08),
    (0.55, 0.57, 0.60), (0.88, 0.88, 0.86), (0.42, 0.25, 0.15), (0.05, 0.12, 0.30),
]


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
    scene.display.shading.show_specular_highlight = True
    scene.world = bpy.data.worlds.new("ShipWorld")
    scene.world.color = (0.55, 0.62, 0.70)


def make_material(name: str, color: Sequence[float], metallic: float = 0.0,
                  roughness: float = 0.5, emission: float = 0.0) -> bpy.types.Material:
    rgba = (color[0], color[1], color[2], 1.0)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = rgba  # Workbench（レンダ画像）用
    mat.use_backface_culling = False  # 板（ブルワーク・手すり）を両面表示（glTF doubleSided）
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission > 0:
            if "Emission Color" in bsdf.inputs:
                bsdf.inputs["Emission Color"].default_value = rgba
                bsdf.inputs["Emission Strength"].default_value = emission
            elif "Emission" in bsdf.inputs:
                bsdf.inputs["Emission"].default_value = rgba
    return mat


def init_materials(paint: dict) -> None:
    def col(key, default):
        v = paint.get(key)
        return tuple(v) if v else default

    specs = {
        "hull_topside": (col("hull_topside", (0.12, 0.13, 0.15)), 0.2, 0.55, 0.0),
        "boot_top": (col("boot_top", (0.06, 0.06, 0.07)), 0.1, 0.6, 0.0),
        "hull_bottom": (col("hull_bottom", (0.55, 0.12, 0.10)), 0.1, 0.7, 0.0),
        "deck": (col("deck", (0.32, 0.36, 0.33)), 0.1, 0.75, 0.0),
        "superstructure": (col("superstructure", (0.90, 0.90, 0.88)), 0.0, 0.45, 0.0),
        "funnel": (col("funnel", (0.90, 0.90, 0.88)), 0.0, 0.45, 0.0),
        "funnel_band": (col("funnel_band", (0.70, 0.13, 0.10)), 0.0, 0.45, 0.0),
        "funnel_top": (col("funnel_top", (0.05, 0.05, 0.05)), 0.0, 0.8, 0.0),
        "railing": (col("railing", (0.85, 0.86, 0.86)), 0.3, 0.4, 0.0),
        "glass": ((0.06, 0.10, 0.14), 0.7, 0.08, 0.0),
        "steel": ((0.55, 0.57, 0.60), 0.8, 0.35, 0.0),
        "bronze": ((0.72, 0.52, 0.25), 0.9, 0.25, 0.0),
        "dark": ((0.03, 0.03, 0.035), 0.0, 0.9, 0.0),
        "safety_orange": ((0.95, 0.40, 0.05), 0.0, 0.5, 0.0),
        "light_white": ((1.0, 1.0, 0.95), 0.0, 0.1, 10.0),
        "light_red": ((1.0, 0.1, 0.1), 0.0, 0.1, 8.0),
        "light_green": ((0.1, 1.0, 0.2), 0.0, 0.1, 8.0),
        "water": ((0.10, 0.25, 0.35), 0.0, 0.2, 0.0),
    }
    stripe = paint.get("stripe")
    if stripe:
        specs["stripe"] = (tuple(stripe["color"]), 0.1, 0.5, 0.0)
    for i, c in enumerate(CONTAINER_COLORS):
        specs[f"container_{i}"] = (c, 0.25, 0.55, 0.0)
    for name, (c, metal, rough, emis) in specs.items():
        MATS[name] = make_material(f"ship_{name}", c, metallic=metal, roughness=rough, emission=emis)


def get_collection(name: str) -> bpy.types.Collection:
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


# --- メッシュ生成 -------------------------------------------------------------

class MeshBuilder:
    """頂点・面・マテリアルを溜めて 1 つの（複数マテリアルの）オブジェクトにする。座標は親ローカル。"""

    def __init__(self) -> None:
        self.verts: List[Vec3] = []
        self.faces: List[Tuple[List[int], int, int]] = []  # (頂点番号, マテリアル番号, 部位タグ)
        self.mat_names: List[str] = []

    def _mi(self, mat: str) -> int:
        if mat not in self.mat_names:
            self.mat_names.append(mat)
        return self.mat_names.index(mat)

    def add(self, pts: Sequence[Vec3]) -> int:
        start = len(self.verts)
        self.verts.extend(tuple(float(c) for c in p) for p in pts)
        return start

    def face(self, idx: Sequence[int], mat: str, tag: int = 0) -> None:
        self.faces.append((list(idx), self._mi(mat), tag))

    def quad(self, a: Vec3, b: Vec3, c: Vec3, d: Vec3, mat: str) -> None:
        s = self.add([a, b, c, d])
        self.face([s, s + 1, s + 2, s + 3], mat)

    def box(self, center: Vec3, size: Vec3, mat: str, rot_z: float = 0.0) -> None:
        cx, cy, cz = center
        hx, hy, hz = (0.5 * s for s in size)
        cr, sr = math.cos(rot_z), math.sin(rot_z)
        pts = []
        for z in (-hz, hz):
            for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
                pts.append((cx + cr * x - sr * y, cy + sr * x + cr * y, cz + z))
        s = self.add(pts)
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.face([s + i for i in f], mat)

    def beam(self, a: Vec3, b: Vec3, w: float, h: float, mat: str) -> None:
        """a から b への角材（幅 w・高さ h）"""
        av, bv = Vector(a), Vector(b)
        d = bv - av
        if d.length < 1e-6:
            return
        t = d.normalized()
        up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
        side = t.cross(up).normalized() * (0.5 * w)
        upv = side.cross(t).normalized() * (0.5 * h)
        corners = [-side - upv, side - upv, side + upv, -side + upv]
        s = self.add([tuple(av + c) for c in corners] + [tuple(bv + c) for c in corners])
        for f in ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (0, 3, 2, 1), (4, 5, 6, 7)):
            self.face([s + i for i in f], mat)

    def prism_z(self, poly: Sequence[Tuple[float, float]], z0: float, z1: float, mat: str,
                cap: bool = True) -> None:
        """XY 平面の多角形を z0〜z1 に押し出す"""
        n = len(poly)
        s = self.add([(x, y, z0) for x, y in poly] + [(x, y, z1) for x, y in poly])
        for i in range(n):
            j = (i + 1) % n
            self.face([s + i, s + j, s + n + j, s + n + i], mat)
        if cap:
            self.face([s + i for i in reversed(range(n))], mat)
            self.face([s + n + i for i in range(n)], mat)

    def prism_x(self, poly_yz: Sequence[Tuple[float, float]], x0: float, x1: float, mat: str) -> None:
        """YZ 平面の多角形を x0〜x1 に押し出す"""
        n = len(poly_yz)
        s = self.add([(x0, y, z) for y, z in poly_yz] + [(x1, y, z) for y, z in poly_yz])
        for i in range(n):
            j = (i + 1) % n
            self.face([s + i, s + j, s + n + j, s + n + i], mat)
        self.face([s + i for i in reversed(range(n))], mat)
        self.face([s + n + i for i in range(n)], mat)

    def frustum(self, base: Vec3, r0: Tuple[float, float], r1: Tuple[float, float], h: float, mat: str,
                axis: str = "Z", seg: int = 24, shift: Tuple[float, float] = (0.0, 0.0),
                cap0: bool = True, cap1: bool = True) -> None:
        """楕円錐台。r0 / r1 は底・上の (半径1, 半径2)。axis 方向に h、上面を shift だけずらす"""
        def to_world(a: float, b: float, t: float) -> Vec3:
            if axis == "Z":
                return (base[0] + a, base[1] + b, base[2] + t)
            if axis == "Y":
                return (base[0] + a, base[1] + t, base[2] + b)
            return (base[0] + t, base[1] + a, base[2] + b)
        ring0, ring1 = [], []
        for k in range(seg):
            ang = 2.0 * math.pi * k / seg
            ring0.append(to_world(r0[0] * math.cos(ang), r0[1] * math.sin(ang), 0.0))
            ring1.append(to_world(r1[0] * math.cos(ang) + shift[0], r1[1] * math.sin(ang) + shift[1], h))
        s = self.add(ring0 + ring1)
        for k in range(seg):
            j = (k + 1) % seg
            self.face([s + k, s + j, s + seg + j, s + seg + k], mat)
        if cap0:
            self.face([s + k for k in reversed(range(seg))], mat)
        if cap1:
            self.face([s + seg + k for k in range(seg)], mat)

    def cylinder(self, center: Vec3, r: float, length: float, mat: str, axis: str = "Z", seg: int = 20) -> None:
        c = list(center)
        k = {"X": 0, "Y": 1, "Z": 2}[axis]
        c[k] -= 0.5 * length
        self.frustum(tuple(c), (r, r), (r, r), length, mat, axis=axis, seg=seg)

    def ellipsoid(self, center: Vec3, radii: Vec3, mat: str, seg: int = 24, rings: int = 12) -> None:
        cx, cy, cz = center
        rx, ry, rz = radii
        top = self.add([(cx, cy, cz + rz)])
        rows = []
        for i in range(1, rings):
            th = math.pi * i / rings
            row = self.add([(cx + rx * math.sin(th) * math.cos(2 * math.pi * k / seg),
                             cy + ry * math.sin(th) * math.sin(2 * math.pi * k / seg),
                             cz + rz * math.cos(th)) for k in range(seg)])
            rows.append(row)
        bot = self.add([(cx, cy, cz - rz)])
        for k in range(seg):
            j = (k + 1) % seg
            self.face([top, rows[0] + j, rows[0] + k], mat)
            self.face([bot, rows[-1] + k, rows[-1] + j], mat)
        for r0, r1 in zip(rows[:-1], rows[1:]):
            for k in range(seg):
                j = (k + 1) % seg
                self.face([r0 + k, r0 + j, r1 + j, r1 + k], mat)

    def build(self, name: str, coll: bpy.types.Collection, parent: Optional[bpy.types.Object],
              loc: Vec3 = (0.0, 0.0, 0.0), smooth_deg: Optional[float] = None,
              bisect_z: Sequence[float] = (), recolor=None, **props) -> bpy.types.Object:
        bm = bmesh.new()
        tag_layer = bm.faces.layers.int.new("part")
        bverts = [bm.verts.new(v) for v in self.verts]
        bm.verts.ensure_lookup_table()
        for idx, mi, tag in self.faces:
            try:
                f = bm.faces.new([bverts[i] for i in idx])
            except ValueError:
                continue  # 縮退面（重複頂点）
            f.material_index = mi
            f[tag_layer] = tag
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        for z in bisect_z:
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, dist=1e-4, plane_co=(0.0, 0.0, z), plane_no=(0.0, 0.0, 1.0))
        if recolor is not None:
            for f in bm.faces:
                name_new = recolor(f.calc_center_median(), f[tag_layer])
                if name_new:
                    f.material_index = self._mi(name_new)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mat_names:
            me.materials.append(MATS[m])
        if smooth_deg is not None:
            me.shade_smooth()
            me.set_sharp_from_angle(angle=math.radians(smooth_deg))
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        if parent is not None:
            ob.parent = parent
        ob.location = loc
        for k, v in props.items():
            ob[k] = v
        return ob


def make_empty(name: str, loc: Vec3, coll: bpy.types.Collection,
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


# --- 共通の寸法 -----------------------------------------------------------------

class Ship:
    """設定と船体形状から、各部の配置に使う寸法をまとめる"""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self.hp = hf.params_from_cfg(cfg)
        dim = cfg["dimensions"]
        self.Lpp = float(dim["length_pp_m"])
        self.B = float(dim["beam_m"])
        self.D = float(dim["depth_m"])
        self.d = float(dim["draft_m"])
        self.freeboard = self.D - self.d
        # 艤装品の大きさの基準（749GT = 1、漁船 ≒ 0.25）
        self.k = max(0.25, min(1.5, self.B / 14.0))
        self.small = self.Lpp < 25.0

    def u_at(self, y: float) -> float:
        """前後位置 y（甲板付近）→ 断面パラメータ u"""
        if y >= 0:
            return min(1.0, y / hf.bow_x(self.hp, self.freeboard))
        return max(-1.0, y / hf.stern_x(self.hp))

    def deck_z_at(self, y: float) -> float:
        return hf.deck_z(self.hp, self.u_at(y))

    def deck_half_at(self, y: float) -> float:
        return hf.b_deck(self.hp, self.u_at(y))

    def half_breadth_at(self, y: float, z: float) -> float:
        """前後位置 y・高さ z での船体外板の半幅（断面の折れ線を補間）"""
        u = y / hf.stern_x(self.hp) if y < 0 else y / hf.bow_x(self.hp, z)
        u = max(-1.0, min(1.0, u))
        half = hf.section_half(self.hp, u, 40, 8)
        for (y0, z0), (y1, z1) in zip(half[:-1], half[1:]):
            if min(z0, z1) <= z <= max(z0, z1) and z1 != z0:
                return y0 + (y1 - y0) * (z - z0) / (z1 - z0)
        return 0.0


# --- 船殻 ---------------------------------------------------------------------

TAG_DECK = 1


def build_hull(ship: Ship, coll: bpy.types.Collection, parent: bpy.types.Object) -> bpy.types.Object:
    p = ship.hp
    paint = ship.cfg.get("paint", {})
    mb = MeshBuilder()
    rings = hf.rings(p, n_stations=61, n_below=16, n_above=6)
    n = len(rings[0])
    starts = [mb.add(r) for r in rings]
    for a, b in zip(starts[:-1], starts[1:]):
        for k in range(n - 1):
            mb.face([a + k, a + k + 1, b + k + 1, b + k], "hull_topside")
        # 甲板（左舷甲板端 = 0、右舷甲板端 = n-1）
        mb.face([a + n - 1, a, b, b + n - 1], "deck", TAG_DECK)
    mb.face([starts[0] + k for k in range(n)], "hull_topside")          # トランサム
    mb.face([starts[-1] + k for k in reversed(range(n))], "hull_topside")  # 船首端（幅 0 に近い）

    band = paint.get("boot_top_band_m", [-0.35, 0.35])
    stripe = paint.get("stripe")
    cuts = [band[0], band[1]] + (list(stripe["z_m"]) if stripe else [])

    def recolor(c, tag):
        if tag == TAG_DECK:
            return "deck"
        if c.z < band[0]:
            return "hull_bottom"
        if c.z < band[1]:
            return "boot_top"
        if stripe and stripe["z_m"][0] <= c.z <= stripe["z_m"][1]:
            return "stripe"
        return "hull_topside"

    hull = mb.build("hull", coll, parent, smooth_deg=40.0, bisect_z=cuts, recolor=recolor, part_type="hull")

    # 付加物（同じオブジェクトにまとめると塗装の再分割が要るので別オブジェクト）
    ap = MeshBuilder()
    bb = ship.cfg.get("hull", {}).get("bulbous_bow", {})
    if bb.get("enabled", False):
        prot = float(bb.get("protrusion_m", 2.0))
        r = float(bb.get("radius_m", 1.2))
        zc = float(bb.get("center_z_m", -0.5 * ship.d))
        a_long = 0.5 * (prot + 2.5 * r)
        fp = p.Lpp / 2.0
        ap.ellipsoid((0.0, fp + prot - a_long, zc), (0.8 * r, a_long, r), "hull_bottom", seg=24, rings=12)
    props = ship.cfg.get("actuators", {}).get("propellers", [])
    if len(props) == 1:
        # スケグ（船尾の竜骨から船尾管まで）と船尾管ボス
        x, y, z = props[0]["shaft_pos_m"]
        dia = float(props[0]["diameter_m"])
        y_run = p.run_start_u * hf.stern_x(p)
        y_pf = y + 0.45 * dia
        top = []
        for i in range(13):
            yy = y_run + (y_pf - y_run) * i / 12
            top.append((yy, hf.keel_z(p, yy / hf.stern_x(p)) + 0.3))
        poly = top + [(y_pf, z - 0.2 * dia), (y_run + 0.15 * (y_pf - y_run), -ship.d)]
        t = max(0.12, 0.12 * dia)
        ap.prism_x(poly, -t, t, "hull_bottom")
        ap.frustum((0.0, y_pf, z), (0.17 * dia, 0.17 * dia), (0.12 * dia, 0.12 * dia), y + 0.15 * dia - y_pf,
                   "hull_bottom", axis="Y")
    else:
        # 二軸船: 軸とブラケット
        for pr in props:
            x, y, z = pr["shaft_pos_m"]
            dia = float(pr["diameter_m"])
            y_hull = y + 0.25 * ship.Lpp
            z_hull = hf.hull_bottom_z_at(p, y_hull, x)
            z_hull = z if math.isinf(z_hull) else z_hull
            ap.beam((x, y + 0.2 * dia, z), (x, y_hull, z_hull + 0.1), 0.08 * dia, 0.08 * dia, "steel")
            bracket_top = hf.hull_bottom_z_at(p, y + 0.5 * dia, x)
            if not math.isinf(bracket_top):
                ap.beam((x, y + 0.5 * dia, z), (x * 0.6, y + 0.5 * dia, bracket_top + 0.1), 0.15 * dia, 0.05 * dia, "steel")
    # バウ／スターンスラスタのトンネル口（舷側の黒い円）
    for th in ship.cfg.get("actuators", {}).get("thrusters", []):
        x, y, z = th.get("pos_m", [0.0, 0.0, 0.0])
        dia = float(th.get("diameter_m", 1.0))
        hb = ship.half_breadth_at(y, z)
        if hb > 0.5 * dia:
            ap.cylinder((0.0, y, z), 0.5 * dia, 2.0 * hb + 0.04, "dark", axis="X")
    if ap.faces:
        ap.build("hull_appendages", coll, parent, smooth_deg=50.0, part_type="hull")
    return hull


# --- 甲板艤装（ブルワーク・手すり・係船設備） -----------------------------------

def deck_edge(ship: Ship, n: int = 81) -> List[Tuple[float, float, float]]:
    """右舷の甲板端 (x, y, z) を船尾→船首の順に"""
    p = ship.hp
    out = []
    for u in hf.stations(n):
        out.append((hf.b_deck(p, u), hf.x_of(p, u, hf.deck_z(p, u)), hf.deck_z(p, u)))
    return out


def build_deck_fittings(ship: Ship, coll: bpy.types.Collection, parent: bpy.types.Object,
                        house: Optional[Tuple[float, float, float]]) -> None:
    """house: 上部構造物の (後端 y, 前端 y, 半幅)。その範囲の舷側は手すりを付けない"""
    mb = MeshBuilder()
    edge = deck_edge(ship)
    k = ship.k
    full_bulwark = ship.small
    bw_h = 0.55 if ship.small else 1.3 * min(1.2, k)
    fore_u = 0.72
    rail_h = 1.0 if not ship.small else 0.8
    p = ship.hp

    for side in (1.0, -1.0):
        for (x0, y0, z0), (x1, y1, z1) in zip(edge[:-1], edge[1:]):
            u = ship.u_at(0.5 * (y0 + y1))
            a = (side * x0, y0, z0)
            b = (side * x1, y1, z1)
            if full_bulwark or u > fore_u:
                # ブルワーク（外板の延長、船体色）＋ 上端の手すり材
                mb.quad(a, b, (b[0], b[1], b[2] + bw_h), (a[0], a[1], a[2] + bw_h), "hull_topside")
                mb.beam((a[0], a[1], a[2] + bw_h), (b[0], b[1], b[2] + bw_h), 0.12 * k + 0.03, 0.06, "railing")
                continue
            if house and house[0] - 1.0 <= y0 <= house[1] + 1.0 and house[2] > 0.9 * x0:
                continue
            # 手すり（上下 2 本の横材と支柱）
            for hz in (rail_h, 0.5 * rail_h):
                mb.beam((a[0], a[1], a[2] + hz), (b[0], b[1], b[2] + hz), 0.05, 0.05, "railing")
            mb.beam(a, (a[0], a[1], a[2] + rail_h), 0.05, 0.05, "railing")
    # トランサムの手すり
    xs, ys, zs = edge[0]
    mb.beam((-xs, ys, zs + rail_h), (xs, ys, zs + rail_h), 0.05, 0.05, "railing")

    # 係船設備: 揚錨機（船首）とボラード（前後各 2 対）
    y_fore = hf.x_of(p, 0.86, ship.freeboard)
    z_fore = hf.deck_z(p, 0.86)
    if not ship.small:
        for side in (1.0, -1.0):
            mb.cylinder((side * 0.18 * ship.B, y_fore, z_fore + 0.55 * k), 0.45 * k, 0.9 * k, "safety_orange", axis="X")
            mb.box((side * 0.18 * ship.B, y_fore - 0.9 * k, z_fore + 0.3 * k), (1.2 * k, 0.8 * k, 0.6 * k), "deck")
        for u in (0.80, -0.92):
            y = hf.x_of(p, u, ship.freeboard)
            z = hf.deck_z(p, u)
            half = hf.b_deck(p, u)
            for side in (1.0, -1.0):
                for dy in (-0.35 * k, 0.35 * k):
                    mb.cylinder((side * (half - 0.9 * k), y + dy, z + 0.3 * k), 0.18 * k, 0.6 * k, "dark")
    mb.build("deck_fittings", coll, parent, smooth_deg=35.0, part_type="deck_fittings")


# --- 上部構造物 ---------------------------------------------------------------

def window_row(mb: MeshBuilder, face: str, origin: Vec3, length: float, z: float,
               w: float, h: float, pitch: float, depth: float = 0.05) -> None:
    """壁面に窓を並べる。face: 'front'(+Y 面), 'back'(-Y 面), 'port'(-X 面), 'stbd'(+X 面)。
    origin = 面の中心 (x, y)、length = 面の幅方向の長さ"""
    n = max(1, int((length - 0.6 * pitch) / pitch) + 1)
    span = (n - 1) * pitch
    for i in range(n):
        s = -0.5 * span + i * pitch
        if face in ("front", "back"):
            sign = 1.0 if face == "front" else -1.0
            mb.box((origin[0] + s, origin[1] + sign * 0.5 * depth, z), (w, depth * 2, h), "glass")
        else:
            sign = 1.0 if face == "stbd" else -1.0
            mb.box((origin[0] + sign * 0.5 * depth, origin[1] + s, z), (depth * 2, w, h), "glass")


def window_band(mb: MeshBuilder, x0: float, x1: float, y0: float, y1: float, z: float, h: float,
                front: bool = True, sides: bool = True, back: bool = False, inset: float = 0.3) -> None:
    """箱の側面に連続窓（ブリッジ・旅客デッキ）"""
    t = 0.06
    if front:
        mb.box((0.5 * (x0 + x1), y1 + 0.5 * t, z), (x1 - x0 - 2 * inset, t * 2, h), "glass")
    if back:
        mb.box((0.5 * (x0 + x1), y0 - 0.5 * t, z), (x1 - x0 - 2 * inset, t * 2, h), "glass")
    if sides:
        for x, sgn in ((x1, 1.0), (x0, -1.0)):
            mb.box((x + sgn * 0.5 * t, 0.5 * (y0 + y1), z), (t * 2, y1 - y0 - 2 * inset, h), "glass")


def build_funnel(mb: MeshBuilder, x: float, y: float, z0: float, height: float, dia: float) -> None:
    r_long, r_lat = 0.75 * dia, 0.5 * dia
    rake = 0.12 * height
    parts = [(0.72, "funnel"), (0.16, "funnel_band"), (0.12, "funnel_top")]
    z = z0
    for frac, mat in parts:
        h = frac * height
        t0 = (z - z0) / height
        t1 = (z + h - z0) / height
        s0, s1 = 1.0 - 0.15 * t0, 1.0 - 0.15 * t1
        mb.frustum((x, y - rake * t0, z), (r_lat * s0, r_long * s0), (r_lat * s1, r_long * s1), h, mat,
                   shift=(0.0, -rake * (t1 - t0)), cap0=(mat == "funnel"), cap1=(mat == "funnel_top"))
        z += h


def build_mast(ship: Ship, mb: MeshBuilder, x: float, y: float, z_base: float, mounts: List[dict]) -> None:
    """レーダ架台つきマスト。空中線（radar_mast_*）は別オブジェクトで、ここは台座まで"""
    k = ship.k
    radars = [m for m in mounts if m.get("type") == "marine_radar"]
    tops = [float(m["pos_m"][2]) for m in mounts if abs(float(m["pos_m"][1]) - y) < 3.0 and m["pos_m"][2] > z_base]
    z_top = max(tops + [z_base + 3.0 * k]) + 0.4 * k
    r = 0.16 * k + 0.04
    mb.frustum((x, y, z_base), (r * 1.4, r * 1.4), (r, r), z_top - z_base, "superstructure", seg=16)
    # 桁（信号灯・アンテナ）
    mb.beam((x - 1.6 * k, y, z_top - 1.0 * k), (x + 1.6 * k, y, z_top - 1.0 * k), 0.12 * k, 0.12 * k, "superstructure")
    for m in radars:
        rx, ry, rz = (float(v) for v in m["pos_m"])
        z_plat = rz - 0.55 * k
        mb.box((rx, ry, z_plat), (2.2 * k + 0.4, 1.6 * k + 0.4, 0.15), "superstructure")
        # 台座（回転しない）
        mb.box((rx, ry, 0.5 * (z_plat + rz - 0.18)), (0.45 * k + 0.1, 0.45 * k + 0.1, rz - 0.18 - z_plat), "superstructure")
        if abs(ry - y) > 0.5 or abs(rx - x) > 0.5:
            mb.beam((x, y, z_plat), (rx, ry, z_plat), 0.15 * k, 0.15 * k, "superstructure")
    # 小物（GNSS・カメラ・LiDAR）
    for m in mounts:
        mx, my, mz = (float(v) for v in m["pos_m"])
        t = m.get("type", "")
        if t == "gnss_antenna":
            mb.frustum((mx, my, mz - 0.15), (0.12, 0.12), (0.06, 0.06), 0.18, "superstructure", seg=12)
        elif t in ("lidar_3d", "lidar_2d"):
            mb.cylinder((mx, my, mz), 0.08, 0.12, "dark", seg=12)
        elif t == "camera_rgb":
            mb.box((mx, my, mz), (0.18, 0.25, 0.15), "dark")
            # 支柱（post_m：筐体の下から甲板まで）。甲板より高く上げた船首カメラが浮かないように
            post = float(m.get("post_m", 0.0))
            if post > 0.0:
                mb.cylinder((mx, my, mz - 0.075 - 0.5 * post), 0.05, post, "steel", seg=10)
        elif t == "passive_radar_reflector":
            mb.ellipsoid((mx, my, mz), (0.18, 0.18, 0.25), "steel", seg=4, rings=2)


def build_superstructure(ship: Ship, coll: bpy.types.Collection,
                         parent: bpy.types.Object) -> Optional[Tuple[float, float, float]]:
    sup = ship.cfg.get("superstructure", {})
    if not sup.get("enabled", True):
        return None
    stype = sup.get("type", "aft_bridge")
    mounts = ship.cfg.get("mounts", [])
    mb = MeshBuilder()
    if stype == "passenger_decks":
        house = _passenger_decks(ship, sup, mb, mounts)
    elif stype == "forward_wheelhouse":
        house = _wheelhouse_small(ship, sup, mb, mounts)
    else:
        house = _aft_bridge(ship, sup, mb, mounts)
    mb.build("superstructure", coll, parent, smooth_deg=30.0, part_type="superstructure")
    return house


def _aft_bridge(ship: Ship, sup: dict, mb: MeshBuilder, mounts: List[dict]) -> Tuple[float, float, float]:
    """船尾船橋型（コンテナ船）: 居住区の段 ＋ 船橋（両翼）＋ 煙突 ＋ マスト"""
    k = ship.k
    L = float(sup.get("length_m", 14.0))
    W = float(sup.get("width_m", 12.0))
    H = float(sup.get("height_m", 11.0))
    W_wing = float(sup.get("bridge_wing_width_m", W + 2.0))
    decks = max(2, int(sup.get("decks", 4)))
    yc = float(sup.get("pos_y_m", -0.38 * ship.Lpp))
    y0, y1 = yc - 0.5 * L, yc + 0.5 * L
    z0 = ship.deck_z_at(yc) - 0.05
    h = H / decks
    # 居住区（段ごとに張り出しの縁）
    for i in range(decks - 1):
        zb = z0 + i * h
        mb.box((0.0, yc, zb + 0.5 * h), (W, L, h), "superstructure")
        mb.box((0.0, yc, zb + h), (W + 0.3, L + 0.3, 0.18), "superstructure")
        zw = zb + 0.55 * h
        window_row(mb, "front", (0.0, y1), W - 1.5, zw, 1.0 * k, 0.9 * k, 2.2 * k)
        window_row(mb, "back", (0.0, y0), W - 1.5, zw, 0.9 * k, 0.8 * k, 2.6 * k)
        window_row(mb, "stbd", (0.5 * W, yc), L - 1.5, zw, 0.9 * k, 0.9 * k, 2.4 * k)
        window_row(mb, "port", (-0.5 * W, yc), L - 1.5, zw, 0.9 * k, 0.9 * k, 2.4 * k)
    # 船橋（前寄り）・両翼・屋根
    zb = z0 + (decks - 1) * h
    Lw = 0.6 * L
    yw = y1 - 0.5 * Lw
    mb.box((0.0, yw, zb + 0.5 * h), (W, Lw, h), "superstructure")
    window_band(mb, -0.5 * W, 0.5 * W, yw - 0.5 * Lw, y1, zb + 0.58 * h, 0.42 * h, front=True, sides=True)
    wing_y = y1 - 0.25 * Lw
    for sgn in (1.0, -1.0):
        x_in, x_out = sgn * 0.5 * W, sgn * 0.5 * W_wing
        mb.box((0.5 * (x_in + x_out), wing_y, zb + 0.1), (abs(x_out - x_in), 0.5 * Lw, 0.2), "superstructure")
        mb.box((x_out, wing_y, zb + 0.6), (0.12, 0.5 * Lw, 1.0), "superstructure")
    mb.box((0.0, yw, zb + h + 0.15), (W + 0.6, Lw + 0.6, 0.3), "superstructure")
    roof_z = zb + h + 0.3
    # 煙突（居住区上・船橋の後ろ）
    funnel = sup.get("funnel")
    if funnel:
        fx, fy, _ = (float(v) for v in funnel.get("pos_m", [0.0, y0 + 0.2 * L, 0.0]))
        H_f = float(funnel.get("height_m", 4.0)) * 1.3
        build_funnel(mb, fx, fy, zb, H_f, float(funnel.get("diameter_m", 1.8)))
    # マスト（レーダ位置に）
    radars = [m for m in mounts if m.get("type") == "marine_radar"]
    mx, my = (float(radars[0]["pos_m"][0]), float(radars[0]["pos_m"][1])) if radars else (0.0, yw)
    if not (y0 <= my <= y1):
        my = yw
    build_mast(ship, mb, mx, my, roof_z if yw - 0.5 * Lw <= my <= y1 else zb, mounts)
    # 自由降下式救命艇（居住区後端の中心線上、船尾向きに傾けた台座）
    lb_y = y0 - 2.0 * k
    lb_z = z0 + 1.6 * h
    mb.ellipsoid((0.0, lb_y, lb_z), (1.1 * k, 3.4 * k, 1.0 * k), "safety_orange")
    mb.box((0.0, lb_y + 0.6 * k, lb_z - 1.1 * k), (2.6 * k, 5.5 * k, 0.2), "steel")
    for sgn in (1.0, -1.0):
        mb.beam((sgn * 1.2 * k, y0, lb_z - 1.1 * k), (sgn * 1.2 * k, lb_y - 1.5 * k, z0), 0.15, 0.15, "steel")
    return (y0, y1, 0.5 * W)


def _passenger_decks(ship: Ship, sup: dict, mb: MeshBuilder, mounts: List[dict]) -> Tuple[float, float, float]:
    """旅客フェリー型: 後方へ段々に短くなる旅客デッキ（連続窓・遊歩甲板）＋ 前端の船橋 ＋ 二本煙突"""
    k = ship.k
    L = float(sup.get("length_m", 40.0))
    W = float(sup.get("width_m", ship.B - 0.5))
    H = float(sup.get("height_m", 8.0))
    W_wing = float(sup.get("bridge_wing_width_m", ship.B))
    decks = max(1, int(sup.get("decks", 3)))
    yc = float(sup.get("pos_y_m", 0.0))
    y1 = yc + 0.5 * L
    z0 = ship.deck_z_at(yc) - 0.05
    h = H / decks
    step = 0.12 * L
    rail_h = 1.0
    for i in range(decks):
        Li = L - i * step
        y0i = y1 - Li
        zb = z0 + i * h
        Wi = W if i == 0 else W - 0.6
        mb.box((0.0, 0.5 * (y0i + y1), zb + 0.5 * h), (Wi, Li, h), "superstructure")
        window_band(mb, -0.5 * Wi, 0.5 * Wi, y0i, y1, zb + 0.55 * h, 0.4 * h, front=True, sides=True,
                    back=(i > 0), inset=1.0)
        # 段の上面（遊歩甲板）の手すり
        Lr = Li - step if i < decks - 1 else Li
        top = zb + h
        for sgn in (1.0, -1.0):
            mb.beam((sgn * 0.5 * Wi, y0i, top + rail_h), (sgn * 0.5 * Wi, y0i + Lr, top + rail_h), 0.05, 0.05, "railing")
        mb.beam((-0.5 * Wi, y0i, top + rail_h), (0.5 * Wi, y0i, top + rail_h), 0.05, 0.05, "railing")
        if i < decks - 1:
            # 後部遊歩甲板の救命いかだ（白い筒）
            for sgn in (1.0, -1.0):
                for j in range(3):
                    mb.cylinder((sgn * (0.5 * Wi - 0.8), y0i + 1.5 + 1.4 * j, top + 0.45), 0.4, 1.1, "superstructure",
                                axis="Y", seg=12)
    # 船橋（最上段の前端）
    zb = z0 + decks * h
    Lw, Ww, Hw = 6.0 * k, 0.7 * W, 2.8
    yw = y1 - 0.5 * Lw - 0.5
    mb.box((0.0, yw, zb + 0.5 * Hw), (Ww, Lw, Hw), "superstructure")
    window_band(mb, -0.5 * Ww, 0.5 * Ww, yw - 0.5 * Lw, yw + 0.5 * Lw, zb + 0.6 * Hw, 0.45 * Hw, front=True, sides=True)
    for sgn in (1.0, -1.0):
        mb.box((sgn * 0.25 * (W_wing + Ww), yw + 0.2 * Lw, zb + 0.1), (0.5 * (W_wing - Ww), 0.5 * Lw, 0.2), "superstructure")
        mb.box((sgn * 0.5 * W_wing, yw + 0.2 * Lw, zb + 0.6), (0.12, 0.5 * Lw, 1.0), "superstructure")
    mb.box((0.0, yw, zb + Hw + 0.15), (Ww + 0.5, Lw + 0.5, 0.3), "superstructure")
    # 二本煙突（最上段の上）
    tf = sup.get("twin_funnel")
    if tf:
        for key in ("port_pos_m", "stbd_pos_m"):
            fx, fy, _ = (float(v) for v in tf[key])
            build_funnel(mb, fx, fy, zb, float(tf.get("height_m", 3.5)) * 1.2, float(tf.get("diameter_m", 1.2)))
    radars = [m for m in mounts if m.get("type") == "marine_radar"]
    mx, my = (float(radars[0]["pos_m"][0]), float(radars[0]["pos_m"][1])) if radars else (0.0, yw)
    build_mast(ship, mb, mx, my, zb + Hw + 0.3, mounts)
    # 船尾ランプウェイ（跳ね上げた状態）
    vd = ship.cfg.get("hull", {}).get("vehicle_deck", {})
    if vd.get("stern_ramp"):
        p = ship.hp
        ys = -hf.stern_x(p)
        zs = hf.deck_z(p, -1.0)
        w = 0.55 * ship.B
        lr = 5.0
        ang = math.radians(75.0)
        mb.box((0.0, ys - 0.5 * lr * math.cos(ang), zs + 0.5 * lr * math.sin(ang)), (w, 0.3, lr), "steel",
               rot_z=0.0)
    return (y1 - L, y1, 0.5 * W)


def _wheelhouse_small(ship: Ship, sup: dict, mb: MeshBuilder, mounts: List[dict]) -> Tuple[float, float, float]:
    """小型漁船: 前傾した窓の操舵室 ＋ マスト（レーダ反射器・集魚灯）＋ 後部作業甲板（ネットドラム・ガントリー）"""
    L = float(sup.get("length_m", 3.5))
    W = float(sup.get("width_m", 2.2))
    H = float(sup.get("height_m", 2.2))
    yc = float(sup.get("pos_y_m", 0.15 * ship.Lpp))
    y0, y1 = yc - 0.5 * L, yc + 0.5 * L
    z0 = ship.deck_z_at(yc) - 0.03
    h_low = 0.55 * H
    mb.box((0.0, yc, z0 + 0.5 * h_low), (W, L, h_low), "superstructure")
    # 上部（ガラス張り、前面は後傾）
    rake = 0.35
    poly = [(y0, z0 + h_low), (y1, z0 + h_low), (y1 - rake, z0 + H), (y0, z0 + H)]
    mb.prism_x(poly, -0.5 * W + 0.04, 0.5 * W - 0.04, "glass")
    # 窓枠（柱）
    for x in (-0.5 * W, -0.17 * W, 0.17 * W, 0.5 * W):
        mb.beam((x, y1, z0 + h_low), (x, y1 - rake, z0 + H), 0.08, 0.08, "superstructure")
    for y in (y0, y0 + 0.5 * L):
        for x in (-0.5 * W, 0.5 * W):
            mb.beam((x, y, z0 + h_low), (x, y, z0 + H), 0.08, 0.08, "superstructure")
    roof_z = z0 + H
    mb.box((0.0, yc - 0.5 * rake, roof_z + 0.05), (W + 0.25, L + 0.1, 0.1), "superstructure")
    # マスト
    mm = [m for m in mounts if m.get("type") in ("passive_radar_reflector", "gnss_antenna", "marine_radar")]
    mx, my = (float(mm[0]["pos_m"][0]), float(mm[0]["pos_m"][1])) if mm else (0.0, yc)
    build_mast(ship, mb, mx, my, roof_z + 0.1, mounts)
    # 集魚灯（マストの桁から船首・船尾へ張った線に沿って）
    if sup.get("mast", {}).get("fishing_lights", False):
        p = ship.hp
        z_top = max([float(m["pos_m"][2]) for m in mounts] + [roof_z + 1.5])
        bow = (0.0, hf.x_of(p, 0.97, ship.freeboard), hf.deck_z(p, 0.97) + 0.8)
        stern = (0.0, -hf.stern_x(p) + 0.4, hf.deck_z(p, -1.0) + 2.2)
        for end in (bow, stern):
            a = Vector((mx, my, z_top - 0.3))
            b = Vector(end)
            mb.beam(tuple(a), tuple(b), 0.02, 0.02, "dark")
            for j in range(1, 6):
                c = a + (b - a) * (j / 6.0)
                mb.ellipsoid((c.x, c.y, c.z - 0.12), (0.09, 0.09, 0.12), "light_white", seg=8, rings=4)
    # 後部作業甲板: ネットドラムとガントリー
    p = ship.hp
    yd = -0.28 * ship.Lpp
    zd = ship.deck_z_at(yd)
    mb.cylinder((0.0, yd, zd + 0.45), 0.32, 1.3, "safety_orange", axis="X", seg=16)
    for sgn in (1.0, -1.0):
        mb.box((sgn * 0.75, yd, zd + 0.25), (0.08, 0.5, 0.5), "steel")
    ys = -hf.stern_x(p) + 0.35
    zs = hf.deck_z(p, -1.0)
    half = hf.b_deck(p, -1.0) - 0.15
    for sgn in (1.0, -1.0):
        mb.beam((sgn * half, ys, zs), (sgn * half * 0.8, ys + 0.2, zs + 2.0), 0.1, 0.1, "steel")
    mb.beam((-half * 0.8, ys + 0.2, zs + 2.0), (half * 0.8, ys + 0.2, zs + 2.0), 0.12, 0.12, "steel")
    return (y0, y1, 0.5 * W)


# --- 貨物（コンテナ） -------------------------------------------------------------

def build_cargo(ship: Ship, coll: bpy.types.Collection, parent: bpy.types.Object,
                house: Optional[Tuple[float, float, float]]) -> int:
    cargo_cfg = ship.cfg.get("hull", {}).get("cargo_hold", {})
    if cargo_cfg.get("type", "") != "container_bays":
        return 0
    p = ship.hp
    mb = MeshBuilder()
    bays = int(cargo_cfg.get("bays", 4))
    stacks = int(cargo_cfg.get("stacks", 5))
    tiers = int(cargo_cfg.get("tiers", 3))
    c_len, c_w, c_h = 12.19, 2.44, 2.59   # 40 ft
    gap = 0.6
    y_start = (house[1] if house else -0.3 * ship.Lpp) + 1.5
    y_end = hf.x_of(p, 0.70, ship.freeboard)
    bays = max(1, min(bays, int((y_end - y_start) / (c_len + gap))))
    count = 0
    for b in range(bays):
        yb = y_start + (b + 0.5) * (c_len + gap)
        half = min(ship.deck_half_at(yb - 0.5 * c_len), ship.deck_half_at(yb + 0.5 * c_len)) - 0.6
        n_st = max(1, min(stacks, int(2 * half / (c_w + 0.05))))
        zd = max(ship.deck_z_at(yb - 0.5 * c_len), ship.deck_z_at(yb + 0.5 * c_len))
        w_hatch = n_st * (c_w + 0.05) + 0.3
        mb.box((0.0, yb, zd + 0.45), (w_hatch, c_len + 0.4, 0.9), "deck")
        z_base = zd + 0.9
        for s in range(n_st):
            x = (s - (n_st - 1) / 2.0) * (c_w + 0.05)
            for t in range(tiers):
                h = (b * 131 + s * 31 + t * 7) % 17
                if t == tiers - 1 and h < 5:
                    continue  # 最上段は所々空ける
                color = (b * 7 + s * 3 + t * 5 + h) % len(CONTAINER_COLORS)
                mb.box((x, yb, z_base + (t + 0.5) * (c_h + 0.02)), (c_w, c_len, c_h), f"container_{color}")
                count += 1
    if count:
        mb.build("cargo", coll, parent, smooth_deg=30.0, part_type="cargo")
    return count


# --- 可動部（舵・プロペラ・レーダ空中線） ------------------------------------------

def foil_section(chord: float, thickness: float, n: int = 12) -> List[Tuple[float, float]]:
    """NACA 4 桁対称翼の断面 (x 厚み方向, y 翼弦方向)。前縁 = +y（船首側）、舵軸は翼弦の 30 % に置く"""
    pts_upper = []
    for i in range(n + 1):
        t = (1.0 - math.cos(math.pi * i / n)) / 2.0  # 0: 前縁, 1: 後縁
        yt = 5.0 * thickness * (0.2969 * math.sqrt(t) - 0.1260 * t - 0.3516 * t ** 2 + 0.2843 * t ** 3 - 0.1036 * t ** 4)
        pts_upper.append((yt * chord, (0.3 - t) * chord))
    lower = [(-x, y) for x, y in reversed(pts_upper[1:-1])]
    return pts_upper + lower


def build_actuators(ship: Ship, coll: bpy.types.Collection, parent: bpy.types.Object) -> None:
    act = ship.cfg.get("actuators", {})
    for p in act.get("propellers", []):
        pid = p["id"]
        dia = float(p.get("diameter_m", 3.0))
        pos = tuple(p.get("shaft_pos_m", [0.0, -40.0, -2.0]))
        mb = MeshBuilder()
        r_hub = 0.17 * dia
        mb.frustum((0.0, 0.15 * dia, 0.0), (r_hub, r_hub), (0.9 * r_hub, 0.9 * r_hub), -0.3 * dia, "bronze", axis="Y")
        mb.frustum((0.0, -0.15 * dia, 0.0), (0.9 * r_hub, 0.9 * r_hub), (0.2 * r_hub, 0.2 * r_hub), -0.15 * dia, "bronze", axis="Y")
        n_bl = int(p.get("blades", 4))
        pitch = math.atan(float(p.get("pitch_ratio", 0.85)) / (math.pi * 0.7))
        for b in range(n_bl):
            ang = 2.0 * math.pi * b / n_bl
            ca, sa = math.cos(ang), math.sin(ang)
            outline = []
            for i in range(9):
                t = i / 8.0
                r = r_hub * 0.9 + (0.5 * dia - r_hub * 0.9) * t
                w = 0.38 * dia * math.sin(math.pi * (0.15 + 0.85 * t)) ** 0.7 * (1.0 - 0.3 * t)
                outline.append((r, 0.5 * w))
            ring = [(r, c) for r, c in outline] + [(r, -c) for r, c in reversed(outline)]
            pts = []
            for r, c in ring:
                # 翼弦はピッチ角だけ回転（回転面内の成分と軸方向の成分）
                tang, axial = c * math.cos(pitch), c * math.sin(pitch)
                pts.append((r * sa + tang * ca, axial, r * ca - tang * sa))
            s = mb.add(pts)
            mb.face(list(range(s, s + len(pts))), "bronze")
        mb.build(f"propeller_{pid}", coll, parent, loc=pos, smooth_deg=60.0,
                 joint_type="spin", joint_axis=[0.0, 1.0, 0.0], part_type="propeller", propeller_dia_m=dia)

    for r in act.get("rudders", []):
        rid = r["id"]
        area = float(r.get("area_m2", 7.0))
        ar = float(r.get("aspect_ratio", 1.6))
        pos = tuple(r.get("pos_m", [0.0, -43.0, -2.0]))
        h = (area * ar) ** 0.5
        chord = area / h
        mb = MeshBuilder()
        mb.prism_z(foil_section(chord, 0.18), -0.5 * h, 0.5 * h, "hull_bottom")
        mb.cylinder((0.0, 0.0, 0.5 * h + 0.4), 0.06 * chord + 0.05, 0.8, "steel", seg=12)  # 舵軸
        mb.build(f"rudder_{rid}", coll, parent, loc=pos, smooth_deg=50.0,
                 joint_type="hinge", joint_axis=[0.0, 0.0, 1.0], part_type="rudder", rudder_area_m2=area)

    for m in ship.cfg.get("mounts", []):
        if m.get("type") != "marine_radar":
            continue
        mid = m["id"]
        pos = tuple(m.get("pos_m", [0.0, -35.0, 20.0]))
        length = 3.6 if m.get("band") == "S_BAND" else 2.4
        length *= min(1.0, ship.k + 0.2)
        mb = MeshBuilder()
        mb.box((0.0, 0.08, 0.12), (length, 0.16, 0.32), "superstructure")    # スロットアレイ
        mb.box((0.0, 0.0, -0.06), (0.35, 0.35, 0.18), "superstructure")      # 回転部
        mb.build(f"radar_mast_{mid}", coll, parent, loc=pos, smooth_deg=30.0,
                 joint_type="spin", joint_axis=[0.0, 0.0, 1.0], part_type="radar_antenna")


# --- 浮力サイト・当たり判定・マウント・航海灯（物理・センサとの契約。形は変えない） -------

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
        b_st = (B / 2.0) * max(0.15, (1.0 - abs(xi) ** 2.2) ** 0.5)
        transverse_dist = b_st * offset_ratio
        for side, sx in (("port", -1.0), ("stbd", 1.0)):
            name = f"buoyancy_st{i:02d}_{side}"
            pos = (sx * transverse_dist, y, 0.0)
            make_empty(name, pos, coll, parent=parent, size=0.8,
                       station_idx=i, side=side, baseline_z=-d, part_type="buoyancy_site")
            sites.append({"name": name, "station": i, "side": side, "pos": pos})
    return sites


def build_collision(cfg: dict, coll: bpy.types.Collection, parent: bpy.types.Object) -> List[bpy.types.Object]:
    """物理（MJCF）と同じ凸箱と RCS 属性。表示・glb 出力はしない"""
    dim = cfg["dimensions"]
    Lpp = float(dim["length_pp_m"])
    B = float(dim["beam_m"])
    D = float(dim["depth_m"])
    d = float(dim["draft_m"])
    total_rcs = float(cfg.get("signatures", {}).get("radar_cross_section_m2", 2500.0))
    out = []
    specs = [("collision_hull_main", (B * 0.95, Lpp * 0.65, D), (0.0, 0.0, (D - 2.0 * d) * 0.5), 0.45),
             ("collision_hull_bow", (B * 0.70, Lpp * 0.25, D * 1.1), (0.0, Lpp * 0.38, (D - 2.0 * d) * 0.5), 0.20)]
    sup = cfg.get("superstructure", {})
    if sup.get("enabled", True):
        L_s = float(sup.get("length_m", 14.0))
        W_s = float(sup.get("width_m", 12.0))
        H_s = float(sup.get("height_m", 11.0))
        y_c = -Lpp * 0.38 if sup.get("type") == "aft_bridge" else 0.0
        specs.append(("collision_superstructure", (W_s, L_s, H_s), (0.0, y_c, (D - d) + H_s * 0.5), 0.35))
    for name, size, loc, frac in specs:
        mb = MeshBuilder()
        mb.box((0.0, 0.0, 0.0), size, "steel")
        ob = mb.build(name, coll, parent, loc=loc, part_type="collision", rcs_sigma=total_rcs * frac)
        ob.display_type = "WIRE"
        ob.hide_render = True
        out.append(ob)
    return out


def build_mounts_and_lights(cfg: dict, coll_mount: bpy.types.Collection,
                            coll_light: bpy.types.Collection, parent: bpy.types.Object) -> None:
    for m in cfg.get("mounts", []):
        mid = m["id"]
        pos = tuple(m.get("pos_m", [0.0, 0.0, 0.0]))
        make_empty(f"mount_{mid}", pos, coll_mount, parent=parent, size=0.6,
                   mount_type=m.get("type", "sensor"), part_type="mount")
    light_mat_map = {"white": "light_white", "red": "light_red", "green": "light_green"}
    for lt in cfg.get("nav_lights", []):
        lid = lt["id"]
        col = lt.get("color", "white")
        mb = MeshBuilder()
        mb.cylinder((0.0, 0.0, 0.0), 0.12, 0.20, light_mat_map.get(col, "light_white"), seg=12)
        mb.build(f"navlight_{lid}", coll_light, parent, loc=tuple(lt.get("pos_m", [0.0, 0.0, 0.0])),
                 part_type="nav_light", light_color=col, arc_deg=float(lt.get("arc_deg", 225.0)))


# --- レンダリング ---------------------------------------------------------------

def visual_bounds() -> Tuple[Vector, Vector]:
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.hide_render:
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def render_views(out_dir: Path, resolution: int = 1000) -> Dict[str, str]:
    renders_dir = out_dir / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = int(resolution * 0.6)
    scene.render.image_settings.file_format = "PNG"

    cams = get_collection("Cameras")
    cam_data = bpy.data.cameras.new("RenderCam")
    cam = bpy.data.objects.new("Camera_Render", cam_data)
    cams.objects.link(cam)
    scene.camera = cam

    lo, hi = visual_bounds()
    center = (lo + hi) * 0.5
    size = hi - lo
    span = max(size.x, size.y, size.z)

    def look(direction: Vector, ortho: bool, scale: float) -> None:
        cam_data.type = "ORTHO" if ortho else "PERSP"
        if ortho:
            cam_data.ortho_scale = scale
        else:
            cam_data.lens = 50.0
        cam.location = center + direction.normalized() * span * 2.2
        if abs(direction.normalized().z) > 0.99:
            cam.rotation_euler = (0.0, 0.0, math.pi / 2.0)  # 真上: 船首を画面右へ
        else:
            cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

    views = {
        "front": (Vector((0, 1, 0)), True, max(size.x, size.z / 0.6) * 1.15),
        "back": (Vector((0, -1, 0)), True, max(size.x, size.z / 0.6) * 1.15),
        "port": (Vector((-1, 0, 0)), True, max(size.y, size.z / 0.6) * 1.08),
        "starboard": (Vector((1, 0, 0)), True, max(size.y, size.z / 0.6) * 1.08),
        "top": (Vector((0, 0, 1)), True, max(size.y, size.x / 0.6) * 1.08),
        "iso": (Vector((1.0, 0.9, 0.7)), True, span * 1.05),
        "hero": (Vector((1.0, 1.3, 0.45)), False, 0.0),
    }
    results = {}
    for name, (direction, ortho, scale) in views.items():
        look(direction, ortho, scale)
        path = renders_dir / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        results[name] = str(path)

    # 水面付き（水線より上の見え方。ビューアの見た目に近い）
    mb = MeshBuilder()
    r = span * 2.0
    mb.quad((-r, -r, 0.0), (r, -r, 0.0), (r, r, 0.0), (-r, r, 0.0), "water")
    water = mb.build("render_water", cams, None)
    look(Vector((1.0, 1.3, 0.3)), False, 0.0)
    path = renders_dir / "hero_water.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    results["hero_water"] = str(path)
    bpy.data.objects.remove(water)
    return results


# --- メイン ---------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config_json)
    with cfg_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)
    subject = cfg.get("template_id", "vessel")
    out_dir = cfg_path.parent

    setup_scene()
    init_materials(cfg.get("paint", {}))
    ship = Ship(cfg)

    coll_hull = get_collection("Hull")
    coll_sup = get_collection("Superstructure")
    coll_cargo = get_collection("Cargo")
    coll_act = get_collection("Actuators")
    coll_buoy = get_collection("BUOYANCY_SITES")
    coll_coll = get_collection("COLLISION")
    coll_mount = get_collection("MOUNTS")
    coll_light = get_collection("NAV_LIGHTS")

    root = make_empty(subject, (0.0, 0.0, 0.0), bpy.context.scene.collection,
                      part_type="root", vehicle_type="vessel", subject_id=subject)

    build_hull(ship, coll_hull, root)
    house = build_superstructure(ship, coll_sup, root)
    build_deck_fittings(ship, coll_hull, root, house)
    containers = build_cargo(ship, coll_cargo, root, house)
    build_actuators(ship, coll_act, root)
    buoy_sites = build_buoyancy_sites(cfg, coll_buoy, root)
    collision = build_collision(cfg, coll_coll, root)
    build_mounts_and_lights(cfg, coll_mount, coll_light, root)

    blend_path = out_dir / f"{subject}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    # glb: 物理用の COLLISION 箱は出力しない（ビューアで船体に重なって見えるため）
    for ob in collision:
        ob.hide_set(True)
    glb_path = out_dir / f"{subject}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB",
                              use_visible=True, export_cameras=False, export_lights=False)
    for ob in collision:
        ob.hide_set(False)

    renders = render_views(out_dir)

    lo, hi = visual_bounds()
    hp = ship.hp
    report = {
        "subject": subject,
        "blend_file": str(blend_path),
        "glb_file": str(glb_path),
        "renders": renders,
        "buoyancy_sites_count": len(buoy_sites),
        "containers_count": containers,
        "total_objects": len(bpy.data.objects),
        "total_meshes": len(bpy.data.meshes),
        "total_faces": sum(len(m.polygons) for m in bpy.data.meshes),
        "visual_bounds_m": {"min": list(lo), "max": list(hi)},
        "hull_form": {
            "underwater_volume_m3": hf.underwater_volume(hp),
            "target_volume_m3": hp.target_volume,
            "midship_superellipse_n": hp.n_mid,
            "fullness": hp.fullness,
            "transom_z_m": hp.transom_z,
        },
    }
    with (out_dir / "build_report.json").open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"[build_ship.py] Successfully built {subject}: {blend_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
