from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shorten visible legs and add a conservative fur shell.")
    parser.add_argument("--input", required=True)
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


def bounds_for_indices(mesh: bpy.types.Object, indices: list[int | None]) -> dict[str, list[float]]:
    points = [vertex.co.copy() for vertex in mesh.data.vertices if max_weight(vertex, indices) > 0.05]
    if not points:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}
    return {
        "min": [min(getattr(point, axis) for point in points) for axis in "xyz"],
        "max": [max(getattr(point, axis) for point in points) for axis in "xyz"],
    }


def make_material(name: str, color: tuple[float, float, float, float], alpha: float = 1.0) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.blend_method = "BLEND" if alpha < 1.0 else "OPAQUE"
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], alpha)
        bsdf.inputs["Alpha"].default_value = alpha
        bsdf.inputs["Roughness"].default_value = 0.88
    return material


def retune_photo_materials(mesh: bpy.types.Object) -> dict[str, dict[str, list[float]]]:
    """Nudge flat material colors toward the new side references without changing UVs or textures."""
    target_colors = {
        "PhotoCat_White_Longhair": (0.965, 0.925, 0.840, 1.0),
        "PhotoCat_Warm_Calico": (0.720, 0.350, 0.105, 1.0),
        "PhotoCat_Dark_Calico": (0.070, 0.052, 0.038, 1.0),
        "PhotoCat_Cream_Shadow": (0.700, 0.610, 0.490, 1.0),
    }
    report: dict[str, dict[str, list[float]]] = {}
    for material in mesh.data.materials:
        if material.name not in target_colors:
            continue
        bsdf = material.node_tree.nodes.get("Principled BSDF") if material.use_nodes else None
        before = list(bsdf.inputs["Base Color"].default_value) if bsdf else []
        after = list(target_colors[material.name])
        if bsdf:
            bsdf.inputs["Base Color"].default_value = target_colors[material.name]
            bsdf.inputs["Roughness"].default_value = 0.90
        report[material.name] = {"before": before, "after": after}
    return report


def shorten_legs_and_lower_body(mesh: bpy.types.Object) -> dict:
    leg_names = [
        "FrontUpperLeg.L",
        "FrontLowerLeg.L",
        "FrontUpperLeg.R",
        "FrontLowerLeg.R",
        "BackUpperLeg.L",
        "BackLowerLeg.L",
        "BackUpperLeg.R",
        "BackLowerLeg.R",
    ]
    shoulder_names = ["FrontShoulder.L", "FrontShoulder.R", "BackShoulder.L", "BackShoulder.R"]
    body_names = ["Body", "Back", "Torso", "Torso2", "Torso3"]
    neck_names = ["Neck1", "Neck2", "Neck3"]

    leg_indices = [group_index(mesh, name) for name in leg_names]
    shoulder_indices = [group_index(mesh, name) for name in shoulder_names]
    body_indices = [group_index(mesh, name) for name in body_names]
    neck_indices = [group_index(mesh, name) for name in neck_names]

    before = {
        "legs": bounds_for_indices(mesh, leg_indices),
        "body": bounds_for_indices(mesh, body_indices),
    }
    foot_z = before["legs"]["min"][2]
    leg_scale = 0.35
    counts = {"legs": 0, "shoulders": 0, "body": 0, "neck": 0, "lower_leg_paw": 0}

    for vertex in mesh.data.vertices:
        co = vertex.co
        leg_w = max_weight(vertex, leg_indices)
        shoulder_w = max_weight(vertex, shoulder_indices)
        body_w = max_weight(vertex, body_indices)
        neck_w = max_weight(vertex, neck_indices)

        if leg_w > 0.03:
            influence = min(leg_w, 1.0)
            compressed_z = foot_z + (co.z - foot_z) * leg_scale
            co.z = co.z * (1.0 - influence) + compressed_z * influence
            co.x *= 1.0 + 0.045 * influence
            if co.z < foot_z + 0.34:
                co.x *= 1.0 + 0.085 * influence
                co.y *= 1.0 + 0.040 * influence
                counts["lower_leg_paw"] += 1
            counts["legs"] += 1

        if shoulder_w > 0.03:
            influence = min(shoulder_w, 1.0)
            co.z -= 0.21 * influence
            co.x *= 1.0 + 0.115 * influence
            counts["shoulders"] += 1

        if body_w > 0.03:
            influence = min(body_w, 1.0)
            co.z -= 0.23 * influence
            co.x *= 1.0 + 0.16 * influence
            if co.z < foot_z + 1.25:
                co.z -= 0.055 * influence
            counts["body"] += 1

        if neck_w > 0.03:
            influence = min(neck_w, 1.0)
            co.z -= 0.13 * influence
            co.x *= 1.0 + 0.14 * influence
            counts["neck"] += 1

    mesh.data.update()
    after = {
        "legs": bounds_for_indices(mesh, leg_indices),
        "body": bounds_for_indices(mesh, body_indices),
    }
    return {"counts": counts, "leg_scale": leg_scale, "foot_z": foot_z, "before": before, "after": after}


