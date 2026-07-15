from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import bpy
from mathutils import Vector


DEFAULT_PALETTE = {
    "white": (0.95, 0.94, 0.91),
    "cream": (0.86, 0.77, 0.66),
    "warm_brown": (0.68, 0.32, 0.08),
    "dark": (0.09, 0.07, 0.06),
    "accent": (0.45, 0.22, 0.10),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply palette-driven vertex-color bake to a cat model.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--palette", required=True)
    parser.add_argument("--texture-dir", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--output-fbx", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--resolution", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--axis-left-right", choices=["X", "Y", "Z"], default="X")
    parser.add_argument("--axis-front-back", choices=["X", "Y", "Z"], default="Y")
    parser.add_argument("--axis-up", choices=["X", "Y", "Z"], default="Z")
    parser.add_argument("--front-positive", default="true")
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    return parser.parse_args(argv)


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_scene(input_path: Path) -> None:
    suffix = input_path.suffix.lower()
    if suffix == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(input_path))
        return
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(input_path))
        return
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(input_path))
        return
    raise RuntimeError(f"Unsupported input model: {input_path}")


def mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]


def armature_objects() -> list[bpy.types.Object]:
    return [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]


def skinned_mesh_objects() -> list[bpy.types.Object]:
    return [obj for obj in mesh_objects() if any(modifier.type == "ARMATURE" for modifier in obj.modifiers)]


def target_meshes() -> list[bpy.types.Object]:
    skinned = skinned_mesh_objects()
    return skinned if skinned else mesh_objects()


def split_body_shell(meshes: list[bpy.types.Object]) -> tuple[list[bpy.types.Object], list[bpy.types.Object]]:
    shell = [obj for obj in meshes if "fur_shell" in obj.name.lower() or "shell" in obj.name.lower()]
    shell_names = {obj.name for obj in shell}
    body = [obj for obj in meshes if obj.name not in shell_names]
    if not body and meshes:
        body = meshes
        shell = []
    return body, shell


def axis_value(vector: Vector, axis: str) -> float:
    if axis == "X":
        return vector.x
    if axis == "Y":
        return vector.y
    return vector.z


def bounds_for_meshes(meshes: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in meshes:
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    if not points:
        return Vector((-1.0, -1.0, -1.0)), Vector((1.0, 1.0, 1.0))
    return (
        Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))),
        Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))),
    )


def normalized_coordinate(
    point: Vector,
    low: Vector,
    high: Vector,
    axis_left_right: str,
    axis_front_back: str,
    axis_up: str,
    front_positive: bool,
) -> tuple[float, float, float]:
    def norm(axis: str) -> float:
        lo = axis_value(low, axis)
        hi = axis_value(high, axis)
        if math.isclose(lo, hi):
            return 0.5
        return max(0.0, min(1.0, (axis_value(point, axis) - lo) / (hi - lo)))

    u = norm(axis_left_right)
    v = norm(axis_front_back)
    w = norm(axis_up)
    if not front_positive:
        v = 1.0 - v
    return u, v, w


def parse_palette_simple(path: Path) -> tuple[dict[str, tuple[float, float, float]], dict[str, str]]:
    palette = dict(DEFAULT_PALETTE)
    sources = {name: "fallback" for name in palette}
    current_name: str | None = None
    rgb_pattern = re.compile(r"rgb:\s*\[([^\]]+)\]")
    source_pattern = re.compile(r"source:\s*([A-Za-z_]+)")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("- name:"):
            current_name = line.split(":", 1)[1].strip().strip("\"'")
            continue
        if current_name and line.startswith("rgb:"):
            match = rgb_pattern.search(line)
            if match:
                values = [float(item.strip()) for item in match.group(1).split(",")]
                if len(values) == 3:
                    palette[current_name] = (values[0], values[1], values[2])
            continue
        if current_name and line.startswith("- "):
            # Block-style rgb emitted by PyYAML; handled in a second pass below.
            continue
        if current_name and line.startswith("source:"):
            match = source_pattern.search(line)
            if match:
                sources[current_name] = match.group(1)

    # Support block-style rgb emitted by PyYAML.
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line.startswith("- name:"):
            continue
        name = line.split(":", 1)[1].strip().strip("\"'")
        rgb_values: list[float] = []
        source = sources.get(name, "fallback")
        cursor = index + 1
        while cursor < len(lines):
            current = lines[cursor].strip()
            if current.startswith("- name:"):
                break
            if current.startswith("rgb: ["):
                match = rgb_pattern.search(current)
                if match:
                    rgb_values = [float(item.strip()) for item in match.group(1).split(",")]
            elif current == "rgb:":
                probe = cursor + 1
                while probe < len(lines):
                    item = lines[probe].strip()
                    if not item.startswith("- "):
                        break
                    try:
                        rgb_values.append(float(item[2:].strip()))
                    except ValueError:
                        break
                    probe += 1
            elif current.startswith("source:"):
                source = current.split(":", 1)[1].strip()
            cursor += 1
        if len(rgb_values) == 3:
            palette[name] = (rgb_values[0], rgb_values[1], rgb_values[2])
            sources[name] = source
    return palette, sources


