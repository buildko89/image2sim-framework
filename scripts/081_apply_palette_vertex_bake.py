from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT = "output/rigged/cat_animated.blend"
DEFAULT_PALETTE = "config/cat_color_palette.yaml"
DEFAULT_TEXTURE_DIR = "output/textures/cat_palette_vertex_bake"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_palette_vertex_bake_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_palette_vertex_bake_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_palette_vertex_bake_pass.fbx"
DEFAULT_REPORT = "output/reports/task81_palette_vertex_bake_pass.json"
DEFAULT_FRONT_PREVIEW = "output/reports/task81_palette_vertex_bake_front_preview.png"
DEFAULT_SIDE_PREVIEW = "output/reports/task81_palette_vertex_bake_side_preview.png"
DEFAULT_RESOLUTION = 2048


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run palette-driven vertex color bake for a cat model.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--palette", default=DEFAULT_PALETTE)
    parser.add_argument("--texture-dir", default=DEFAULT_TEXTURE_DIR)
    parser.add_argument("--output-blend", default=DEFAULT_OUTPUT_BLEND)
    parser.add_argument("--output-glb", default=DEFAULT_OUTPUT_GLB)
    parser.add_argument("--output-fbx", default=DEFAULT_OUTPUT_FBX)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--front-preview", default=DEFAULT_FRONT_PREVIEW)
    parser.add_argument("--side-preview", default=DEFAULT_SIDE_PREVIEW)
    parser.add_argument("--resolution", type=int, default=DEFAULT_RESOLUTION)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--axis-left-right", choices=["X", "Y", "Z"], default="X")
    parser.add_argument("--axis-front-back", choices=["X", "Y", "Z"], default="Y")
    parser.add_argument("--axis-up", choices=["X", "Y", "Z"], default="Z")
    parser.add_argument("--front-positive", choices=["true", "false"], default="true")
    parser.add_argument("--blender", help="Path to blender executable. Defaults to BLENDER_PATH.")
    parser.add_argument("--skip-preview", action="store_true")
    parser.add_argument("--skip-godot-stage", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


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


def run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    return completed


def render_preview(blender_path: str, render_script: Path, input_glb: Path, output_path: Path, view: str) -> int:
    command = [
        blender_path,
        "--background",
        "--python",
        str(render_script),
        "--",
        "--input",
        str(input_glb),
        "--output",
        str(output_path),
        "--view",
        view,
    ]
    return run_command(command, timeout=180).returncode


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    load_env_file(repo_root / ".env")

    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    input_model = resolve_path(repo_root, args.input)
    palette = resolve_path(repo_root, args.palette)
    texture_dir = resolve_path(repo_root, args.texture_dir)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    front_preview = resolve_path(repo_root, args.front_preview)
    side_preview = resolve_path(repo_root, args.side_preview)
    blender_script = repo_root / "blender" / "cat_palette_vertex_bake.py"
    render_script = repo_root / "blender" / "render_glb_preview.py"
    inspect_script = repo_root / "scripts" / "056_inspect_glb.py"
    plan_path = report.with_name("task81_palette_vertex_bake_pass_plan.json")

    plan = {
        "task": "Task 81: Palette Driven Vertex Color Bake",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "input": repo_relative_path(repo_root, input_model),
        "palette": repo_relative_path(repo_root, palette),
        "texture_dir": repo_relative_path(repo_root, texture_dir),
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "report": repo_relative_path(repo_root, report),
        "front_preview": repo_relative_path(repo_root, front_preview),
        "side_preview": repo_relative_path(repo_root, side_preview),
        "resolution": args.resolution,
        "seed": args.seed,
        "axis": {
            "left_right": args.axis_left_right,
            "front_back": args.axis_front_back,
            "up": args.axis_up,
            "front_positive": args.front_positive,
        },
        "blender": blender_path,
    }
    write_json(plan_path, plan)

    print("Task 81 palette-driven vertex color bake")
    print(f"- Input: {input_model}")
    print(f"- Palette: {palette}")
    print(f"- Output GLB: {output_glb}")
    print(f"- Blender: {blender_path}")

    missing = [path for path in [input_model, palette, blender_script] if not path.exists()]
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
        str(input_model),
        "--palette",
        str(palette),
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
        "--resolution",
        str(args.resolution),
        "--seed",
        str(args.seed),
        "--axis-left-right",
        args.axis_left_right,
        "--axis-front-back",
        args.axis_front_back,
        "--axis-up",
        args.axis_up,
        "--front-positive",
        args.front_positive,
    ]
    completed = run_command(command, timeout=600)
    if completed.returncode != 0:
        print(f"ERROR: Blender returned exit code {completed.returncode}.")
        return completed.returncode
    if not output_glb.exists():
        print(f"ERROR: Expected GLB was not created: {output_glb}")
        return 1

    if inspect_script.exists():
        inspect_report = report.with_name("task81_palette_vertex_bake_glb_inspection.json")
        inspect_completed = run_command([sys.executable, str(inspect_script), str(output_glb), "--report", str(inspect_report)], timeout=60)
        if inspect_completed.returncode != 0:
            return inspect_completed.returncode

    if not args.skip_preview and render_script.exists():
        front_code = render_preview(blender_path, render_script, output_glb, front_preview, "front")
        side_code = render_preview(blender_path, render_script, output_glb, side_preview, "side")
        if front_code != 0 or side_code != 0:
            return front_code or side_code

    if not args.skip_godot_stage:
        godot_dir = repo_root / "godot" / "Godot3dcat"
        if godot_dir.exists():
            staged_glb = godot_dir / "cat_palette_vertex_bake_pass.glb"
            shutil.copy2(output_glb, staged_glb)
            # Keep the active appearance scene path update manual; do not overwrite cat_deformed.glb here.
            print(f"- Staged Godot GLB: {staged_glb}")

    print(f"- Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
