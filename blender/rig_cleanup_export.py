from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a rigged Blender asset and export animated GLB/FBX.")
    parser.add_argument("--input", required=True, help="Input .blend, .glb, .gltf, or .fbx path.")
    parser.add_argument("--output-blend", required=True, help="Output normalized .blend path.")
    parser.add_argument("--output-glb", required=True, help="Output animated GLB path.")
    parser.add_argument("--output-fbx", required=True, help="Output animated FBX path.")
    parser.add_argument("--report", required=True, help="Output JSON report path.")
    parser.add_argument("--target-height", type=float, default=1.0)
    parser.add_argument("--remove-helper-meshes", action="store_true")
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
    raise ValueError(f"Unsupported rigged input extension: {input_path.suffix}")


def set_scene_units() -> None:
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def root_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.parent is None]


def remove_helper_meshes() -> list[str]:
    removed: list[str] = []
    for obj in list(mesh_objects()):
        has_armature_modifier = any(modifier.type == "ARMATURE" for modifier in obj.modifiers)
        if obj.name.lower().startswith("icosphere") and not has_armature_modifier:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    return removed


def world_bbox(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    min_v = Vector((min(point.x for point in points), min(point.y for point in points), min(point.z for point in points)))
    max_v = Vector((max(point.x for point in points), max(point.y for point in points), max(point.z for point in points)))
    return min_v, max_v


def translate_roots(offset: Vector) -> None:
    for obj in root_objects():
        obj.location = obj.location + offset
    bpy.context.view_layer.update()


def scale_roots(scale_factor: float) -> None:
    for obj in root_objects():
        obj.location = obj.location * scale_factor
        obj.scale = obj.scale * scale_factor
    bpy.context.view_layer.update()


def normalize_rig(target_height: float) -> dict:
    meshes = mesh_objects()
    before_min, before_max = world_bbox(meshes)
    before_size = before_max - before_min

    scale_factor = 1.0
    if target_height > 0 and before_size.z > 0:
        scale_factor = target_height / before_size.z
        scale_roots(scale_factor)

    scaled_min, scaled_max = world_bbox(meshes)
    center_x = (scaled_min.x + scaled_max.x) / 2.0
    center_y = (scaled_min.y + scaled_max.y) / 2.0
    translate_roots(Vector((-center_x, -center_y, -scaled_min.z)))

    after_min, after_max = world_bbox(meshes)
    after_size = after_max - after_min
    return {
        "before_bbox_min": list(before_min),
        "before_bbox_max": list(before_max),
        "before_size": list(before_size),
        "scale_factor": scale_factor,
        "after_bbox_min": list(after_min),
        "after_bbox_max": list(after_max),
        "after_size": list(after_size),
    }


def action_report() -> list[dict]:
    actions: list[dict] = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        actions.append(
            {
                "name": action.name,
                "frame_start": float(start),
                "frame_end": float(end),
            }
        )
    return actions


def mesh_report() -> list[dict]:
    meshes: list[dict] = []
    for obj in mesh_objects():
        meshes.append(
            {
                "name": obj.name,
                "vertex_count": len(obj.data.vertices),
                "polygon_count": len(obj.data.polygons),
                "material_count": len(obj.data.materials),
                "modifiers": [modifier.type for modifier in obj.modifiers],
            }
        )
    return meshes


def armature_report() -> list[dict]:
    armatures: list[dict] = []
    for obj in armature_objects():
        armatures.append(
            {
                "name": obj.name,
                "bone_count": len(obj.data.bones),
                "root_bones": [bone.name for bone in obj.data.bones if bone.parent is None],
            }
        )
    return armatures


def export_assets(output_blend: Path, output_glb: Path, output_fbx: Path) -> None:
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_fbx.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB", export_animation_mode="ACTIONS")
    bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
        bake_anim=True,
        bake_anim_use_all_actions=True,
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)

    load_asset(input_path)
    set_scene_units()
    removed = remove_helper_meshes() if args.remove_helper_meshes else []
    normalization = normalize_rig(args.target_height)
    actions = action_report()
    meshes = mesh_report()
    armatures = armature_report()
    export_assets(output_blend, output_glb, output_fbx)

    report = {
        "task": "Task 4: Blender Rig Cleanup and Animation Export",
        "input": str(input_path),
        "outputs": {
            "blend": str(output_blend),
            "glb": str(output_glb),
            "fbx": str(output_fbx),
        },
        "target_height": args.target_height,
        "removed_objects": removed,
        "mesh_count": len(meshes),
        "armature_count": len(armatures),
        "action_count": len(actions),
        "normalization": normalization,
        "meshes": meshes,
        "armatures": armatures,
        "actions": actions,
        "notes": [
            "Normalization was applied to root objects to preserve the armature/mesh relationship.",
            "Mesh transforms were not destructively applied.",
            "A true sleep/lie-down animation is still not present.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved Blend: {output_blend}")
    print(f"Exported GLB: {output_glb}")
    print(f"Exported FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
