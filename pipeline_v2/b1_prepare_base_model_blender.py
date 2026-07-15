"""B-1: Prepare Base Model (Blender CLI script)

Leopard_Hybrid_A1.Fbx をインポートし、猫サイズにスケール正規化して
ベースモデルとして保存する。

使用方法:
  blender --background --python pipeline_v2/b1_prepare_base_model_blender.py -- \
    --input "input/cat/uploads_files_6085726_FbxBlender/FbxBlender/Leopard_Hybrid_A1.Fbx" \
    --output-blend "output_v2/base/cat_base.blend" \
    --output-glb "output_v2/base/cat_base.glb" \
    --report "output_v2/reports/b1_prepare_base_model.json"
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


# 目標: 猫の体長を約 0.4m (40cm) にスケーリング
TARGET_BODY_LENGTH = 0.4


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare base cat model from Leopard FBX.")
    parser.add_argument("--input", required=True, help="Input FBX model path")
    parser.add_argument("--output-blend", required=True, help="Output .blend path")
    parser.add_argument("--output-glb", required=True, help="Output .glb path")
    parser.add_argument("--report", required=True, help="Output JSON report path")
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


def import_fbx(filepath: str) -> None:
    """FBX をインポート"""
    bpy.ops.import_scene.fbx(filepath=filepath)


def get_meshes() -> list[bpy.types.Object]:
    """シーン内のメッシュオブジェクトを取得"""
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def get_armatures() -> list[bpy.types.Object]:
    """シーン内のアーマチュアオブジェクトを取得"""
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def compute_scene_bbox() -> tuple[Vector, Vector]:
    """シーン内の全メッシュのワールド座標バウンディングボックスを計算"""
    all_points = []
    for obj in get_meshes():
        for corner in obj.bound_box:
            all_points.append(obj.matrix_world @ Vector(corner))
    if not all_points:
        return Vector((0, 0, 0)), Vector((1, 1, 1))
    min_v = Vector((min(p.x for p in all_points), min(p.y for p in all_points), min(p.z for p in all_points)))
    max_v = Vector((max(p.x for p in all_points), max(p.y for p in all_points), max(p.z for p in all_points)))
    return min_v, max_v


def normalize_scale(target_length: float) -> float:
    """モデルの最長軸が target_length になるようにスケーリング"""
    min_v, max_v = compute_scene_bbox()
    dimensions = max_v - min_v
    max_dim = max(dimensions.x, dimensions.y, dimensions.z)
    if max_dim < 1e-6:
        print("WARNING: Model has zero dimensions, skipping scale")
        return 1.0

    scale_factor = target_length / max_dim
    print(f"  Current dimensions: {dimensions.x:.4f} x {dimensions.y:.4f} x {dimensions.z:.4f}")
    print(f"  Max dimension: {max_dim:.4f}")
    print(f"  Scale factor: {scale_factor:.6f}")

    # 全ルートオブジェクトをスケーリング
    # 注意: transform_apply はしない。アニメーション付きアーマチュアにスケールを
    # 適用すると pose の location キーフレームが旧単位のまま残って動きが壊れ、
    # 親子オブジェクトへの個別適用は子の変換を破壊する。
    # スケールはオブジェクトに乗せたままにする（glTF エクスポータはノードスケール
    # として正しく出力し、Godot 等のエンジンでも問題なく扱える）。
    root_objects = [obj for obj in bpy.context.scene.objects if obj.parent is None]
    for obj in root_objects:
        obj.scale *= scale_factor

    bpy.context.view_layer.update()

    return scale_factor


def set_origin_to_feet() -> None:
    """モデルの原点を足元（バウンディングボックスの底面中心）に設定"""
    min_v, max_v = compute_scene_bbox()
    # 底面の中心を原点にする
    center_x = (min_v.x + max_v.x) / 2
    center_y = (min_v.y + max_v.y) / 2
    bottom_z = min_v.z

    offset = Vector((center_x, center_y, bottom_z))
    print(f"  Setting origin to feet: ({center_x:.4f}, {center_y:.4f}, {bottom_z:.4f})")

    # 全オブジェクトの位置をオフセット
    for obj in bpy.context.scene.objects:
        if obj.parent is None:
            obj.location -= offset

    bpy.context.view_layer.update()


def scene_report() -> dict:
    """シーンの状態をレポート用に取得"""
    meshes = get_meshes()
    armatures = get_armatures()
    min_v, max_v = compute_scene_bbox()
    dimensions = max_v - min_v

    mesh_info = []
    total_verts = 0
    total_polys = 0
    for m in meshes:
        v = len(m.data.vertices)
        p = len(m.data.polygons)
        total_verts += v
        total_polys += p
        mesh_info.append({
            "name": m.name,
            "vertices": v,
            "polygons": p,
            "materials": [s.material.name if s.material else "(empty)" for s in m.material_slots],
            "uv_layers": [l.name for l in m.data.uv_layers],
        })

    arm_info = []
    for a in armatures:
        bones = [b.name for b in a.data.bones] if a.data else []
        arm_info.append({
            "name": a.name,
            "bone_count": len(bones),
        })

    actions = []
    for action in bpy.data.actions:
        s, e = action.frame_range
        actions.append({"name": action.name, "frames": int(e - s + 1)})

    return {
        "mesh_count": len(meshes),
        "total_vertices": total_verts,
        "total_polygons": total_polys,
        "armature_count": len(armatures),
        "action_count": len(actions),
        "dimensions_m": [round(dimensions.x, 4), round(dimensions.y, 4), round(dimensions.z, 4)],
        "bbox_min": [round(min_v.x, 4), round(min_v.y, 4), round(min_v.z, 4)],
        "bbox_max": [round(max_v.x, 4), round(max_v.y, 4), round(max_v.z, 4)],
        "meshes": mesh_info,
        "armatures": arm_info,
        "actions": actions,
    }


def export_glb(filepath: str) -> None:
    """GLB としてエクスポート"""
    bpy.ops.object.select_all(action="SELECT")
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=filepath,
        export_format="GLB",
        use_selection=True,
        export_animation_mode="ACTIONS",
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    report_path = Path(args.report)

    print(f"B-1: Prepare Base Model")
    print(f"  Input: {input_path}")

    # シーンをクリア
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # FBX インポート
    print(f"\n[Step 1] Importing FBX...")
    import_fbx(str(input_path))

    # インポート直後の状態
    before_report = scene_report()
    print(f"  Imported: {before_report['mesh_count']} meshes, "
          f"{before_report['total_vertices']} verts, "
          f"{before_report['armature_count']} armatures, "
          f"{before_report['action_count']} actions")
    print(f"  Dimensions: {before_report['dimensions_m']}")

    # スケール正規化
    print(f"\n[Step 2] Normalizing scale to {TARGET_BODY_LENGTH}m body length...")
    scale_factor = normalize_scale(TARGET_BODY_LENGTH)

    # 原点を足元に設定
    print(f"\n[Step 3] Setting origin to feet...")
    set_origin_to_feet()

    # 正規化後の状態
    after_report = scene_report()
    print(f"  Final dimensions: {after_report['dimensions_m']}")

    # Blend 保存
    print(f"\n[Step 4] Saving .blend...")
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    print(f"  Saved: {output_blend}")

    # GLB エクスポート
    print(f"\n[Step 5] Exporting GLB...")
    export_glb(str(output_glb))
    print(f"  Exported: {output_glb}")

    # レポート出力
    report = {
        "task": "B-1: Prepare Base Model",
        "input": str(input_path),
        "outputs": {
            "blend": str(output_blend),
            "glb": str(output_glb),
        },
        "scale_factor": scale_factor,
        "target_body_length_m": TARGET_BODY_LENGTH,
        "before_normalization": before_report,
        "after_normalization": after_report,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Report: {report_path}")
    print(f"\nDone!")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
