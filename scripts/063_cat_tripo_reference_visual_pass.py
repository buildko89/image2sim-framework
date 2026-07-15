from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_BLEND = "output/rigged/cat_fluffy_shortleg_pass.blend"
DEFAULT_TRIPO_REFERENCE = "output/raw_3d/cloud_manual/tripo/calico_cat_v25/calico_cat_v25.glb"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_tripo_reference_visual_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_tripo_reference_visual_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_tripo_reference_visual_pass.fbx"
DEFAULT_REPORT = "output/reports/task63_cat_tripo_reference_visual_pass.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Tripo reference visual pass in Blender.")
    parser.add_argument("--input", default=DEFAULT_INPUT_BLEND)
    parser.add_argument("--tripo-reference", default=DEFAULT_TRIPO_REFERENCE)
    parser.add_argument("--output-blend", default=DEFAULT_OUTPUT_BLEND)
    parser.add_argument("--output-glb", default=DEFAULT_OUTPUT_GLB)
    parser.add_argument("--output-fbx", default=DEFAULT_OUTPUT_FBX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--blender", help="Path to blender executable. Defaults to BLENDER_PATH.")
    parser.add_argument("--dry-run", action="store_true")
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


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_blend = resolve_path(repo_root, args.input)
    tripo_reference = resolve_path(repo_root, args.tripo_reference)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    blender_script = repo_root / "blender" / "cat_tripo_reference_visual_pass.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

    plan = {
        "task": "Task 6.3: Tripo Reference Visual Pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "input": repo_relative_path(repo_root, input_blend),
        "tripo_reference": repo_relative_path(repo_root, tripo_reference),
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "report": repo_relative_path(repo_root, report),
        "blender": blender_path,
        "steps": [
            "open the existing fluffy short-leg rigged Blend",
            "import Tripo v2.5 GLB as a Blend-only visual reference",
            "retune flat calico material colors using Tripo and real-photo guidance",
            "adjust polygon material assignments for white, warm brown, dark, and cream fur",
            "strengthen chest, belly, and side fur shell volume without changing the armature",
            "export only the skinned rig and armature to animated GLB/FBX",
        ],
    }
    write_json(report.with_name("task63_cat_tripo_reference_visual_pass_plan.json"), plan)

    print("Task 6.3 Tripo reference visual pass")
    print(f"- Input Blend: {input_blend}")
    print(f"- Tripo reference: {tripo_reference}")
    print(f"- Output Blend: {output_blend}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Output FBX: {output_fbx}")
    print(f"- Blender: {blender_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0 if input_blend.exists() and tripo_reference.exists() else 2
    if not input_blend.exists():
        print(f"ERROR: Required input not found: {input_blend}")
        return 2
    if not tripo_reference.exists():
        print(f"ERROR: Tripo reference not found: {tripo_reference}")
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
        str(input_blend),
        "--tripo-reference",
        str(tripo_reference),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report),
    ]
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
