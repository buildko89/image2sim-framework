from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_ASSET = "output/rigged/cat_base_rigged.glb"
DEFAULT_OUTPUT_BLEND = "output/clean_3d/cat_rigged_clean.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_rigged_clean.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_rigged_clean.fbx"
DEFAULT_REPORT = "output/reports/task4_blender_rig_cleanup_export.json"
DEFAULT_TARGET_HEIGHT = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Blender rig cleanup/export for Task 4.")
    parser.add_argument("--input", default=DEFAULT_INPUT_ASSET)
    parser.add_argument("--output-blend", default=DEFAULT_OUTPUT_BLEND)
    parser.add_argument("--output-glb", default=DEFAULT_OUTPUT_GLB)
    parser.add_argument("--output-fbx", default=DEFAULT_OUTPUT_FBX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--target-height", type=float, default=DEFAULT_TARGET_HEIGHT)
    parser.add_argument("--blender", help="Path to blender executable. Defaults to BLENDER_PATH.")
    parser.add_argument("--remove-helper-meshes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path.resolve())


def resolve_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_asset = resolve_path(repo_root, args.input)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    blender_script = repo_root / "blender" / "rig_cleanup_export.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

    plan = {
        "task": "Task 4: Blender Rig Cleanup and Animation Export",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "input": repo_relative_path(repo_root, input_asset),
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "report": repo_relative_path(repo_root, report),
        "target_height": args.target_height,
        "remove_helper_meshes": args.remove_helper_meshes,
        "blender": blender_path,
        "steps": [
            "load rigged asset",
            "set metric units",
            "optionally remove helper meshes",
            "normalize root objects to target height and floor origin",
            "save normalized blend",
            "export animated GLB",
            "export animated FBX",
        ],
    }
    write_json(report.with_name("task4_blender_rig_cleanup_export_plan.json"), plan)

    print("Task 4 Blender rig cleanup/export")
    print(f"- Input: {input_asset}")
    print(f"- Output Blend: {output_blend}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Output FBX: {output_fbx}")
    print(f"- Blender: {blender_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0

    if not input_asset.exists():
        print(f"ERROR: Input asset not found: {input_asset}")
        return 2
    if not Path(blender_path).exists():
        print(f"ERROR: Blender executable not found: {blender_path}")
        return 2

    command = [
        blender_path,
        "--background",
        "--python",
        str(blender_script),
        "--",
        "--input",
        str(input_asset),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report),
        "--target-height",
        str(args.target_height),
    ]
    if args.remove_helper_meshes:
        command.append("--remove-helper-meshes")

    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    if completed.returncode != 0:
        print(f"ERROR: Blender returned exit code {completed.returncode}.")
        return completed.returncode
    print(f"- Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
