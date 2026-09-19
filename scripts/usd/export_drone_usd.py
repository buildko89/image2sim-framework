"""
scripts/usd/export_drone_usd.py

Blender CLI を呼び出し、ドローンモデル (.blend) から USD レイヤー分解と
マスターアセンブリ drone_assembly.usda を生成するランナースクリプト。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
DEFAULT_BLEND = REPO_ROOT / "output" / "drone2_parametric" / "drone2.blend"
DEFAULT_OUT_DIR = REPO_ROOT / "output" / "drone2_parametric" / "usd"


def parse_args():
    parser = argparse.ArgumentParser(description="Export Drone blend model to OpenUSD layers.")
    parser.add_argument("--blend", default=str(DEFAULT_BLEND), help="Path to drone .blend file.")
    parser.add_argument("--blender", default=str(DEFAULT_BLENDER), help="Path to Blender executable.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT_DIR), help="Output directory for USD.")
    parser.add_argument("--root-prim-name", default="Drone_Root", help="Root prim name.")
    parser.add_argument("--config", default=str(REPO_ROOT / "config" / "drone2_model.yaml"), help="Path to drone YAML config.")
    return parser.parse_args()


def main():
    args = parse_args()
    blend_path = Path(args.blend).resolve()
    blender_path = Path(args.blender).resolve()
    output_dir = Path(args.output_dir).resolve()
    config_path = Path(args.config).resolve()

    if not blend_path.is_file():
        raise FileNotFoundError(f"Blend file not found: {blend_path}")
    if not blender_path.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender_path}")

    worker_script = REPO_ROOT / "scripts" / "usd" / "export_drone_usd_blender.py"
    if not worker_script.is_file():
        raise FileNotFoundError(f"Worker script not found: {worker_script}")

    cmd = [
        str(blender_path),
        str(blend_path),
        "--background",
        "--python-exit-code",
        "1",
        "--python",
        str(worker_script),
        "--",
        "--output-dir",
        str(output_dir),
        "--root-prim-name",
        args.root_prim_name,
    ]

    print(f"[USD Runner] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)

    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    if res.returncode != 0:
        sys.exit(res.returncode)

    print(f"[USD Runner] USD layers successfully exported to {output_dir}")

    # USD Physics & Variants/Sensors の自動付与
    assembly_file = output_dir / "drone_assembly.usda"
    if assembly_file.is_file() and config_path.is_file():
        try:
            from scripts.usd.author_drone_physics import setup_drone_physics
            setup_drone_physics(assembly_file, config_path)
            print(f"[USD Runner] USD Physics successfully authored to {assembly_file}")
        except Exception as e:
            print(f"[USD Runner] Warning: Failed to author USD Physics: {e}", file=sys.stderr)

        try:
            from scripts.usd.author_drone_variants_sensors import setup_drone_variants_and_sensors
            setup_drone_variants_and_sensors(assembly_file)
            print(f"[USD Runner] USD Variants & Sensors successfully authored to {assembly_file}")
        except Exception as e:
            print(f"[USD Runner] Warning: Failed to author USD Variants & Sensors: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