def load_palette(path: Path) -> tuple[dict[str, tuple[float, float, float]], dict[str, str]]:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        result = dict(DEFAULT_PALETTE)
        sources = {name: "fallback" for name in result}
        for entry in data.get("palette", []):
            name = str(entry.get("name", ""))
            rgb = entry.get("rgb")
            if name and isinstance(rgb, list) and len(rgb) == 3:
                result[name] = (float(rgb[0]), float(rgb[1]), float(rgb[2]))
                sources[name] = str(entry.get("source", "unknown"))
        return result, sources
    except Exception:
        return parse_palette_simple(path)


def smooth_hash_noise(u: float, v: float, w: float, scale: float = 5.0, seed: int = 0) -> float:
    su, sv, sw = u * scale, v * scale, w * scale
    value = (
        math.sin(su * 12.9898 + sv * 78.233 + seed)
        * math.cos(sv * 43.758 + sw * 15.432 + seed * 1.7)
        * math.sin(sw * 27.616 + su * 51.329 + seed * 2.3)
    )
    return math.sin(value * 43758.5453) * 0.5 + 0.5


def fur_direction_noise(u: float, v: float, w: float, strength: float = 0.045, seed: int = 0) -> float:
    wave = math.sin(u * 42.0 + v * 9.0 + seed) * math.sin(w * 35.0 + seed * 0.37)
    return wave * strength


