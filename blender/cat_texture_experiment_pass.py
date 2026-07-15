from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


MATERIAL_TEXTURE_KEYS = {
    "PhotoCat_White_Longhair": "white_fur.png",
    "PhotoCat_Warm_Calico": "warm_calico_fur.png",
    "PhotoCat_Dark_Calico": "dark_calico_fur.png",
    "PhotoCat_Cream_Shadow": "cream_shadow_fur.png",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add UVs and visible fur-like base color textures to the rigged cat.")
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


def ensure_uv(mesh: bpy.types.Object) -> dict:
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name="TextureUV")
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


def material_key(material_name: str) -> str | None:
    for prefix, texture_name in MATERIAL_TEXTURE_KEYS.items():
        if material_name.startswith(prefix):
            return texture_name
    return None


def apply_texture(material: bpy.types.Material, image_path: Path) -> dict:
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        return {"material": material.name, "texture": str(image_path), "linked": False}

    image = bpy.data.images.load(str(image_path), check_existing=True)
    texture_node = nodes.new(type="ShaderNodeTexImage")
    texture_node.name = f"{material.name}_BaseColorTexture"
    texture_node.image = image
    texture_node.extension = "REPEAT"
    links.new(texture_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.93
    return {"material": material.name, "texture": str(image_path), "linked": True}


def apply_textures(texture_dir: Path) -> list[dict]:
    reports = []
    seen: set[str] = set()
    for material in bpy.data.materials:
        texture_name = material_key(material.name)
        if texture_name is None:
            continue
        if material.name in seen:
            continue
        seen.add(material.name)
        image_path = texture_dir / texture_name
        if not image_path.exists():
            reports.append({"material": material.name, "texture": str(image_path), "linked": False, "missing": True})
            continue
        reports.append(apply_texture(material, image_path))
    return reports


def mesh_report() -> list[dict]:
    return [
        {
            "name": obj.name,
            "vertex_count": len(obj.data.vertices),
            "polygon_count": len(obj.data.polygons),
            "material_count": len(obj.data.materials),
            "uv_layers": [layer.name for layer in obj.data.uv_layers],
            "modifiers": [modifier.type for modifier in obj.modifiers],
            "skinned": any(modifier.type == "ARMATURE" for modifier in obj.modifiers),
        }
        for obj in mesh_objects()
    ]


def action_report() -> list[dict]:
    result = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        result.append({"name": action.name, "frame_start": float(start), "frame_end": float(end)})
    return result


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

    bpy.ops.wm.open_mainfile(filepath=str(input_path))
    bpy.context.scene.unit_settings.system = "METRIC"

    uv_reports = [ensure_uv(mesh) for mesh in skinned_mesh_objects()]
    texture_reports = apply_textures(texture_dir)

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 6.4: Texture Experiment Pass",
        "input": str(input_path),
        "texture_dir": str(texture_dir),
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "uv_reports": uv_reports,
        "texture_reports": texture_reports,
        "mesh_count": len(mesh_report()),
        "armature_count": len(armature_objects()),
        "action_count": len(action_report()),
        "meshes": mesh_report(),
        "actions": action_report(),
        "notes": [
            "This pass adds UVs and actual base color textures to the rigged cat materials.",
            "Textures are procedural fur-like test images, not a true Tripo texture transfer.",
            "The goal is to verify that a texture-based path creates visible differences in Godot.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved texture experiment Blend: {output_blend}")
    print(f"Exported texture experiment GLB: {output_glb}")
    print(f"Exported texture experiment FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