def create_fur_shell(mesh: bpy.types.Object) -> bpy.types.Object:
    existing = bpy.data.objects.get("PhotoCat_Fur_Shell")
    if existing:
        bpy.data.objects.remove(existing, do_unlink=True)

    shell = mesh.copy()
    shell.data = mesh.data.copy()
    shell.name = "PhotoCat_Fur_Shell"
    shell.data.name = "PhotoCat_Fur_Shell_Mesh"
    bpy.context.collection.objects.link(shell)
    shell.parent = mesh.parent
    shell.matrix_world = mesh.matrix_world.copy()

    lower_leg_indices = [group_index(shell, name) for name in ("FrontLowerLeg.L", "FrontLowerLeg.R", "BackLowerLeg.L", "BackLowerLeg.R")]
    upper_leg_indices = [group_index(shell, name) for name in ("FrontUpperLeg.L", "FrontUpperLeg.R", "BackUpperLeg.L", "BackUpperLeg.R")]
    shoulder_indices = [group_index(shell, name) for name in ("FrontShoulder.L", "FrontShoulder.R", "BackShoulder.L", "BackShoulder.R")]
    body_indices = [group_index(shell, name) for name in ("Body", "Back", "Torso", "Torso2", "Torso3")]
    chest_indices = [group_index(shell, name) for name in ("Neck1", "Neck2", "Neck3")]
    head_indices = [group_index(shell, "Head")]
    tail_indices = [group_index(shell, f"Tail{index}") for index in range(1, 9)]

    # Keep the photo-calico material assignments from cat_visual_pass; the shell should add volume, not repaint the cat.
    for vertex in shell.data.vertices:
        body_w = max_weight(vertex, body_indices)
        chest_w = max_weight(vertex, chest_indices)
        head_w = max_weight(vertex, head_indices)
        tail_w = max_weight(vertex, tail_indices)
        lower_leg_w = max_weight(vertex, lower_leg_indices)
        upper_leg_w = max_weight(vertex, upper_leg_indices)
        shoulder_w = max_weight(vertex, shoulder_indices)
        leg_w = max(lower_leg_w, upper_leg_w)
        influence = max(body_w, chest_w, head_w * 0.65, tail_w * 0.85, leg_w * 0.42, shoulder_w * 0.70)
        if influence <= 0.02:
            continue
        inflate = 0.052 * min(influence, 1.0)
        vertex.co += vertex.normal * inflate
        if body_w > 0.05:
            vertex.co.x *= 1.0 + 0.030 * min(body_w, 1.0)
            vertex.co.z -= 0.075 * min(body_w, 1.0)
        if chest_w > 0.05 or shoulder_w > 0.05:
            ruff = min(max(chest_w, shoulder_w), 1.0)
            vertex.co.x *= 1.0 + 0.055 * ruff
            vertex.co.z -= 0.100 * ruff
        if upper_leg_w > 0.05:
            vertex.co.z -= 0.075 * min(upper_leg_w, 1.0)
        if lower_leg_w > 0.05:
            lower = min(lower_leg_w, 1.0)
            vertex.co.x *= 1.0 + 0.070 * lower
            vertex.co.y *= 1.0 + 0.030 * lower
            vertex.co.z -= 0.052 * lower
        if tail_w > 0.05:
            vertex.co += vertex.normal * 0.030 * min(tail_w, 1.0)

    shell.data.update()
    return shell


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
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    bpy.context.scene.unit_settings.system = "METRIC"

    mesh = main_mesh()
    material_report = retune_photo_materials(mesh)
    leg_report = shorten_legs_and_lower_body(mesh)
    shell = create_fur_shell(mesh)

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 5.9: Short Legs and Fluffy Fur Silhouette Pass",
        "input": str(input_path),
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "main_mesh": mesh.name,
        "fur_shell": shell.name,
        "reference_images": [
            "input/raw_photos/横.png",
            "input/raw_photos/横2.png",
        ],
        "material_report": material_report,
        "leg_report": leg_report,
        "mesh_count": len(mesh_report()),
        "armature_count": len(armature_objects()),
        "action_count": len(action_report()),
        "meshes": mesh_report(),
        "actions": action_report(),
        "notes": [
            "Leg vertices are compressed strongly toward the feet to reduce the visible leg height.",
            "The body, shoulders, chest, and upper legs are lowered and widened so long fur visually hides more of the legs from the side.",
            "Lower legs and paws are slightly widened on the mesh and fur shell to better match the rounded, hairy side-view feet in the new references.",
            "Flat material colors are nudged toward the side photos, but this remains a non-textured material-color approximation.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved fluffy shortleg Blend: {output_blend}")
    print(f"Exported fluffy shortleg GLB: {output_glb}")
    print(f"Exported fluffy shortleg FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
