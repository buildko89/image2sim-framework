from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_BLEND = "output/clean_3d/cat_rigged_clean.blend"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_appearance_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_appearance_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_appearance_pass.fbx"
DEFAULT_REPORT = "output/reports/task55_cat_appearance_pass.json"
DEFAULT_REFERENCE_IMAGES = [
    "input/selected_photos/reference_side_right_body_1698975320501.jpg",
    "input/selected_photos/reference_front_face_1763363798733.jpg",
    "input/selected_photos/reference_back_top_tail_1755598074234.jpg",
]
DEFAULT_REFERENCE_MESH = "output/clean_3d/cat_clean.glb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Task 5.5 cat appearance pass in Blender.")
    parser.add_argument("--input", default=DEFAULT_INPUT_BLEND)
    parser.add_argument("--output-blend", default=DEFAULT_OUTPUT_BLEND)
    parser.add_argument("--output-glb", default=DEFAULT_OUTPUT_GLB)
    parser.add_argument("--output-fbx", default=DEFAULT_OUTPUT_FBX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--reference-image", action="append", help="Reference image path. Repeatable.")
    parser.add_argument("--reference-mesh", default=DEFAULT_REFERENCE_MESH)
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
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    reference_images = args.reference_image or DEFAULT_REFERENCE_IMAGES
    reference_image_paths = [resolve_path(repo_root, path) for path in reference_images]
    reference_mesh = resolve_path(repo_root, args.reference_mesh) if args.reference_mesh else None
    blender_script = repo_root / "blender" / "cat_appearance_pass.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

    missing_inputs = [path for path in [input_blend, *reference_image_paths] if not path.exists()]
    if reference_mesh and not reference_mesh.exists():
        missing_inputs.append(reference_mesh)

    plan = {
        "task": "Task 5.5: Cat Appearance Pass on Fox Rig",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "input": repo_relative_path(repo_root, input_blend),
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "report": repo_relative_path(repo_root, report),
        "reference_images": [repo_relative_path(repo_root, path) for path in reference_image_paths],
        "reference_mesh": repo_relative_path(repo_root, reference_mesh) if reference_mesh else None,
        "missing_inputs": [repo_relative_path(repo_root, path) for path in missing_inputs],
        "blender": blender_path,
        "steps": [
            "open the cleaned rigged Fox-based blend",
            "replace skinned mesh materials with a first cat-like calico material layout",
            "place selected reference images in a non-export reference collection",
            "place the static Hunyuan3D mesh as a non-export shape reference",
            "save a working .blend",
            "export only the rigged mesh and armature to animated GLB/FBX",
        ],
    }
    write_json(report.with_name("task55_cat_appearance_pass_plan.json"), plan)

    print("Task 5.5 cat appearance pass")
    print(f"- Input Blend: {input_blend}")
    print(f"- Output Blend: {output_blend}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Output FBX: {output_fbx}")
    print(f"- Blender: {blender_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0 if not missing_inputs else 2

    if missing_inputs:
        for path in missing_inputs:
            print(f"ERROR: Required input not found: {path}")
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
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report),
    ]
    for path in reference_image_paths:
        command.extend(["--reference-image", str(path)])
    if reference_mesh:
        command.extend(["--reference-mesh", str(reference_mesh)])

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
