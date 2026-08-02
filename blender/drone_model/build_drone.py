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
    parser = argparse.ArgumentParser(description="パラメトリックドローンモデルを生成します。")
    parser.add_argument("--config-json", required=True)
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def mm(value: float) -> float:
    return float(value) / 1000.0


def per_rotor_mm(section: dict[str, Any], key: str, rotor_id: str) -> float:
    override_key = f"{key[:-3]}_by_rotor_mm" if key.endswith("_mm") else f"{key}_by_rotor_mm"
    overrides = section.get(override_key, {})
    return mm(overrides.get(rotor_id, section[key]))


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
            if float(config.get("guard", {}).get("mount_tube_diameter_mm", 0.0)) > 0.0:
                names.add(f"guard_mount_{rotor_id}")
        if landing_enabled:
            names.add(f"landing_leg_{rotor_id}")
    structure = config.get("structure", {})
    if structure.get("enabled"):
        names.update(f"frame_{member['id']}" for member in structure.get("members", []))
    if config.get("wing", {}).get("enabled"):
        names.add("main_wing")
    for item in config.get("equipment", {}).get("cameras", []):
        names.add(f"camera_{item['id']}_gimbal")
    for item in config.get("equipment", {}).get("round_sensors", []):
        names.add(f"sensor_{item['id']}_barrel")
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
        bsdf.inputs["Alpha"].default_value = color[3]
    if color[3] < 1.0:
        if hasattr(material, "surface_render_method"):
            material.surface_render_method = "DITHERED"
        elif hasattr(material, "blend_method"):
            material.blend_method = "BLEND"
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


