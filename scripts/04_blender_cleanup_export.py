from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT_ASSET = "output/raw_3d/cat_reference_scene.blend"
DEFAULT_CLEAN_3D_DIR = "output/clean_3d"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_clean.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_clean.fbx"
DEFAULT_TARGET_HEIGHT = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize a Blender asset and export GLB/FBX.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    parser.add_argument("--input", dest="input_asset", help="Input .blend, .glb, .gltf, .fbx, or .obj path.")
    parser.add_argument("--output-glb", help="Output GLB path.")
    parser.add_argument("--output-fbx", help="Output FBX path.")
    parser.add_argument("--reports-dir", help="Output reports directory.")
    parser.add_argument("--target-height", type=float, help="Target asset height in Blender meters.")
    parser.add_argument("--remove-reference-objects", action="store_true")
    parser.add_argument("--apply-transforms", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Write a plan report without running Blender.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing GLB/FBX outputs.")
    return parser.parse_args()


def resolve_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path.resolve())


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except ImportError:
        pass
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(repo_root: Path, config_path: str | None) -> dict[str, Any]:
    if not config_path:
        return {}
    path = resolve_path(repo_root, config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file was not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data


def settings_from_config(config: dict[str, Any]) -> dict[str, Any]:
    cleanup_config = config.get("blender_cleanup_export") or {}
    blender_config = config.get("blender") or {}
    if not isinstance(cleanup_config, dict):
        cleanup_config = {}
    if not isinstance(blender_config, dict):
        blender_config = {}
    return {
        "input_asset": cleanup_config.get("input_asset", DEFAULT_INPUT_ASSET),
        "output_glb": cleanup_config.get("output_glb", DEFAULT_OUTPUT_GLB),
        "output_fbx": cleanup_config.get("output_fbx", DEFAULT_OUTPUT_FBX),
        "reports_dir": cleanup_config.get("reports_dir", config.get("reports_dir", DEFAULT_REPORTS_DIR)),
        "target_height": float(cleanup_config.get("target_height", DEFAULT_TARGET_HEIGHT)),
        "blender_path_env": blender_config.get("path_env", "BLENDER_PATH"),
    }


def ensure_output_available(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists. Use --overwrite to replace it: {path}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_report(
    repo_root: Path,
    input_asset: Path,
    output_glb: Path,
    output_fbx: Path,
    target_height: float,
    remove_reference_objects: bool,
    apply_transforms: bool,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "task": "Task 4 - Blender Cleanup and Export",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "input_asset": repo_relative_path(repo_root, input_asset),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "target_height": target_height,
        "remove_reference_objects": remove_reference_objects,
        "apply_transforms": apply_transforms,
        "steps": [
            "load_asset",
            "set_metric_units",
            "optional_remove_reference_objects",
            "center_asset_on_origin_xy",
            "place_asset_base_on_z_zero",
            "scale_to_target_height",
            "optional_apply_transforms",
            "export_glb",
            "export_fbx",
        ],
    }


def run_blender(
    blender_path: str,
    blender_script: Path,
    input_asset: Path,
    output_glb: Path,
    output_fbx: Path,
    report_path: Path,
    target_height: float,
    remove_reference_objects: bool,
    apply_transforms: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        blender_path,
        "-b",
        "--python",
        str(blender_script),
        "--",
        "--input",
        str(input_asset),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report_path),
        "--target-height",
        str(target_height),
    ]
    if remove_reference_objects:
        command.append("--remove-reference-objects")
    if apply_transforms:
        command.append("--apply-transforms")
    return subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    load_env_file(repo_root / ".env")
    config = load_config(repo_root, args.config_path)
    settings = settings_from_config(config)

    input_asset = resolve_path(repo_root, args.input_asset or settings["input_asset"])
    output_glb = resolve_path(repo_root, args.output_glb or settings["output_glb"])
    output_fbx = resolve_path(repo_root, args.output_fbx or settings["output_fbx"])
    reports_dir = resolve_path(repo_root, args.reports_dir or settings["reports_dir"])
    target_height = args.target_height if args.target_height is not None else settings["target_height"]

    plan = build_report(
        repo_root,
        input_asset,
        output_glb,
        output_fbx,
        target_height,
        args.remove_reference_objects,
        args.apply_transforms,
        args.dry_run,
    )
    plan_path = reports_dir / "blender_cleanup_export_plan.json"
    write_json(plan_path, plan)

    print("Blender cleanup and export")
    print(f"- Input asset: {input_asset}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Output FBX: {output_fbx}")
    print(f"- Target height: {target_height}")
    print(f"- Plan: {plan_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0

    if not input_asset.exists():
        print(f"ERROR: Input asset was not found: {input_asset}")
        return 2
    ensure_output_available(output_glb, args.overwrite)
    ensure_output_available(output_fbx, args.overwrite)

    blender_path = os.environ.get(settings["blender_path_env"], "")
    if not blender_path:
        print(f"ERROR: {settings['blender_path_env']} is not set. Add it to .env or run with --dry-run.")
        return 2
    if not Path(blender_path).exists():
        print(f"ERROR: Blender executable was not found: {blender_path}")
        return 2

    report_path = reports_dir / "blender_cleanup_export.json"
    completed = run_blender(
        blender_path,
        repo_root / "blender" / "cleanup_export.py",
        input_asset,
        output_glb,
        output_fbx,
        report_path,
        target_height,
        args.remove_reference_objects,
        args.apply_transforms,
    )

    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    if completed.returncode != 0:
        print(f"ERROR: Blender returned exit code {completed.returncode}.")
        return completed.returncode

    print(f"- Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
