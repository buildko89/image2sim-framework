from __future__ import annotations

import argparse
import json
import math
import sys
from array import array
from pathlib import Path

import bpy
from mathutils import Vector


TEXTURE_SIZE = 1024
ALPHA_THRESHOLD = 0.08


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate photo camera projection textures for the rigged cat.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--side-image", required=True)
    parser.add_argument("--front-image", required=True)
    parser.add_argument("--back-image", required=True)
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


def world_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return Vector((-1.0, -1.0, -1.0)), Vector((1.0, 1.0, 1.0))
    low = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    high = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return low, high


def ensure_uv(mesh: bpy.types.Object) -> dict:
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name="PhotoProjectionUV")
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.03, area_weight=0.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    mesh.data.update()
    return {
        "mesh": mesh.name,
        "uv_layer_count": len(mesh.data.uv_layers),
        "active_uv": mesh.data.uv_layers.active.name if mesh.data.uv_layers.active else None,
    }


class ProjectionImage:
    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self.image = bpy.data.images.load(str(path), check_existing=True)
        self.image.colorspace_settings.name = "sRGB"
        self.width, self.height = self.image.size
        self.pixels = list(self.image.pixels[:])
        self.alpha_bbox = self._alpha_bbox()

    def _alpha_at_index(self, x: int, y: int) -> float:
        return self.pixels[(y * self.width + x) * 4 + 3]

    def _alpha_bbox(self) -> tuple[int, int, int, int]:
        min_x = self.width
        min_y = self.height
        max_x = 0
        max_y = 0
        found = False
        step = 2 if max(self.width, self.height) > 1300 else 1
        for y in range(0, self.height, step):
            row = y * self.width * 4
            for x in range(0, self.width, step):
                if self.pixels[row + x * 4 + 3] > ALPHA_THRESHOLD:
                    min_x = min(min_x, x)
                    min_y = min(min_y, y)
                    max_x = max(max_x, x)
                    max_y = max(max_y, y)
                    found = True
        if not found:
            return 0, 0, self.width - 1, self.height - 1
        pad_x = int((max_x - min_x) * 0.025)
        pad_y = int((max_y - min_y) * 0.025)
        return (
            max(0, min_x - pad_x),
            max(0, min_y - pad_y),
            min(self.width - 1, max_x + pad_x),
            min(self.height - 1, max_y + pad_y),
        )

    def sample(self, u: float, v: float) -> tuple[float, float, float, float] | None:
        if u < 0.0 or u > 1.0 or v < 0.0 or v > 1.0:
            return None
        min_x, min_y, max_x, max_y = self.alpha_bbox
        x = int(round(min_x + u * max(1, max_x - min_x)))
        y = int(round(min_y + v * max(1, max_y - min_y)))
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        index = (y * self.width + x) * 4
        alpha = self.pixels[index + 3]
        if alpha <= ALPHA_THRESHOLD:
            return None
        color = (
            self.pixels[index],
            self.pixels[index + 1],
            self.pixels[index + 2],
            alpha,
        )
        return color

    def report(self) -> dict:
        return {
            "name": self.name,
            "path": str(self.path),
            "size": [self.width, self.height],
            "alpha_bbox": list(self.alpha_bbox),
        }


def normalize(value: float, low: float, high: float) -> float:
    if math.isclose(high, low):
        return 0.5
    return (value - low) / (high - low)


def projected_sample(
    point: Vector,
    normal: Vector,
    low: Vector,
    high: Vector,
    sources: dict[str, ProjectionImage],
) -> tuple[float, float, float, float] | None:
    nx = abs(normal.x)
    ny_front = max(0.0, -normal.y)
    ny_back = max(0.0, normal.y)
    nz_top = max(0.0, normal.z)
    choices = [
        ("side", nx + 0.24),
        ("front", ny_front + 0.12),
        ("back", ny_back * 0.72 + nz_top * 0.58),
    ]
    choices.sort(key=lambda item: item[1], reverse=True)

    tx = normalize(point.x, low.x, high.x)
    ty = normalize(point.y, low.y, high.y)
    tz = normalize(point.z, low.z, high.z)
    coords = {
        "side": (1.0 - ty, 1.0 - tz),
        "front": (tx, 1.0 - tz),
        "back": (tx, 1.0 - ty),
    }
    for name, weight in choices:
        if weight <= 0.05:
            continue
        color = sources[name].sample(*coords[name])
        if color is not None:
            return color
    return None


