from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter


DEFAULT_INPUT_BLEND = "output/rigged/cat_tripo_reference_visual_pass.blend"
DEFAULT_TEXTURE_DIR = "output/textures/task64_cat_texture_experiment"
DEFAULT_OUTPUT_BLEND = "output/rigged/cat_texture_experiment_pass.blend"
DEFAULT_OUTPUT_GLB = "output/clean_3d/cat_texture_experiment_pass.glb"
DEFAULT_OUTPUT_FBX = "output/clean_3d/cat_texture_experiment_pass.fbx"
DEFAULT_REPORT = "output/reports/task64_cat_texture_experiment_pass.json"

TEXTURE_SPECS = {
    "white_fur.png": {
        "base": (236, 226, 205),
        "light": (252, 247, 235),
        "dark": (162, 150, 132),
        "accent": (204, 184, 150),
        "strength": 0.75,
    },
    "warm_calico_fur.png": {
        "base": (184, 88, 28),
        "light": (230, 144, 62),
        "dark": (92, 45, 22),
        "accent": (245, 182, 93),
        "strength": 0.9,
    },
    "dark_calico_fur.png": {
        "base": (42, 31, 24),
        "light": (100, 77, 58),
        "dark": (12, 10, 9),
        "accent": (72, 52, 38),
        "strength": 0.95,
    },
    "cream_shadow_fur.png": {
        "base": (176, 154, 120),
        "light": (226, 207, 172),
        "dark": (104, 90, 72),
        "accent": (196, 169, 126),
        "strength": 0.8,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run texture experiment pass for the rigged cat.")
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


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path.resolve())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def blend_color(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(a[i] * (1.0 - t) + b[i] * t))) for i in range(3))


def make_fur_texture(path: Path, spec: dict[str, Any], seed: int, size: int = 1024) -> None:
    rng = random.Random(seed)
    base = spec["base"]
    image = Image.new("RGB", (size, size), base)
    draw = ImageDraw.Draw(image, "RGBA")

    # Soft broad bands.
    for _ in range(90):
        x = rng.randint(-size // 4, size + size // 4)
        width = rng.randint(10, 34)
        color = spec["light"] if rng.random() < 0.45 else spec["dark"]
        alpha = int(rng.randint(18, 58) * spec["strength"])
        slant = rng.randint(-130, 130)
        draw.line((x, -20, x + slant, size + 20), fill=(*color, alpha), width=width)

    # Fine fur strands.
    for _ in range(950):
        x = rng.randint(-40, size + 40)
        y = rng.randint(-20, size)
        length = rng.randint(120, 420)
        slant = rng.randint(-45, 45)
        color = rng.choice([spec["light"], spec["dark"], spec["accent"]])
        alpha = int(rng.randint(22, 82) * spec["strength"])
        width = rng.choice([1, 1, 1, 2, 3])
        draw.line((x, y, x + slant, y + length), fill=(*color, alpha), width=width)

    # A few darker clumps like Tripo's visible streaks, kept conservative.
    for _ in range(60):
        x = rng.randint(-20, size + 20)
        y = rng.randint(0, size)
        length = rng.randint(160, 520)
        slant = rng.randint(-35, 35)
        alpha = int(rng.randint(40, 95) * spec["strength"])
        draw.line((x, y, x + slant, y + length), fill=(*spec["dark"], alpha), width=rng.randint(2, 5))

    image = image.filter(ImageFilter.GaussianBlur(radius=0.35))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def generate_textures(texture_dir: Path) -> list[str]:
    outputs = []
    for index, (filename, spec) in enumerate(TEXTURE_SPECS.items()):
        path = texture_dir / filename
        make_fur_texture(path, spec, seed=6400 + index)
        outputs.append(str(path))
    return outputs


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_blend = resolve_path(repo_root, args.input)
    texture_dir = resolve_path(repo_root, args.texture_dir)
    output_blend = resolve_path(repo_root, args.output_blend)
    output_glb = resolve_path(repo_root, args.output_glb)
    output_fbx = resolve_path(repo_root, args.output_fbx)
    report = resolve_path(repo_root, args.report)
    blender_script = repo_root / "blender" / "cat_texture_experiment_pass.py"
    blender_path = args.blender or os.environ.get("BLENDER_PATH") or r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
    texture_outputs = generate_textures(texture_dir)

    plan = {
        "task": "Task 6.4: Texture Experiment Pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "input": repo_relative_path(repo_root, input_blend),
        "texture_dir": repo_relative_path(repo_root, texture_dir),
        "generated_textures": [repo_relative_path(repo_root, Path(path)) for path in texture_outputs],
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "output_fbx": repo_relative_path(repo_root, output_fbx),
        "report": repo_relative_path(repo_root, report),
        "blender": blender_path,
        "steps": [
            "generate visible fur-like base color PNG textures",
            "open the Tripo reference visual Blend",
            "add UVs to skinned meshes with Blender smart project",
            "connect image textures to cat materials",
            "export only the rigged mesh, fur shell, and armature",
        ],
    }
    write_json(report.with_name("task64_cat_texture_experiment_pass_plan.json"), plan)

    print("Task 6.4 texture experiment pass")
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
