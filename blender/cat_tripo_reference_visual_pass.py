from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply a conservative Tripo v2.5 reference visual pass to the rigged cat.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--tripo-reference", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--output-fbx", required=True)
    parser.add_argument("--report", required=True)
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


def main_mesh() -> bpy.types.Object:
    candidates = [obj for obj in skinned_mesh_objects() if "Fur_Shell" not in obj.name]
    if not candidates:
        raise RuntimeError("No main skinned mesh found.")
    return candidates[0]


def fur_shell_meshes() -> list[bpy.types.Object]:
    return [obj for obj in skinned_mesh_objects() if "Fur_Shell" in obj.name]


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


def polygon_center(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon) -> Vector:
    center = Vector((0.0, 0.0, 0.0))
    for index in polygon.vertices:
        center += mesh.data.vertices[index].co
    return center / max(len(polygon.vertices), 1)


def polygon_group_weight(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon, indices: list[int | None]) -> float:
    weights = [max_weight(mesh.data.vertices[index], indices) for index in polygon.vertices]
    return sum(weights) / max(len(weights), 1)


def normalized(value: float, min_value: float, max_value: float) -> float:
    span = max_value - min_value
    if span <= 0:
        return 0.5
    return max(0.0, min(1.0, (value - min_value) / span))


def set_material_color(material: bpy.types.Material, color: tuple[float, float, float, float], roughness: float = 0.92) -> list[float]:
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    before: list[float] = []
    if bsdf:
        before = list(bsdf.inputs["Base Color"].default_value)
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
    return before


def retune_materials(meshes: list[bpy.types.Object]) -> dict[str, dict[str, list[float]]]:
    target_colors = {
        "PhotoCat_White_Longhair": (0.940, 0.900, 0.815, 1.0),
        "PhotoCat_Warm_Calico": (0.740, 0.370, 0.115, 1.0),
        "PhotoCat_Dark_Calico": (0.085, 0.060, 0.043, 1.0),
        "PhotoCat_Cream_Shadow": (0.630, 0.555, 0.440, 1.0),
        "PhotoCat_Pink_Nose_Ear": (0.840, 0.515, 0.475, 1.0),
        "PhotoCat_Green_Eyes": (0.400, 0.620, 0.430, 1.0),
    }
    report: dict[str, dict[str, list[float]]] = {}
    for mesh in meshes:
        for material in mesh.data.materials:
            if material.name not in target_colors:
                continue
            before = set_material_color(material, target_colors[material.name])
            report[material.name] = {"before": before, "after": list(target_colors[material.name])}
    return report


def material_slots(mesh: bpy.types.Object) -> dict[str, int]:
    names = {material.name: index for index, material in enumerate(mesh.data.materials)}
    return {
        "white": names.get("PhotoCat_White_Longhair", 0),
        "brown": names.get("PhotoCat_Warm_Calico", 1),
        "black": names.get("PhotoCat_Dark_Calico", 2),
        "cream": names.get("PhotoCat_Cream_Shadow", 3),
        "pink": names.get("PhotoCat_Pink_Nose_Ear", names.get("PhotoCat_White_Longhair", 0)),
        "green": names.get("PhotoCat_Green_Eyes", names.get("PhotoCat_White_Longhair", 0)),
    }


def assign_tripo_reference_pattern(mesh: bpy.types.Object) -> dict[str, int]:
    slots = material_slots(mesh)
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

        # Body: white base with a dark top saddle and warmer side patches.
        if leg_w < 0.12 and 0.49 < y < 0.75 and 0.42 < x < 0.63 and z > 0.46:
            slot = "black"
        if leg_w < 0.12 and 0.34 < y < 0.78 and (x < 0.35 or x > 0.65) and 0.42 < z < 0.78:
            slot = "brown"
        if leg_w < 0.12 and 0.27 < y < 0.52 and x < 0.48 and z > 0.56:
            slot = "brown"
        if leg_w < 0.12 and 0.20 < y < 0.42 and 0.44 < x < 0.65 and z > 0.62:
            slot = "cream"

        # Chest and belly should read as long warm white fur rather than solid patch color.
        if z < 0.35 and 0.24 < y < 0.74 and leg_w < 0.15:
            slot = "cream"
        if 0.18 < y < 0.38 and z < 0.55:
            slot = "white"

        # Keep feet and visible lower/upper legs mostly white or cream, matching the real side photos.
        if leg_w > 0.16:
            slot = "cream" if 0.42 < z < 0.64 and y > 0.54 else "white"
        if leg_w > 0.12 and z < 0.50:
            slot = "white"

        if head_w > 0.18:
            slot = "white"
            if z > 0.57 and x < 0.45:
                slot = "black"
            if z > 0.55 and x > 0.57:
                slot = "brown"
            if 0.47 < x < 0.59 and z > 0.62:
                slot = "white"
            if 0.42 < x < 0.56 and y < 0.20 and 0.38 < z < 0.57:
                slot = "cream"

        if ear_w > 0.18:
            slot = "pink" if z < 0.70 else ("black" if x < 0.5 else "brown")

        # Keep tail banded, but avoid copying Tripo's exaggerated tail shape.
        if tail_w > 0.08:
            band = math.floor(y * 8.0)
            if band % 3 == 0:
                slot = "black"
            elif band % 3 == 1:
                slot = "brown"
            else:
                slot = "cream"

        polygon.material_index = slots[slot]
        counts[slot] += 1

    mesh.data.update()
    return counts


