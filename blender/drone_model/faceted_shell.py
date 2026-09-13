"""角ばった多面体の胴体（origin-01 系の意匠）を作る —— `body.shape: faceted`。

2026-09-13 新規（惑星専用機 titan_df8 のため）。
★ 既存の胴体（lofted / bulged_box / rounded_box）は丸みで作るので、どう設定しても
  origin-01 のような「面取りした板を組んだ硬い殻」にはならない。この形はそれを別に持つ。
★ `build_drone.py` からは `body.shape == "faceted"` のときだけ呼ばれる。**既存機体の出力は変わらない。**

形の作り方:
  * 断面は **8 角形**（幅 W・高さ H の長方形の 4 隅を `chamfer_w` × `chamfer_h` だけ落とした形）。
  * 前後方向（+Y が機首）に **ステーション**を並べ、各ステーションで断面を
    `scale_w` / `scale_h` 倍・`z_offset` 上下させて、隣どうしを平面の四角形でつなぐ。
  * **スムーズシェードを使わない**（面の境目が稜線として見えるのがこの意匠の要点）。
  * 飾り（`faceted.details`）: 上面のパネル・アクセントライン・側面の通風口・前面のバイザー。
    飾りにも part_type を付ける（下流の blend2mjcf.py が質量表で引くため）。
"""
from __future__ import annotations

import math
from typing import Any

import bpy


def _mm(v: float) -> float:
    return float(v) / 1000.0


def _octagon(w: float, h: float, cw: float, ch: float) -> list[tuple[float, float]]:
    """(x, z) の 8 点。右上から反時計まわり（+Y から見て）。"""
    hw, hh = w / 2.0, h / 2.0
    return [
        (hw, hh - ch), (hw - cw, hh), (-hw + cw, hh), (-hw, hh - ch),
        (-hw, -hh + ch), (-hw + cw, -hh), (hw - cw, -hh), (hw, -hh + ch),
    ]


def _link(obj: bpy.types.Object, collection: bpy.types.Collection, material: bpy.types.Material,
          parent: bpy.types.Object) -> bpy.types.Object:
    collection.objects.link(obj)
    if obj.type == "MESH":
        obj.data.materials.append(material)
    obj.parent = parent
    return obj


def _mesh(name: str, verts, faces) -> bpy.types.Object:
    me = bpy.data.meshes.new(f"{name}_mesh")
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    me.update()
    for p in me.polygons:
        p.use_smooth = False
    return bpy.data.objects.new(name, me)


def _plate(name: str, size_m, loc_m, chamfer_m: float) -> bpy.types.Object:
    """面取りした薄い板（上から見て 8 角形・厚み方向は平ら）。size = (x, y, z)。"""
    sx, sy, sz = size_m
    c = min(chamfer_m, sx * 0.45, sy * 0.45)
    ring = [(sx / 2, sy / 2 - c), (sx / 2 - c, sy / 2), (-sx / 2 + c, sy / 2), (-sx / 2, sy / 2 - c),
            (-sx / 2, -sy / 2 + c), (-sx / 2 + c, -sy / 2), (sx / 2 - c, -sy / 2), (sx / 2, -sy / 2 + c)]
    verts = [(x, y, -sz / 2) for x, y in ring] + [(x, y, sz / 2) for x, y in ring]
    faces = [tuple(range(7, -1, -1)), tuple(range(8, 16))]
    for i in range(8):
        j = (i + 1) % 8
        faces.append((i, j, j + 8, i + 8))
    obj = _mesh(name, verts, faces)
    obj.location = loc_m
    return obj


