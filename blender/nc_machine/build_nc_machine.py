"""build_nc_machine.py - 加工機・台車・パレットを Blender で生成する（見た目の正本）。

実行方法:
    blender --background --factory-startup --python blender/nc_machine/build_nc_machine.py -- --config-json <resolved.json>

出力（resolved.json と同じフォルダ）:
    - <subject>.blend
    - <subject>.glb（ノード名＝MJCF のボディ名。可動部は独立ノード）
    - renders/*.png（front / top / left / right / iso / hero）
    - build_report.json

形は scripts/nc_machine/nc_geometry.py の結果をそのまま使う（MJCF と同じ値）。
ボディは Empty、部品はその子のメッシュ（名前＝geom 名）。サイトは書き出さない（MJCF だけが持つ）。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, Sequence, Tuple

import bmesh
import bpy
from mathutils import Quaternion, Vector

REPO_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_DIR / "scripts" / "nc_machine"))
import nc_geometry as ncg  # noqa: E402

MATS: Dict[str, bpy.types.Material] = {}
METALLIC = {"chuck": 0.6, "jaw": 0.8, "turret": 0.5, "door_glass": 0.2}


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="build_nc_machine.py")
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
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.world = bpy.data.worlds.new("NcWorld")
    scene.world.color = (0.78, 0.80, 0.82)


def make_material(name: str, rgba: Sequence[float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(f"nc_{name}")
    mat.use_nodes = True
    mat.diffuse_color = tuple(rgba)
    mat.use_backface_culling = False
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = tuple(rgba)
        bsdf.inputs["Metallic"].default_value = METALLIC.get(name, 0.1)
        bsdf.inputs["Roughness"].default_value = 0.45
        if rgba[3] < 1.0:
            bsdf.inputs["Alpha"].default_value = rgba[3]
            if hasattr(mat, "surface_render_method"):
                mat.surface_render_method = "BLENDED"
            else:
                mat.blend_method = "BLEND"
    return mat


def make_empty(name: str, loc, parent, coll) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_type = "PLAIN_AXES"
    ob.empty_display_size = 0.1
    ob.location = Vector(loc)
    coll.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def make_geom(g: dict, parent, coll) -> bpy.types.Object:
    me = bpy.data.meshes.new(g["name"])
    bm = bmesh.new()
    if g["type"] == "box":
        bmesh.ops.create_cube(bm, size=1.0)
        sx, sy, sz = (2.0 * s for s in g["size"])
        for v in bm.verts:
            v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    elif g["type"] == "cylinder":
        r, h = g["size"][0], g["size"][1]
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=48, radius1=r, radius2=r, depth=2.0 * h)
    else:
        raise ValueError(f"未対応の形: {g['type']}")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(MATS[g["material"]])
    ob = bpy.data.objects.new(g["name"], me)
    ob.location = Vector(g["pos"])
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Quaternion(g["quat"])
    ob["collide"] = bool(g["collide"])
    coll.objects.link(ob)
    ob.parent = parent
    return ob


def build(desc: dict) -> Dict[str, bpy.types.Object]:
    for name, rgba in desc["materials"].items():
        MATS[name] = make_material(name, rgba)
    coll = bpy.data.collections.new(desc["template_id"])
    bpy.context.scene.collection.children.link(coll)
    empties: Dict[str, bpy.types.Object] = {}
    for bd in desc["bodies"]:
        parent = empties[bd["parent"]] if bd["parent"] else None
        e = make_empty(bd["name"], bd["pos"], parent, coll)
        e["part_type"] = "body"
        e["subject_id"] = desc["template_id"]
        empties[bd["name"]] = e
        for g in bd["geoms"]:
            make_geom(g, e, coll)
    return empties


def visual_bounds() -> Tuple[Vector, Vector]:
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    bpy.context.view_layer.update()
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector((min(lo.x, w.x), min(lo.y, w.y), min(lo.z, w.z)))
            hi = Vector((max(hi.x, w.x), max(hi.y, w.y), max(hi.z, w.z)))
    return lo, hi


def render_views(out_dir: Path, resolution: int = 1000) -> Dict[str, str]:
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

    lo, hi = visual_bounds()
    center = (lo + hi) * 0.5
    size = hi - lo
    span = max(size.x, size.y, size.z)

    def look(direction: Vector, ortho: bool, scale: float) -> None:
        cam_data.type = "ORTHO" if ortho else "PERSP"
        if ortho:
            cam_data.ortho_scale = scale
        else:
            cam_data.lens = 40.0
        d = direction.normalized()
        cam.location = center + d * span * 2.5
        if abs(d.z) > 0.99:
            cam.rotation_euler = (0.0, 0.0, 0.0)
        else:
            cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()

    # 加工機の正面は -Y 側（扉が前面 y=0）
    views = {
        "front": (Vector((0, -1, 0)), True, max(size.x, size.z / 0.75) * 1.1),
        "top": (Vector((0, 0, 1)), True, max(size.x, size.y / 0.75) * 1.1),
        "left": (Vector((-1, 0, 0)), True, max(size.y, size.z / 0.75) * 1.1),
        "right": (Vector((1, 0, 0)), True, max(size.y, size.z / 0.75) * 1.1),
        "iso": (Vector((0.8, -1.0, 0.7)), True, span * 1.3),
        "hero": (Vector((0.6, -1.2, 0.5)), False, 0.0),
    }
    out = {}
    for name, (direction, ortho, scale) in views.items():
        look(direction, ortho, scale)
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
    desc = ncg.describe(cfg)
    subject = desc["template_id"]

    setup_scene()
    build(desc)

    blend_path = out_dir / f"{subject}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    glb_path = out_dir / f"{subject}.glb"
    bpy.ops.export_scene.gltf(filepath=str(glb_path), export_format="GLB", export_cameras=False,
                              export_lights=False, export_extras=True)
    renders = render_views(out_dir)

    lo, hi = visual_bounds()
    report = {
        "subject": subject,
        "blend_file": str(blend_path),
        "glb_file": str(glb_path),
        "renders": renders,
        "bounds_m": {"min": list(lo), "max": list(hi)},
        "total_objects": len(bpy.data.objects),
        "total_faces": sum(len(m.polygons) for m in bpy.data.meshes),
        "blender_version": bpy.app.version_string,
    }
    (out_dir / "build_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[build_nc_machine] {subject}: {glb_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # Blender は例外でも 0 で終わることがあるので明示的に失敗させる
        import traceback
        traceback.print_exc()
        print(f"[build_nc_machine] FAILED: {exc}")
        sys.exit(1)
