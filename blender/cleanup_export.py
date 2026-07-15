from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a Blender asset and export GLB/FBX.")
    parser.add_argument("--input", required=True, help="Input .blend, .glb, .gltf, .fbx, or .obj path.")
    parser.add_argument("--output-glb", required=True, help="Output GLB path.")
    parser.add_argument("--output-fbx", required=True, help="Output FBX path.")
    parser.add_argument("--report", required=True, help="Output JSON report path.")
    parser.add_argument("--target-height", type=float, default=1.0)
    parser.add_argument("--remove-reference-objects", action="store_true")
    parser.add_argument("--apply-transforms", action="store_true")
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
    if suffix == ".obj":
        bpy.ops.wm.obj_import(filepath=str(input_path))
        return
    raise ValueError(f"Unsupported input asset extension: {input_path.suffix}")


def remove_reference_objects() -> list[str]:
    removed: list[str] = []
    for obj in list(bpy.context.scene.objects):
        is_reference = obj.get("source_role") in {"mask", "selected", "reference"} or obj.name.startswith("reference_")
        is_image_empty = obj.type == "EMPTY" and obj.empty_display_type == "IMAGE"
        if is_reference or is_image_empty:
            removed.append(obj.name)
            bpy.data.objects.remove(obj, do_unlink=True)
    return removed


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def world_bbox(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        points.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not points:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    min_v = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_v = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return min_v, max_v


def normalize(objects: list[bpy.types.Object], target_height: float) -> dict:
    before_min, before_max = world_bbox(objects)
    before_size = before_max - before_min

    scale_factor = 1.0
    if target_height > 0 and before_size.z > 0:
        scale_factor = target_height / before_size.z
        for obj in objects:
            obj.scale = obj.scale * scale_factor
        bpy.context.view_layer.update()

    scaled_min, scaled_max = world_bbox(objects)
    center_x = (scaled_min.x + scaled_max.x) / 2.0
    center_y = (scaled_min.y + scaled_max.y) / 2.0
    offset = Vector((-center_x, -center_y, -scaled_min.z))
    for obj in objects:
        obj.location = obj.location + offset
    bpy.context.view_layer.update()

    after_min, after_max = world_bbox(objects)
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


def apply_transforms(objects: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        obj.select_set(False)


def set_scene_units() -> None:
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1.0


def export_assets(output_glb: Path, output_fbx: Path) -> None:
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_fbx.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB")
    bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_ALL",
    )


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)

    load_asset(input_path)
    set_scene_units()
    removed = remove_reference_objects() if args.remove_reference_objects else []
    meshes = mesh_objects()
    metrics = normalize(meshes, args.target_height) if meshes else {}
    if args.apply_transforms and meshes:
        apply_transforms(meshes)
    export_assets(output_glb, output_fbx)

    report = {
        "input": str(input_path),
        "output_glb": str(output_glb),
        "output_fbx": str(output_fbx),
        "target_height": args.target_height,
        "mesh_count": len(meshes),
        "removed_objects": removed,
        "normalization": metrics,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Exported GLB: {output_glb}")
    print(f"Exported FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
