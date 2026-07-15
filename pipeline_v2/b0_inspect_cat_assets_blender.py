"""B-0: Cat Model Asset Inspection

Blender CLI スクリプト。input/cat/ と input/cat2/ 内の全3Dモデルを
ロードし、リグ・メッシュ・アニメーション情報を抽出してJSONレポートを出力する。

使用方法:
  blender --background --python pipeline_v2/b0_inspect_cat_assets_blender.py -- \
    --output output_v2/reports/b0_asset_inspection.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect cat model assets in Blender.")
    parser.add_argument("--output", required=True, help="Output JSON report path")
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


def clear_scene() -> None:
    """全オブジェクトとデータを削除してシーンをリセットする。"""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_model(filepath: Path) -> bool:
    """モデルをインポートする。成功したら True を返す。"""
    suffix = filepath.suffix.lower()
    try:
        if suffix == ".fbx":
            bpy.ops.import_scene.fbx(filepath=str(filepath))
            return True
        elif suffix in {".glb", ".gltf"}:
            bpy.ops.import_scene.gltf(filepath=str(filepath))
            return True
        elif suffix == ".blend":
            # .blend は直接開くと他のデータが消えるため、Append で全オブジェクトをリンク
            with bpy.data.libraries.load(str(filepath), link=False) as (data_from, data_to):
                data_to.objects = data_from.objects
            for obj in data_to.objects:
                if obj is not None:
                    bpy.context.collection.objects.link(obj)
            return True
        elif suffix == ".stl":
            bpy.ops.wm.stl_import(filepath=str(filepath))
            return True
    except Exception as e:
        print(f"  Import failed: {e}")
        return False
    return False


def inspect_scene() -> dict:
    """現在のシーンからモデル情報を抽出する。"""
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]

    # メッシュ情報
    mesh_info = []
    total_vertices = 0
    total_polygons = 0
    for mesh in meshes:
        verts = len(mesh.data.vertices)
        polys = len(mesh.data.polygons)
        total_vertices += verts
        total_polygons += polys

        # UV と マテリアル
        uv_layers = [layer.name for layer in mesh.data.uv_layers]
        materials = [slot.material.name if slot.material else "(empty)" for slot in mesh.material_slots]

        # モディファイア
        modifiers = [{"name": mod.name, "type": mod.type} for mod in mesh.modifiers]

        # バウンディングボックス
        bbox = mesh.bound_box
        world_corners = [mesh.matrix_world @ Vector(corner) for corner in bbox]
        min_corner = [min(c[i] for c in world_corners) for i in range(3)]
        max_corner = [max(c[i] for c in world_corners) for i in range(3)]
        dimensions = [max_corner[i] - min_corner[i] for i in range(3)]

        # Shape Keys (Morph Targets)
        shape_keys = []
        if mesh.data.shape_keys:
            shape_keys = [kb.name for kb in mesh.data.shape_keys.key_blocks]

        mesh_info.append({
            "name": mesh.name,
            "vertices": verts,
            "polygons": polys,
            "uv_layers": uv_layers,
            "materials": materials,
            "modifiers": modifiers,
            "shape_keys": shape_keys,
            "dimensions_m": [round(d, 4) for d in dimensions],
            "has_armature_modifier": any(mod.type == "ARMATURE" for mod in mesh.modifiers),
        })

    # アーマチュア情報
    armature_info = []
    for arm in armatures:
        bones = []
        if arm.data:
            bones = [bone.name for bone in arm.data.bones]
        armature_info.append({
            "name": arm.name,
            "bone_count": len(bones),
            "bone_names": bones[:20],  # 最大20個まで（レポートサイズ制限）
            "bone_names_truncated": len(bones) > 20,
        })

    # アニメーション情報
    action_info = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        action_info.append({
            "name": action.name,
            "frame_start": float(start),
            "frame_end": float(end),
            "frame_count": int(end - start + 1),
        })

    return {
        "mesh_count": len(meshes),
        "total_vertices": total_vertices,
        "total_polygons": total_polygons,
        "armature_count": len(armatures),
        "action_count": len(action_info),
        "has_rig": len(armatures) > 0,
        "has_animations": len(action_info) > 0,
        "has_shape_keys": any(m.get("shape_keys") for m in mesh_info),
        "meshes": mesh_info,
        "armatures": armature_info,
        "actions": action_info,
    }


def find_models(repo_root: Path) -> list[dict]:
    """input/cat/ と input/cat2/ 配下のモデルファイルを再帰的に検索する。"""
    model_extensions = {".fbx", ".glb", ".gltf", ".blend", ".stl"}
    search_dirs = [
        repo_root / "input" / "cat",
        repo_root / "input" / "cat2",
    ]

    models = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for path in sorted(search_dir.rglob("*")):
            if path.suffix.lower() in model_extensions and path.is_file():
                # .blend1 等のバックアップファイルを除外
                if path.suffix.lower() == ".blend" and "blend1" in path.name:
                    continue
                models.append({
                    "path": str(path),
                    "relative_path": str(path.relative_to(repo_root)),
                    "filename": path.name,
                    "format": path.suffix.lower(),
                    "size_mb": round(path.stat().st_size / (1024 * 1024), 2),
                })
    return models


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)

    # リポジトリルートを推定
    repo_root = Path(__file__).resolve().parents[1]

    # モデルファイルを検索
    models = find_models(repo_root)
    print(f"Found {len(models)} model files to inspect.")

    # 各モデルをインポートして検査
    results = []
    for i, model in enumerate(models):
        print(f"\n[{i+1}/{len(models)}] Inspecting: {model['filename']} ({model['format']}, {model['size_mb']} MB)")

        clear_scene()
        success = import_model(Path(model["path"]))

        if success:
            scene_info = inspect_scene()
            model["inspection"] = scene_info
            model["status"] = "ok"
            print(f"  → Meshes: {scene_info['mesh_count']}, "
                  f"Vertices: {scene_info['total_vertices']}, "
                  f"Rig: {'YES' if scene_info['has_rig'] else 'NO'}, "
                  f"Animations: {scene_info['action_count']}, "
                  f"ShapeKeys: {'YES' if scene_info['has_shape_keys'] else 'NO'}")
        else:
            model["inspection"] = None
            model["status"] = "import_failed"
            print(f"  → FAILED to import")

        results.append(model)

    # ベストモデル候補の判定 (リグ + アニメーション があるモデルを優先)
    candidates = []
    for r in results:
        if r["status"] != "ok" or r["inspection"] is None:
            continue
        info = r["inspection"]
        score = 0
        if info["has_rig"]:
            score += 100
        if info["has_animations"]:
            score += 50
        score += min(info["action_count"] * 10, 50)  # アニメーション数に応じたボーナス
        if info["has_shape_keys"]:
            score += 20
        if info["total_vertices"] > 500:
            score += 10  # ある程度のメッシュ密度

        candidates.append({
            "filename": r["filename"],
            "relative_path": r["relative_path"],
            "score": score,
            "has_rig": info["has_rig"],
            "has_animations": info["has_animations"],
            "action_count": info["action_count"],
            "total_vertices": info["total_vertices"],
            "total_polygons": info["total_polygons"],
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # レポート出力
    report = {
        "task": "B-0: Cat Model Asset Inspection",
        "total_models_found": len(models),
        "models": results,
        "ranking": candidates[:10],
        "recommended": candidates[0] if candidates else None,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Report saved: {output_path}")
    print(f"\nTop 5 candidates:")
    for i, c in enumerate(candidates[:5]):
        print(f"  {i+1}. {c['filename']} (score={c['score']}, rig={c['has_rig']}, "
              f"anims={c['action_count']}, verts={c['total_vertices']})")
    if candidates:
        print(f"\n→ Recommended: {candidates[0]['filename']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
