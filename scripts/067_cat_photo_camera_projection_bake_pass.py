from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


DEFAULT_INPUT_BLEND = "output/rigged/cat_tripo_reference_visual_pass.blend"
DEFAULT_SIDE_IMAGE = "input/masks/reference_side_standing_pattern_1713434749448_cutout.png"
DEFAULT_FRONT_IMAGE = "input/masks/reference_front_face_1763363798733_cutout.png"
DEFAULT_BACK_IMAGE = "input/masks/reference_back_top_tail_1755598074234_cutout.png"
DEFAULT_TEXTURE_DIR = "output/textures/task67_cat_photo_camera_projection_bake"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_photo_camera_projection_bake_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_photo_camera_projection_bake_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_photo_camera_projection_bake_pass.fbx"
DEFAULT_REPORT = "output/reports/task67_cat_photo_camera_projection_bake_pass.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-photo camera projection bake for the rigged cat.")
    parser.add_argument("--input", default=DEFAULT_INPUT_BLEND)
    parser.add_argument("--side-image", default=DEFAULT_SIDE_IMAGE)
    parser.add_argument("--front-image", default=DEFAULT_FRONT_IMAGE)
    parser.add_argument("--back-image", default=DEFAULT_BACK_IMAGE)
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
    side_image = resolve_path(repo_root, args.side_image)
    front_image = resolve_path(repo_root, args.front_image)
    back_image = resolve_path(repo_root, args.back_image)
    texture_dir = resolve_path(repo_root, args.texture_dir)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    blender_script = repo_root / "blender" / "cat_photo_camera_projection_bake_pass.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"

    print("Task 6.7 photo camera projection bake pass")
    print(f"- Input Blend: {input_blend}")
    print(f"- Side image: {side_image}")
    print(f"- Front image: {front_image}")
    print(f"- Back image: {back_image}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Blender: {blender_path}")

    required = [input_blend, side_image, front_image, back_image]
    missing = [path for path in required if not path.exists()]
    if args.dry_run:
        if missing:
            print("- Missing inputs:")
            for path in missing:
                print(f"  - {path}")
            return 2
        print("- Dry-run: Blender was not executed.")
        return 0
    if missing:
        for path in missing:
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
        "--side-image",
        str(side_image),
        "--front-image",
        str(front_image),
        "--back-image",
        str(back_image),
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
