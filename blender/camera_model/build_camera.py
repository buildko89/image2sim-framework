"""build_camera.py - カメラ（iRVision 2D など）の見た目を Blender で生成する。

実行方法:
    blender --background --factory-startup --python blender/camera_model/build_camera.py -- --config-json <resolved.json>

出力（resolved.json と同じフォルダ）:
    - <id>.blend
    - <id>.glb
    - <id>_visual.usdc   … 見た目のメッシュだけの USD（Z 上・m。author_camera_usd.py が参照する）
    - renders/*.png      … front / side / top / iso
    - build_report.json

形は scripts/camera_model/camera_geometry.py の結果（resolved.json の parts）をそのまま使う。
Blender の座標 = 本体の座標（原点 = 光学中心、+x = 光軸、+z = 上）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict

import bpy
from mathutils import Vector

MATS: Dict[str, bpy.types.Material] = {}
ROLE_COLOR = {"housing": "housing", "window": "window", "lens": "lens", "label": "label", "connector": "connector"}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="build_camera.py")
    p.add_argument("--config-json", required=True)
    return p.parse_args(argv)


def setup_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("World")
    world.color = (0.85, 0.85, 0.85)
    scene.world = world


def material(name: str, rgb, alpha: float = 1.0, emission: float = 0.0, metallic: float = 0.0,
             roughness: float = 0.5) -> bpy.types.Material:
    if name in MATS:
        return MATS[name]
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, alpha)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
        bsdf.inputs["Alpha"].default_value = alpha
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
        if emission > 0:
            bsdf.inputs["Emission Color"].default_value = (*rgb, 1.0)
            bsdf.inputs["Emission Strength"].default_value = emission
    if alpha < 1.0:
        m.surface_render_method = "BLENDED"
    MATS[name] = m
    return m


def materials_for(cfg: dict) -> Dict[str, bpy.types.Material]:
    col = cfg["visual"]["colors"]
    led_rgb = tuple(cfg["optics"]["led_rgb"])
    return {
        "housing": material("irv_housing", col["housing"], roughness=0.6),
        "window": material("irv_window", col["window"], alpha=0.35, roughness=0.05),
        "lens": material("irv_lens", col["lens"], metallic=0.2, roughness=0.1),
        "label": material("irv_label", col["label"], metallic=0.6, roughness=0.4),
        "connector": material("irv_connector", col["connector"], metallic=0.5, roughness=0.4),
        "led": material("irv_led", led_rgb, emission=3.0),
    }


def add_part(part: dict, mats: Dict[str, bpy.types.Material], parent: bpy.types.Object) -> bpy.types.Object:
    c = Vector(part["center"])
    if part["shape"] == "box":
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=c)
        obj = bpy.context.active_object
        obj.scale = Vector(part["half"])
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        if part.get("bevel"):
            mod = obj.modifiers.new("bevel", "BEVEL")
            mod.width = part["bevel"]
            mod.segments = 3
            mod.limit_method = "ANGLE"
            bpy.ops.object.modifier_apply(modifier=mod.name)
    else:
        rot = (0.0, math.pi / 2, 0.0) if part["axis"] == "x" else (0.0, 0.0, 0.0)
        bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=part["radius"], depth=2 * part["half_length"],
                                            location=c, rotation=rot)
        obj = bpy.context.active_object
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    obj.name = part["name"]
    obj.data.name = part["name"]
    obj.data.materials.append(mats[part["role"]])
    obj.parent = parent
    bpy.ops.object.shade_flat()
    return obj


def render_views(out_dir: Path, center: Vector, size: float, resolution: int = 900) -> Dict[str, str]:
    renders = out_dir / "renders"
    renders.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = int(resolution * 0.75)
    scene.render.image_settings.file_format = "PNG"
    cam_data = bpy.data.cameras.new("RenderCam")
    cam = bpy.data.objects.new("Camera_Render", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    views = {
        "front": Vector((1, 0, 0)), "side": Vector((0, 1, 0)), "top": Vector((0, 0, 1)),
        "iso": Vector((1, 0.8, 0.6)),
    }
    out = {}
    for name, d in views.items():
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = size * 1.6
        d = d.normalized()
        cam.location = center + d * size * 4
        up = Vector((0, 0, 1)) if name != "top" else Vector((-1, 0, 0))
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler() if name != "top" else \
            (-d).to_track_quat("-Z", "X").to_euler()
        _ = up
        path = renders / f"{name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        out[name] = str(path)
    bpy.data.objects.remove(cam)
    return out


def main() -> int:
    args = parse_args()
    cfg_path = Path(args.config_json)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out_dir = cfg_path.parent
    tid = cfg["template_id"]
    setup_scene()
    mats = materials_for(cfg)

    root = bpy.data.objects.new(cfg["root_prim"] + "_Visual", None)
    bpy.context.scene.collection.objects.link(root)
    objs = [add_part(p, mats, root) for p in cfg["parts"]]

    blend_path = out_dir / f"{tid}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    glb_path = out_dir / f"{tid}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_cameras=False,
                              export_lights=False, export_apply=True)

    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    for o in objs:
        o.select_set(True)
    usd_path = out_dir / f"{tid}_visual.usdc"
    bpy.ops.wm.usd_export(
        filepath=str(usd_path),
        selected_objects_only=True,
        export_materials=True,
        generate_preview_surface=True,
        convert_orientation=False,   # Isaac Sim と同じ Z 上・m のまま
        export_uvmaps=True,
        export_normals=True,
        root_prim_path="/" + cfg["root_prim"] + "_Visual",
        relative_paths=True,
    )

    env = cfg["envelope_body"]
    center = Vector([(env["min"][i] + env["max"][i]) / 2 for i in range(3)])
    renders = render_views(out_dir, center, max(env["size"]))

    report = {
        "template_id": tid,
        "blend_file": str(blend_path),
        "glb_file": str(glb_path),
        "visual_usd": str(usd_path),
        "objects": [o.name for o in objs],
        "renders": renders,
        "blender_version": bpy.app.version_string,
    }
    (out_dir / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[build_camera] {tid}: {glb_path}, {usd_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
