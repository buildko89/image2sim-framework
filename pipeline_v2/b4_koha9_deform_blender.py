"""B-4: Koha9 Body Deform (Blender CLI script)

cat_calico.blend（三毛テクスチャ適用済み Leopard ベース）を koha9_cat 体型へ変形する。
参照: png/koha1-4.png（短足・丸顔・ふっくら胴体）

変形の設計:
  1. 短足化: 接地高からの smoothstep Z圧縮を「メッシュ頂点」と「エディットボーン」の
     両方に同一関数で適用し、リグとスキンの整合を保つ（旧 cat_master_deform.py の方式）。
     胴体・頭・尻尾は圧縮量ぶん一律に下がる。
  2. 丸顔化: 頭部ウェイト (bip01_head + bone001-015) をブレンド係数に、頭部中心
     （bip01_head ボーン位置）まわりの一様拡大 + マズルの前後圧縮。
     ボーンは動かさない（骨に対する相対オフセットはスキニングで回転に追従するため安全）。
  3. 胴体ふっくら: 脊椎ウェイト (pelvis/spine/spine1/spine2) で X 方向拡幅 + 法線膨張。
  4. 脚の太さ: 脚ウェイトで法線方向に微膨張（短足の寸胴感）。
  5. コンパクト化 (v2): 前後方向 (Y) を体中心まわりに一律圧縮して胴・首・尻尾を詰める。
     メッシュとエディットボーンに同一適用（Z圧縮と同じ整合方式）。
  6. 尻尾ふっくら (v2): 尻尾ウェイト (bone016-020) で法線膨張。

使用方法:
  blender --background --python pipeline_v2/b4_koha9_deform_blender.py -- \
    --input output_v2/base/cat_calico.blend \
    --output-blend output_v2/base/cat_koha9.blend \
    --output-glb output_v2/base/cat_koha9.glb \
    --report output_v2/reports/b4_koha9_deform.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

MESH_NAME = "Leopard_Hybrid"

BODY_GROUPS = ["bip01_pelvis", "bip01_spine", "bip01_spine1", "bip01_spine2"]
HEAD_GROUPS = ["bip01_head"] + [f"bone{i:03d}" for i in range(1, 16)]
LEG_GROUPS = [
    f"bip01_{side}_{part}"
    for side in ("l", "r")
    for part in ("upperarm", "forearm", "hand", "thigh", "calf", "horselink", "foot")
]
FOOT_GROUPS = [
    f"bip01_{side}_{part}"
    for side in ("l", "r")
    for part in ("hand", "foot", "toe0", "toe2", "finger0", "finger2")
]

# チューニングパラメータ（すべてワールド座標系・メートル）
LEG_HEIGHT = 0.060   # この高さまでを「脚」として圧縮（接地面基準）
LEG_SCALE = 0.45     # 脚の高さ倍率（0.45 = 55% 短縮）
HEAD_SCALE = 1.10    # 頭部の一様拡大率
MUZZLE_COMPRESS = 0.72   # マズルの前後圧縮率
MUZZLE_OFFSET = 0.015    # 頭部中心からこの距離より前をマズルとみなす
BODY_WIDEN = 0.16    # 胴体の X 拡幅率（1.0 + w * BODY_WIDEN）
LEG_INFLATE = 0.004  # 脚の法線方向膨張量 (m)
BODY_COMPACT_Y = 0.85    # 前後方向の圧縮率（胴・首・尻尾を詰める）
BODY_INFLATE = 0.003     # 胴体の法線方向膨張量 (m)。大きくするとファーカードが浮いてささくれる
TAIL_INFLATE = 0.004     # 尻尾の法線方向膨張量 (m)

TAIL_GROUPS = [f"bone{i:03d}" for i in range(16, 21)]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deform calico cat toward koha9 proportions.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--report", required=True)
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


def group_indices(obj: bpy.types.Object, names: list[str]) -> set[int]:
    return {g.index for g in obj.vertex_groups if g.name in names}


def weight_of(vertex, indices: set[int]) -> float:
    return max((g.weight for g in vertex.groups if g.group in indices), default=0.0)


def smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 3.0 * t * t - 2.0 * t * t * t


def make_deform_z(ground_z: float, leg_height: float, leg_scale: float):
    """接地面からの高さで滑らかに Z を圧縮する関数。脚より上は一律オフセット。"""
    body_offset = leg_height * (1.0 - leg_scale)

    def deform_z(z: float) -> float:
        h = z - ground_z
        if h <= 0.0:
            return z
        if h >= leg_height:
            return z - body_offset
        t = smoothstep(1.0 - h / leg_height)  # 接地に近いほど 1
        return ground_z + h * ((1.0 - t) + leg_scale * t) - (1.0 - t) * body_offset * (h / leg_height)

    return deform_z


def find_head_center(arm_obj: bpy.types.Object) -> Vector:
    bone = arm_obj.data.bones.get("bip01_head")
    if not bone:
        raise RuntimeError("bip01_head bone not found")
    return arm_obj.matrix_world @ bone.head_local


def find_body_center_y(arm_obj: bpy.types.Object) -> float:
    """前脚 (hand) と後脚 (foot) の中間 Y。ここを中心に前後圧縮すると立ち位置が保たれる。"""
    mw = arm_obj.matrix_world
    hand = arm_obj.data.bones.get("bip01_l_hand")
    foot = arm_obj.data.bones.get("bip01_l_foot")
    if not hand or not foot:
        raise RuntimeError("leg bones not found for body center estimation")
    return ((mw @ hand.head_local).y + (mw @ foot.head_local).y) / 2.0


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.input)

    obj = bpy.data.objects.get(MESH_NAME)
    if obj is None:
        raise RuntimeError(f"Mesh object '{MESH_NAME}' not found")
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")

    mw = obj.matrix_world.copy()
    mw_inv = mw.inverted()
    nrm_mat = mw.to_3x3().inverted().transposed()

    body_idx = group_indices(obj, BODY_GROUPS)
    head_idx = group_indices(obj, HEAD_GROUPS)
    leg_idx = group_indices(obj, LEG_GROUPS)
    foot_idx = group_indices(obj, FOOT_GROUPS)
    tail_idx = group_indices(obj, TAIL_GROUPS)

    # 接地高: 足先ウェイトの強い頂点の最小 Z（尻尾が地面より下に垂れるため全頂点 min は不可）
    foot_zs = [
        (mw @ v.co).z for v in obj.data.vertices if weight_of(v, foot_idx) > 0.5
    ]
    if not foot_zs:
        raise RuntimeError("No foot-weighted vertices found for ground estimation")
    ground_z = min(foot_zs)

    head_center = find_head_center(arm)
    muzzle_plane_y = head_center.y - MUZZLE_OFFSET  # 前方 = -Y
    body_center_y = find_body_center_y(arm)
    deform_z = make_deform_z(ground_z, LEG_HEIGHT, LEG_SCALE)

    def compact_y(y: float) -> float:
        return body_center_y + (y - body_center_y) * BODY_COMPACT_Y

    dims_before = list(obj.dimensions)
    print(f"[B-4] ground_z={ground_z:.4f} head_center={tuple(round(c, 4) for c in head_center)}")
    print(f"[B-4] dims before: {[round(d, 4) for d in dims_before]}")

    counts = {"head": 0, "muzzle": 0, "body": 0, "leg_inflate": 0, "tail_inflate": 0, "z_compressed": 0}

    for v in obj.data.vertices:
        w = mw @ v.co

        # 1. 丸顔化: 頭部中心まわりの一様拡大（頭ウェイトでブレンド）
        head_w = weight_of(v, head_idx)
        if head_w > 0.01:
            scaled = head_center + (w - head_center) * HEAD_SCALE
            w = w.lerp(scaled, min(head_w, 1.0))
            counts["head"] += 1
            # 2. マズル前後圧縮（鼻先を頭部中心へ引き寄せて丸い印象に）
            if w.y < muzzle_plane_y:
                target_y = muzzle_plane_y + (w.y - muzzle_plane_y) * MUZZLE_COMPRESS
                w.y = w.y + (target_y - w.y) * min(head_w, 1.0)
                counts["muzzle"] += 1

        # 3. 胴体拡幅 + 法線膨張（ふっくら感）
        body_w = weight_of(v, body_idx)
        if body_w > 0.01:
            w.x *= 1.0 + BODY_WIDEN * min(body_w, 1.0)
            n = (nrm_mat @ v.normal).normalized()
            w += n * (BODY_INFLATE * min(body_w, 1.0))
            counts["body"] += 1

        # 4. 脚の微膨張（法線方向）
        leg_w = weight_of(v, leg_idx)
        if leg_w > 0.05:
            n = (nrm_mat @ v.normal).normalized()
            w += n * (LEG_INFLATE * min(leg_w, 1.0))
            counts["leg_inflate"] += 1

        # 5. 尻尾の法線膨張（もふもふ尻尾）
        tail_w = weight_of(v, tail_idx)
        if tail_w > 0.05:
            n = (nrm_mat @ v.normal).normalized()
            w += n * (TAIL_INFLATE * min(tail_w, 1.0))
            counts["tail_inflate"] += 1

        # 6. 短足化 + コンパクト化（全頂点対象、ボーンと同一関数）
        new_z = deform_z(w.z)
        if abs(new_z - w.z) > 1e-6:
            counts["z_compressed"] += 1
        w.z = new_z
        w.y = compact_y(w.y)

        v.co = mw_inv @ w
    obj.data.update()

    # === エディットボーンにも同一の Z 圧縮を適用（丸顔・拡幅はボーン不要）===
    amw = arm.matrix_world.copy()
    amw_inv = amw.inverted()
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    bone_count = 0
    for eb in arm.data.edit_bones:
        for attr in ("head", "tail"):
            p = amw @ getattr(eb, attr)
            p.z = deform_z(p.z)
            p.y = compact_y(p.y)
            setattr(eb, attr, amw_inv @ p)
        bone_count += 1
    bpy.ops.object.mode_set(mode="OBJECT")

    dims_after = list(obj.dimensions)
    print(f"[B-4] dims after:  {[round(d, 4) for d in dims_after]}")
    print(f"[B-4] deformed counts: {counts}, bones adjusted: {bone_count}")

    out_blend = Path(args.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    out_glb = Path(args.output_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format="GLB",
        use_selection=True,
        export_animation_mode="ACTIONS",
    )
    print(f"  Exported: {out_glb}")

    report = {
        "task": "B-4: Koha9 Body Deform",
        "reference_images": ["png/koha1.png", "png/koha2.png", "png/koha3.png", "png/koha4.png"],
        "input": args.input,
        "outputs": {"blend": str(out_blend), "glb": str(out_glb)},
        "parameters": {
            "ground_z": ground_z,
            "leg_height": LEG_HEIGHT,
            "leg_scale": LEG_SCALE,
            "head_scale": HEAD_SCALE,
            "muzzle_compress": MUZZLE_COMPRESS,
            "body_widen": BODY_WIDEN,
            "leg_inflate": LEG_INFLATE,
            "body_compact_y": BODY_COMPACT_Y,
            "body_inflate": BODY_INFLATE,
            "tail_inflate": TAIL_INFLATE,
            "body_center_y": body_center_y,
        },
        "head_center_world": [round(c, 4) for c in head_center],
        "dimensions_before": [round(d, 4) for d in dims_before],
        "dimensions_after": [round(d, 4) for d in dims_after],
        "deformed_vertex_counts": counts,
        "bones_adjusted": bone_count,
        "actions": [a.name for a in bpy.data.actions],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
