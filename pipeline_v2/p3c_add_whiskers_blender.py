"""P3-9: 髭を生成して GLB を出し直す（髭対応.png への対応）。

素材のマンチカンには髭のジオメトリが無い。リファレンス（配色2.pdf ほか）の髭は
「口元から左右へ弧を描いて下向きに垂れる白い髭 + 眉の上の短い髭」なので、
テーパー付きの細いチューブ（カーブ→メッシュ化）で生成し、全頂点を bip01_head に
ウェイト 1.0 で割り当てて頭に追従させる。

マズル表面の実測（p3_uv_position.npz、レスト）:
  |X| 0.013 -> Z≈0.218 / 0.019 -> 0.2145 / 0.025 -> 0.209（Y 0.180〜0.199 でほぼ一定）
  眉: Y 0.222〜0.234 の表面 Z max ≈ 0.191

  blender --background --python pipeline_v2/p3c_add_whiskers_blender.py -- \
    --input output_v2/base/p3_koha9.blend \
    --output-blend output_v2/base/p3_koha9.blend \
    --output-glb output_v2/base/p3_koha9.glb
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy

HEAD_BONE = "bip01_head"
OBJ_NAME = "Whiskers"
MAT_NAME = "Whiskers"

# 髭1本 = (根元 xyz, 水平方位 yaw[deg], 長さ, 立ち上がり, 垂れ, 根元半径)
# yaw は +X 側で「+X からどれだけ前(+Z)へ振るか」。-X 側は X を反転して使う。
# リファレンスでは中段が最も長く、全体に下向きへ弧を描く。
# P4-顔第2段階（2026-07-15）: マズル延長 (+8.3mm) に合わせて根元を新旧 npz の
# 同一テクセル対応で再マップ（az +0.0083 / ax +0.0005。眉は x のみ +0.0005）。
ROWS = [
    # 上段（目の下あたりから前へ）
    (0.1945, 0.0145, 0.2243, [(+32, 0.056), (+12, 0.062), (-8, 0.058)], 0.010, 0.022),
    # 中段（最長）
    (0.1895, 0.0170, 0.2208, [(+28, 0.066), (+8, 0.074), (-12, 0.068)], 0.006, 0.028),
    # 下段（短め・強めに垂れる）
    (0.1845, 0.0179, 0.2188, [(+24, 0.054), (+4, 0.060), (-16, 0.055)], 0.002, 0.032),
]
# 眉の上の髭（上向き・後ろへ流れる）。眉庇 BROW_OUT で額の表面が +4.4mm 前へ出たのに追従
BROWS = [
    (0.0190, 0.2270, 0.1899, [(+35, 0.040), (+15, 0.046), (-5, 0.042)]),
]
ROOT_RADIUS = 0.00075
TIP_RADIUS_FRAC = 0.16
SEGS = 10


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    # face (2026-07-12): 実物の髭は白く細く、眉の髭は控えめ。既定値は従来どおり
    p.add_argument("--root-radius", type=float, default=ROOT_RADIUS)
    p.add_argument("--color", default="0.92,0.90,0.87")
    p.add_argument("--brow-scale", type=float, default=1.0)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def whisker_points(root, yaw_deg, length, rise, droop, side, brow=False):
    """根元から先端までの点列。水平に伸びつつ t^2 で垂れる（眉は逆に立ち上がる）。"""
    yaw = math.radians(yaw_deg)
    dx = math.cos(yaw) * side
    dz = math.sin(yaw)
    pts = []
    for i in range(SEGS + 1):
        t = i / SEGS
        x = root[0] + dx * length * t
        z = root[2] + dz * length * t
        if brow:
            y = root[1] + rise * t + droop * t * t   # 眉: 上へ弧
        else:
            y = root[1] + rise * t - droop * t * t   # 口元: 下へ垂れる
        pts.append((x, y, z))
    return pts


def build_whisker_curve(name, pts):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = 1.0          # 実半径は各点の radius で与える
    cu.bevel_resolution = 2
    cu.resolution_u = 6
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for i, (x, y, z) in enumerate(pts):
        # 座標は glTF 系（Y上/Z前）で設計している。Blender は Z上/-Y前なので
        # b = (gx, -gz, gy) に変換して置く（変換を忘れると髭が尻尾側に出る。実測）。
        sp.points[i].co = (x, -z, y, 1.0)
        t = i / (len(pts) - 1)
        sp.points[i].radius = ROOT_RADIUS * (1.0 - (1.0 - TIP_RADIUS_FRAC) * t)
    ob = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main() -> int:
    global ROOT_RADIUS
    a = parse_args()
    ROOT_RADIUS = a.root_radius
    col = tuple(float(v) for v in a.color.split(","))
    bpy.ops.wm.open_mainfile(filepath=a.input)

    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    if bpy.data.objects.get(OBJ_NAME):
        raise SystemExit(f"{OBJ_NAME} は既に存在する（二重生成を防ぐため中断）")

    curves = []
    n = 0
    for side in (+1.0, -1.0):
        for y, ax, az, fan, rise, droop in ROWS:
            for yaw, length in fan:
                root = (side * ax, y, az - 0.002)
                curves.append(build_whisker_curve(
                    f"wk_{n}", whisker_points(root, yaw, length, rise, droop, side)))
                n += 1
        for bx, by, bz, fan in BROWS:
            for yaw, length in fan:
                root = (side * bx, by, bz - 0.002)
                curves.append(build_whisker_curve(
                    f"wk_{n}", whisker_points(root, yaw, length * a.brow_scale,
                                              0.024 * a.brow_scale, 0.014 * a.brow_scale,
                                              side, brow=True)))
                n += 1

    # カーブ→メッシュ化して1オブジェクトに統合
    bpy.ops.object.select_all(action="DESELECT")
    for ob in curves:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = curves[0]
    bpy.ops.object.convert(target="MESH")
    bpy.ops.object.join()
    wsk = bpy.context.view_layer.objects.active
    wsk.name = OBJ_NAME
    wsk.data.name = OBJ_NAME

    # 白いマテリアル（テクスチャ不要。p3_apply の画像差し替え対象外）
    mat = bpy.data.materials.new(MAT_NAME)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.45
    wsk.data.materials.append(mat)

    # 全頂点を頭ボーンへ（髭は頭に剛体追従でよい）
    vg = wsk.vertex_groups.new(name=HEAD_BONE)
    vg.add(range(len(wsk.data.vertices)), 1.0, "REPLACE")
    mod = wsk.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    # 親子付けはしない。`wsk.parent = arm` とするとアーマチュアのオブジェクト変換
    # （0.0009 スケールの罠）が掛かって髭が一点に潰れる（実測）。変形はモディファイアで足りる。
    print(f"[P3c] armature world scale: {tuple(round(v,6) for v in arm.matrix_world.to_scale())}")

    print(f"[P3c] whiskers: {n} 本 / {len(wsk.data.vertices)} verts -> bone {HEAD_BONE}")

    out_blend = Path(a.output_blend)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
