from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a first cat-like appearance pass on the Fox rig.")
    parser.add_argument("--input", required=True, help="Input rigged .blend path.")
    parser.add_argument("--output-blend", required=True, help="Output working .blend path.")
    parser.add_argument("--output-glb", required=True, help="Output animated GLB path.")
    parser.add_argument("--output-fbx", required=True, help="Output animated FBX path.")
    parser.add_argument("--report", required=True, help="Output JSON report path.")
    parser.add_argument("--reference-image", action="append", default=[], help="Reference image path to place in the .blend.")
    parser.add_argument("--reference-mesh", help="Optional static reference GLB/FBX path to append to the .blend.")
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
    objects = skinned_mesh_objects() + armature_objects()
    result: list[bpy.types.Object] = []
    seen: set[str] = set()
    for obj in objects:
        if obj.name not in seen:
            result.append(obj)
            seen.add(obj.name)
    return result


def create_material(name: str, color: tuple[float, float, float, float], roughness: float = 0.65) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = roughness
    return material


def setup_cat_materials(mesh: bpy.types.Object) -> dict[str, int]:
    mesh.data.materials.clear()
    materials = [
        create_material("Cat_Fur_Warm_White", (0.86, 0.80, 0.70, 1.0)),
        create_material("Cat_Patch_Brown", (0.48, 0.24, 0.10, 1.0)),
        create_material("Cat_Patch_Black", (0.04, 0.035, 0.03, 1.0)),
        create_material("Cat_Cream_Undercoat", (0.74, 0.64, 0.48, 1.0)),
        create_material("Cat_Ear_Nose_Dark", (0.14, 0.08, 0.065, 1.0)),
    ]
    for material in materials:
        mesh.data.materials.append(material)
    return {
        "white": 0,
        "brown": 1,
        "black": 2,
        "cream": 3,
        "dark": 4,
    }


def local_polygon_center(mesh: bpy.types.Object, polygon: bpy.types.MeshPolygon) -> Vector:
    vertices = [mesh.data.vertices[index].co for index in polygon.vertices]
    center = Vector((0.0, 0.0, 0.0))
    for vertex in vertices:
        center += vertex
    return center / max(len(vertices), 1)


def assign_calico_pattern(mesh: bpy.types.Object, slots: dict[str, int]) -> dict[str, int]:
    if not mesh.data.polygons:
        return {}

    centers = [local_polygon_center(mesh, polygon) for polygon in mesh.data.polygons]
    min_x = min(center.x for center in centers)
    max_x = max(center.x for center in centers)
    min_y = min(center.y for center in centers)
    max_y = max(center.y for center in centers)
    min_z = min(center.z for center in centers)
    max_z = max(center.z for center in centers)

    def norm(value: float, min_value: float, max_value: float) -> float:
        span = max_value - min_value
        if span <= 0:
            return 0.5
        return (value - min_value) / span

    counts = {name: 0 for name in slots}
    for polygon, center in zip(mesh.data.polygons, centers):
        x = norm(center.x, min_x, max_x)
        y = norm(center.y, min_y, max_y)
        z = norm(center.z, min_z, max_z)

        slot_name = "white"
        if z < 0.30:
            slot_name = "cream"

        # Broad asymmetric patches make the asset read less like the original orange fox.
        if 0.28 < y < 0.64 and x < 0.43 and z > 0.28:
            slot_name = "brown"
        if 0.54 < y < 0.88 and x > 0.50 and z > 0.25:
            slot_name = "black"
        if y > 0.80 and z > 0.48:
            slot_name = "black" if x > 0.47 else "brown"
        if y < 0.18 and z > 0.38:
            slot_name = "dark"

        # Add a few smaller organic islands without relying on procedural shader export.
        noise = math.sin((x * 17.0) + (y * 11.0) + (z * 5.0))
        if z > 0.35 and noise > 0.82:
            slot_name = "brown"
        elif z > 0.35 and noise < -0.86:
            slot_name = "black"

        polygon.material_index = slots[slot_name]
        counts[slot_name] += 1
    return counts


def add_reference_collection() -> bpy.types.Collection:
    collection = bpy.data.collections.new("Cat_Appearance_References")
    bpy.context.scene.collection.children.link(collection)
    return collection


def scaled_plane_size(width: float, height: float, max_width: float) -> tuple[float, float]:
    if width <= 0:
        return max_width, max_width
    return max_width, max_width * (height / width)


