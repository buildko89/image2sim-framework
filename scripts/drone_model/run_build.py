from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO / "config" / "drone2_model.yaml"
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
VIEWS = (
    ("top", "上"),
    ("bottom", "下"),
    ("front", "前"),
    ("back", "後"),
    ("left", "左"),
    ("right", "右"),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="パラメトリックドローンモデルを生成します。")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--blender", default=str(DEFAULT_BLENDER))
    parser.add_argument(
        "--output-directory",
        help="設定のoutput.directoryを上書きします（回帰確認用の一時出力先など）。",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-contact-sheet", action="store_true")
    return parser.parse_args()


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("設定ファイルの最上位はmappingである必要があります。")
    return data


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """テンプレートへ機体固有設定を再帰的に上書きする。"""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_model_config(path: Path) -> dict[str, Any]:
    subject = load_yaml(path)
    template_value = subject.get("template_file")
    if not template_value:
        return subject
    template_path = resolve_repo_path(template_value)
    if not template_path.is_file():
        raise FileNotFoundError(f"テンプレート設定がありません: {template_path}")
    template = load_yaml(template_path)
    resolved = deep_merge(template, subject)
    resolved["template_metadata"] = {
        "template_file": str(template_path),
        "template_id": str(template.get("template_id", template_path.stem)),
        "subject_config": str(path),
    }
    return resolved


def measurement_value(config: dict[str, Any], name: str, required: bool = True) -> float | None:
    try:
        value = config["measurements"][name]["value"]
    except (KeyError, TypeError) as exc:
        if required:
            raise ValueError(f"必須実測項目がありません: {name}") from exc
        return None
    if value is None:
        if required:
            raise ValueError(f"必須実測値は正数である必要があります: {name}")
        return None
    if float(value) <= 0:
        raise ValueError(f"必須実測値は正数である必要があります: {name}")
    return float(value)


def per_rotor_value(section: dict[str, Any], key: str, rotor_id: str) -> float:
    override_key = f"{key[:-3]}_by_rotor_mm" if key.endswith("_mm") else f"{key}_by_rotor_mm"
    return float(section.get(override_key, {}).get(rotor_id, section[key]))


def validate_and_resolve(config: dict[str, Any]) -> dict[str, Any]:
    layout = config.setdefault("layout", {})
    mode = str(layout.get("mode", "square_diagonal" if layout.get("square_motor_layout") else "explicit"))
    motor_z = float(layout.get("motor_axis_z_mm", 0.0))
    spacing_x: float | None = None
    spacing_y: float | None = None

    if mode == "square_diagonal":
        diagonal = measurement_value(config, "motor_center_diagonal_mm")
        spacing_x = spacing_y = float(diagonal) / math.sqrt(2.0)
        half_x, half_y = spacing_x / 2.0, spacing_y / 2.0
        positions = {
            "fl": [-half_x, -half_y, motor_z],
            "fr": [+half_x, -half_y, motor_z],
            "rl": [-half_x, +half_y, motor_z],
            "rr": [+half_x, +half_y, motor_z],
        }
    elif mode == "radial":
        count = int(layout["rotor_count"])
        if count < 1:
            raise ValueError("radial配置のrotor_countは1以上にしてください。")
        radius = float(layout["radius_mm"])
        start = math.radians(float(layout.get("start_angle_deg", -90.0)))
        prefix = str(layout.get("id_prefix", "r"))
        positions = {}
        for index in range(count):
            angle = start + index * 2.0 * math.pi / count
            positions[f"{prefix}{index + 1}"] = [radius * math.cos(angle), radius * math.sin(angle), motor_z]
    elif mode == "explicit":
        raw_positions = layout.get("motor_positions_mm")
        if not isinstance(raw_positions, dict) or not raw_positions:
            raise ValueError("explicit配置にはlayout.motor_positions_mmが必要です。")
        positions = {}
        for rotor_id, values in raw_positions.items():
            if not isinstance(values, list) or len(values) not in {2, 3}:
                raise ValueError(f"モーター位置は[x, y]または[x, y, z]です: {rotor_id}")
            positions[str(rotor_id)] = [float(values[0]), float(values[1]), float(values[2]) if len(values) == 3 else motor_z]
    else:
        raise ValueError(f"未対応のlayout.modeです: {mode}")

    rotor_ids = list(positions)
    propeller_cfg = config["propeller"]
    configured_directions = propeller_cfg.get("directions", {})
    pattern = list(propeller_cfg.get("direction_pattern", ["ccw", "cw"]))
    if not pattern:
        raise ValueError("propeller.direction_patternを空にはできません。")
    directions = {
        rotor_id: str(configured_directions.get(rotor_id, pattern[index % len(pattern)]))
        for index, rotor_id in enumerate(rotor_ids)
    }

    propeller = float(propeller_cfg.get("diameter_mm") or measurement_value(config, "propeller_diameter_mm"))
    guard = config.setdefault("guard", {"enabled": False})
    guard_enabled = bool(guard.get("enabled", True))
    guard_outer = guard_outer_x = guard_outer_y = guard_inner = clearance = None
    if guard_enabled:
        size_mode = str(guard.get("size_mode", "fit_overall"))
        if size_mode in {"fit_overall", "fit_overall_xy"}:
            width = measurement_value(config, "overall_width_mm")
            length = measurement_value(config, "overall_length_mm")
            xs = [value[0] for value in positions.values()]
            ys = [value[1] for value in positions.values()]
            span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
            fitted_x = float(width) - span_x
            fitted_y = float(length) - span_y
            if size_mode == "fit_overall_xy":
                guard_outer_x, guard_outer_y = fitted_x, fitted_y
                guard_outer = min(fitted_x, fitted_y)
            else:
                guard_outer = min(fitted_x, fitted_y)
                guard_outer_x = guard_outer_y = guard_outer
        elif size_mode == "explicit":
            configured = guard.get("outer_diameter_mm")
            guard_outer = float(configured["value"] if isinstance(configured, dict) else configured)
            guard_outer_x = float(guard.get("outer_width_mm", guard_outer))
            guard_outer_y = float(guard.get("outer_length_mm", guard_outer))
        else:
            raise ValueError(f"未対応のguard.size_modeです: {size_mode}")
        if min(float(guard_outer_x), float(guard_outer_y)) <= 0:
            raise ValueError("ガード外径は正数である必要があります。")
        tube = float(guard["tube_diameter_mm"])
        guard_inner = guard_outer - 2.0 * tube
        clearance = (guard_inner - propeller) / 2.0
        if clearance <= 0:
            raise ValueError(f"プロペラ径{propeller:.3f} mmがガード内径{guard_inner:.3f} mmへ収まりません。")

    config["derived"] = {
        "layout_mode": mode,
        "rotor_ids": rotor_ids,
        "rotor_count": len(rotor_ids),
        "rotor_directions": directions,
        "motor_center_spacing_x_mm": spacing_x,
        "motor_center_spacing_y_mm": spacing_y,
        "guard_outer_diameter_mm": guard_outer,
        "guard_outer_width_mm": guard_outer_x,
        "guard_outer_length_mm": guard_outer_y,
        "guard_inner_diameter_mm": guard_inner,
        "propeller_radial_clearance_mm": clearance,
        "motor_positions_mm": positions,
    }
    return config


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO / path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def font(size: int) -> ImageFont.ImageFont:
    candidates = (
        Path("C:/Windows/Fonts/meiryo.ttc"),
        Path("C:/Windows/Fonts/YuGothM.ttc"),
    )
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def fit_panel(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    panel = Image.new("RGB", size, (232, 232, 232))
    source = ImageOps.exif_transpose(image)
    if source.mode in {"RGBA", "LA"}:
        rgba = source.convert("RGBA")
        bbox = rgba.getchannel("A").getbbox()
        if bbox:
            rgba = rgba.crop(bbox)
        flattened = Image.new("RGB", rgba.size, (232, 232, 232))
        flattened.paste(rgba.convert("RGB"), (0, 0), rgba.getchannel("A"))
        source = flattened
    else:
        source = source.convert("RGB")
    fitted = ImageOps.contain(source, (size[0] - 16, size[1] - 16))
    panel.paste(fitted, ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2))
    return panel


def load_reference_image(path: Path) -> Image.Image:
    """Pillow非対応のHEICはImageMagickへフォールバックして読み込む。"""
    try:
        with Image.open(path) as source:
            return source.copy()
    except Exception as pillow_error:
        completed = subprocess.run(
            ["magick", str(path), "-auto-orient", "png:-"],
            capture_output=True,
            timeout=90,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode("utf-8", errors="replace")[-1000:]
            raise RuntimeError(f"参照画像を開けません: {path}: {pillow_error}; {stderr}") from pillow_error
        with Image.open(io.BytesIO(completed.stdout)) as converted:
            return converted.copy()


def build_contact_sheet(config: dict[str, Any], output_dir: Path) -> Path:
    cell = (420, 315)
    label_width = 90
    header_height = 54
    sheet = Image.new("RGB", (label_width + cell[0] * 2, header_height + cell[1] * len(VIEWS)), (32, 32, 35))
    draw = ImageDraw.Draw(sheet)
    title_font = font(18)
    label_font = font(16)
    draw.text((label_width + 8, 14), "実物写真", fill=(245, 245, 245), font=title_font)
    draw.text((label_width + cell[0] + 8, 14), "パラメトリックモデル", fill=(245, 245, 245), font=title_font)

    references = config.get("references", {})
    for row, (view, label) in enumerate(VIEWS):
        y = header_height + row * cell[1]
        draw.text((12, y + 12), label, fill=(255, 225, 120), font=label_font)
        if view not in references:
            raise ValueError(f"比較シートに必要な参照画像がありません: references.{view}")
        source_path = resolve_repo_path(references[view])
        render_path = output_dir / "renders" / f"{view}.png"
        source = load_reference_image(source_path)
        sheet.paste(fit_panel(source, cell), (label_width, y))
        with Image.open(render_path) as rendered:
            sheet.paste(fit_panel(rendered, cell), (label_width + cell[0], y))

    path = output_dir / "comparison_sheet.png"
    sheet.save(path)
    return path


def build_qa(config: dict[str, Any], build_report: dict[str, Any]) -> dict[str, Any]:
    world_position_tolerance_mm = 1e-4
    actual = build_report["dimensions_mm"]
    actual_body = build_report["part_dimensions_mm"]["body_core"]
    hierarchy = build_report.get("collection_hierarchy", {})
    collection_nodes: dict[str, dict[str, Any]] = {}

    def collect_nodes(nodes: dict[str, Any]) -> None:
        for name, node in nodes.items():
            collection_nodes[name] = node
            collect_nodes(node.get("children", {}))

    collect_nodes(hierarchy)
    expected_top_collections = {"MODEL_VISUAL", "ANCHORS", "COLLISION", "CAMERAS", "REF_PHOTOS"}
    expected_rotor_collections = {
        f"VIS_ROTOR_{rotor_id}"
        for rotor_id in config["derived"]["rotor_ids"]
    }
    object_parents = build_report.get("object_parents", {})
    rotor_assemblies = build_report.get("rotor_assemblies", {})
    expected_fixed_children = {}
    expected_spinning_children = {}
    for rotor_id in config["derived"]["rotor_ids"]:
        fixed = {f"motor_{rotor_id}", f"motor_{rotor_id}_shaft"}
        if config.get("motor_mount", {}).get("enabled"):
            fixed.add(f"motor_mount_{rotor_id}")
        if config.get("esc", {}).get("enabled"):
            fixed.add(f"esc_{rotor_id}")
        expected_fixed_children[rotor_id] = sorted(fixed)
        expected_spinning_children[rotor_id] = sorted({
            f"rotor_{rotor_id}_blades",
            f"rotor_{rotor_id}_hub",
        })
    groove_parent_errors = {
        name: parent
        for name, parent in object_parents.items()
        if "__groove_" in name and parent != name.split("__groove_", 1)[0]
    }
    expected_center_of_mass = [
        float(value)
        for value in config.get("physics", {}).get("center_of_mass_mm", [0.0, 0.0, 0.0])
    ]
    expected_axis_locations = {
        rotor_id: [
            float(config["derived"]["motor_positions_mm"][rotor_id][0]),
            float(config["derived"]["motor_positions_mm"][rotor_id][1]),
            per_rotor_value(config["propeller"], "center_z_mm", rotor_id),
        ]
        for rotor_id in config["derived"]["rotor_ids"]
    }
    expected_motor_locations = {
        rotor_id: [
            float(config["derived"]["motor_positions_mm"][rotor_id][0]),
            float(config["derived"]["motor_positions_mm"][rotor_id][1]),
            per_rotor_value(config["motor"], "center_z_mm", rotor_id),
        ]
        for rotor_id in config["derived"]["rotor_ids"]
    }
    coordinate_records = [
        *build_report.get("motor_axes", {}).values(),
        build_report.get("center_of_mass", {}),
        *build_report.get("rotor_assemblies", {}).values(),
        *build_report.get("collision_proxies", {}).values(),
        *build_report.get("sensor_masts", {}).values(),
        *build_report.get("guard_mounts", {}).values(),
        *build_report.get("camera_modules", {}).values(),
    ]
    checks: dict[str, dict[str, Any]] = {
        "build_report_schema": {
            "expected": "1.3",
            "actual": build_report.get("schema_version"),
            "pass": build_report.get("schema_version") == "1.3",
        },
        "world_coordinate_metadata": {
            "reported_transform_space": build_report.get("coordinate_system", {}).get("reported_transform_space"),
            "record_count": len(coordinate_records),
            "pass": build_report.get("coordinate_system", {}).get("reported_transform_space") == "world"
            and bool(coordinate_records)
            and all(item.get("coordinate_space") == "world" for item in coordinate_records),
        },
        "motor_count": {
            "expected": int(config["derived"]["rotor_count"]),
            "actual": len(build_report["motor_axes"]),
            "pass": len(build_report["motor_axes"]) == int(config["derived"]["rotor_count"]),
        },
        "required_names": {
            "missing": build_report.get("missing_required_names", []),
            "pass": not build_report.get("missing_required_names"),
        },
        "duplicate_suffix_names": {
            "names": build_report.get("duplicate_suffix_names", []),
            "pass": not build_report.get("duplicate_suffix_names"),
        },
        "duplicate_suffix_collection_names": {
            "names": build_report.get("duplicate_suffix_collection_names", []),
            "pass": not build_report.get("duplicate_suffix_collection_names"),
        },
        "top_level_collections": {
            "expected": sorted(expected_top_collections),
            "actual": sorted(hierarchy),
            "pass": set(hierarchy) == expected_top_collections,
        },
        "rotor_collections": {
            "expected": sorted(expected_rotor_collections),
            "actual": sorted(expected_rotor_collections & set(collection_nodes)),
            "pass": expected_rotor_collections <= set(collection_nodes)
            and all(collection_nodes[name].get("direct_objects", 0) > 0 for name in expected_rotor_collections),
        },
        "collection_recursive_counts": {
            "expected": build_report.get("collections", {}),
            "actual": {
                name: hierarchy.get(name, {}).get("all_objects")
                for name in expected_top_collections
            },
            "pass": all(
                hierarchy.get(name, {}).get("all_objects") == count
                for name, count in build_report.get("collections", {}).items()
            ),
        },
        "groove_parents": {
            "errors": groove_parent_errors,
            "pass": not groove_parent_errors,
        },
        "rotor_fixed_children": {
            "expected": expected_fixed_children,
            "actual": {
                rotor_id: item.get("fixed_children", [])
                for rotor_id, item in rotor_assemblies.items()
            },
            "pass": set(rotor_assemblies) == set(expected_fixed_children)
            and all(
                rotor_assemblies[rotor_id].get("fixed_children", []) == children
                for rotor_id, children in expected_fixed_children.items()
            ),
        },
        "rotor_spinning_children": {
            "expected": expected_spinning_children,
            "actual": {
                rotor_id: item.get("spinning_children", [])
                for rotor_id, item in rotor_assemblies.items()
            },
            "pass": set(rotor_assemblies) == set(expected_spinning_children)
            and all(
                rotor_assemblies[rotor_id].get("spinning_children", []) == children
                for rotor_id, children in expected_spinning_children.items()
            ),
        },
        "rotor_spin_origins": {
            "maximum_error_mm": max(
                (float(item.get("origin_error_mm", math.inf)) for item in rotor_assemblies.values()),
                default=math.inf,
            ),
            "pass": len(rotor_assemblies) == int(config["derived"]["rotor_count"])
            and all(float(item.get("origin_error_mm", math.inf)) <= 1e-6 for item in rotor_assemblies.values()),
        },
        "world_thrust_axes": {
            "actual": {
                rotor_id: item.get("world_thrust_axis")
                for rotor_id, item in build_report.get("motor_axes", {}).items()
            },
            "pass": all(
                item.get("world_thrust_axis") is not None
                and all(
                    abs(float(actual) - expected) <= 1e-9
                    for actual, expected in zip(item["world_thrust_axis"], (0.0, 0.0, 1.0))
                )
                for item in build_report.get("motor_axes", {}).values()
            ),
        },
        "motor_axis_world_positions": {
            "expected_mm": expected_axis_locations,
            "actual_mm": {
                rotor_id: item.get("location_mm")
                for rotor_id, item in build_report.get("motor_axes", {}).items()
            },
            "pass": set(build_report.get("motor_axes", {})) == set(expected_axis_locations)
            and all(
                len(build_report["motor_axes"][rotor_id].get("location_mm", [])) == 3
                and all(
                    abs(float(actual) - expected) <= world_position_tolerance_mm
                    for actual, expected in zip(
                        build_report["motor_axes"][rotor_id]["location_mm"],
                        expected_location,
                    )
                )
                for rotor_id, expected_location in expected_axis_locations.items()
            ),
        },
        "motor_world_positions": {
            "expected_mm": expected_motor_locations,
            "actual_mm": {
                rotor_id: item.get("motor_location_mm")
                for rotor_id, item in build_report.get("motor_axes", {}).items()
            },
            "pass": set(build_report.get("motor_axes", {})) == set(expected_motor_locations)
            and all(
                len(build_report["motor_axes"][rotor_id].get("motor_location_mm", [])) == 3
                and all(
                    abs(float(actual) - expected) <= world_position_tolerance_mm
                    for actual, expected in zip(
                        build_report["motor_axes"][rotor_id]["motor_location_mm"],
                        expected_location,
                    )
                )
                for rotor_id, expected_location in expected_motor_locations.items()
            ),
        },
        "anchor_matrix_world_consistency": {
            "pass": all(
                len(item.get("matrix_world", [])) == 4
                and len(item.get("location_mm", [])) == 3
                and all(
                    abs(float(item["matrix_world"][axis][3]) * 1000.0 - float(item["location_mm"][axis]))
                    <= world_position_tolerance_mm
                    for axis in range(3)
                )
                for item in [
                    *build_report.get("motor_axes", {}).values(),
                    build_report.get("center_of_mass", {}),
                ]
            ),
        },
        "center_of_mass_world_position": {
            "expected_mm": expected_center_of_mass,
            "actual_mm": build_report.get("center_of_mass", {}).get("location_mm"),
            "pass": build_report.get("center_of_mass", {}).get("location_mm") is not None
            and all(
                abs(float(actual) - expected) <= world_position_tolerance_mm
                for actual, expected in zip(
                    build_report["center_of_mass"]["location_mm"],
                    expected_center_of_mass,
                )
            ),
        },
        "collision_proxy_world_records": {
            "expected_count": int(build_report.get("collections", {}).get("COLLISION", 0)),
            "actual_count": len(build_report.get("collision_proxies", {})),
            "pass": len(build_report.get("collision_proxies", {}))
            == int(build_report.get("collections", {}).get("COLLISION", -1))
            and all(
                item.get("coordinate_space") == "world"
                and len(item.get("matrix_world", [])) == 4
                for item in build_report.get("collision_proxies", {}).values()
            ),
        },
    }
    if config.get("wing", {}).get("enabled"):
        expected_wing_children = {"main_wing"} | {
            f"wing_bracket_{item['id']}"
            for item in config.get("wing", {}).get("brackets", [])
        }
        checks["wing_parents"] = {
            "expected_parent": "wing_root",
            "children": sorted(expected_wing_children),
            "actual": {
                name: object_parents.get(name)
                for name in sorted(expected_wing_children)
            },
            "pass": object_parents.get("wing_root") == "drone_root"
            and all(object_parents.get(name) == "wing_root" for name in expected_wing_children),
        }
    expected_under = sorted(config.get("motor", {}).get("under_frame_rotors", []))
    if expected_under:
        actual_under = sorted(
            rotor_id
            for rotor_id, item in build_report["motor_axes"].items()
            if item.get("mount_side") == "under_frame"
        )
        checks["under_frame_motors"] = {
            "expected": expected_under,
            "actual": actual_under,
            "pass": actual_under == expected_under,
        }
    dimensional_checks = (
        ("overall_width", "overall_width_mm", actual["x"]),
        ("overall_length", "overall_length_mm", actual["y"]),
        ("overall_height", "overall_height_mm", actual["z"]),
        ("body_width", "body_width_mm", actual_body["x"]),
        ("body_height", "body_height_mm", actual_body["z"]),
        ("body_length", "body_length_mm", actual_body["y"]),
    )
    for check_name, measurement_name, actual_value in dimensional_checks:
        expected = measurement_value(config, measurement_name, required=False)
        if expected is not None:
            tolerance = float(config["measurements"][measurement_name].get("tolerance_mm", 0.5))
            checks[check_name] = {
                "expected_mm": expected,
                "actual_mm": actual_value,
                "error_mm": actual_value - expected,
                "tolerance_mm": tolerance,
                "pass": abs(actual_value - expected) <= tolerance,
            }
    first_motor = next(iter(build_report.get("motor_axes", {}).values()), None)
    first_guard_mount = next(iter(build_report.get("guard_mounts", {}).values()), None)
    front_camera = build_report.get("camera_modules", {}).get("front")
    detailed_dimensions = (
        (
            "motor_housing_diameter",
            "motor_housing_diameter_mm",
            first_motor["motor_dimensions_mm"][0] if first_motor else None,
        ),
        (
            "guard_mount_tube_diameter",
            "guard_mount_tube_diameter_mm",
            first_guard_mount["dimensions_mm"][0] if first_guard_mount else None,
        ),
        (
            "front_camera_diameter",
            "front_camera_diameter_mm",
            max(front_camera["dimensions_mm"][0], front_camera["dimensions_mm"][2]) if front_camera else None,
        ),
    )
    for check_name, measurement_name, actual_value in detailed_dimensions:
        expected = measurement_value(config, measurement_name, required=False)
        if expected is not None:
            tolerance = float(config["measurements"][measurement_name].get("tolerance_mm", 0.5))
            checks[check_name] = {
                "expected_mm": expected,
                "actual_mm": actual_value,
                "error_mm": None if actual_value is None else actual_value - expected,
                "tolerance_mm": tolerance,
                "pass": actual_value is not None and abs(actual_value - expected) <= tolerance,
            }
    arm_measurements = (
        ("front_arm_outer_length", "front_arm_outer_length_mm", ("fl", "fr"), "outer"),
        ("front_arm_inner_length", "front_arm_inner_length_mm", ("fl", "fr"), "inner"),
        ("rear_arm_outer_length", "rear_arm_outer_length_mm", ("rl", "rr"), "outer"),
        ("rear_arm_inner_length", "rear_arm_inner_length_mm", ("rl", "rr"), "inner"),
    )
    for check_name, measurement_name, rotor_ids, role in arm_measurements:
        expected = measurement_value(config, measurement_name, required=False)
        if expected is None:
            continue
        actual_values = {
            rotor_id: build_report.get("arm_members", {}).get(rotor_id, {}).get(role, {}).get("measured_length_mm")
            for rotor_id in rotor_ids
        }
        tolerance = float(config["measurements"][measurement_name].get("tolerance_mm", 1.0))
        checks[check_name] = {
            "expected_mm": expected,
            "actual_mm": actual_values,
            "tolerance_mm": tolerance,
            "pass": all(
                value is not None and abs(float(value) - expected) <= tolerance
                for value in actual_values.values()
            ),
        }
    expected_vertical_roles = sorted(str(value) for value in config.get("arm", {}).get("vertical_member_roles", []))
    if expected_vertical_roles:
        actual_vertical_roles = {
            rotor_id: {
                role: sorted(
                    build_report.get("arm_members", {}).get(rotor_id, {}).get(role, {}).get("vertical_roles", [])
                )
                for role in ("outer", "inner")
            }
            for rotor_id in config["derived"]["rotor_ids"]
        }
        checks["arm_vertical_members"] = {
            "expected": expected_vertical_roles,
            "actual": actual_vertical_roles,
            "pass": all(
                roles == expected_vertical_roles
                for rotor in actual_vertical_roles.values()
                for roles in rotor.values()
            ),
        }
    camera_protrusion = measurement_value(config, "front_camera_protrusion_mm", required=False)
    if camera_protrusion is not None:
        actual_protrusion = (
            build_report.get("camera_modules", {}).get("front", {}).get("body_protrusion_mm")
        )
        tolerance = float(config["measurements"]["front_camera_protrusion_mm"].get("tolerance_mm", 0.5))
        checks["front_camera_protrusion"] = {
            "expected_mm": camera_protrusion,
            "actual_mm": actual_protrusion,
            "error_mm": None if actual_protrusion is None else actual_protrusion - camera_protrusion,
            "tolerance_mm": tolerance,
            "pass": actual_protrusion is not None and abs(actual_protrusion - camera_protrusion) <= tolerance,
        }
    guard_tube = measurement_value(config, "guard_tube_diameter_mm", required=False)
    if guard_tube is not None:
        actual_tubes = {
            rotor_id: item.get("tube_diameter_mm")
            for rotor_id, item in build_report.get("guard_modules", {}).items()
        }
        tolerance = float(config["measurements"]["guard_tube_diameter_mm"].get("tolerance_mm", 0.3))
        checks["guard_tube_diameter"] = {
            "expected_mm": guard_tube,
            "actual_mm": actual_tubes,
            "tolerance_mm": tolerance,
            "pass": bool(actual_tubes)
            and all(
                value is not None and abs(float(value) - guard_tube) <= tolerance
                for value in actual_tubes.values()
            ),
        }
    expected_sweep = config.get("guard", {}).get("sweep_deg")
    if expected_sweep is not None:
        actual_sweeps = {
            rotor_id: item.get("sweep_deg")
            for rotor_id, item in build_report.get("guard_modules", {}).items()
        }
        checks["guard_sweep"] = {
            "expected_deg": float(expected_sweep),
            "actual_deg": actual_sweeps,
            "pass": bool(actual_sweeps)
            and all(
                value is not None and abs(float(value) - float(expected_sweep)) <= 0.01
                for value in actual_sweeps.values()
            ),
        }
    expected_guard_height = measurement_value(config, "guard_height_above_motor_pod_mm", required=False)
    if expected_guard_height is not None:
        actual_guard_heights = {
            rotor_id: item.get("height_above_motor_pod_mm")
            for rotor_id, item in build_report.get("guard_modules", {}).items()
        }
        tolerance = float(config["measurements"]["guard_height_above_motor_pod_mm"].get("tolerance_mm", 1.0))
        checks["guard_height_above_motor_pod"] = {
            "expected_mm": expected_guard_height,
            "actual_mm": actual_guard_heights,
            "tolerance_mm": tolerance,
            "pass": bool(actual_guard_heights)
            and all(
                value is not None and abs(float(value) - expected_guard_height) <= tolerance
                for value in actual_guard_heights.values()
            ),
        }
    expected_guard_projection = measurement_value(config, "guard_mount_to_arc_mm", required=False)
    if expected_guard_projection is not None:
        actual_guard_projections = {
            rotor_id: item.get("strut_horizontal_projection_mm", [])
            for rotor_id, item in build_report.get("guard_modules", {}).items()
        }
        tolerance = float(config["measurements"]["guard_mount_to_arc_mm"].get("tolerance_mm", 2.0))
        checks["guard_mount_to_arc_horizontal"] = {
            "expected_mm": expected_guard_projection,
            "actual_mm": actual_guard_projections,
            "tolerance_mm": tolerance,
            "pass": bool(actual_guard_projections)
            and all(
                values
                and all(abs(float(value) - expected_guard_projection) <= tolerance for value in values)
                for values in actual_guard_projections.values()
            ),
        }
    motor_locations = [axis["location_mm"] for axis in build_report["motor_axes"].values()]
    if motor_locations:
        expected_diagonal = measurement_value(config, "motor_center_diagonal_mm", required=False)
        if expected_diagonal is not None:
            actual_diagonal = max(
                math.hypot(a[0] - b[0], a[1] - b[1])
                for index, a in enumerate(motor_locations)
                for b in motor_locations[index + 1 :]
            )
            tolerance = float(config["measurements"]["motor_center_diagonal_mm"].get("tolerance_mm", 1.0))
            checks["motor_center_diagonal"] = {
                "expected_mm": expected_diagonal,
                "actual_mm": actual_diagonal,
                "error_mm": actual_diagonal - expected_diagonal,
                "tolerance_mm": tolerance,
                "pass": abs(actual_diagonal - expected_diagonal) <= tolerance,
            }
        motor_span_x = max(item[0] for item in motor_locations) - min(item[0] for item in motor_locations)
        motor_span_y = max(item[1] for item in motor_locations) - min(item[1] for item in motor_locations)
        for check_name, measurement_name, actual_value in (
            ("motor_center_span_x", "motor_center_span_x_mm", motor_span_x),
            ("motor_center_span_y", "motor_center_span_y_mm", motor_span_y),
        ):
            expected = measurement_value(config, measurement_name, required=False)
            if expected is not None:
                tolerance = float(config["measurements"][measurement_name].get("tolerance_mm", 1.0))
                checks[check_name] = {
                    "expected_mm": expected,
                    "actual_mm": actual_value,
                    "error_mm": actual_value - expected,
                    "tolerance_mm": tolerance,
                    "pass": abs(actual_value - expected) <= tolerance,
                }
    expected_mast_height = measurement_value(config, "gps_mast_height_mm", required=False)
    if expected_mast_height is not None:
        mast_heights = {
            mast_id: item["height_mm"]
            for mast_id, item in build_report.get("sensor_masts", {}).items()
        }
        tolerance = float(config["measurements"]["gps_mast_height_mm"].get("tolerance_mm", 1.0))
        checks["gps_mast_height"] = {
            "expected_mm": expected_mast_height,
            "actual_mm": mast_heights,
            "tolerance_mm": tolerance,
            "pass": bool(mast_heights)
            and all(abs(value - expected_mast_height) <= tolerance for value in mast_heights.values()),
        }
    passed = all(item["pass"] for item in checks.values())
    return {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if passed else "FAIL",
        "dimensions_provisional": bool(config.get("dimensions_provisional", True)),
        "checks": checks,
        "notes": list(config.get("qa_notes", [
            "写真から判別できない小部品形状は代表形状でモデル化しています。",
            "質量、重心、慣性、実機ローター回転方向は実測・確認後に更新してください。",
        ])),
    }


def write_markdown_report(
    config: dict[str, Any],
    build_report: dict[str, Any],
    qa_report: dict[str, Any],
    output_dir: Path,
) -> Path:
    derived = config["derived"]
    dimensions = build_report["dimensions_mm"]
    body_dimensions = build_report["part_dimensions_mm"]["body_core"]
    template_name = config.get("template_metadata", {}).get("template_id", "テンプレート未指定（従来互換）")
    lines = [
        f"# {config['subject_id']} パラメトリックモデル生成結果",
        "",
        f"生成日時：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        "",
        "## 判定",
        "",
        f"- 構造・寸法QA：`{qa_report['status']}`",
        f"- 使用テンプレート：`{template_name}`",
        f"- 配置方式：`{derived['layout_mode']}`、ローター数：{derived['rotor_count']}",
        f"- 寸法状態：{'暫定' if config.get('dimensions_provisional', True) else '確定'}",
        "- 物理状態：未確定（質量・重心・慣性・ローター回転方向の実測が必要）",
        "",
        "## 入力寸法",
        "",
        "| 項目 | 値 |",
        "|---|---:|",
    ]
    labels = {
        "overall_width_mm": "機体全幅", "overall_length_mm": "機体全長",
        "overall_height_mm": "機体全高",
        "motor_center_span_x_mm": "左右モーター中心スパン",
        "motor_center_span_y_mm": "前後モーター中心スパン",
        "motor_center_diagonal_mm": "対角モーター中心間", "propeller_diameter_mm": "プロペラ直径",
        "body_height_mm": "中央ボディ高さ", "body_length_mm": "中央ボディ前後長",
    }
    for name, item in config.get("measurements", {}).items():
        if isinstance(item, dict) and item.get("value") is not None:
            unit = "g" if name.endswith("_g") else "mm"
            lines.append(f"| {labels.get(name, name)} | {float(item['value']):.3f} {unit} |")
    lines.extend(["", "## 派生値", "", f"- ローターID：{', '.join(derived['rotor_ids'])}"])
    if derived.get("motor_center_spacing_x_mm") is not None:
        lines.append(f"- 左右・前後モーター中心間：{derived['motor_center_spacing_x_mm']:.3f} mm")
    if derived.get("guard_outer_diameter_mm") is not None:
        lines.extend([
            f"- ガード外径：{derived['guard_outer_diameter_mm']:.3f} mm",
            f"- ガード内径：{derived['guard_inner_diameter_mm']:.3f} mm",
            f"- プロペラ先端の半径方向隙間：{derived['propeller_radial_clearance_mm']:.3f} mm",
        ])
    motor_locations = list(derived["motor_positions_mm"].values())
    if motor_locations:
        span_x = max(item[0] for item in motor_locations) - min(item[0] for item in motor_locations)
        span_y = max(item[1] for item in motor_locations) - min(item[1] for item in motor_locations)
        lines.append(f"- モーター中心スパン：X={span_x:.3f} mm、Y={span_y:.3f} mm")
    lines.extend([
        "", "## 生成結果", "",
        f"- バウンディング寸法：X={dimensions['x']:.3f}、Y={dimensions['y']:.3f}、Z={dimensions['z']:.3f} mm",
        f"- 中央ボディ寸法：幅={body_dimensions['x']:.3f}、長さ={body_dimensions['y']:.3f}、高さ={body_dimensions['z']:.3f} mm",
        f"- 表示用Mesh数：{build_report['visual_mesh_count']}",
        f"- triangles：{build_report['triangles']}",
        f"- Blender：{build_report['blender_version']}",
        "", "## 注意", "",
        "- 写真は形状判断の資料であり、画像から形状を自動推定しているわけではありません。",
        "- 質量、重心、慣性、各ローター回転方向は実測・確認後に更新してください。",
        "",
    ])
    path = output_dir / "BUILD_REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    args = parse_args()
    config_path = resolve_repo_path(args.config)
    blender_path = Path(args.blender)
    if not config_path.is_file():
        raise FileNotFoundError(f"設定ファイルがありません: {config_path}")
    if not blender_path.is_file():
        raise FileNotFoundError(f"Blenderがありません: {blender_path}")

    config = validate_and_resolve(load_model_config(config_path))
    if args.output_directory:
        config["output"]["directory"] = str(resolve_repo_path(args.output_directory))
    output_cfg = config["output"]
    output_dir = resolve_repo_path(output_cfg["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    key_outputs = [output_dir / output_cfg["blend"], output_dir / output_cfg["glb"]]
    if not args.overwrite and any(path.exists() for path in key_outputs):
        raise FileExistsError("既存成果物があります。更新する場合は--overwriteを指定してください。")

    # Blender側では解決済み設定の保存階層に依存せず、同じ出力先を使わせる。
    output_cfg["directory"] = str(output_dir.resolve())
    resolved_path = output_dir / output_cfg["resolved_config"]
    resolved_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    blender_script = REPO / "blender" / "drone_model" / "build_drone.py"
    command = [
        str(blender_path),
        "--background",
        "--factory-startup",
        "--python-exit-code",
        "1",
        "--python",
        str(blender_script),
        "--",
        "--config-json",
        str(resolved_path),
    ]
    completed = subprocess.run(
        command,
        cwd=REPO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    (output_dir / "blender_stdout.log").write_text(completed.stdout or "", encoding="utf-8")
    (output_dir / "blender_stderr.log").write_text(completed.stderr or "", encoding="utf-8")
    if completed.returncode != 0 or "Traceback" in (completed.stdout or "") or "Traceback" in (completed.stderr or ""):
        print((completed.stdout or "")[-4000:])
        print((completed.stderr or "")[-4000:], file=sys.stderr)
        return completed.returncode or 1

    required = [
        output_dir / output_cfg["blend"],
        output_dir / output_cfg["glb"],
        output_dir / output_cfg["build_report"],
        *(output_dir / "renders" / f"{view}.png" for view, _ in VIEWS),
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError(f"Blender成果物が不足しています: {missing}")

    build_report = json.loads((output_dir / output_cfg["build_report"]).read_text(encoding="utf-8"))
    qa_report = build_qa(config, build_report)
    qa_path = output_dir / output_cfg["qa_report"]
    qa_path.write_text(json.dumps(qa_report, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.skip_contact_sheet:
        build_contact_sheet(config, output_dir)
    markdown_path = write_markdown_report(config, build_report, qa_report, output_dir)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "config": str(config_path),
        "config_sha256": sha256_file(config_path),
        "resolved_config": str(resolved_path),
        "blend": str(output_dir / output_cfg["blend"]),
        "glb": str(output_dir / output_cfg["glb"]),
        "glb_sha256": sha256_file(output_dir / output_cfg["glb"]),
        "qa": str(qa_path),
        "qa_status": qa_report["status"],
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"生成完了: {output_dir / output_cfg['glb']}")
    print(f"QA: {qa_report['status']}")
    print(f"日本語レポート: {markdown_path}")
    return 0 if qa_report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