def create_faceted_body(
    name: str,
    body: dict[str, Any],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
    material_lookup: dict[str, bpy.types.Material],
) -> bpy.types.Object:
    W = _mm(body["width_mm"])
    L = _mm(body["length_mm"])
    H = _mm(body["height_mm"])
    zc = _mm(body.get("center_z_mm", 0.0))
    f = body.get("faceted", {}) or {}
    cw = W * float(f.get("chamfer_w", 0.18))
    ch = H * float(f.get("chamfer_h", 0.30))
    # ステーション: t は −1（尾端）〜 +1（機首端）
    stations = f.get("stations") or [
        {"t": -1.00, "scale_w": 0.70, "scale_h": 0.62, "z_offset": 0.04},
        {"t": -0.80, "scale_w": 0.96, "scale_h": 0.92, "z_offset": 0.00},
        {"t": 0.35, "scale_w": 1.00, "scale_h": 1.00, "z_offset": 0.00},
        {"t": 0.78, "scale_w": 0.92, "scale_h": 0.86, "z_offset": -0.03},
        {"t": 1.00, "scale_w": 0.58, "scale_h": 0.50, "z_offset": -0.10},
    ]
    verts: list[tuple[float, float, float]] = []
    for st in stations:
        y = float(st["t"]) * L / 2.0
        sw, sh = float(st["scale_w"]), float(st["scale_h"])
        dz = float(st.get("z_offset", 0.0)) * H
        for x, z in _octagon(W * sw, H * sh, cw * sw, ch * sh):
            verts.append((x, y, zc + z + dz))
    faces = []
    ns = len(stations)
    for s in range(ns - 1):
        a, b = s * 8, (s + 1) * 8
        for i in range(8):
            j = (i + 1) % 8
            faces.append((a + i, a + j, b + j, b + i))
    faces.append(tuple(range(7, -1, -1)))                      # 尾端のふた
    faces.append(tuple(range((ns - 1) * 8, ns * 8)))           # 機首のふた
    body_obj = _link(_mesh(name, verts, faces), collection, material, parent)

    # --- 飾り ---------------------------------------------------------------
    d = f.get("details", {}) or {}
    top_z = zc + H / 2.0
    accent = material_lookup.get(str(d.get("accent_material", "led_green")), material)
    panel_mat = material_lookup.get(str(d.get("panel_material", "aluminum")), material)
    glass = material_lookup.get(str(d.get("visor_material", "lens")), material)
    trim_mat = material_lookup.get(str(d.get("trim_material", "black")), material)

    if d.get("top_panel", True):
        # ★ 上面の一段高いパネル（origin-01 の上面の段差）
        pw, pl = W * 0.62 - 2 * cw * 0.3, L * 0.55
        o = _link(_plate(f"{name}_top_panel", (pw, pl, _mm(18.0)), (0.0, -L * 0.05, top_z + _mm(9.0)), W * 0.08),
                  collection, trim_mat, parent)
        o["part_type"] = "body_panel"
    if d.get("accent_stripes", True):
        # ★ アクセントライン 2 本（上面パネルの左右・前後方向）
        sw_ = _mm(float(d.get("stripe_width_mm", 36.0)))
        for side, sx in (("left", -1.0), ("right", 1.0)):
            o = _link(_plate(f"{name}_stripe_{side}", (sw_, L * 0.42, _mm(8.0)),
                             (sx * W * 0.17, L * 0.02, top_z + _mm(22.0)), sw_ * 0.4),
                      collection, accent, parent)
            o["part_type"] = "accent_stripe"
        # 側面の水平ライン
        for side, sx in (("left", -1.0), ("right", 1.0)):
            o = _link(_plate(f"{name}_side_line_{side}", (_mm(10.0), L * 0.60, _mm(22.0)),
                             (sx * (W / 2.0 + _mm(4.0)), -L * 0.02, zc + H * 0.12), _mm(4.0)),
                      collection, accent, parent)
            o["part_type"] = "accent_stripe"
    if d.get("side_panels", True):
        # ★ 側面の少し沈んだ灰色のパネル（面の段差で稜線を増やす）
        for side, sx in (("left", -1.0), ("right", 1.0)):
            o = _link(_plate(f"{name}_side_panel_{side}", (_mm(14.0), L * 0.34, H * 0.26),
                             (sx * (W / 2.0 + _mm(2.0)), -L * 0.18, zc - H * 0.12), _mm(20.0)),
                      collection, panel_mat, parent)
            o["part_type"] = "body_panel"
    if d.get("vents", True):
        # ★ 通風口（上面パネルの後ろに並ぶ細い溝）
        n = int(d.get("vent_count", 5))
        for i in range(n):
            y = -L * 0.30 - i * _mm(46.0)
            o = _link(_plate(f"{name}_vent_{i + 1:02d}", (W * 0.36, _mm(22.0), _mm(10.0)),
                             (0.0, y, top_z + _mm(5.0) - (L * 0.0)), _mm(6.0)),
                      collection, trim_mat, parent)
            o["part_type"] = "body_vent"
    if d.get("visor", True):
        # ★ 機首の斜めのバイザー（暗いガラス）
        nose_st = stations[-2]
        vy = float(nose_st["t"]) * L / 2.0 + L * 0.06
        o = _link(_plate(f"{name}_visor", (W * 0.62 * float(nose_st["scale_w"]), _mm(16.0), H * 0.34),
                         (0.0, vy, zc + H * 0.08), _mm(30.0)),
                  collection, glass, parent)
        o.rotation_euler = (math.radians(-28.0), 0.0, 0.0)
        o["part_type"] = "body_visor"
    return body_obj