def add_reference_image(collection: bpy.types.Collection, path: Path, index: int) -> str:
    image = bpy.data.images.load(str(path), check_existing=True)
    width, height = image.size
    plane_width, plane_height = scaled_plane_size(float(width), float(height), 1.1)
    x = -2.2 + (index * 1.25)

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(x, -1.5, 0.7), rotation=(math.radians(70), 0.0, 0.0))
    plane = bpy.context.object
    plane.name = f"reference_image_{index + 1:02d}_{path.stem}"
    plane.dimensions = (plane_width, plane_height, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    material = create_material(f"{plane.name}_material", (1.0, 1.0, 1.0, 1.0))
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    if bsdf:
        material.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        if "Alpha" in tex.outputs and "Alpha" in bsdf.inputs:
            material.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    material.blend_method = "BLEND"
    plane.data.materials.append(material)
    plane["source_path"] = str(path)
    plane["source_role"] = "cat_appearance_reference"

    for parent in plane.users_collection:
        parent.objects.unlink(plane)
    collection.objects.link(plane)
    return plane.name


def import_reference_mesh(collection: bpy.types.Collection, path: Path) -> list[str]:
    before = {obj.name for obj in bpy.context.scene.objects}
    suffix = path.suffix.lower()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(path))
    elif suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(path))
    else:
        return []

    created: list[str] = []
    for obj in list(bpy.context.scene.objects):
        if obj.name in before:
            continue
        obj.name = f"reference_mesh_{obj.name}"
        obj.location.x += 1.6
        obj.location.y -= 1.2
        obj["source_path"] = str(path)
        obj["source_role"] = "static_shape_reference"
        for parent in obj.users_collection:
            parent.objects.unlink(obj)
        collection.objects.link(obj)
        created.append(obj.name)
    return created


def ensure_camera_and_light() -> None:
    if not any(obj.type == "LIGHT" for obj in bpy.context.scene.objects):
        bpy.ops.object.light_add(type="AREA", location=(0.0, -3.0, 3.0))
        light = bpy.context.object
        light.name = "Cat_Appearance_Area_Light"
        light.data.energy = 450
        light.data.size = 4
    if not bpy.context.scene.camera:
        bpy.ops.object.camera_add(location=(0.0, -3.0, 1.2), rotation=(math.radians(72), 0.0, 0.0))
        bpy.context.scene.camera = bpy.context.object


def action_report() -> list[dict]:
    report: list[dict] = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        report.append({"name": action.name, "frame_start": float(start), "frame_end": float(end)})
    return report


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
    active = skinned_mesh_objects()[0] if skinned_mesh_objects() else (armature_objects()[0] if armature_objects() else None)
    if active:
        bpy.context.view_layer.objects.active = active

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

    target_meshes = skinned_mesh_objects()
    if not target_meshes:
        raise RuntimeError("No skinned mesh was found for the cat appearance pass.")

    material_counts: dict[str, dict[str, int]] = {}
    for mesh in target_meshes:
        slots = setup_cat_materials(mesh)
        material_counts[mesh.name] = assign_calico_pattern(mesh, slots)

    reference_collection = add_reference_collection()
    reference_images = []
    for index, value in enumerate(args.reference_image):
        path = Path(value)
        if path.exists():
            reference_images.append(add_reference_image(reference_collection, path, index))

    reference_meshes: list[str] = []
    if args.reference_mesh:
        reference_mesh = Path(args.reference_mesh)
        if reference_mesh.exists():
            reference_meshes = import_reference_mesh(reference_collection, reference_mesh)

    ensure_camera_and_light()
    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 5.5: Cat Appearance Pass on Fox Rig",
        "input": str(input_path),
        "outputs": {
            "blend": str(output_blend),
            "glb": str(output_glb),
            "fbx": str(output_fbx),
        },
        "reference_images": [str(path) for path in args.reference_image],
        "reference_mesh": args.reference_mesh,
        "created_reference_objects": reference_images + reference_meshes,
        "material_strategy": "Assigned export-safe polygon material indices for a first calico-like cat pass.",
        "material_polygon_counts": material_counts,
        "mesh_count": len(mesh_report()),
        "armature_count": len(armature_objects()),
        "action_count": len(action_report()),
        "meshes": mesh_report(),
        "actions": action_report(),
        "notes": [
            "This first pass changes materials only; it avoids destructive shape edits to preserve skinning.",
            "Reference planes and static reference mesh are saved in the .blend but excluded from GLB/FBX export.",
            "The result should be checked in Godot with Idle, Walk, and Jump_ToIdle before shape edits.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved appearance Blend: {output_blend}")
    print(f"Exported appearance GLB: {output_glb}")
    print(f"Exported appearance FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