def create_bulged_body(
    name: str,
    config: dict[str, Any],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """端部を残しつつ中央側面が緩く外へ膨らむ、丸み付き密閉ボディ。"""
    width = mm(config["width_mm"])
    length = mm(config["length_mm"])
    height = mm(config["height_mm"])
    center_z = mm(config["center_z_mm"])
    longitudinal_segments = max(6, int(config.get("longitudinal_segments", 24)))
    radial_segments = max(12, int(config.get("radial_segments", 32)))
    end_width_ratio = float(config.get("end_width_ratio", 0.82))
    end_height_ratio = float(config.get("end_height_ratio", 0.82))
    bulge_power = float(config.get("bulge_power", 0.72))
    cross_power = float(config.get("cross_section_power", 0.72))
    half_width = width / 2.0
    half_height = height / 2.0
    half_length = length / 2.0
    verts: list[tuple[float, float, float]] = []

    for i in range(longitudinal_segments + 1):
        fraction = i / longitudinal_segments
        y = -half_length + length * fraction
        profile = math.sin(math.pi * fraction) ** bulge_power
        radius_x = half_width * (end_width_ratio + (1.0 - end_width_ratio) * profile)
        radius_z = half_height * (end_height_ratio + (1.0 - end_height_ratio) * profile)
        for j in range(radial_segments):
            angle = 2.0 * math.pi * j / radial_segments
            x = radius_x * signed_power(math.cos(angle), cross_power)
            z = center_z + radius_z * signed_power(math.sin(angle), cross_power)
            verts.append((x, y, z))

    faces: list[tuple[int, ...]] = []
    for i in range(longitudinal_segments):
        current = i * radial_segments
        following = (i + 1) * radial_segments
        for j in range(radial_segments):
            next_j = (j + 1) % radial_segments
            faces.append((current + j, following + j, following + next_j, current + next_j))
    faces.append(tuple(reversed(range(radial_segments))))
    last_ring = longitudinal_segments * radial_segments
    faces.append(tuple(last_ring + j for j in range(radial_segments)))

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
    obj["part_type"] = "bulged_body_shell"
    obj["measured_width_mm"] = float(config["width_mm"])
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


def create_box_between(
    name: str,
    start: Vector,
    end: Vector,
    width: float,
    thickness: float,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """XY平面上の2点を結ぶ角形ビームを作る。"""
    direction = end - start
    length = math.hypot(direction.x, direction.y)
    midpoint = (start + end) / 2.0
    obj = create_rounded_box(
        name,
        (length, width, thickness),
        tuple(midpoint),
        min(width, thickness) * 0.22,
        collection,
        material,
        parent,
    )
    obj.rotation_euler[2] = math.atan2(direction.y, direction.x)
    return obj


def create_beam_between(
    name: str,
    start: Vector,
    end: Vector,
    width: float,
    depth: float,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """任意の3次元2点を結ぶ角形ビーム。"""
    direction = end - start
    length = direction.length
    obj = create_rounded_box(
        name,
        (width, depth, length),
        tuple((start + end) / 2.0),
        min(width, depth) * 0.18,
        collection,
        material,
        parent,
    )
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.rotation_mode = "XYZ"
    return obj


def create_truss_arm(
    name: str,
    start: Vector,
    end: Vector,
    config: dict[str, Any],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """上下左右4本の縦通材と側面ウェブを持つ、中空射出成形風アーム。"""
    direction = Vector((end.x - start.x, end.y - start.y, 0.0)).normalized()
    side = Vector((-direction.y, direction.x, 0.0))
    center_z = mm(config["center_z_mm"])
    root_spacing = mm(config.get("rail_spacing_root_mm", config["root_width_mm"]))
    tip_spacing = mm(config.get("rail_spacing_tip_mm", config["tip_width_mm"]))
    rail_width = mm(config.get("rail_width_mm", 2.6))
    truss_height = mm(config.get("truss_height_mm", config["thickness_mm"]))
    rail_thickness = mm(config.get("rail_thickness_mm", 2.2))
    z_offset = max(0.0, (truss_height - rail_thickness) / 2.0)
    primary: bpy.types.Object | None = None
    rail_index = 0
    for vertical_sign in (-1.0, 1.0):
        for lateral_sign in (-1.0, 1.0):
            rail_index += 1
            rail_start = Vector((start.x, start.y, center_z + vertical_sign * z_offset)) + side * root_spacing * lateral_sign / 2.0
            rail_end = Vector((end.x, end.y, center_z + vertical_sign * z_offset)) + side * tip_spacing * lateral_sign / 2.0
            rail = create_box_between(
                name if rail_index == 1 else f"{name}_rail_{rail_index}",
                rail_start,
                rail_end,
                rail_width,
                rail_thickness,
                collection,
                material,
                parent,
            )
            rail["part_type"] = "truss_arm_longitudinal"
            primary = primary or rail

    web_count = max(1, int(config.get("side_web_count", 2)))
    for lateral_index, lateral_sign in enumerate((-1.0, 1.0), start=1):
        for web_index in range(web_count):
            fraction = (web_index + 1) / (web_count + 1)
            center = Vector((start.x, start.y, center_z)).lerp(Vector((end.x, end.y, center_z)), fraction)
            spacing = root_spacing + (tip_spacing - root_spacing) * fraction
            lateral = side * spacing * lateral_sign / 2.0
            low = center + lateral + Vector((0.0, 0.0, -z_offset))
            high = center + lateral + Vector((0.0, 0.0, z_offset))
            web = create_beam_between(
                f"{name}_side_{lateral_index}_web_{web_index + 1:02d}",
                low,
                high,
                rail_width,
                rail_thickness,
                collection,
                material,
                parent,
            )
            web["part_type"] = "truss_arm_side_web"

    cross_fraction = float(config.get("cross_brace_fraction", 0.58))
    cross_center = Vector((start.x, start.y, center_z + z_offset)).lerp(Vector((end.x, end.y, center_z + z_offset)), cross_fraction)
    cross_spacing = root_spacing + (tip_spacing - root_spacing) * cross_fraction
    cross = create_box_between(
        f"{name}_top_cross_brace",
        cross_center - side * cross_spacing / 2.0,
        cross_center + side * cross_spacing / 2.0,
        rail_width,
        rail_thickness,
        collection,
        material,
        parent,
    )
    cross["part_type"] = "truss_arm_top_web"
    if primary is None:
        raise ValueError("トラスアームを生成できませんでした。")
    return primary


def create_measured_triangle_arm(
    name: str,
    motor_center: Vector,
    config: dict[str, Any],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """前後2系統の各上・下材がポッドへ収束する立体三角アーム。"""
    region = "front" if motor_center.y < 0.0 else "rear"
    lengths = config[f"{region}_member_lengths_mm"]
    center_z = mm(config["center_z_mm"])
    root_spacing_z = mm(config.get("vertical_root_spacing_mm", 0.0))
    rail_width = mm(config.get("rail_width_mm", 2.0))
    rail_thickness = mm(config.get("rail_thickness_mm", 2.0))
    body_half_width = mm(config["body_root_half_width_mm"])
    motor_radius = mm(config["motor_pod_radius_mm"])
    side_sign = -1.0 if motor_center.x < 0.0 else 1.0
    longitudinal_sign = -1.0 if motor_center.y < 0.0 else 1.0
    root_x = side_sign * body_half_width
    tip = Vector((motor_center.x - side_sign * motor_radius, motor_center.y, center_z))
    lateral_span = abs(tip.x - root_x)
    primary: bpy.types.Object | None = None

    for role in ("outer", "inner"):
        measured_length = mm(float(lengths[role]))
        if measured_length <= lateral_span:
            raise ValueError(
                f"{name}.{role}の実測長がボディ側面からモーターポッドまでの横距離以下です。"
            )
        longitudinal_span = math.sqrt(measured_length * measured_length - lateral_span * lateral_span)
        root_y = tip.y - longitudinal_sign * longitudinal_span
        for vertical_role, vertical_sign in (("upper", 1.0), ("lower", -1.0)):
            start = Vector((
                root_x,
                root_y,
                center_z + vertical_sign * root_spacing_z / 2.0,
            ))
            if role == "outer" and vertical_role == "upper":
                object_name = name
            elif role == "inner" and vertical_role == "upper":
                object_name = f"{name}_{role}"
            else:
                object_name = f"{name}_{role}_{vertical_role}"
            member = create_beam_between(
                object_name,
                start,
                tip,
                rail_width,
                rail_thickness,
                collection,
                material,
                parent,
            )
            member["part_type"] = "measured_triangle_arm_member"
            member["member_role"] = role
            member["vertical_role"] = vertical_role
            member["body_region"] = region
            member["measured_length_mm"] = float(lengths[role])
            member["projected_length_mm"] = float(lengths[role])
            primary = primary or member

    if primary is None:
        raise ValueError("三角アームを生成できませんでした。")
    return primary


def create_aluminum_extrusion(
    name: str,
    dimensions: tuple[float, float, float],
    location: tuple[float, float, float],
    collection: bpy.types.Collection,
    aluminum: bpy.types.Material,
    groove_material: bpy.types.Material,
    parent: bpy.types.Object,
    add_grooves: bool = True,
) -> bpy.types.Object:
    """寸法を保持した角形アルミ押出材。溝は軽量な表面ストリップで表現する。"""
    obj = create_rounded_box(
        name,
        dimensions,
        location,
        min(mm(1.2), min(dimensions) * 0.08),
        collection,
        aluminum,
        parent,
    )
    obj["part_type"] = "aluminum_extrusion"
    obj["profile_dimensions_mm"] = [round(value * 1000.0, 3) for value in dimensions]
    if not add_grooves:
        return obj

    long_axis = max(range(3), key=lambda index: dimensions[index])
    cross_axes = [index for index in range(3) if index != long_axis]
    groove_width = mm(3.2)
    groove_depth = mm(0.7)
    for face_axis in cross_axes:
        offset_axis = next(index for index in cross_axes if index != face_axis)
        slots = (-mm(15.0), mm(15.0)) if dimensions[offset_axis] >= mm(50.0) else (0.0,)
        for side_index, side in enumerate((-1.0, 1.0), start=1):
            for slot_index, slot in enumerate(slots, start=1):
                strip_dimensions = [groove_width, groove_width, groove_width]
                strip_dimensions[long_axis] = max(dimensions[long_axis] - mm(4.0), groove_width)
                strip_dimensions[offset_axis] = groove_width
                strip_dimensions[face_axis] = groove_depth
                strip_location = list(location)
                strip_location[face_axis] += side * (dimensions[face_axis] / 2.0 + groove_depth * 0.35)
                strip_location[offset_axis] += slot
                groove = create_rounded_box(
                    f"{name}__groove_{face_axis}_{side_index}_{slot_index}",
                    tuple(strip_dimensions),
                    tuple(strip_location),
                    0.0,
                    collection,
                    groove_material,
                    parent,
                )
                groove["part_type"] = "extrusion_groove"
    return obj


def create_airfoil_wing(
    name: str,
    config: dict[str, Any],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """中央厚・前縁丸みを持つ対称翼。翼幅、翼弦、厚み、テーパを設定可能。"""
    span = mm(config["span_mm"])
    root_chord = mm(config["root_chord_mm"])
    tip_chord = mm(config.get("tip_chord_mm", config["root_chord_mm"]))
    thickness = mm(config["thickness_mm"])
    center_y = mm(config.get("center_y_mm", 0.0))
    center_z = mm(config.get("center_z_mm", 0.0))
    chord_segments = max(8, int(config.get("chord_segments", 18)))
    span_stations = (-span / 2.0, 0.0, span / 2.0)
    verts: list[tuple[float, float, float]] = []

    for x in span_stations:
        taper = abs(x) / (span / 2.0) if span else 0.0
        chord = root_chord + (tip_chord - root_chord) * taper
        for surface in (1.0, -1.0):
            for index in range(chord_segments + 1):
                fraction = index / chord_segments
                y = center_y - chord / 2.0 + chord * fraction
                profile = math.sin(math.pi * fraction) ** 0.72
                z = center_z + surface * thickness * profile / 2.0
                verts.append((x, y, z))

    ring = 2 * (chord_segments + 1)
    faces: list[tuple[int, ...]] = []
    for station in range(len(span_stations) - 1):
        current = station * ring
        following = (station + 1) * ring
        for surface in range(2):
            start = surface * (chord_segments + 1)
            for index in range(chord_segments):
                a = current + start + index
                b = current + start + index + 1
                c = following + start + index + 1
                d = following + start + index
                faces.append((a, b, c, d) if surface == 0 else (d, c, b, a))
        for edge in (0, chord_segments):
            top_a = current + edge
            top_b = following + edge
            bottom_a = current + chord_segments + 1 + edge
            bottom_b = following + chord_segments + 1 + edge
            faces.append((top_a, bottom_a, bottom_b, top_b))
    for station, reverse in ((0, True), (len(span_stations) - 1, False)):
        base = station * ring
        loop = list(range(base, base + chord_segments + 1))
        loop += list(range(base + 2 * (chord_segments + 1) - 1, base + chord_segments, -1))
        faces.append(tuple(reversed(loop)) if reverse else tuple(loop))

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
    obj["part_type"] = "main_wing"
    obj["span_mm"] = float(config["span_mm"])
    obj["root_chord_mm"] = float(config["root_chord_mm"])
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
    outer_width: float,
    outer_length: float,
    tube_diameter: float,
    center_z: float,
    gap_deg: float,
    major_segments: int,
    minor_segments: int,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
    sweep_deg: float | None = None,
) -> tuple[bpy.types.Object, float, tuple[float, float]]:
    tube_radius = tube_diameter / 2.0
    radius_x = outer_width / 2.0 - tube_radius
    radius_y = outer_length / 2.0 - tube_radius
    toward_body = math.atan2(-center.y, -center.x)
    if sweep_deg is None:
        gap = math.radians(gap_deg)
        start = toward_body + gap / 2.0
        sweep = 2.0 * math.pi - gap
    else:
        sweep = math.radians(sweep_deg)
        outward = toward_body + math.pi
        start = outward - sweep / 2.0
    verts: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []

    for i in range(major_segments + 1):
        angle = start + sweep * i / major_segments
        centerline = Vector((radius_x * math.cos(angle), radius_y * math.sin(angle), center_z))
        normal = Vector((math.cos(angle) / radius_x, math.sin(angle) / radius_y, 0.0)).normalized()
        for j in range(minor_segments):
            minor = 2.0 * math.pi * j / minor_segments
            point = centerline + normal * (tube_radius * math.cos(minor))
            point.z += tube_radius * math.sin(minor)
            verts.append(tuple(point))
    for i in range(major_segments):
        for j in range(minor_segments):
            next_j = (j + 1) % minor_segments
            a = i * minor_segments + j
            b = i * minor_segments + next_j
            c = (i + 1) * minor_segments + next_j
            d = (i + 1) * minor_segments + j
            faces.append((a, b, c, d))

    start_cap = len(verts)
    verts.append((radius_x * math.cos(start), radius_y * math.sin(start), center_z))
    end_angle = start + sweep
    end_cap = len(verts)
    verts.append((radius_x * math.cos(end_angle), radius_y * math.sin(end_angle), center_z))
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
    obj["outer_width_mm"] = round(outer_width * 1000.0, 3)
    obj["outer_length_mm"] = round(outer_length * 1000.0, 3)
    obj["tube_diameter_mm"] = round(tube_diameter * 1000.0, 3)
    obj["sweep_deg"] = round(math.degrees(sweep), 3)
    return obj, toward_body, (radius_x, radius_y)


def create_hemisphere_housing(
    name: str,
    diameter: float,
    depth: float,
    aim: Vector,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    parent: bpy.types.Object,
    radial_segments: int = 32,
    arc_segments: int = 10,
) -> bpy.types.Object:
    """直径と前方深さで定義する、背面開口付き半球カメラハウジング。"""
    radius = diameter / 2.0
    verts: list[tuple[float, float, float]] = [(0.0, -depth, 0.0)]
    for ring in range(1, arc_segments + 1):
        theta = math.pi * ring / (2.0 * arc_segments)
        radial = radius * math.sin(theta)
        y = -depth * math.cos(theta)
        for segment in range(radial_segments):
            angle = 2.0 * math.pi * segment / radial_segments
            verts.append((radial * math.cos(angle), y, radial * math.sin(angle)))

    faces: list[tuple[int, ...]] = []
    first_ring = 1
    for segment in range(radial_segments):
        next_segment = (segment + 1) % radial_segments
        faces.append((0, first_ring + segment, first_ring + next_segment))
    for ring in range(arc_segments - 1):
        current = 1 + ring * radial_segments
        following = current + radial_segments
        for segment in range(radial_segments):
            next_segment = (segment + 1) % radial_segments
            faces.append((current + segment, following + segment, following + next_segment, current + next_segment))
    last_ring = 1 + (arc_segments - 1) * radial_segments
    faces.append(tuple(reversed([last_ring + segment for segment in range(radial_segments)])))

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
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = Vector((0.0, -1.0, 0.0)).rotation_difference(aim)
    obj.rotation_mode = "XYZ"
    obj["part_type"] = "hemisphere_camera_housing"
    obj["diameter_mm"] = round(diameter * 1000.0, 3)
    return obj


def create_camera_module(
    item: dict[str, Any],
    collection: bpy.types.Collection,
    housing_material: bpy.types.Material,
    lens_material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    """向きと可動範囲を持つカメラ外形・レンズ・光学軸アンカー。"""
    camera_id = str(item["id"])
    location = Vector(tuple(mm(value) for value in item["location_mm"]))
    aim = Vector(tuple(float(value) for value in item.get("aim_vector", [0.0, -1.0, 0.0]))).normalized()
    pivot = create_empty(f"camera_{camera_id}_gimbal", tuple(location), collection, parent, size=mm(4.0))
    pivot["part_type"] = "camera_gimbal" if item.get("movable") else "camera_mount"
    pivot["aim_vector"] = list(aim)
    pivot["field_of_view_deg"] = float(item.get("field_of_view_deg", 0.0))
    pivot["tilt_range_deg"] = float(item.get("tilt_range_deg", 0.0))
    pivot["rotation_axis"] = str(item.get("rotation_axis", "+X"))
    shape = str(item.get("shape", "rounded_box"))
    if shape == "hemisphere":
        housing_diameter = mm(item["diameter_mm"])
        housing_depth = mm(item.get("hemisphere_depth_mm", float(item["diameter_mm"]) / 2.0))
        housing = create_hemisphere_housing(
            f"camera_{camera_id}_housing",
            housing_diameter,
            housing_depth,
            aim,
            collection,
            housing_material,
            pivot,
        )
        pin_diameter = mm(item.get("pivot_pin_diameter_mm", 0.0))
        pin_length = mm(item.get("pivot_pin_length_mm", 0.0))
        if pin_diameter > 0.0 and pin_length > 0.0:
            radius = housing_diameter / 2.0
            for side_name, sign in (("left", -1.0), ("right", 1.0)):
                inner = Vector((sign * (radius - mm(0.8)), 0.0, 0.0))
                outer = Vector((sign * (radius + pin_length), 0.0, 0.0))
                pin = create_cylinder_between(
                    f"camera_{camera_id}_pivot_{side_name}",
                    inner,
                    outer,
                    pin_diameter / 2.0,
                    collection,
                    housing_material,
                    pivot,
                    vertices=20,
                )
                pin["part_type"] = "camera_gimbal_pivot"
    else:
        housing = create_rounded_box(
            f"camera_{camera_id}_housing",
            tuple(mm(value) for value in item["housing_dimensions_mm"]),
            (0.0, 0.0, 0.0),
            mm(item.get("bevel_mm", 2.0)),
            collection,
            housing_material,
            pivot,
        )
    housing["part_type"] = "camera_housing"
    lens_depth = mm(item.get("lens_depth_mm", 3.0))
    default_lens_offset = float(item.get("hemisphere_depth_mm", 6.0)) + float(item.get("lens_depth_mm", 3.0)) / 2.0
    lens_offset = mm(item.get("lens_center_offset_mm", default_lens_offset))
    lens_start = aim * (lens_offset - lens_depth / 2.0)
    lens_end = aim * (lens_offset + lens_depth / 2.0)
    barrel = create_cylinder_between(
        f"camera_{camera_id}_lens_barrel",
        lens_start,
        lens_end,
        mm(item.get("lens_diameter_mm", 8.0)) / 2.0,
        collection,
        housing_material,
        pivot,
        vertices=32,
    )
    barrel["part_type"] = "camera_lens_barrel"
    glass_end = lens_end + aim * mm(0.7)
    glass = create_cylinder_between(
        f"camera_{camera_id}_lens",
        lens_end,
        glass_end,
        mm(item.get("glass_diameter_mm", item.get("lens_diameter_mm", 8.0) * 0.72)) / 2.0,
        collection,
        lens_material,
        pivot,
        vertices=32,
    )
    glass["part_type"] = "camera_lens"
    return pivot


def create_round_sensor(
    item: dict[str, Any],
    collection: bpy.types.Collection,
    housing_material: bpy.types.Material,
    lens_material: bpy.types.Material,
    parent: bpy.types.Object,
) -> bpy.types.Object:
    sensor_id = str(item["id"])
    location = Vector(tuple(mm(value) for value in item["location_mm"]))
    aim = Vector(tuple(float(value) for value in item.get("aim_vector", [0.0, -1.0, 0.0]))).normalized()
    depth = mm(item.get("depth_mm", 3.0))
    start = location - aim * depth / 2.0
    end = location + aim * depth / 2.0
    barrel = create_cylinder_between(
        f"sensor_{sensor_id}_barrel",
        start,
        end,
        mm(item.get("diameter_mm", 6.0)) / 2.0,
        collection,
        housing_material,
        parent,
        vertices=24,
    )
    barrel["part_type"] = str(item.get("part_type", "sensor"))
    face = create_cylinder_between(
        f"sensor_{sensor_id}_face",
        end,
        end + aim * mm(0.6),
        mm(item.get("face_diameter_mm", item.get("diameter_mm", 6.0) * 0.7)) / 2.0,
        collection,
        lens_material,
        parent,
        vertices=24,
    )
    face["part_type"] = str(item.get("part_type", "sensor"))
    return barrel


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
    if config.get("specifications"):
        root["product_specifications_json"] = json.dumps(config["specifications"], ensure_ascii=False)


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
    propeller_opacity = float(config.get("propeller", {}).get("opacity", 1.0))
    rotor_color = (
        (0.58, 0.62, 0.68, propeller_opacity)
        if propeller_opacity < 1.0
        else (0.025, 0.028, 0.032, 1.0)
    )
    rotor_material = make_material("透明プロペラ" if propeller_opacity < 1.0 else "プロペラ", rotor_color, metallic=0.02, roughness=0.22)
    red = make_material("脚部レッド", (0.35, 0.012, 0.015, 1.0), metallic=0.05, roughness=0.42)
    aluminum = make_material("アルミ押出材", (0.52, 0.56, 0.60, 1.0), metallic=0.82, roughness=0.24)
    wing_material = make_material("主翼ホワイト", (0.76, 0.79, 0.82, 1.0), metallic=0.05, roughness=0.38)
    electronics_material = make_material("電装ケース", (0.10, 0.12, 0.14, 1.0), metallic=0.18, roughness=0.38)
    battery_material = make_material("バッテリー", (0.12, 0.18, 0.24, 1.0), metallic=0.05, roughness=0.48)
    yellow = make_material("識別イエロー", (0.92, 0.50, 0.035, 1.0), metallic=0.05, roughness=0.35)
    shell_white = make_material("機体シェルホワイト", (0.80, 0.84, 0.87, 1.0), metallic=0.04, roughness=0.32)
    lens_glass = make_material("レンズガラス", (0.008, 0.018, 0.030, 1.0), metallic=0.12, roughness=0.08)
    material_lookup = {
        "dark": dark, "black": black, "aluminum": aluminum, "wing": wing_material,
        "electronics": electronics_material, "battery": battery_material, "red": red, "yellow": yellow,
        "white": shell_white, "lens": lens_glass,
    }

    root = create_empty("drone_root", (0.0, 0.0, 0.0), visual, None, size=0.01)
    add_scene_metadata(root, config)
    physics = config.get("physics", {})
    com = create_empty("center_of_mass", tuple(mm(v) for v in physics.get("center_of_mass_mm", [0.0, 0.0, 0.0])), anchors, root, size=0.008)
    com["anchor_type"] = "center_of_mass"
    com["source"] = str(physics.get("center_of_mass_source", "placeholder"))

    body = config["body"]
    body_shape = str(body.get("shape", "lofted"))
    body_material = material_lookup.get(str(body.get("material", "dark")), dark)
    if body_shape == "lofted":
        body_obj = create_lofted_body("body_core", body, visual, body_material, root)
    elif body_shape == "bulged_box":
        body_obj = create_bulged_body("body_core", body, visual, body_material, root)
    elif body_shape == "rounded_box":
        body_obj = create_rounded_box(
            "body_core",
            (mm(body["width_mm"]), mm(body["length_mm"]), mm(body["height_mm"])),
            (0.0, 0.0, mm(body.get("center_z_mm", 0.0))),
            mm(body.get("bevel_mm", 2.0)),
            visual,
            body_material,
            root,
        )
    else:
        raise ValueError(f"未対応のbody.shapeです: {body_shape}")
    body_obj["part_type"] = "body"

    frame_objects: list[bpy.types.Object] = []
    structure = config.get("structure", {})
    if structure.get("enabled"):
        for member in structure.get("members", []):
            frame_obj = create_aluminum_extrusion(
                f"frame_{member['id']}",
                tuple(mm(value) for value in member["dimensions_mm"]),
                tuple(mm(value) for value in member["location_mm"]),
                visual,
                aluminum,
                dark,
                root,
                bool(structure.get("show_grooves", True)),
            )
            frame_obj["profile"] = str(member.get("profile", "custom"))
            frame_obj["source"] = str(member.get("source", "configured"))
            frame_objects.append(frame_obj)

    wing = config.get("wing", {})
    if wing.get("enabled"):
        create_airfoil_wing("main_wing", wing, visual, wing_material, root)
        for bracket in wing.get("brackets", []):
            bracket_obj = create_rounded_box(
                f"wing_bracket_{bracket['id']}",
                tuple(mm(value) for value in bracket["dimensions_mm"]),
                tuple(mm(value) for value in bracket["location_mm"]),
                mm(bracket.get("bevel_mm", 2.0)),
                visual,
                aluminum,
                root,
            )
            bracket_obj["part_type"] = "wing_bracket"

    for item in config.get("equipment", {}).get("boxes", []):
        equipment_obj = create_rounded_box(
            f"equipment_{item['id']}",
            tuple(mm(value) for value in item["dimensions_mm"]),
            tuple(mm(value) for value in item["location_mm"]),
            mm(item.get("bevel_mm", 3.0)),
            visual,
            material_lookup.get(str(item.get("material", "electronics")), electronics_material),
            root,
        )
        equipment_obj["part_type"] = str(item.get("part_type", "equipment"))
        if item.get("model"):
            equipment_obj["model"] = str(item["model"])

    for item in config.get("equipment", {}).get("masts", []):
        mast_x, mast_y, mast_base_z = (mm(value) for value in item["base_mm"])
        mast_height = mm(item["height_mm"])
        mast = create_cylinder(
            f"equipment_{item['id']}_mast", mm(item.get("diameter_mm", 12.0)) / 2.0,
            mast_height, (mast_x, mast_y, mast_base_z + mast_height / 2.0),
            visual, black, root, vertices=16,
        )
        mast["part_type"] = "sensor_mast"
        head_height = mm(item.get("head_height_mm", 18.0))
        head = create_cylinder(
            f"equipment_{item['id']}_head", mm(item.get("head_diameter_mm", 70.0)) / 2.0,
            head_height, (mast_x, mast_y, mast_base_z + mast_height + head_height / 2.0),
            visual, electronics_material, root, vertices=24,
        )
        head["part_type"] = str(item.get("part_type", "sensor"))

    for item in config.get("equipment", {}).get("cameras", []):
        create_camera_module(item, visual, electronics_material, lens_glass, root)

    for item in config.get("equipment", {}).get("round_sensors", []):
        create_round_sensor(item, visual, electronics_material, lens_glass, root)

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
    guard_outer_width = mm(config["derived"]["guard_outer_width_mm"]) if guard_enabled else None
    guard_outer_length = mm(config["derived"]["guard_outer_length_mm"]) if guard_enabled else None
    motor_mount = config.get("motor_mount", {})
    esc = config.get("esc", {})

    for rotor_id in rotor_ids:
        position_mm = positions[rotor_id]
        motor_xy = Vector((mm(position_mm[0]), mm(position_mm[1]), 0.0))
        support_axis = "x" if abs(motor_xy.x) >= abs(motor_xy.y) else "y"
        motor_center_z = per_rotor_mm(motor, "center_z_mm", rotor_id)
        propeller_center_z = per_rotor_mm(propeller, "center_z_mm", rotor_id)
        root_point = motor_xy * float(arm["root_fraction"])
        if arm_enabled:
            arm_style = str(arm.get("style", "solid"))
            if arm_style == "measured_triangle":
                create_measured_triangle_arm(f"arm_{rotor_id}", motor_xy, arm, visual, dark, root)
            elif arm_style == "truss":
                create_truss_arm(f"arm_{rotor_id}", root_point, motor_xy, arm, visual, dark, root)
            else:
                create_tapered_arm(
                    f"arm_{rotor_id}", root_point, motor_xy,
                    mm(arm["root_width_mm"]), mm(arm["tip_width_mm"]),
                    mm(arm["thickness_mm"]), mm(arm["center_z_mm"]),
                    visual, dark, root,
                )

        if motor_mount.get("enabled"):
            mount_dimensions = [mm(value) for value in motor_mount["dimensions_mm"]]
            if support_axis == "y":
                mount_dimensions[0], mount_dimensions[1] = mount_dimensions[1], mount_dimensions[0]
            mount_obj = create_rounded_box(
                f"motor_mount_{rotor_id}",
                tuple(mount_dimensions),
                (motor_xy.x, motor_xy.y, per_rotor_mm(motor_mount, "center_z_mm", rotor_id)),
                mm(motor_mount.get("bevel_mm", 3.0)),
                visual,
                aluminum,
                root,
            )
            mount_obj["part_type"] = "motor_bracket"

        if esc.get("enabled"):
            offset = mm(esc.get("inward_offset_mm", 180.0))
            esc_x, esc_y = motor_xy.x, motor_xy.y
            esc_dimensions = [mm(value) for value in esc["dimensions_mm"]]
            if support_axis == "x":
                esc_x -= math.copysign(offset, motor_xy.x)
            else:
                esc_y -= math.copysign(offset, motor_xy.y)
                esc_dimensions[0], esc_dimensions[1] = esc_dimensions[1], esc_dimensions[0]
            esc_obj = create_rounded_box(
                f"esc_{rotor_id}",
                tuple(esc_dimensions),
                (esc_x, esc_y, mm(esc["center_z_mm"])),
                mm(esc.get("bevel_mm", 4.0)),
                visual,
                electronics_material,
                root,
            )
            esc_obj["part_type"] = "esc"
            esc_obj["model"] = str(esc.get("model", ""))

        motor_obj = create_cylinder(
            f"motor_{rotor_id}",
            mm(motor["housing_diameter_mm"]) / 2.0,
            mm(motor["housing_height_mm"]),
            (motor_xy.x, motor_xy.y, motor_center_z),
            visual,
            dark,
            root,
            vertices=32,
        )
        motor_obj["part_type"] = "motor_housing"
        motor_obj["mount_side"] = "under_frame" if motor_center_z < 0.0 else "over_frame"

        shaft_half_height = mm(motor["shaft_height_mm"]) / 2.0
        shaft_center_z = (
            propeller_center_z - shaft_half_height
            if propeller_center_z >= motor_center_z
            else propeller_center_z + shaft_half_height
        )
        create_cylinder(
            f"motor_{rotor_id}_shaft",
            mm(motor["shaft_diameter_mm"]) / 2.0,
            mm(motor["shaft_height_mm"]),
            (motor_xy.x, motor_xy.y, shaft_center_z),
            visual,
            black,
            root,
            vertices=16,
        )

        axis = create_empty(
            f"motor_{rotor_id}_axis",
            (motor_xy.x, motor_xy.y, propeller_center_z),
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
            (motor_xy.x, motor_xy.y, propeller_center_z),
            visual,
            root,
            size=0.006,
        )
        rotor_root["part_type"] = "rotor"
        rotor_root["rotation_direction"] = str(directions[rotor_id])
        display_angles = propeller.get("display_angles_deg", {})
        rotor_root.rotation_euler[2] = math.radians(float(display_angles.get(rotor_id, 0.0)))
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
            (motor_xy.x, motor_xy.y, propeller_center_z),
            visual,
            black,
            root,
            vertices=24,
        )

        if guard_enabled:
            mount_tube_diameter = mm(guard.get("mount_tube_diameter_mm", 0.0))
            mount_tube_height = mm(guard.get("mount_tube_height_mm", 0.0))
            mount_tube_center_z = mm(guard.get("mount_tube_center_z_mm", guard["center_z_mm"]))
            if mount_tube_diameter > 0.0 and mount_tube_height > 0.0:
                mount_tube = create_cylinder(
                    f"guard_mount_{rotor_id}",
                    mount_tube_diameter / 2.0,
                    mount_tube_height,
                    (motor_xy.x, motor_xy.y, mount_tube_center_z),
                    visual,
                    electronics_material,
                    root,
                    vertices=32,
                )
                mount_tube["part_type"] = "propeller_guard_mount_tube"
            guard_obj, toward_body, guard_radii = create_guard_arc(
                f"guard_{rotor_id}", motor_xy, guard_outer_width, guard_outer_length,
                mm(guard["tube_diameter_mm"]), mm(guard["center_z_mm"]),
                float(guard["inner_gap_deg"]), int(guard["major_segments"]),
                int(guard["minor_segments"]), visual, black, root,
                float(guard["sweep_deg"]) if guard.get("sweep_deg") is not None else None,
            )
            guard_obj["part_type"] = "propeller_guard"
            guard_obj["height_above_motor_pod_mm"] = round(
                (mm(guard["center_z_mm"]) - motor_center_z) * 1000.0,
                3,
            )
            legacy_strut_z = mm(guard.get("strut_center_z_mm", guard["center_z_mm"] - 2.2))
            strut_start_z = mm(guard["strut_start_z_mm"]) if guard.get("strut_start_z_mm") is not None else legacy_strut_z
            strut_end_z = mm(guard["strut_end_z_mm"]) if guard.get("strut_end_z_mm") is not None else legacy_strut_z
            strut_start_radius = mount_tube_diameter / 2.0 if mount_tube_diameter > 0.0 else 0.0
            strut_count = int(guard.get("strut_count", 3))
            configured_offsets = guard.get("strut_angle_offsets_deg")
            if configured_offsets is not None:
                offsets = [float(value) for value in configured_offsets]
            else:
                offsets = [0.0] if strut_count == 1 else [(-62.0 + 124.0 * i / (strut_count - 1)) for i in range(strut_count)]
            for index, offset_deg in enumerate(offsets, start=1):
                angle = toward_body + math.pi + math.radians(offset_deg)
                start = Vector((
                    motor_xy.x + strut_start_radius * math.cos(angle),
                    motor_xy.y + strut_start_radius * math.sin(angle),
                    strut_start_z,
                ))
                end = Vector((
                    motor_xy.x + guard_radii[0] * math.cos(angle),
                    motor_xy.y + guard_radii[1] * math.sin(angle),
                    strut_end_z,
                ))
                strut = create_cylinder_between(
                    f"guard_{rotor_id}_strut_{index:02d}", start, end,
                    mm(guard.get("strut_radius_mm", 0.72)), visual, black, root, vertices=10,
                )
                strut["horizontal_projection_mm"] = round(
                    math.hypot(end.x - start.x, end.y - start.y) * 1000.0,
                    3,
                )
                strut["vertical_rise_mm"] = round((end.z - start.z) * 1000.0, 3)

        if landing_enabled:
            create_cylinder(
                f"landing_leg_{rotor_id}", mm(landing["leg_diameter_mm"]) / 2.0,
                mm(landing["leg_height_mm"]), (motor_xy.x, motor_xy.y, mm(landing["leg_center_z_mm"])),
                visual, black, root, vertices=16,
            )
            create_cylinder(
                f"foot_{rotor_id}", mm(landing["foot_diameter_mm"]) / 2.0,
                mm(landing["foot_height_mm"]), (motor_xy.x, motor_xy.y, mm(landing["foot_center_z_mm"])),
                visual, material_lookup.get(str(landing.get("foot_material", "red")), red), root, vertices=20,
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
    for frame_obj in frame_objects:
        create_collision_box(
            f"collision_{frame_obj.name}",
            tuple(frame_obj.dimensions),
            tuple(frame_obj.location),
            collision,
            root,
        )

    visual_meshes = mesh_objects(visual)
    minimum, maximum = world_bounds(visual_meshes)
    dimensions = maximum - minimum
    body_minimum, body_maximum = world_bounds([body_obj])
    body_dimensions = body_maximum - body_minimum
    frame_minimum, frame_maximum = world_bounds(frame_objects)
    frame_dimensions = frame_maximum - frame_minimum
    triangles = sum(len(poly.vertices) - 2 for obj in visual_meshes for poly in obj.data.polygons)
    all_names = {obj.name for obj in bpy.data.objects}
    missing_names = sorted(required_object_names(config) - all_names)
    duplicate_suffix_names = sorted(name for name in all_names if name.rsplit(".", 1)[-1].isdigit())
    motor_axes = {
        rotor_id: {
            "location_mm": [round(value * 1000.0, 6) for value in bpy.data.objects[f"motor_{rotor_id}_axis"].location],
            "motor_location_mm": [round(value * 1000.0, 6) for value in bpy.data.objects[f"motor_{rotor_id}"].location],
            "motor_dimensions_mm": [round(value * 1000.0, 6) for value in bpy.data.objects[f"motor_{rotor_id}"].dimensions],
            "mount_side": str(bpy.data.objects[f"motor_{rotor_id}"].get("mount_side", "unknown")),
            "local_thrust_axis": "+Z",
            "rotation_direction": directions[rotor_id],
        }
        for rotor_id in rotor_ids
    }
    sensor_masts = {
        str(item["id"]): {
            "height_mm": round(bpy.data.objects[f"equipment_{item['id']}_mast"].dimensions.z * 1000.0, 6),
            "base_mm": [float(value) for value in item["base_mm"]],
            "head_diameter_mm": float(item.get("head_diameter_mm", 70.0)),
        }
        for item in config.get("equipment", {}).get("masts", [])
    }
    guard_mounts = {
        rotor_id: {
            "dimensions_mm": [round(value * 1000.0, 6) for value in bpy.data.objects[f"guard_mount_{rotor_id}"].dimensions],
        }
        for rotor_id in rotor_ids
        if f"guard_mount_{rotor_id}" in bpy.data.objects
    }
    arm_members = {
        rotor_id: {
            role: {
                "measured_length_mm": float(
                    bpy.data.objects[
                        f"arm_{rotor_id}" if role == "outer" else f"arm_{rotor_id}_{role}"
                    ].get("measured_length_mm", 0.0)
                ),
                "vertical_roles": sorted(
                    str(bpy.data.objects[object_name].get("vertical_role", ""))
                    for object_name in (
                        (f"arm_{rotor_id}", f"arm_{rotor_id}_outer_lower")
                        if role == "outer"
                        else (f"arm_{rotor_id}_inner", f"arm_{rotor_id}_inner_lower")
                    )
                    if object_name in bpy.data.objects
                ),
            }
            for role in ("outer", "inner")
            if (f"arm_{rotor_id}" if role == "outer" else f"arm_{rotor_id}_{role}") in bpy.data.objects
        }
        for rotor_id in rotor_ids
    }
    guard_modules = {
        rotor_id: {
            "outer_width_mm": float(bpy.data.objects[f"guard_{rotor_id}"].get("outer_width_mm", 0.0)),
            "outer_length_mm": float(bpy.data.objects[f"guard_{rotor_id}"].get("outer_length_mm", 0.0)),
            "tube_diameter_mm": float(bpy.data.objects[f"guard_{rotor_id}"].get("tube_diameter_mm", 0.0)),
            "sweep_deg": float(bpy.data.objects[f"guard_{rotor_id}"].get("sweep_deg", 0.0)),
            "center_z_mm": float(guard.get("center_z_mm", 0.0)),
            "height_above_motor_pod_mm": float(
                bpy.data.objects[f"guard_{rotor_id}"].get("height_above_motor_pod_mm", 0.0)
            ),
            "strut_horizontal_projection_mm": [
                float(bpy.data.objects[f"guard_{rotor_id}_strut_{index:02d}"].get("horizontal_projection_mm", 0.0))
                for index in range(1, int(guard.get("strut_count", 3)) + 1)
            ],
            "strut_vertical_rise_mm": [
                float(bpy.data.objects[f"guard_{rotor_id}_strut_{index:02d}"].get("vertical_rise_mm", 0.0))
                for index in range(1, int(guard.get("strut_count", 3)) + 1)
            ],
        }
        for rotor_id in rotor_ids
        if f"guard_{rotor_id}" in bpy.data.objects
    }
    camera_modules = {
        str(item["id"]): {
            "shape": str(item.get("shape", "rounded_box")),
            "location_mm": [float(value) for value in item["location_mm"]],
            "body_protrusion_mm": round(
                (
                    body_minimum.y
                    - world_bounds([bpy.data.objects[f"camera_{item['id']}_housing"]])[0].y
                )
                * 1000.0,
                6,
            )
            if tuple(item.get("aim_vector", [0.0, -1.0, 0.0])) == (0.0, -1.0, 0.0)
            else None,
            "configured_body_protrusion_mm": float(item.get("body_protrusion_mm", 0.0)),
            "dimensions_mm": [
                round(value * 1000.0, 6)
                for value in bpy.data.objects[f"camera_{item['id']}_housing"].dimensions
            ],
        }
        for item in config.get("equipment", {}).get("cameras", [])
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
            },
            "structure_frame": {
                "x": round(frame_dimensions.x * 1000.0, 6),
                "y": round(frame_dimensions.y * 1000.0, 6),
                "z": round(frame_dimensions.z * 1000.0, 6),
            },
        },
        "visual_mesh_count": len(visual_meshes),
        "triangles": triangles,
        "motor_axes": motor_axes,
        "sensor_masts": sensor_masts,
        "arm_members": arm_members,
        "guard_mounts": guard_mounts,
        "guard_modules": guard_modules,
        "camera_modules": camera_modules,
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