def barycentric(px: float, py: float, a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> tuple[float, float, float] | None:
    denom = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(denom) < 1e-9:
        return None
    w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / denom
    w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / denom
    w2 = 1.0 - w0 - w1
    if w0 < -0.001 or w1 < -0.001 or w2 < -0.001:
        return None
    return w0, w1, w2


def write_pixel(buffer: array, width: int, x: int, y: int, color: tuple[float, float, float, float]) -> None:
    index = (y * width + x) * 4
    buffer[index] = color[0]
    buffer[index + 1] = color[1]
    buffer[index + 2] = color[2]
    buffer[index + 3] = 1.0


def rasterize_triangle(
    buffer: array,
    coverage: bytearray,
    uv: list[Vector],
    points: list[Vector],
    normal: Vector,
    low: Vector,
    high: Vector,
    sources: dict[str, ProjectionImage],
) -> int:
    tex_coords = [(uv_point.x * (TEXTURE_SIZE - 1), (1.0 - uv_point.y) * (TEXTURE_SIZE - 1)) for uv_point in uv]
    min_x = max(0, int(math.floor(min(p[0] for p in tex_coords))))
    max_x = min(TEXTURE_SIZE - 1, int(math.ceil(max(p[0] for p in tex_coords))))
    min_y = max(0, int(math.floor(min(p[1] for p in tex_coords))))
    max_y = min(TEXTURE_SIZE - 1, int(math.ceil(max(p[1] for p in tex_coords))))
    painted = 0
    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            weights = barycentric(x + 0.5, y + 0.5, tex_coords[0], tex_coords[1], tex_coords[2])
            if weights is None:
                continue
            point = points[0] * weights[0] + points[1] * weights[1] + points[2] * weights[2]
            color = projected_sample(point, normal, low, high, sources)
            if color is None:
                continue
            write_pixel(buffer, TEXTURE_SIZE, x, y, color)
            coverage[y * TEXTURE_SIZE + x] = 1
            painted += 1
    return painted


def soften_unpainted(buffer: array, coverage: bytearray) -> int:
    fill_color = (0.82, 0.76, 0.66, 1.0)
    filled = 0
    for y in range(TEXTURE_SIZE):
        for x in range(TEXTURE_SIZE):
            index = y * TEXTURE_SIZE + x
            if coverage[index]:
                continue
            write_pixel(buffer, TEXTURE_SIZE, x, y, fill_color)
            filled += 1
    return filled


def bake_mesh_texture(
    mesh: bpy.types.Object,
    texture_dir: Path,
    low: Vector,
    high: Vector,
    sources: dict[str, ProjectionImage],
) -> dict:
    uv_report = ensure_uv(mesh)
    uv_layer = mesh.data.uv_layers.active
    if uv_layer is None:
        raise RuntimeError(f"No UV layer available on {mesh.name}")

    buffer = array("f", [0.0, 0.0, 0.0, 1.0] * (TEXTURE_SIZE * TEXTURE_SIZE))
    coverage = bytearray(TEXTURE_SIZE * TEXTURE_SIZE)
    normal_matrix = mesh.matrix_world.to_3x3().inverted().transposed()
    painted = 0
    triangle_count = 0

    for polygon in mesh.data.polygons:
        loop_indices = list(polygon.loop_indices)
        if len(loop_indices) < 3:
            continue
        for offset in range(1, len(loop_indices) - 1):
            tri_loop_indices = [loop_indices[0], loop_indices[offset], loop_indices[offset + 1]]
            uv_points = [uv_layer.data[index].uv.copy() for index in tri_loop_indices]
            world_points = [mesh.matrix_world @ mesh.data.vertices[mesh.data.loops[index].vertex_index].co for index in tri_loop_indices]
            normal = (normal_matrix @ polygon.normal).normalized()
            painted += rasterize_triangle(buffer, coverage, uv_points, world_points, normal, low, high, sources)
            triangle_count += 1

    filled = soften_unpainted(buffer, coverage)
    image_name = f"{mesh.name}_PhotoCameraProjection"
    image = bpy.data.images.new(image_name, width=TEXTURE_SIZE, height=TEXTURE_SIZE, alpha=False)
    image.pixels.foreach_set(buffer)
    image_path = texture_dir / f"{mesh.name}_photo_camera_projection.png"
    image.filepath_raw = str(image_path)
    image.file_format = "PNG"
    image.save()
    assign_projected_material(mesh, image)
    return {
        "mesh": mesh.name,
        "texture": str(image_path),
        "uv": uv_report,
        "triangles": triangle_count,
        "painted_pixels": painted,
        "filled_pixels": filled,
    }


def assign_projected_material(mesh: bpy.types.Object, image: bpy.types.Image) -> None:
    material = bpy.data.materials.new(f"PhotoCat_CameraProjected_{mesh.name}")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    texture_node = nodes.new(type="ShaderNodeTexImage")
    texture_node.name = f"{mesh.name}_PhotoProjectionTexture"
    texture_node.image = image
    texture_node.extension = "EXTEND"
    if bsdf is not None:
        links.new(texture_node.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 0.96
    mesh.data.materials.clear()
    mesh.data.materials.append(material)
    for polygon in mesh.data.polygons:
        polygon.material_index = 0


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

    sources = {
        "side": ProjectionImage("side", Path(args.side_image)),
        "front": ProjectionImage("front", Path(args.front_image)),
        "back": ProjectionImage("back", Path(args.back_image)),
    }
    targets = skinned_mesh_objects()
    low, high = world_bounds(targets)
    bake_reports = [bake_mesh_texture(mesh, texture_dir, low, high, sources) for mesh in targets]

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx)

    report = {
        "task": "Task 6.7: Photo Camera Projection Bake Pass",
        "input": str(input_path),
        "sources": {name: source.report() for name, source in sources.items()},
        "texture_dir": str(texture_dir),
        "bounds": {
            "low": [round(value, 6) for value in low],
            "high": [round(value, 6) for value in high],
        },
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "bake_reports": bake_reports,
        "mesh_count": len(mesh_objects()),
        "armature_count": len(armature_objects()),
        "action_count": len(bpy.data.actions),
        "notes": [
            "This pass uses real photo cutouts as orthographic camera projection sources.",
            "Side projection maps model Y/Z to the side photo; front maps X/Z; back maps X/Y.",
            "The result is a diagnostic bake, not a calibrated camera solve.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved photo camera projection Blend: {output_blend}")
    print(f"Exported photo camera projection GLB: {output_glb}")
    print(f"Exported photo camera projection FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
