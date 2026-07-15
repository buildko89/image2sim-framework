from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a simple orthographic preview for a GLB asset.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--view", choices=["side", "front"], default="side")
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    return parser.parse_args(argv)


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def scene_bounds() -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in mesh_objects():
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return Vector((-1.0, -1.0, -1.0)), Vector((1.0, 1.0, 1.0))
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.import_scene.gltf(filepath=str(input_path))

    min_v, max_v = scene_bounds()
    center = (min_v + max_v) / 2.0
    size = max((max_v - min_v).x, (max_v - min_v).y, (max_v - min_v).z)

    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    if args.view == "side":
        camera.location = center + Vector((size * 2.8, 0.0, 0.0))
    else:
        camera.location = center + Vector((0.0, -size * 2.8, 0.0))
    look_at(camera, center)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = size * 1.8
    bpy.context.scene.camera = camera

    light_data = bpy.data.lights.new("PreviewKey", "AREA")
    light = bpy.data.objects.new("PreviewKey", light_data)
    bpy.context.collection.objects.link(light)
    light.location = center + Vector((size * 1.2, -size * 1.5, size * 2.2))
    light_data.energy = 550
    light_data.size = size * 2.0

    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    if hasattr(bpy.context.scene, "eevee"):
        bpy.context.scene.eevee.taa_render_samples = 64
    bpy.context.scene.render.resolution_x = 1400
    bpy.context.scene.render.resolution_y = 900
    bpy.context.scene.view_settings.view_transform = "Filmic"
    bpy.context.scene.view_settings.look = "Medium High Contrast"
    bpy.context.scene.render.film_transparent = False
    bpy.context.scene.world.color = (0.78, 0.80, 0.82)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    print(f"Rendered preview: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
