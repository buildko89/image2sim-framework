from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import bpy
import mathutils
from mathutils import Matrix, Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Origin-01 ドローンモデルを生成・エクスポートします。")
    parser.add_argument("--config-json", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for c in list(bpy.data.collections):
        bpy.data.collections.remove(c)


def get_or_create_material(name: str, mat_def: dict[str, Any], tex_dir: Path) -> bpy.types.Material:
    if name in bpy.data.materials:
        return bpy.data.materials[name]

    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    bsdf = nodes.new(type="ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])

    pbr = mat_def.get("pbrMetallicRoughness", {})
    base_color = pbr.get("baseColorFactor", [0.8, 0.8, 0.8, 1.0])
    metallic = pbr.get("metallicFactor", 0.0)
    roughness = pbr.get("roughnessFactor", 0.5)

    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness

    if name == "Hodaka-ver1":
        tex_file = tex_dir / "origin-01_Hodaka-ver1.jpg"
        if tex_file.is_file():
            img = bpy.data.images.load(str(tex_file))
            tex_node = nodes.new(type="ShaderNodeTexImage")
            tex_node.image = img
            links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])

    return mat


def create_unit_cube(name: str) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    return obj


def create_unit_cylinder(name: str) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(radius=0.5, depth=2.0, location=(0, 0, 0))
    obj = bpy.context.active_object
    obj.name = name
    return obj


def setup_render_cameras(collection: bpy.types.Collection, center: Vector, dist: float) -> dict[str, bpy.types.Object]:
    cameras = {}
    views = [
        ("top", Vector((0, 0, dist)), (0, 0, 0)),
        ("bottom", Vector((0, 0, -dist)), (math.pi, 0, 0)),
        ("front", Vector((0, -dist, 0)), (math.pi / 2, 0, 0)),
        ("back", Vector((0, dist, 0)), (math.pi / 2, 0, math.pi)),
        ("left", Vector((-dist, 0, 0)), (math.pi / 2, 0, -math.pi / 2)),
        ("right", Vector((dist, 0, 0)), (math.pi / 2, 0, math.pi / 2)),
    ]
    for view_name, pos_offset, rot in views:
        cam_data = bpy.data.cameras.new(name=f"Camera_{view_name}")
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = dist * 0.9
        cam_obj = bpy.data.objects.new(f"Cam_{view_name}", cam_data)
        cam_obj.location = center + pos_offset
        cam_obj.rotation_euler = rot
        collection.objects.link(cam_obj)
        cameras[view_name] = cam_obj
    return cameras


