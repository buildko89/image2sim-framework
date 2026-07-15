from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


DEFAULT_INPUT_BLEND = "output/rigged/cat_tripo_reference_visual_pass.blend"
DEFAULT_TEXTURE_DIR = "output/textures/task66_cat_tripo_projection_bake"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_tripo_projection_bake_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_tripo_projection_bake_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_tripo_projection_bake_pass.fbx"
DEFAULT_REPORT = "output/reports/task66_cat_tripo_projection_bake_pass.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Tripo reference selected-to-active projection bake.")
    parser.add_argument("--input", default=DEFAULT_INPUT_BLEND)
    parser.add_argument("--texture-dir", default=DEFAULT_TEXTURE_DIR)
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


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_blend = resolve_path(repo_root, args.input)
    texture_dir = resolve_path(repo_root, args.texture_dir)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    blender_script = repo_root / "blender" / "cat_tripo_projection_bake_pass.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

    print("Task 6.6 Tripo projection bake pass")
    print(f"- Input Blend: {input_blend}")
    print(f"- Texture dir: {texture_dir}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Blender: {blender_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0 if input_blend.exists() else 2
    if not input_blend.exists():
        print(f"ERROR: Required input not found: {input_blend}")
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
        "--texture-dir",
        str(texture_dir),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=420)
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr)
    if completed.returncode != 0:
        print(f"ERROR: Blender returned exit code {completed.returncode}.")
        return completed.returncode
    print(f"- Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
