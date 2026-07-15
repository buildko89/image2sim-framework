from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Improve the cat visual likeness using calico photos as reference.")
    parser.add_argument("--input", required=True, help="Input shape-pass .blend path.")
    parser.add_argument("--output-blend", required=True, help="Output visual-pass .blend path.")
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


def group_index(mesh: bpy.types.Object, name: str) -> int | None:
    group = mesh.vertex_groups.get(name)
    return group.index if group else None


def vertex_weight(vertex: bpy.types.MeshVertex, index: int | None) -> float:
    if index is None:
        return 0.0
    for group in vertex.groups:
        if group.group == index:
            return group.weight
    return 0.0


def max_weight(vertex: bpy.types.MeshVertex, indices: list[int | None]) -> float:
    return max((vertex_weight(vertex, index) for index in indices), default=0.0)


def create_material(name: str, color: tuple[float, float, float, float], roughness: float = 0.78) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
    return material


def setup_materials(mesh: bpy.types.Object) -> dict[str, int]:
    mesh.data.materials.clear()
    materials = [
        create_material("PhotoCat_White_Longhair", (0.92, 0.88, 0.80, 1.0)),
        create_material("PhotoCat_Warm_Calico", (0.62, 0.32, 0.13, 1.0)),
        create_material("PhotoCat_Dark_Calico", (0.035, 0.030, 0.026, 1.0)),
        create_material("PhotoCat_Cream_Shadow", (0.78, 0.69, 0.55, 1.0)),
        create_material("PhotoCat_Pink_Nose_Ear", (0.86, 0.50, 0.46, 1.0)),
        create_material("PhotoCat_Green_Eyes", (0.42, 0.68, 0.48, 1.0)),
    ]
    for material in materials:
        mesh.data.materials.append(material)
    return {
        "white": 0,
        "brown": 1,
        "black": 2,
        "cream": 3,
        "pink": 4,
        "green": 5,
    }


def polygon_center(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon) -> Vector:
    center = Vector((0.0, 0.0, 0.0))
    for index in polygon.vertices:
        center += mesh.data.vertices[index].co
    return center / max(len(polygon.vertices), 1)


def polygon_group_weight(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon, indices: list[int | None]) -> float:
    weights = []
    for index in polygon.vertices:
        weights.append(max_weight(mesh.data.vertices[index], indices))
    return sum(weights) / max(len(weights), 1)


def normalized(value: float, min_value: float, max_value: float) -> float:
    span = max_value - min_value
    if span <= 0:
        return 0.5
    return max(0.0, min(1.0, (value - min_value) / span))


def assign_photo_calico_pattern(mesh: bpy.types.Object, slots: dict[str, int]) -> dict[str, int]:
    centers = [polygon_center(mesh, polygon) for polygon in mesh.data.polygons]
    min_x = min(center.x for center in centers)
    max_x = max(center.x for center in centers)
    min_y = min(center.y for center in centers)
    max_y = max(center.y for center in centers)
    min_z = min(center.z for center in centers)
    max_z = max(center.z for center in centers)

    head_indices = [group_index(mesh, "Head")]
    ear_indices = [group_index(mesh, f"Ear{index}.{side}") for side in ("L", "R") for index in range(1, 5)]
    tail_indices = [group_index(mesh, f"Tail{index}") for index in range(1, 9)]
    leg_indices = [
        group_index(mesh, name)
        for name in (
            "FrontUpperLeg.L",
            "FrontLowerLeg.L",
            "FrontUpperLeg.R",
            "FrontLowerLeg.R",
            "BackUpperLeg.L",
            "BackLowerLeg.L",
            "BackUpperLeg.R",
            "BackLowerLeg.R",
        )
    ]

    counts = {name: 0 for name in slots}
    for polygon, center in zip(mesh.data.polygons, centers):
        x = normalized(center.x, min_x, max_x)
        y = normalized(center.y, min_y, max_y)
        z = normalized(center.z, min_z, max_z)
        head_w = polygon_group_weight(mesh, polygon, head_indices)
        ear_w = polygon_group_weight(mesh, polygon, ear_indices)
        tail_w = polygon_group_weight(mesh, polygon, tail_indices)
        leg_w = polygon_group_weight(mesh, polygon, leg_indices)

        slot = "white"

        if leg_w > 0.15 and z < 0.45:
            slot = "white"

        # Back/rump calico patches: mostly white cat, with a black saddle and warm brown side patches.
        if 0.52 < y < 0.74 and 0.42 < x < 0.62 and z > 0.42:
            slot = "black"
        if 0.43 < y < 0.78 and (x < 0.34 or x > 0.66) and z > 0.34:
            slot = "brown"
        if 0.32 < y < 0.50 and x < 0.44 and z > 0.46:
            slot = "brown"

        # Face/head: white center, dark left/right cap, warm patch around one cheek.
        if head_w > 0.18:
            slot = "white"
            if z > 0.58 and x < 0.45:
                slot = "black"
            if z > 0.58 and x > 0.58:
                slot = "brown"
            if 0.48 < x < 0.58 and z > 0.70:
                slot = "white"
            if 0.49 < x < 0.62 and y < 0.18 and 0.40 < z < 0.62:
                slot = "brown"

        if ear_w > 0.18:
            slot = "pink" if z < 0.70 else ("black" if x < 0.5 else "brown")

        # Long calico tail with alternating darker bands.
        if tail_w > 0.08:
            band = math.floor(y * 9.0)
            if band % 3 == 0:
                slot = "black"
            elif band % 3 == 1:
                slot = "brown"
            else:
                slot = "cream"

        polygon.material_index = slots[slot]
        counts[slot] += 1
    return counts