def enhance_fur_shell(mesh: bpy.types.Object) -> dict[str, int]:
    body_indices = [group_index(mesh, name) for name in ("Body", "Back", "Torso", "Torso2", "Torso3")]
    chest_indices = [group_index(mesh, name) for name in ("Neck1", "Neck2", "Neck3")]
    shoulder_indices = [group_index(mesh, name) for name in ("FrontShoulder.L", "FrontShoulder.R", "BackShoulder.L", "BackShoulder.R")]
    upper_leg_indices = [group_index(mesh, name) for name in ("FrontUpperLeg.L", "FrontUpperLeg.R", "BackUpperLeg.L", "BackUpperLeg.R")]
    head_indices = [group_index(mesh, "Head")]

    counts = {"body": 0, "chest": 0, "shoulder": 0, "upper_leg": 0, "head": 0}
    for vertex in mesh.data.vertices:
        body_w = max_weight(vertex, body_indices)
        chest_w = max_weight(vertex, chest_indices)
        shoulder_w = max_weight(vertex, shoulder_indices)
        upper_leg_w = max_weight(vertex, upper_leg_indices)
        head_w = max_weight(vertex, head_indices)

        if body_w > 0.04:
            influence = min(body_w, 1.0)
            vertex.co += vertex.normal * 0.022 * influence
            vertex.co.z -= 0.050 * influence
            vertex.co.x *= 1.0 + 0.018 * influence
            counts["body"] += 1

        if chest_w > 0.04:
            influence = min(chest_w, 1.0)
            vertex.co += vertex.normal * 0.030 * influence
            vertex.co.z -= 0.075 * influence
            vertex.co.x *= 1.0 + 0.030 * influence
            counts["chest"] += 1

        if shoulder_w > 0.04:
            influence = min(shoulder_w, 1.0)
            vertex.co += vertex.normal * 0.020 * influence
            vertex.co.z -= 0.045 * influence
            counts["shoulder"] += 1

        if upper_leg_w > 0.04:
            influence = min(upper_leg_w, 1.0)
            vertex.co.z -= 0.038 * influence
            vertex.co.x *= 1.0 + 0.025 * influence
            counts["upper_leg"] += 1

        if head_w > 0.04:
            influence = min(head_w, 1.0)
            vertex.co += vertex.normal * 0.010 * influence
            vertex.co.x *= 1.0 + 0.012 * influence
            counts["head"] += 1

    mesh.data.update()
    return counts


def import_tripo_reference(path: Path, anchor: bpy.types.Object) -> list[str]:
    if not path.exists():
        return []
    before = {obj.name for obj in bpy.context.scene.objects}
    bpy.ops.import_scene.gltf(filepath=str(path))
    imported = [obj for obj in bpy.context.scene.objects if obj.name not in before]
    if not imported:
        return []
    for obj in imported:
        obj.name = f"TripoV25_Reference_{obj.name}"
        obj.hide_render = False
        obj.hide_viewport = False

    min_x = min((anchor.matrix_world @ Vector(corner)).x for corner in anchor.bound_box)
    for obj in imported:
        obj.location.x += min_x - 2.2
        obj.location.z += 0.1
    return [obj.name for obj in imported]


def action_report() -> list[dict]:
    result = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        result.append({"name": action.name, "frame_start": float(start), "frame_end": float(end)})
    return result


def mesh_report() -> list[dict]:
    return [
        {
            "name": obj.name,
            "vertex_count": len(obj.data.vertices),
            "polygon_count": len(obj.data.polygons),
            "material_count": len(obj.data.materials),
            "modifiers": [modifier.type for modifier in obj.modifiers],
            "skinned": any(modifier.type == "ARMATURE" for modifier in obj.modifiers),
        }
        for obj in mesh_objects()
    ]


def export_selected(output_glb: Path, output_fbx: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in skinned_mesh_objects() + armature_objects():
        obj.select_set(True)
    active = main_mesh()
    bpy.context.view_layer.objects.active = active
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
    tripo_reference = Path(args.tripo_reference)
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    bpy.context.scene.unit_settings.system = "METRIC"

    main = main_mesh()
    shells = fur_shell_meshes()
    skinned = [main] + shells

    material_report = retune_materials(skinned)
    pattern_reports = {mesh.name: assign_tripo_reference_pattern(mesh) for mesh in skinned}
    shell_reports = {mesh.name: enhance_fur_shell(mesh) for mesh in shells}
    tripo_objects = import_tripo_reference(tripo_reference, main)

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 6.3: Tripo Reference Visual Pass",
        "input": str(input_path),
        "tripo_reference": str(tripo_reference),
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "main_mesh": main.name,
        "fur_shells": [mesh.name for mesh in shells],
        "tripo_reference_objects_in_blend_only": tripo_objects,
        "material_report": material_report,
        "pattern_reports": pattern_reports,
        "fur_shell_enhancement": shell_reports,
        "mesh_count": len(mesh_report()),
        "armature_count": len(armature_objects()),
        "action_count": len(action_report()),
        "meshes": mesh_report(),
        "actions": action_report(),
        "notes": [
            "Tripo v2.5 is imported into the Blend as a visual reference only and excluded from GLB/FBX export.",
            "The rigged model keeps its armature, skinning, and animation actions.",
            "This pass changes flat material colors, polygon material assignment, and fur-shell volume only.",
            "No automatic texture transfer, UV bake, Tripo mesh rigging, or Hunyuan3D texture generation is performed.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved Tripo reference visual Blend: {output_blend}")
    print(f"Exported Tripo reference visual GLB: {output_glb}")
    print(f"Exported Tripo reference visual FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
