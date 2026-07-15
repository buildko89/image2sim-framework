from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a conservative cat-like shape pass to the rigged model.")
    parser.add_argument("--input", required=True, help="Input cat appearance .blend path.")
    parser.add_argument("--output-blend", required=True, help="Output shape-pass .blend path.")
    parser.add_argument("--output-glb", required=True, help="Output animated GLB path.")
    parser.add_argument("--output-fbx", required=True, help="Output animated FBX path.")
    parser.add_argument("--report", required=True, help="Output JSON report path.")
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    return parser.parse_args(argv)


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def skinned_mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in mesh_objects() if any(modifier.type == "ARMATURE" for modifier in obj.modifiers)]


def main_rig_objects() -> list[bpy.types.Object]:
    result: list[bpy.types.Object] = []
    seen: set[str] = set()
    for obj in skinned_mesh_objects() + armature_objects():
        if obj.name not in seen:
            result.append(obj)
            seen.add(obj.name)
    return result


def vertex_group_index(mesh: bpy.types.Object, name: str) -> int | None:
    group = mesh.vertex_groups.get(name)
    return group.index if group else None


def vertex_weight(vertex: bpy.types.MeshVertex, group_index: int | None) -> float:
    if group_index is None:
        return 0.0
    for group in vertex.groups:
        if group.group == group_index:
            return group.weight
    return 0.0


def max_weight(vertex: bpy.types.MeshVertex, groups: list[int | None]) -> float:
    return max((vertex_weight(vertex, group) for group in groups), default=0.0)


def weighted_points(mesh: bpy.types.Object, group_names: list[str], min_weight: float = 0.05) -> list[Vector]:
    group_indices = [vertex_group_index(mesh, name) for name in group_names]
    points: list[Vector] = []
    for vertex in mesh.data.vertices:
        if max_weight(vertex, group_indices) >= min_weight:
            points.append(vertex.co.copy())
    return points


def bounds(points: list[Vector]) -> dict[str, list[float]]:
    if not points:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0], "center": [0.0, 0.0, 0.0]}
    min_v = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_v = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (min_v + max_v) / 2.0
    return {"min": list(min_v), "max": list(max_v), "center": list(center)}


def apply_shape_pass(mesh: bpy.types.Object) -> dict:
    tail_groups = [f"Tail{index}" for index in range(1, 9)]
    ear_groups = [f"Ear{index}.{side}" for side in ("L", "R") for index in range(1, 5)]
    head_group = ["Head"]
    neck_groups = ["Neck1", "Neck2", "Neck3"]

    tail_indices = [vertex_group_index(mesh, name) for name in tail_groups]
    ear_indices = [vertex_group_index(mesh, name) for name in ear_groups]
    head_indices = [vertex_group_index(mesh, name) for name in head_group]
    neck_indices = [vertex_group_index(mesh, name) for name in neck_groups]

    tail_before = bounds(weighted_points(mesh, tail_groups))
    ear_before = bounds(weighted_points(mesh, ear_groups))
    head_before = bounds(weighted_points(mesh, head_group))

    tail_start_y = tail_before["min"][1]
    tail_center_z = tail_before["center"][2]
    head_center_y = head_before["center"][1]

    counts = {
        "tail_vertices": 0,
        "ear_vertices": 0,
        "head_vertices": 0,
        "neck_vertices": 0,
    }

    for vertex in mesh.data.vertices:
        co = vertex.co
        tail_w = max_weight(vertex, tail_indices)
        ear_w = max_weight(vertex, ear_indices)
        head_w = max_weight(vertex, head_indices)
        neck_w = max_weight(vertex, neck_indices)

        if tail_w > 0.02:
            influence = min(tail_w, 1.0)
            tail_t = max(0.0, min(1.0, (co.y - tail_start_y) / 2.4))
            length_factor = 1.0 - (0.30 * influence)
            radial_factor = 1.0 - ((0.34 + 0.14 * tail_t) * influence)
            co.y = tail_start_y + (co.y - tail_start_y) * length_factor
            co.x *= radial_factor
            co.z = tail_center_z + (co.z - tail_center_z) * radial_factor
            counts["tail_vertices"] += 1

        if ear_w > 0.02:
            influence = min(ear_w, 1.0)
            side_sign = 1.0 if co.x >= 0.0 else -1.0
            co.x *= 1.0 - (0.12 * influence)
            co.y += 0.035 * influence
            co.z -= 0.16 * influence
            # Keep a small outward point so the ears remain readable after shrinking.
            co.x += side_sign * 0.018 * influence
            counts["ear_vertices"] += 1

        if head_w > 0.02 and co.y < head_center_y:
            influence = min(head_w, 1.0)
            co.y = head_center_y + (co.y - head_center_y) * (1.0 - 0.16 * influence)
            co.x *= 1.0 + 0.035 * influence
            counts["head_vertices"] += 1

        if neck_w > 0.02:
            influence = min(neck_w, 1.0)
            co.z -= 0.035 * influence
            counts["neck_vertices"] += 1

    mesh.data.update()

    return {
        "mesh": mesh.name,
        "counts": counts,
        "tail_before": tail_before,
        "tail_after": bounds(weighted_points(mesh, tail_groups)),
        "ear_before": ear_before,
        "ear_after": bounds(weighted_points(mesh, ear_groups)),
        "head_before": head_before,
        "head_after": bounds(weighted_points(mesh, head_group)),
        "notes": [
            "Tail vertices were shortened and narrowed using existing Tail vertex groups.",
            "Ear vertices were lowered and slightly narrowed using existing Ear vertex groups.",
            "Head front vertices were gently compressed to reduce the long fox muzzle impression.",
            "Vertex groups, armature modifiers, and animation actions were preserved.",
        ],
    }


def action_report() -> list[dict]:
    actions: list[dict] = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        actions.append({"name": action.name, "frame_start": float(start), "frame_end": float(end)})
    return actions


def mesh_report() -> list[dict]:
    return [
        {
            "name": obj.name,
            "vertex_count": len(obj.data.vertices),
            "polygon_count": len(obj.data.polygons),
            "material_count": len(obj.data.materials),
            "modifiers": [modifier.type for modifier in obj.modifiers],
        }
        for obj in mesh_objects()
    ]


def export_selected(output_glb: Path, output_fbx: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in main_rig_objects():
        obj.select_set(True)
    skinned = skinned_mesh_objects()
    armatures = armature_objects()
    if skinned:
        bpy.context.view_layer.objects.active = skinned[0]
    elif armatures:
        bpy.context.view_layer.objects.active = armatures[0]

    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_fbx.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(output_glb),
        export_format="GLB",
        use_selection=True,
        export_animation_mode="ACTIONS",
    )
    bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        use_selection=True,
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

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    bpy.context.scene.unit_settings.system = "METRIC"

    skinned = skinned_mesh_objects()
    if not skinned:
        raise RuntimeError("No skinned mesh found for shape pass.")
    shape_reports = [apply_shape_pass(mesh) for mesh in skinned]

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 5.6: Conservative Cat Shape Pass",
        "input": str(input_path),
        "outputs": {
            "blend": str(output_blend),
            "glb": str(output_glb),
            "fbx": str(output_fbx),
        },
        "shape_reports": shape_reports,
        "mesh_count": len(mesh_report()),
        "armature_count": len(armature_objects()),
        "action_count": len(action_report()),
        "meshes": mesh_report(),
        "actions": action_report(),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved shape Blend: {output_blend}")
    print(f"Exported shape GLB: {output_glb}")
    print(f"Exported shape FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