def bounds_for_groups(mesh: bpy.types.Object, group_names: list[str]) -> dict[str, list[float]]:
    indices = [group_index(mesh, name) for name in group_names]
    points = [vertex.co.copy() for vertex in mesh.data.vertices if max_weight(vertex, indices) > 0.05]
    if not points:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0], "center": [0.0, 0.0, 0.0]}
    min_v = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    max_v = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    center = (min_v + max_v) / 2.0
    return {"min": list(min_v), "max": list(max_v), "center": list(center)}


def apply_longhair_calico_shape(mesh: bpy.types.Object) -> dict:
    body_indices = [group_index(mesh, name) for name in ("Back", "Torso", "Torso2", "Torso3", "Body")]
    neck_indices = [group_index(mesh, name) for name in ("Neck1", "Neck2", "Neck3")]
    head_indices = [group_index(mesh, "Head")]
    ear_indices = [group_index(mesh, f"Ear{index}.{side}") for side in ("L", "R") for index in range(1, 5)]
    tail_indices = [group_index(mesh, f"Tail{index}") for index in range(1, 9)]
    leg_indices = [
        group_index(mesh, name)
        for name in (
            "FrontUpperLeg.L",
            "FrontLowerLeg.L",
            "FrontUpperLeg.R",
            "FrontLowerLeg.R",
            "BackUpperLeg.L",
            "BackLowerLeg.L",
            "BackUpperLeg.R",
            "BackLowerLeg.R",
        )
    ]

    before = {
        "body": bounds_for_groups(mesh, ["Back", "Torso", "Torso2", "Torso3", "Body"]),
        "head": bounds_for_groups(mesh, ["Head"]),
        "tail": bounds_for_groups(mesh, [f"Tail{index}" for index in range(1, 9)]),
        "ears": bounds_for_groups(mesh, [f"Ear{index}.{side}" for side in ("L", "R") for index in range(1, 5)]),
    }
    tail_start_y = before["tail"]["min"][1]
    tail_center_z = before["tail"]["center"][2]
    head_center_y = before["head"]["center"][1]

    counts = {"body": 0, "neck": 0, "head": 0, "ears": 0, "tail": 0, "legs": 0}
    for vertex in mesh.data.vertices:
        co = vertex.co
        body_w = max_weight(vertex, body_indices)
        neck_w = max_weight(vertex, neck_indices)
        head_w = max_weight(vertex, head_indices)
        ear_w = max_weight(vertex, ear_indices)
        tail_w = max_weight(vertex, tail_indices)
        leg_w = max_weight(vertex, leg_indices)

        if body_w > 0.03:
            influence = min(body_w, 1.0)
            # Long-haired body: wider and lower visually, without moving bones.
            co.x *= 1.0 + 0.20 * influence
            co.z -= 0.045 * influence
            co.y *= 1.0 - 0.045 * influence
            counts["body"] += 1

        if neck_w > 0.03:
            influence = min(neck_w, 1.0)
            co.x *= 1.0 + 0.18 * influence
            co.z -= 0.050 * influence
            co.y += 0.025 * influence
            counts["neck"] += 1

        if head_w > 0.03:
            influence = min(head_w, 1.0)
            co.x *= 1.0 + 0.14 * influence
            co.z *= 1.0 - 0.035 * influence
            if co.y < head_center_y:
                co.y = head_center_y + (co.y - head_center_y) * (1.0 - 0.24 * influence)
            counts["head"] += 1

        if ear_w > 0.03:
            influence = min(ear_w, 1.0)
            side = 1.0 if co.x >= 0.0 else -1.0
            co.x *= 1.0 - 0.18 * influence
            co.x += side * 0.012 * influence
            co.z -= 0.22 * influence
            co.y += 0.055 * influence
            counts["ears"] += 1

        if tail_w > 0.03:
            influence = min(tail_w, 1.0)
            tail_t = max(0.0, min(1.0, (co.y - tail_start_y) / 2.2))
            # The reference cat has a long plume tail, so undo the previous short-tail bias.
            co.y = tail_start_y + (co.y - tail_start_y) * (1.0 + 0.18 * influence)
            plume = 1.0 + (0.26 + 0.16 * tail_t) * influence
            co.x *= plume
            co.z = tail_center_z + (co.z - tail_center_z) * plume
            counts["tail"] += 1

        if leg_w > 0.03:
            influence = min(leg_w, 1.0)
            # Make legs read shorter under long fur, while keeping feet near the floor.
            if co.z > 0.20:
                co.z -= 0.035 * influence
            co.x *= 1.0 + 0.045 * influence
            counts["legs"] += 1

    mesh.data.update()
    after = {
        "body": bounds_for_groups(mesh, ["Back", "Torso", "Torso2", "Torso3", "Body"]),
        "head": bounds_for_groups(mesh, ["Head"]),
        "tail": bounds_for_groups(mesh, [f"Tail{index}" for index in range(1, 9)]),
        "ears": bounds_for_groups(mesh, [f"Ear{index}.{side}" for side in ("L", "R") for index in range(1, 5)]),
    }
    return {"counts": counts, "before": before, "after": after}


