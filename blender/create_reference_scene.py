from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Blender reference scene from image files.")
    parser.add_argument("--images-json", required=True, help="JSON file containing image path records.")
    parser.add_argument("--output-blend", required=True, help="Output .blend file path.")
    parser.add_argument("--output-glb", help="Optional output .glb file path.")
    parser.add_argument("--reference-mode", choices=["planes", "empties"], default="planes")
    parser.add_argument("--spacing", type=float, default=2.5)
    parser.add_argument("--max-width", type=float, default=2.0)
    parser.add_argument("--export-glb", action="store_true")
    return parser.parse_args()


def load_image_records(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        records = json.load(handle)
    if not isinstance(records, list):
        raise ValueError("images-json must contain a list of image records.")
    return records


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()


def image_dimensions(image: bpy.types.Image) -> tuple[float, float]:
    width, height = image.size
    if not width or not height:
        return 1.0, 1.0
    return float(width), float(height)


def scaled_plane_size(width: float, height: float, max_width: float) -> tuple[float, float]:
    aspect = height / width if width else 1.0
    return max_width, max_width * aspect


def create_image_plane(image_path: Path, name: str, location: tuple[float, float, float], max_width: float) -> bpy.types.Object:
    image = bpy.data.images.load(str(image_path), check_existing=True)
    width, height = image_dimensions(image)
    plane_width, plane_height = scaled_plane_size(width, height, max_width)

    bpy.ops.mesh.primitive_plane_add(size=1.0, location=location, rotation=(math.radians(90), 0.0, 0.0))
    plane = bpy.context.object
    plane.name = name
    plane.dimensions = (plane_width, plane_height, 1.0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    material = bpy.data.materials.new(f"{name}_material")
    material.use_nodes = True
    material.blend_method = "BLEND"
    material.use_screen_refraction = True
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    material.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    material.node_tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    plane.data.materials.append(material)
    return plane


def create_image_empty(image_path: Path, name: str, location: tuple[float, float, float], max_width: float) -> bpy.types.Object:
    image = bpy.data.images.load(str(image_path), check_existing=True)
    width, height = image_dimensions(image)
    plane_width, _ = scaled_plane_size(width, height, max_width)

    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "IMAGE"
    empty.data = image
    empty.empty_display_size = plane_width
    empty.location = location
    bpy.context.collection.objects.link(empty)
    return empty


def add_camera_and_light(count: int, spacing: float) -> None:
    center_x = ((count - 1) * spacing) / 2 if count else 0.0
    bpy.ops.object.light_add(type="AREA", location=(center_x, -3.0, 4.0))
    light = bpy.context.object
    light.name = "Reference_Area_Light"
    light.data.energy = 350
    light.data.size = 5

    bpy.ops.object.camera_add(location=(center_x, -7.0, 3.0), rotation=(math.radians(65), 0.0, 0.0))
    bpy.context.scene.camera = bpy.context.object


def add_reference_objects(records: list[dict], reference_mode: str, spacing: float, max_width: float) -> list[str]:
    created: list[str] = []
    count = len(records)
    start_x = -((count - 1) * spacing) / 2 if count else 0.0

    for index, record in enumerate(records):
        image_path = Path(record["path"])
        name = f"reference_{index + 1:02d}_{image_path.stem}"
        location = (start_x + index * spacing, 0.0, 1.0)
        if reference_mode == "empties":
            obj = create_image_empty(image_path, name, location, max_width)
        else:
            obj = create_image_plane(image_path, name, location, max_width)
        obj["source_path"] = str(image_path)
        obj["source_role"] = record.get("role", "reference")
        created.append(obj.name)

    return created


def main() -> int:
    args = parse_args()
    image_records = load_image_records(Path(args.images_json))
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb) if args.output_glb else None

    clear_scene()
    created = add_reference_objects(image_records, args.reference_mode, args.spacing, args.max_width)
    add_camera_and_light(len(created), args.spacing)

    bpy.context.scene.unit_settings.system = "METRIC"
    try:
        bpy.context.scene.render.engine = "BLENDER_EEVEE_NEXT"
    except TypeError:
        bpy.context.scene.render.engine = "BLENDER_EEVEE"

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))

    if args.export_glb and output_glb:
        output_glb.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.export_scene.gltf(filepath=str(output_glb), export_format="GLB")

    print(f"Created {len(created)} reference objects.")
    print(f"Saved blend: {output_blend}")
    if args.export_glb and output_glb:
        print(f"Saved glb: {output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