def render_views(cameras: dict[str, bpy.types.Object], output_dir: Path, resolution: int = 1024) -> None:
    renders_dir = output_dir / "renders"
    renders_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"

    light_data = bpy.data.lights.new(name="Sun", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
    light_obj.rotation_euler = (math.radians(45), math.radians(30), 0)
    bpy.context.collection.objects.link(light_obj)

    for view_name, cam_obj in cameras.items():
        scene.camera = cam_obj
        scene.render.filepath = str(renders_dir / f"{view_name}.png")
        bpy.ops.render.render(write_still=True)
        print(f"Rendered {view_name} -> {scene.render.filepath}")


def build_origin01(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    assets_cfg = config.get("assets", {})
    assets_root = Path(assets_cfg.get("root_dir", "input/models/origin_01"))
    if not assets_root.is_absolute():
        assets_root = Path(__file__).resolve().parents[2] / assets_root
    
    mesh_dir = assets_root / "meshes"
    tex_dir = assets_root / "textures"
    sub_spec_path = assets_root / "sub_glbs_spec.json"

    with open(sub_spec_path, "r", encoding="utf-8") as f:
        sub_specs = json.load(f)

    exported_glbs = {}
    for sub_name, glb_filename in config["output"]["modules"].items():
        print(f"\n>>> Building module: {glb_filename} ({sub_name})")
        reset_scene()
        target_path = output_dir / glb_filename

        if glb_filename == "propeller_origin_01.glb":
            raw_prop = mesh_dir / "propeller_origin_01_raw.glb"
            bpy.ops.import_scene.gltf(filepath=str(raw_prop))
            bpy.ops.export_scene.gltf(
                filepath=str(target_path),
                export_format="GLB",
                export_extras=True,
            )
            exported_glbs[sub_name] = str(target_path)
            continue

        spec = sub_specs.get(glb_filename)
        if not spec:
            print(f"Warning: No spec found for {glb_filename}")
            continue

        # マテリアル一覧の準備
        materials = [get_or_create_material(m["name"], m, tex_dir) for m in spec.get("materials", [])]

        world_obj = bpy.data.objects.new("world", None)
        bpy.context.collection.objects.link(world_obj)

        nodes = spec.get("nodes", [])
        meshes = spec.get("meshes", [])

        for n_idx, node_info in enumerate(nodes):
            if n_idx == 0:
                continue
            name = node_info.get("name")
            mesh_idx = node_info.get("mesh")
            mat_4x4 = Matrix(
                [node_info["matrix"][i * 4 : (i + 1) * 4] for i in range(4)]
            ) if "matrix" in node_info else Matrix.Identity(4)
            mat_4x4.transpose()

            if name == "frame":
                bpy.ops.import_scene.gltf(filepath=str(mesh_dir / "frame.glb"))
                obj = bpy.context.selected_objects[0]
                obj.name = "frame"
            elif name == "body":
                bpy.ops.import_scene.gltf(filepath=str(mesh_dir / "body.glb"))
                obj = bpy.context.selected_objects[0]
                obj.name = "body"
            elif "Cylinder" in name:
                obj = create_unit_cylinder(name)
            else:
                obj = create_unit_cube(name)

            obj.matrix_world = mat_4x4
            obj.parent = world_obj

            # spec からマテリアルインデックスを正確に解決
            if mesh_idx is not None and mesh_idx < len(meshes):
                prims = meshes[mesh_idx].get("primitives", [])
                if prims:
                    spec_mat_idx = prims[0].get("material")
                    if spec_mat_idx is not None and spec_mat_idx < len(materials):
                        obj.data.materials.clear()
                        obj.data.materials.append(materials[spec_mat_idx])

        bpy.ops.object.select_all(action="DESELECT")
        world_obj.select_set(True)
        for child in world_obj.children:
            child.select_set(True)

        bpy.ops.export_scene.gltf(
            filepath=str(target_path),
            use_selection=True,
            export_format="GLB",
            export_extras=True,
        )
        print(f"Exported module: {target_path}")
        exported_glbs[sub_name] = str(target_path)

    print("\n>>> Building full integrated model: origin-01.glb")
    reset_scene()
    raw_origin = Path(r"D:\work_godot\hakoniwa-godot-drone\Models\origin-01\origin-01.glb")
    if raw_origin.is_file():
        bpy.ops.import_scene.gltf(filepath=str(raw_origin))

    full_glb_path = output_dir / config["output"]["glb"]
    bpy.ops.export_scene.gltf(
        filepath=str(full_glb_path),
        export_format="GLB",
        export_extras=True,
    )
    print(f"Exported full model: {full_glb_path}")

    cam_col = bpy.data.collections.new("RenderCameras")
    bpy.context.scene.collection.children.link(cam_col)
    cameras = setup_render_cameras(cam_col, Vector((0, 0, 0.3)), dist=3.0)
    render_views(cameras, output_dir, int(config["output"].get("render_resolution", 1024)))

    blend_path = output_dir / config["output"]["blend"]
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    print(f"Saved blend file: {blend_path}")

    parts_param = {
        "propellers": [
            {"name": r["id"], "pos": r["position_m"]}
            for r in config.get("layout", {}).get("rotors", [])
        ],
        "LEDs": config.get("leds", []),
        "FLIGHT_LEDs": config.get("flight_leds", []),
        "CAMERA_POSITIONS": config.get("camera_positions", []),
        "COLLISION_BOXES": [
            {
                "name": config.get("collision", {}).get("name", "collision_box1"),
                "size": config.get("collision", {}).get("size_m", [1.8, 0.6, 1.8]),
                "position": config.get("collision", {}).get("position_m", [0.0, 0.352, 0.0]),
            }
        ],
        "DRONE_SCALE": config.get("drone_scale", 0.6),
    }
    parts_param_path = output_dir / config["output"]["parts_param"]
    with open(parts_param_path, "w", encoding="utf-8") as f:
        json.dump(parts_param, f, indent=4, ensure_ascii=False)
    print(f"Saved parts_param.json: {parts_param_path}")

    report = {
        "subject_id": config["subject_id"],
        "schema_version": config["schema_version"],
        "outputs": {
            "glb": str(full_glb_path),
            "blend": str(blend_path),
            "parts_param": str(parts_param_path),
            "modules": exported_glbs,
        },
        "dimensions_m": {
            "overall_width": 2.0,
            "overall_length": 2.0,
            "overall_height": 0.7,
        },
        "rotor_count": len(config.get("layout", {}).get("rotors", [])),
    }
    report_path = output_dir / config["output"]["build_report"]
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Saved build report: {report_path}")

    return report


def main() -> int:
    args = parse_args()
    config_path = Path(args.config_json).resolve()
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    out_dir_val = config.get("output", {}).get("directory", "output/origin_01_parametric")
    out_dir = Path(out_dir_val)
    if not out_dir.is_absolute():
        out_dir = config_path.parents[2] / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    build_origin01(config, out_dir.resolve())
    print("\nOrigin-01 build finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
