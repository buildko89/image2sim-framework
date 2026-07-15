from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare and inspect a rigged base model.")
    parser.add_argument("--input", required=True, help="Input .blend, .glb, .gltf, or .fbx path.")
    parser.add_argument("--output-blend", required=True, help="Output Blender file path.")
    parser.add_argument("--output-glb", required=True, help="Output animated GLB path.")
    parser.add_argument("--output-fbx", required=True, help="Output animated FBX path.")
    parser.add_argument("--report", required=True, help="Output JSON report path.")
    parser.add_argument("--asset-name", default="cat_base_rigged")
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    return parser.parse_args(argv)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def load_asset(input_path: Path) -> None:
    suffix = input_path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(input_path))
        return

    clear_scene()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(input_path))
        return
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(input_path))
        return
    raise ValueError(f"Unsupported rigged asset extension: {input_path.suffix}")


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def world_bbox(objects: list[bpy.types.Object]) -> tuple[list[float], list[float], list[float]]:
    points: list[Vector] = []
    for obj in objects:
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    min_v = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_v = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    size = max_v - min_v
    return list(min_v), list(max_v), list(size)


def collect_actions() -> list[dict]:
    actions: list[dict] = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        fcurves = getattr(action, "fcurves", None)
        fcurve_count = len(fcurves) if fcurves is not None else None
        actions.append(
            {
                "name": action.name,
                "frame_start": float(start),
                "frame_end": float(end),
                "fcurve_count": fcurve_count,
            }
        )
    return actions


def collect_armatures() -> list[dict]:
    result: list[dict] = []
    for obj in armature_objects():
        result.append(
            {
                "name": obj.name,
                "bone_count": len(obj.data.bones),
                "root_bones": [bone.name for bone in obj.data.bones if bone.parent is None],
            }
        )
    return result


def collect_meshes() -> list[dict]:
    result: list[dict] = []
    for obj in mesh_objects():
        modifiers = [modifier.type for modifier in obj.modifiers]
        result.append(
            {
                "name": obj.name,
                "vertex_count": len(obj.data.vertices),
                "polygon_count": len(obj.data.polygons),
                "material_count": len(obj.data.materials),
                "modifiers": modifiers,
            }
        )
    return result


def set_scene_metadata(asset_name: str) -> None:
    bpy.context.scene.name = asset_name
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def save_and_export(output_blend: Path, output_glb: Path, output_fbx: Path) -> None:
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_fbx.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB")
    bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        bake_anim=True,
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)

    if not input_path.exists():
        raise FileNotFoundError(f"Input rigged asset not found: {input_path}")

    load_asset(input_path)
    set_scene_metadata(args.asset_name)

    meshes = mesh_objects()
    bbox_min, bbox_max, bbox_size = world_bbox(meshes)
    actions = collect_actions()
    armatures = collect_armatures()
    mesh_info = collect_meshes()

    save_and_export(output_blend, output_glb, output_fbx)

    report = {
        "task": "Task 3E: Rigged Cat Base Model Preparation",
        "input": str(input_path),
        "source": "Quaternius Ultimate Animated Animal Pack",
        "license": "CC0 1.0 Universal",
        "selected_base": input_path.stem,
        "outputs": {
            "blend": str(output_blend),
            "glb": str(output_glb),
            "fbx": str(output_fbx),
        },
        "mesh_count": len(meshes),
        "armature_count": len(armatures),
        "action_count": len(actions),
        "bbox_min": bbox_min,
        "bbox_max": bbox_max,
        "bbox_size": bbox_size,
        "armatures": armatures,
        "meshes": mesh_info,
        "actions": actions,
        "notes": [
            "This is a CC0 animated quadruped validation asset, not the final cat appearance.",
            "Task 3F should adapt proportions/materials toward the target cat without breaking the rig.",
            "Sleep or lie-down animation is not present in the source pack and remains for Task 3G.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"Saved Blend: {output_blend}")
    print(f"Exported GLB: {output_glb}")
    print(f"Exported FBX: {output_fbx}")
    print(f"Report: {report_path}")
    print(f"Actions: {len(actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