def clamp_color(color: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(max(0.0, min(1.0, value)) for value in color)


def add_fur_direction_noise(
    color: tuple[float, float, float],
    u: float,
    v: float,
    w: float,
    seed: int,
) -> tuple[float, float, float]:
    noise = fur_direction_noise(u, v, w, seed=seed)
    return clamp_color((color[0] + noise, color[1] + noise, color[2] + noise))


def soften_shell_color(color: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = color
    return (
        min(1.0, r * 0.60 + 0.40),
        min(1.0, g * 0.60 + 0.40),
        min(1.0, b * 0.60 + 0.40),
    )


def blend_color(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    return (
        a[0] * (1.0 - t) + b[0] * t,
        a[1] * (1.0 - t) + b[1] * t,
        a[2] * (1.0 - t) + b[2] * t,
    )


def get_procedural_calico_color(
    u: float,
    v: float,
    w: float,
    palette: dict[str, tuple[float, float, float]],
    is_shell: bool,
    seed: int,
) -> tuple[float, float, float]:
    white = palette.get("white", DEFAULT_PALETTE["white"])
    cream = palette.get("cream", DEFAULT_PALETTE["cream"])
    warm = palette.get("warm_brown", DEFAULT_PALETTE["warm_brown"])
    dark = palette.get("dark", DEFAULT_PALETTE["dark"])
    accent = palette.get("accent", DEFAULT_PALETTE["accent"])

    base_color = cream

    if w < 0.30 or (0.42 < v < 0.76 and abs(u - 0.5) < 0.20):
        base_color = white

    if v > 0.72 and w > 0.50:
        if abs(u - 0.5) < 0.08:
            base_color = white
        elif u > 0.5:
            base_color = warm
        else:
            base_color = dark

    patch_noise = smooth_hash_noise(u, v, w, scale=5.0, seed=seed)
    if w > 0.46 and patch_noise > 0.61:
        base_color = warm if patch_noise < 0.82 else dark
    elif w > 0.42 and patch_noise > 0.54:
        base_color = blend_color(base_color, accent, 0.35)

    if v < 0.18 and w > 0.35:
        stripe = int(v * 18.0 + smooth_hash_noise(u, v, w, 3.0, seed) * 2.0) % 2
        base_color = warm if stripe == 0 else dark

    color = add_fur_direction_noise(base_color, u, v, w, seed=seed)
    if is_shell:
        color = soften_shell_color(color)
    return color


def ensure_uv(mesh: bpy.types.Object) -> dict:
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    created = False
    if not mesh.data.uv_layers:
        mesh.data.uv_layers.new(name="PaletteBakeUV")
        created = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.15192, island_margin=0.025, area_weight=0.0)
        bpy.ops.object.mode_set(mode="OBJECT")
    mesh.data.uv_layers.active = mesh.data.uv_layers[0]
    mesh.data.update()
    return {
        "mesh": mesh.name,
        "uv_layer_count": len(mesh.data.uv_layers),
        "active_uv": mesh.data.uv_layers.active.name if mesh.data.uv_layers.active else None,
        "created_uv": created,
    }


def apply_vertex_colors(
    mesh: bpy.types.Object,
    low: Vector,
    high: Vector,
    palette: dict[str, tuple[float, float, float]],
    is_shell: bool,
    seed: int,
    axis_left_right: str,
    axis_front_back: str,
    axis_up: str,
    front_positive: bool,
) -> dict:
    while mesh.data.color_attributes:
        mesh.data.color_attributes.remove(mesh.data.color_attributes[0])
    color_attr = mesh.data.color_attributes.new(name="PaletteColor", type="FLOAT_COLOR", domain="POINT")
    for index, vertex in enumerate(mesh.data.vertices):
        point = mesh.matrix_world @ vertex.co
        u, v, w = normalized_coordinate(point, low, high, axis_left_right, axis_front_back, axis_up, front_positive)
        r, g, b = get_procedural_calico_color(u, v, w, palette, is_shell=is_shell, seed=seed)
        color_attr.data[index].color = (r, g, b, 1.0)
    return {"mesh": mesh.name, "is_shell": is_shell, "vertices_colored": len(mesh.data.vertices)}


def make_bake_material(image: bpy.types.Image) -> bpy.types.Material:
    material = bpy.data.materials.new(f"PaletteBakeEmit_{image.name}")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    attribute = nodes.new("ShaderNodeAttribute")
    attribute.attribute_name = "PaletteColor"
    texture = nodes.new("ShaderNodeTexImage")
    texture.image = image
    nodes.active = texture
    links.new(attribute.outputs["Color"], emission.inputs["Color"])
    links.new(emission.outputs["Emission"], output.inputs["Surface"])
    return material


def make_final_material(name: str, image_path: Path, alpha: float = 1.0) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    material.blend_method = "BLEND" if alpha < 1.0 else "OPAQUE"
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    texture = nodes.new("ShaderNodeTexImage")
    image = bpy.data.images.load(str(image_path), check_existing=True)
    texture.image = image
    links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.94
    if alpha < 1.0 and "Alpha" in bsdf.inputs:
        bsdf.inputs["Alpha"].default_value = alpha
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    return material


def bake_group(
    meshes: list[bpy.types.Object],
    texture_path: Path,
    image_name: str,
    resolution: int,
) -> dict | None:
    if not meshes:
        return None
    image = bpy.data.images.new(image_name, width=resolution, height=resolution, alpha=True)
    image.generated_color = (0.86, 0.80, 0.72, 1.0)
    bake_material = make_bake_material(image)
    original_materials = {mesh.name: [slot.material for slot in mesh.material_slots] for mesh in meshes}
    for mesh in meshes:
        mesh.data.materials.clear()
        mesh.data.materials.append(bake_material)

    bpy.context.scene.render.engine = "CYCLES"
    bpy.context.scene.cycles.device = "CPU"
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.cycles.bake_type = "EMIT"
    bpy.context.scene.render.bake.use_clear = True
    bpy.context.scene.render.bake.margin = 16

    bpy.ops.object.select_all(action="DESELECT")
    for mesh in meshes:
        mesh.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.bake(type="EMIT", save_mode="INTERNAL")

    texture_path.parent.mkdir(parents=True, exist_ok=True)
    image.filepath_raw = str(texture_path)
    image.file_format = "PNG"
    image.save()

    for mesh in meshes:
        mesh.data.materials.clear()
        for material in original_materials[mesh.name]:
            if material is not None:
                mesh.data.materials.append(material)
    bpy.data.materials.remove(bake_material)
    return {
        "texture": str(texture_path),
        "image": image_name,
        "meshes": [mesh.name for mesh in meshes],
        "resolution": resolution,
    }


def assign_final_materials(body: list[bpy.types.Object], shell: list[bpy.types.Object], body_texture: Path, shell_texture: Path | None) -> None:
    body_material = make_final_material("Cat_Palette_Body_Material", body_texture, alpha=1.0)
    shell_material = make_final_material("Cat_Palette_Fur_Shell_Material", shell_texture or body_texture, alpha=0.42)
    for mesh in body:
        mesh.data.materials.clear()
        mesh.data.materials.append(body_material)
    for mesh in shell:
        mesh.data.materials.clear()
        mesh.data.materials.append(shell_material)


def action_report() -> list[dict]:
    result = []
    for action in bpy.data.actions:
        start, end = action.frame_range
        result.append({"name": action.name, "frame_start": float(start), "frame_end": float(end)})
    return result


def mesh_report(meshes: list[bpy.types.Object]) -> list[dict]:
    return [
        {
            "name": mesh.name,
            "vertex_count": len(mesh.data.vertices),
            "polygon_count": len(mesh.data.polygons),
            "material_count": len(mesh.data.materials),
            "uv_layers": [layer.name for layer in mesh.data.uv_layers],
            "color_attributes": [attr.name for attr in mesh.data.color_attributes],
            "modifiers": [modifier.type for modifier in mesh.modifiers],
        }
        for mesh in meshes
    ]


def export_selected(output_glb: Path, output_fbx: Path, meshes: list[bpy.types.Object]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    export_objects = list(meshes) + armature_objects()
    for obj in export_objects:
        obj.select_set(True)
    if meshes:
        bpy.context.view_layer.objects.active = meshes[0]
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
    palette_path = Path(args.palette)
    texture_dir = Path(args.texture_dir)
    output_blend = Path(args.output_blend)
    output_glb = Path(args.output_glb)
    output_fbx = Path(args.output_fbx)
    report_path = Path(args.report)
    front_positive = parse_bool(args.front_positive)

    load_scene(input_path)
    bpy.context.scene.unit_settings.system = "METRIC"

    palette, palette_sources = load_palette(palette_path)
    meshes = target_meshes()
    if not meshes:
        raise RuntimeError("No target meshes found.")
    body, shell = split_body_shell(meshes)
    all_targets = body + shell
    low, high = bounds_for_meshes(all_targets)

    uv_reports = [ensure_uv(mesh) for mesh in all_targets]
    color_reports = []
    for mesh in body:
        color_reports.append(
            apply_vertex_colors(
                mesh,
                low,
                high,
                palette,
                is_shell=False,
                seed=args.seed,
                axis_left_right=args.axis_left_right,
                axis_front_back=args.axis_front_back,
                axis_up=args.axis_up,
                front_positive=front_positive,
            )
        )
    for mesh in shell:
        color_reports.append(
            apply_vertex_colors(
                mesh,
                low,
                high,
                palette,
                is_shell=True,
                seed=args.seed,
                axis_left_right=args.axis_left_right,
                axis_front_back=args.axis_front_back,
                axis_up=args.axis_up,
                front_positive=front_positive,
            )
        )

    body_texture = texture_dir / "cat_body_basecolor.png"
    shell_texture = texture_dir / "cat_fur_shell_basecolor.png"
    body_bake = bake_group(body, body_texture, "CatPaletteBodyBaseColor", args.resolution)
    shell_bake = bake_group(shell, shell_texture, "CatPaletteFurShellBaseColor", args.resolution) if shell else None
    assign_final_materials(body, shell, body_texture, shell_texture if shell_bake else None)

    texture_dir.mkdir(parents=True, exist_ok=True)
    bake_manifest = {
        "body_bake": body_bake,
        "shell_bake": shell_bake,
        "palette": {name: list(color) for name, color in palette.items()},
        "palette_sources": palette_sources,
        "resolution": args.resolution,
        "seed": args.seed,
    }
    (texture_dir / "bake_manifest.json").write_text(json.dumps(bake_manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    export_selected(output_glb, output_fbx, all_targets)

    report = {
        "task": "Task 81: Palette Driven Vertex Color Bake",
        "input": str(input_path),
        "palette_path": str(palette_path),
        "texture_dir": str(texture_dir),
        "outputs": {"blend": str(output_blend), "glb": str(output_glb), "fbx": str(output_fbx)},
        "axis": {
            "left_right": args.axis_left_right,
            "front_back": args.axis_front_back,
            "up": args.axis_up,
            "front_positive": front_positive,
        },
        "bounds": {"low": [round(value, 6) for value in low], "high": [round(value, 6) for value in high]},
        "palette": {name: list(color) for name, color in palette.items()},
        "palette_sources": palette_sources,
        "uv_reports": uv_reports,
        "color_reports": color_reports,
        "bake_reports": {"body": body_bake, "shell": shell_bake},
        "meshes": mesh_report(all_targets),
        "armature_count": len(armature_objects()),
        "actions": action_report(),
        "notes": [
            "Initial implementation uses palette-driven vertex color bake, not shader node auto-generation.",
            "Coordinates are normalized by target mesh bounding box before calico pattern assignment.",
            "Body and fur shell are baked separately when a shell mesh is present.",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved palette vertex bake Blend: {output_blend}")
    print(f"Exported GLB: {output_glb}")
    print(f"Exported FBX: {output_fbx}")
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
