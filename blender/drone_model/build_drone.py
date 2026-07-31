from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import bpy
from mathutils import Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="drone2のパラメトリックモデルを生成します。")
    parser.add_argument("--config-json", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def mm(value: float) -> float:
    return float(value) / 1000.0


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config-jsonの最上位はobjectである必要があります。")
    return data


def required_object_names(config: dict[str, Any]) -> set[str]:
    names = {"drone_root", "body_core", "center_of_mass"}
    arm_enabled = bool(config.get("arm", {}).get("enabled", True))
    guard_enabled = bool(config.get("guard", {}).get("enabled", True))
    landing_enabled = bool(config.get("landing", {}).get("enabled", True))
    for rotor_id in config["derived"]["rotor_ids"]:
        names.update({f"motor_{rotor_id}", f"rotor_{rotor_id}", f"motor_{rotor_id}_axis"})
        if arm_enabled:
            names.add(f"arm_{rotor_id}")
        if guard_enabled:
            names.add(f"guard_{rotor_id}")
        if landing_enabled:
            names.add(f"landing_leg_{rotor_id}")
    return names


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
    if scene.world is None:
        scene.world = bpy.data.worlds.new("DroneWorld")
    scene.world.color = (0.055, 0.055, 0.065)


def make_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def move_to_collection(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    for current in list(obj.users_collection):
        current.objects.unlink(obj)
    collection.objects.link(obj)


def make_material(name: str, color: tuple[float, float, float, float], metallic: float = 0.0, roughness: float = 0.5) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = color
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")
    if bsdf is not None:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Metallic"].default_value = metallic
        bsdf.inputs["Roughness"].default_value = roughness
    return material


def assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    if obj.type == "MESH":
        obj.data.materials.append(material)


def parent_to(obj: bpy.types.Object, parent: bpy.types.Object) -> None:
    obj.parent = parent


def create_empty(name: str, location: Iterable[float], collection: bpy.types.Collection, parent: bpy.types.Object | None = None, size: float = 0.005) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "ARROWS"
    obj.empty_display_size = size
    obj.location = tuple(location)
    collection.objects.link(obj)
    if parent is not None:
        parent_to(obj, parent)
    return obj


def create_rounded_box(
    name: str,
    dimensions: tuple[float, float, float],
    location: tuple[float, float, float],
    bevel: float,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel > 0:
        modifier = obj.modifiers.new(name="寸法ベベル", type="BEVEL")
        modifier.width = bevel
        modifier.segments = 4
        modifier.limit_method = "ANGLE"
        bpy.ops.object.modifier_apply(modifier=modifier.name)
    move_to_collection(obj, collection)
    assign_material(obj, material)
    parent_to(obj, parent)
    return obj


def signed_power(value: float, power: float) -> float:
    if value == 0.0:
        return 0.0
    return math.copysign(abs(value) ** power, value)


def create_lofted_body(
    name: str,
    config: dict[str, Any],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """前後端へ向かって幅と高さが減る、実測外形内の閉じたボディを作る。"""
    width = mm(config["width_mm"])
    length = mm(config["length_mm"])
    height = mm(config["height_mm"])
    center_z = mm(config["center_z_mm"])
    longitudinal_segments = int(config["longitudinal_segments"])
    radial_segments = int(config["radial_segments"])
    width_power = float(config["width_profile_power"])
    height_power = float(config["height_profile_power"])
    cross_power = float(config["cross_section_power"])
    if longitudinal_segments < 4 or radial_segments < 8:
        raise ValueError("ボディ分割数が少なすぎます。")

    half_width = width / 2.0
    half_length = length / 2.0
    half_height = height / 2.0
    verts: list[tuple[float, float, float]] = [(0.0, -half_length, center_z)]
    ring_starts: list[int] = []

    for i in range(1, longitudinal_segments):
        fraction = i / longitudinal_segments
        y = -half_length + length * fraction
        profile = math.sin(math.pi * fraction)
        radius_x = half_width * profile**width_power
        radius_z = half_height * profile**height_power
        ring_starts.append(len(verts))
        for j in range(radial_segments):
            angle = 2.0 * math.pi * j / radial_segments
            x = radius_x * signed_power(math.cos(angle), cross_power)
            z = center_z + radius_z * signed_power(math.sin(angle), cross_power)
            verts.append((x, y, z))

    rear_tip = len(verts)
    verts.append((0.0, half_length, center_z))
    faces: list[tuple[int, ...]] = []
    first_ring = ring_starts[0]
    for j in range(radial_segments):
        next_j = (j + 1) % radial_segments
        faces.append((0, first_ring + j, first_ring + next_j))
    for ring_index in range(len(ring_starts) - 1):
        current = ring_starts[ring_index]
        following = ring_starts[ring_index + 1]
        for j in range(radial_segments):
            next_j = (j + 1) % radial_segments
            faces.append((current + j, following + j, following + next_j, current + next_j))
    last_ring = ring_starts[-1]
    for j in range(radial_segments):
        next_j = (j + 1) % radial_segments
        faces.append((rear_tip, last_ring + next_j, last_ring + j))

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.validate(verbose=False)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    assign_material(obj, material)
    parent_to(obj, parent)
    obj["part_type"] = "body_shell"
    obj["measured_length_mm"] = float(config["length_mm"])
    obj["measured_height_mm"] = float(config["height_mm"])
    return obj


def create_cylinder(
    name: str,
    radius: float,
    depth: float,
    location: tuple[float, float, float],
    collection: bpy.types.Collection,
    material: bpy.types.Material | None,
    parent: bpy.types.Object,
    vertices: int = 32,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    move_to_collection(obj, collection)
    if material is not None:
        assign_material(obj, material)
    parent_to(obj, parent)
    return obj


def create_cylinder_between(
    name: str,
    start: Vector,
    end: Vector,
    radius: float,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
    vertices: int = 12,
) -> bpy.types.Object:
    direction = end - start
    length = direction.length
    midpoint = (start + end) / 2.0
    obj = create_cylinder(name, radius, length, tuple(midpoint), collection, material, parent, vertices)
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.rotation_mode = "XYZ"
    return obj


def create_tapered_arm(
    name: str,
    start: Vector,
    end: Vector,
    root_width: float,
    tip_width: float,
    thickness: float,
    center_z: float,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    direction = Vector((end.x - start.x, end.y - start.y, 0.0)).normalized()
    side = Vector((-direction.y, direction.x, 0.0))
    low_z = center_z - thickness / 2.0
    high_z = center_z + thickness / 2.0
    points_2d = (
        start + side * root_width / 2.0,
        start - side * root_width / 2.0,
        end - side * tip_width / 2.0,
        end + side * tip_width / 2.0,
    )
    verts = [(point.x, point.y, z) for z in (low_z, high_z) for point in points_2d]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    assign_material(obj, material)
    parent_to(obj, parent)
    bevel = obj.modifiers.new(name="アーム角丸", type="BEVEL")
    bevel.width = min(thickness, tip_width) * 0.18
    bevel.segments = 2
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.select_set(False)
    return obj


def create_rotor_mesh(
    name: str,
    config: dict[str, Any],
    direction_name: str,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    diameter = mm(config["diameter_mm"])
    r0 = mm(config["blade_root_radius_mm"])
    r1 = diameter / 2.0
    w0 = mm(config["blade_root_width_mm"])
    w1 = mm(config["blade_tip_width_mm"])
    thickness = mm(config["blade_thickness_mm"])
    skew = mm(2.2) * (1.0 if direction_name == "ccw" else -1.0)
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for blade_index in range(int(config["blade_count"])):
        angle = blade_index * 2.0 * math.pi / int(config["blade_count"])
        forward = Vector((math.cos(angle), math.sin(angle), 0.0))
        side = Vector((-forward.y, forward.x, 0.0))
        corners = (
            forward * r0 + side * w0 / 2.0,
            forward * r0 - side * w0 / 2.0,
            forward * r1 - side * w1 / 2.0 + side * skew,
            forward * r1 + side * w1 / 2.0 + side * skew,
        )
        base = len(verts)
        verts.extend((point.x, point.y, z) for z in (-thickness / 2.0, thickness / 2.0) for point in corners)
        faces.extend(
            [
                (base + 0, base + 3, base + 2, base + 1),
                (base + 4, base + 5, base + 6, base + 7),
                (base + 0, base + 1, base + 5, base + 4),
                (base + 1, base + 2, base + 6, base + 5),
                (base + 2, base + 3, base + 7, base + 6),
                (base + 3, base + 0, base + 4, base + 7),
            ]
        )
    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    assign_material(obj, material)
    parent_to(obj, parent)
    return obj


def create_guard_arc(
    name: str,
    center: Vector,
    outer_diameter: float,
    tube_diameter: float,
    center_z: float,
    gap_deg: float,
    major_segments: int,
    minor_segments: int,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> tuple[bpy.types.Object, float, float]:
    tube_radius = tube_diameter / 2.0
    major_radius = outer_diameter / 2.0 - tube_radius
    toward_body = math.atan2(-center.y, -center.x)
    gap = math.radians(gap_deg)
    start = toward_body + gap / 2.0
    sweep = 2.0 * math.pi - gap
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for i in range(major_segments + 1):
        angle = start + sweep * i / major_segments
        for j in range(minor_segments):
            minor = 2.0 * math.pi * j / minor_segments
            radial = major_radius + tube_radius * math.cos(minor)
            verts.append((radial * math.cos(angle), radial * math.sin(angle), center_z + tube_radius * math.sin(minor)))
    for i in range(major_segments):
        for j in range(minor_segments):
            next_j = (j + 1) % minor_segments
            a = i * minor_segments + j
            b = i * minor_segments + next_j
            c = (i + 1) * minor_segments + next_j
            d = (i + 1) * minor_segments + j
            faces.append((a, b, c, d))

    start_cap = len(verts)
    verts.append((major_radius * math.cos(start), major_radius * math.sin(start), center_z))
    end_angle = start + sweep
    end_cap = len(verts)
    verts.append((major_radius * math.cos(end_angle), major_radius * math.sin(end_angle), center_z))
    end_ring = major_segments * minor_segments
    for j in range(minor_segments):
        next_j = (j + 1) % minor_segments
        faces.append((start_cap, next_j, j))
        faces.append((end_cap, end_ring + j, end_ring + next_j))

    mesh = bpy.data.meshes.new(f"{name}_mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = (center.x, center.y, 0.0)
    collection.objects.link(obj)
    assign_material(obj, material)
    parent_to(obj, parent)
    return obj, toward_body, major_radius


def create_collision_box(
    name: str,
    dimensions: tuple[float, float, float],
    location: tuple[float, float, float],
    collection: bpy.types.Collection,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    move_to_collection(obj, collection)
    obj.display_type = "WIRE"
    obj.hide_render = True
    obj["collision_shape"] = "box"
    parent_to(obj, parent)
    return obj


def mesh_objects(collection: bpy.types.Collection) -> list[bpy.types.Object]:
    return [obj for obj in collection.all_objects if obj.type == "MESH"]


def world_bounds(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    if not points:
        return Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 0.0))
    minimum = Vector((min(p.x for p in points), min(p.y for p in points), min(p.z for p in points)))
    maximum = Vector((max(p.x for p in points), max(p.y for p in points), max(p.z for p in points)))
    return minimum, maximum


def look_at(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def render_views(visual: bpy.types.Collection, cameras: bpy.types.Collection, output_dir: Path, resolution: int) -> dict[str, str]:
    objects = mesh_objects(visual)
    minimum, maximum = world_bounds(objects)
    center = (minimum + maximum) / 2.0
    longest = max(maximum - minimum)
    distance = max(longest * 4.0, 0.5)
    directions = {
        "front": Vector((0.0, -1.0, 0.0)),
        "back": Vector((0.0, 1.0, 0.0)),
        "left": Vector((-1.0, 0.0, 0.0)),
        "right": Vector((1.0, 0.0, 0.0)),
        "top": Vector((0.0, 0.0, 1.0)),
        "bottom": Vector((0.0, 0.0, -1.0)),
    }
    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    render_dir = output_dir / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}

    for view_name, direction in directions.items():
        camera_data = bpy.data.cameras.new(f"camera_{view_name}_data")
        camera = bpy.data.objects.new(f"camera_{view_name}", camera_data)
        cameras.objects.link(camera)
        camera_data.type = "ORTHO"
        camera_data.ortho_scale = longest * 1.18
        camera.location = center + direction * distance
        look_at(camera, center)
        scene.camera = camera
        path = render_dir / f"{view_name}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs[view_name] = str(path)
    return outputs


def export_glb(path: Path, collections: Iterable[bpy.types.Collection]) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    selected: list[bpy.types.Object] = []
    for collection in collections:
        for obj in collection.all_objects:
            if obj not in selected and obj.type in {"MESH", "EMPTY"}:
                obj.select_set(True)
                selected.append(obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_extras=True,
        export_cameras=False,
        export_lights=False,
    )


def add_scene_metadata(root: bpy.types.Object, config: dict[str, Any]) -> None:
    root["subject_id"] = str(config["subject_id"])
    root["schema_version"] = str(config["schema_version"])
    root["dimensions_provisional"] = bool(config["dimensions_provisional"])
    root["front_axis"] = "-Y"
    root["up_axis"] = "+Z"
    root["template_id"] = str(config.get("template_metadata", {}).get("template_id", "legacy"))
    root["layout_mode"] = str(config["derived"]["layout_mode"])
    root["rotor_count"] = int(config["derived"]["rotor_count"])
    for name in ("motor_center_diagonal_mm", "overall_width_mm", "overall_length_mm", "propeller_diameter_mm"):
        item = config.get("measurements", {}).get(name)
        if isinstance(item, dict) and item.get("value") is not None:
            root[name] = float(item["value"])


def build(config: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    setup_scene()
    visual = make_collection("MODEL_VISUAL")
    anchors = make_collection("ANCHORS")
    collision = make_collection("COLLISION")
    cameras = make_collection("CAMERAS")
    references = make_collection("REF_PHOTOS")
    for name, path in config.get("references", {}).items():
        references[f"source_{name}"] = str(path)

    dark = make_material("機体ダークグレー", (0.045, 0.052, 0.060, 1.0), metallic=0.15, roughness=0.34)
    black = make_material("ガードブラック", (0.008, 0.010, 0.012, 1.0), metallic=0.0, roughness=0.45)
    rotor_material = make_material("プロペラ", (0.025, 0.028, 0.032, 1.0), metallic=0.05, roughness=0.4)
    red = make_material("脚部レッド", (0.35, 0.012, 0.015, 1.0), metallic=0.05, roughness=0.42)

    root = create_empty("drone_root", (0.0, 0.0, 0.0), visual, None, size=0.01)
    add_scene_metadata(root, config)
    physics = config.get("physics", {})
    com = create_empty("center_of_mass", tuple(mm(v) for v in physics.get("center_of_mass_mm", [0.0, 0.0, 0.0])), anchors, root, size=0.008)
    com["anchor_type"] = "center_of_mass"
    com["source"] = str(physics.get("center_of_mass_source", "placeholder"))

    body = config["body"]
    body_shape = str(body.get("shape", "lofted"))
    if body_shape == "lofted":
        body_obj = create_lofted_body("body_core", body, visual, dark, root)
    elif body_shape == "rounded_box":
        body_obj = create_rounded_box(
            "body_core",
            (mm(body["width_mm"]), mm(body["length_mm"]), mm(body["height_mm"])),
            (0.0, 0.0, mm(body.get("center_z_mm", 0.0))),
            mm(body.get("bevel_mm", 2.0)),
            visual,
            dark,
            root,
        )
    else:
        raise ValueError(f"未対応のbody.shapeです: {body_shape}")
    body_obj["part_type"] = "body"

    arm = config["arm"]
    motor = config["motor"]
    propeller = config["propeller"]
    guard = config["guard"]
    landing = config["landing"]
    positions = config["derived"]["motor_positions_mm"]
    rotor_ids = config["derived"]["rotor_ids"]
    directions = config["derived"]["rotor_directions"]
    arm_enabled = bool(arm.get("enabled", True))
    guard_enabled = bool(guard.get("enabled", True))
    landing_enabled = bool(landing.get("enabled", True))
    guard_outer = mm(config["derived"]["guard_outer_diameter_mm"]) if guard_enabled else None

    for rotor_id in rotor_ids:
        position_mm = positions[rotor_id]
        motor_xy = Vector((mm(position_mm[0]), mm(position_mm[1]), 0.0))
        root_point = motor_xy * float(arm["root_fraction"])
        if arm_enabled:
            create_tapered_arm(
                f"arm_{rotor_id}", root_point, motor_xy,
                mm(arm["root_width_mm"]), mm(arm["tip_width_mm"]),
                mm(arm["thickness_mm"]), mm(arm["center_z_mm"]),
                visual, dark, root,
            )

        motor_obj = create_cylinder(
            f"motor_{rotor_id}",
            mm(motor["housing_diameter_mm"]) / 2.0,
            mm(motor["housing_height_mm"]),
            (motor_xy.x, motor_xy.y, mm(motor["center_z_mm"])),
            visual,
            dark,
            root,
            vertices=32,
        )
        motor_obj["part_type"] = "motor_housing"

        create_cylinder(
            f"motor_{rotor_id}_shaft",
            mm(motor["shaft_diameter_mm"]) / 2.0,
            mm(motor["shaft_height_mm"]),
            (motor_xy.x, motor_xy.y, mm(propeller["center_z_mm"] - motor["shaft_height_mm"] / 2.0)),
            visual,
            black,
            root,
            vertices=16,
        )

        axis = create_empty(
            f"motor_{rotor_id}_axis",
            (motor_xy.x, motor_xy.y, mm(propeller["center_z_mm"])),
            anchors,
            root,
            size=0.009,
        )
        axis["anchor_type"] = "rotor_axis"
        axis["thrust_axis_local"] = "+Z"
        axis["rotation_direction"] = str(directions[rotor_id])
        axis["direction_source"] = str(propeller["direction_source"])

        rotor_root = create_empty(
            f"rotor_{rotor_id}",
            (motor_xy.x, motor_xy.y, mm(propeller["center_z_mm"])),
            visual,
            root,
            size=0.006,
        )
        rotor_root["part_type"] = "rotor"
        rotor_root["rotation_direction"] = str(directions[rotor_id])
        create_rotor_mesh(
            f"rotor_{rotor_id}_blades",
            propeller,
            str(directions[rotor_id]),
            visual,
            rotor_material,
            rotor_root,
        )
        create_cylinder(
            f"rotor_{rotor_id}_hub",
            mm(propeller["hub_diameter_mm"]) / 2.0,
            mm(propeller["hub_height_mm"]),
            (motor_xy.x, motor_xy.y, mm(propeller["center_z_mm"])),
            visual,
            black,
            root,
            vertices=24,
        )

        if guard_enabled:
            guard_obj, toward_body, major_radius = create_guard_arc(
                f"guard_{rotor_id}", motor_xy, guard_outer,
                mm(guard["tube_diameter_mm"]), mm(guard["center_z_mm"]),
                float(guard["inner_gap_deg"]), int(guard["major_segments"]),
                int(guard["minor_segments"]), visual, black, root,
            )
            guard_obj["part_type"] = "propeller_guard"
            strut_z = mm(guard["center_z_mm"] - 2.2)
            strut_count = int(guard.get("strut_count", 3))
            offsets = [0.0] if strut_count == 1 else [(-62.0 + 124.0 * i / (strut_count - 1)) for i in range(strut_count)]
            for index, offset_deg in enumerate(offsets, start=1):
                angle = toward_body + math.pi + math.radians(offset_deg)
                start = Vector((motor_xy.x, motor_xy.y, strut_z))
                end = Vector((motor_xy.x + major_radius * math.cos(angle), motor_xy.y + major_radius * math.sin(angle), strut_z))
                create_cylinder_between(
                    f"guard_{rotor_id}_strut_{index:02d}", start, end,
                    mm(guard.get("strut_radius_mm", 0.72)), visual, black, root, vertices=10,
                )

        if landing_enabled:
            create_cylinder(
                f"landing_leg_{rotor_id}", mm(landing["leg_diameter_mm"]) / 2.0,
                mm(landing["leg_height_mm"]), (motor_xy.x, motor_xy.y, mm(landing["leg_center_z_mm"])),
                visual, black, root, vertices=16,
            )
            create_cylinder(
                f"foot_{rotor_id}", mm(landing["foot_diameter_mm"]) / 2.0,
                mm(landing["foot_height_mm"]), (motor_xy.x, motor_xy.y, mm(landing["foot_center_z_mm"])),
                visual, red, root, vertices=20,
            )

    # 初期衝突形状は視覚モデルとは独立した単純形状にする。
    create_collision_box(
        "collision_body",
        (mm(body["width_mm"]), mm(body["length_mm"]), mm(body["height_mm"])),
        (0.0, 0.0, mm(body["center_z_mm"])),
        collision,
        root,
    )
    if arm_enabled:
        for rotor_id in rotor_ids:
            position_mm = positions[rotor_id]
            end = Vector((mm(position_mm[0]), mm(position_mm[1]), mm(arm["center_z_mm"])))
            start = end * float(arm["root_fraction"])
            midpoint = (start + end) / 2.0
            length = (end - start).length
            collision_arm = create_collision_box(
                f"collision_arm_{rotor_id}",
                (length, mm(arm["root_width_mm"]), mm(arm["thickness_mm"])),
                tuple(midpoint), collision, root,
            )
            collision_arm.rotation_euler[2] = math.atan2(end.y - start.y, end.x - start.x)

    visual_meshes = mesh_objects(visual)
    minimum, maximum = world_bounds(visual_meshes)
    dimensions = maximum - minimum
    body_minimum, body_maximum = world_bounds([body_obj])
    body_dimensions = body_maximum - body_minimum
    triangles = sum(len(poly.vertices) - 2 for obj in visual_meshes for poly in obj.data.polygons)
    all_names = {obj.name for obj in bpy.data.objects}
    missing_names = sorted(required_object_names(config) - all_names)
    duplicate_suffix_names = sorted(name for name in all_names if name.rsplit(".", 1)[-1].isdigit())
    motor_axes = {
        rotor_id: {
            "location_mm": [round(value * 1000.0, 6) for value in bpy.data.objects[f"motor_{rotor_id}_axis"].location],
            "local_thrust_axis": "+Z",
            "rotation_direction": directions[rotor_id],
        }
        for rotor_id in rotor_ids
    }

    report = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "blender_version": bpy.app.version_string,
        "subject_id": config["subject_id"],
        "template_id": config.get("template_metadata", {}).get("template_id", "legacy"),
        "layout_mode": config["derived"]["layout_mode"],
        "rotor_count": len(rotor_ids),
        "dimensions_provisional": config["dimensions_provisional"],
        "coordinate_system": {"right": "+X", "front": "-Y", "up": "+Z", "origin": "estimated_center_of_mass"},
        "bbox_min_mm": [round(value * 1000.0, 6) for value in minimum],
        "bbox_max_mm": [round(value * 1000.0, 6) for value in maximum],
        "dimensions_mm": {
            "x": round(dimensions.x * 1000.0, 6),
            "y": round(dimensions.y * 1000.0, 6),
            "z": round(dimensions.z * 1000.0, 6),
        },
        "part_dimensions_mm": {
            "body_core": {
                "x": round(body_dimensions.x * 1000.0, 6),
                "y": round(body_dimensions.y * 1000.0, 6),
                "z": round(body_dimensions.z * 1000.0, 6),
            }
        },
        "visual_mesh_count": len(visual_meshes),
        "triangles": triangles,
        "motor_axes": motor_axes,
        "missing_required_names": missing_names,
        "duplicate_suffix_names": duplicate_suffix_names,
        "collections": {collection.name: len(collection.all_objects) for collection in (visual, anchors, collision, cameras, references)},
    }

    output_cfg = config["output"]
    output_dir.mkdir(parents=True, exist_ok=True)
    render_views(visual, cameras, output_dir, int(output_cfg["render_resolution"]))
    export_glb(output_dir / output_cfg["glb"], (visual, anchors, collision))
    report_path = output_dir / output_cfg["build_report"]
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(output_dir / output_cfg["blend"]))
    return report


def main() -> int:
    args = parse_args()
    config_path = Path(args.config_json).resolve()
    config = load_config(config_path)
    output_dir = Path(config["output"]["directory"])
    if not output_dir.is_absolute():
        output_dir = config_path.parents[2] / output_dir
    report = build(config, output_dir.resolve())
    print(f"生成完了: {output_dir}")
    print(f"表示用Mesh: {report['visual_mesh_count']}")
    print(f"寸法mm: {report['dimensions_mm']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
