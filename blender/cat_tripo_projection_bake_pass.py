from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


BAKE_SIZE = 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bake Tripo reference texture onto the rigged cat mesh.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--texture-dir", required=True)
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


def tripo_source_mesh() -> bpy.types.Object:
    candidates = [obj for obj in mesh_objects() if obj.name.startswith("TripoV25_Reference")]
    if not candidates:
        raise RuntimeError("No TripoV25_Reference mesh found in the input blend.")
    return candidates[0]


def world_bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    low = Vector((min(corner.x for corner in corners), min(corner.y for corner in corners), min(corner.z for corner in corners)))
    high = Vector((max(corner.x for corner in corners), max(corner.y for corner in corners), max(corner.z for corner in corners)))
    return low, high


def bounds_report(obj: bpy.types.Object) -> dict:
    low, high = world_bounds(obj)
    size = high - low
    center = (low + high) * 0.5
    return {
        "name": obj.name,
        "low": [round(value, 6) for value in low],
        "high": [round(value, 6) for value in high],
        "size": [round(value, 6) for value in size],
        "center": [round(value, 6) for value in center],
    }


def align_source_to_target(source: bpy.types.Object, target: bpy.types.Object) -> dict:
    source_before = bounds_report(source)
    target_bounds = bounds_report(target)
    source_low, source_high = world_bounds(source)
    target_low, target_high = world_bounds(target)
    source_size = source_high - source_low
    target_size = target_high - target_low
    scale = Vector(
        (
            target_size.x / source_size.x if source_size.x else 1.0,
            target_size.y / source_size.y if source_size.y else 1.0,
            target_size.z / source_size.z if source_size.z else 1.0,
        )
    )
    source.scale = Vector((source.scale.x * scale.x, source.scale.y * scale.y, source.scale.z * scale.z))
    bpy.context.view_layer.update()
    source_low_after_scale, source_high_after_scale = world_bounds(source)
    source_center = (source_low_after_scale + source_high_after_scale) * 0.5
    target_center = (target_low + target_high) * 0.5
    source.location += target_center - source_center
    bpy.context.view_layer.update()
    return {
        "source_before": source_before,
        "target": target_bounds,
        "scale_applied": [round(value, 6) for value in scale],
        "source_after": bounds_report(source),
    }


def ensure_uv(mesh: bpy.types.Object) -> dict:
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name="ProjectionBakeUV")
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.025, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.data.update()
    return {
        "mesh": mesh.name,
        "uv_layer_count": len(mesh.data.uv_layers),
        "active_uv": mesh.data.uv_layers.active.name if mesh.data.uv_layers.active else None,
    }


def assign_bake_material(mesh: bpy.types.Object, image: bpy.types.Image) -> bpy.types.Material:
    material = bpy.data.materials.new(f"PhotoCat_TripoProjected_{mesh.name}")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    texture_node = nodes.new(type="ShaderNodeTexImage")
    texture_node.name = f"{mesh.name}_TripoProjectionBakeTexture"
    texture_node.image = image
    if bsdf is not None:
        links.new(texture_node.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.94
    nodes.active = texture_node
    mesh.data.materials.clear()
    mesh.data.materials.append(material)
    for polygon in mesh.data.polygons:
        polygon.material_index = 0
    return material


def configure_bake() -> None:
    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.samples = 32
    bpy.context.scene.render.bake.use_selected_to_active = True
    bpy.context.scene.render.bake.use_clear = True
    bpy.context.scene.render.bake.margin = 16
    bpy.context.scene.render.bake.max_ray_distance = 0.45


def bake_target(source: bpy.types.Object, target: bpy.types.Object, texture_dir: Path) -> dict:
    uv_report = ensure_uv(target)
    image_path = texture_dir / f"{target.name}_tripo_projection_bake.png"
    image = bpy.data.images.new(f"{target.name}_TripoProjectionBake", width=BAKE_SIZE, height=BAKE_SIZE, alpha=False)
    image.generated_color = (0.86, 0.78, 0.66, 1.0)
    assign_bake_material(target, image)

    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    configure_bake()
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"})

    image.filepath_raw = str(image_path)
    image.file_format = "PNG"
    image.save()
    return {
        "mesh": target.name,
        "texture": str(image_path),
        "uv": uv_report,
    }


def export_selected(output_glb: Path, output_fbx: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in skinned_mesh_objects() + armature_objects():
        obj.select_set(True)
    bpy.context.view_layer.objects.active = main_mesh()
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
    texture_dir = Path(args.texture_dir)
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)

    texture_dir.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    bpy.context.scene.unit_settings.system = "METRIC"

    source = tripo_source_mesh()
    target = main_mesh()
    alignment_report = align_source_to_target(source, target)
    bake_reports = [bake_target(source, mesh, texture_dir) for mesh in skinned_mesh_objects()]

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 6.6: Tripo Projection Bake Pass",
        "input": str(input_path),
        "texture_dir": str(texture_dir),
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "source_mesh": source.name,
        "alignment": alignment_report,
        "bake_reports": bake_reports,
        "mesh_count": len(mesh_objects()),
        "armature_count": len(armature_objects()),
        "action_count": len(bpy.data.actions),
        "notes": [
            "This is a true selected-to-active color bake attempt from the Tripo reference mesh to the animated rig meshes.",
            "The Tripo mesh is aligned to the target bounding box before baking because the reference scene stores it aside from the rig.",
            "Accuracy is limited by geometry mismatch and simple bounding-box alignment.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved projection bake Blend: {output_blend}")
    print(f"Exported projection bake GLB: {output_glb}")
    print(f"Exported projection bake FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