def action_report() -> list[dict]:
    actions = []
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
    bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB", use_selection=True, export_animation_mode="ACTIONS")
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

    shape_reports = {}
    material_reports = {}
    for mesh in skinned_mesh_objects():
        shape_reports[mesh.name] = apply_longhair_calico_shape(mesh)
        slots = setup_materials(mesh)
        material_reports[mesh.name] = assign_photo_calico_pattern(mesh, slots)

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 5.8: Photo-Based Godot Visual Improvement Pass",
        "input": str(input_path),
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "reference_summary": {
            "cat": "long-haired calico; mostly white body; black/brown head cap and back/rump patches; long fluffy banded tail; round face; short muzzle",
            "source_images": [
                "input/selected_photos/reference_side_right_body_1698975320501.jpg",
                "input/selected_photos/reference_front_face_1763363798733.jpg",
                "input/selected_photos/reference_back_top_tail_1755598074234.jpg",
                "input/selected_photos/reference_side_standing_pattern_1713434749448.jpg",
            ],
        },
        "shape_reports": shape_reports,
        "material_polygon_counts": material_reports,
        "mesh_count": len(mesh_report()),
        "armature_count": len(armature_objects()),
        "action_count": len(action_report()),
        "meshes": mesh_report(),
        "actions": action_report(),
        "notes": [
            "This pass intentionally favors photo likeness over the previous generic cat pass.",
            "The tail is made longer and fuller because the source cat has a plume tail.",
            "The base rig and animation actions are preserved.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved visual Blend: {output_blend}")
    print(f"Exported visual GLB: {output_glb}")
    print(f"Exported visual FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
