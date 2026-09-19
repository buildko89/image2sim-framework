"""
scripts/usd/export_cat_usd.py

Blender CLI を呼び出し、猫モデル (.blend) から USD レイヤー分解と
マスターステージ root_cat.usda を生成するランナースクリプト。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
DEFAULT_BLEND = REPO_ROOT / "output_v2" / "base" / "p3_koha9face.blend"
DEFAULT_OUT_DIR = REPO_ROOT / "output_v2" / "usd"


def parse_args():
    parser = argparse.ArgumentParser(description="Export Cat blend model to OpenUSD layers.")
    parser.add_argument("--blend", default=str(DEFAULT_BLEND), help="Path to cat .blend file.")
    parser.add_argument("--blender", default=str(DEFAULT_BLENDER), help="Path to Blender executable.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUT_DIR), help="Output directory for USD.")
    parser.add_argument("--root-prim-name", default="KohaCat", help="Root prim name.")
    return parser.parse_args()


def main():
    args = parse_args()
    blend_path = Path(args.blend).resolve()
    blender_path = Path(args.blender).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not blend_path.is_file():
        raise FileNotFoundError(f"Blend file not found: {blend_path}")
    if not blender_path.is_file():
        raise FileNotFoundError(f"Blender executable not found: {blender_path}")

    worker_script = REPO_ROOT / "scripts" / "usd" / "export_cat_usd_blender.py"
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

    print(f"[Cat USD Runner] Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, capture_output=True, text=True)

    print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)

    if res.returncode != 0:
        sys.exit(res.returncode)

    print(f"[Cat USD Runner] USD layers successfully exported to {output_dir}")

    # USD Physics & Variants の自動付与
    root_file = output_dir / "root_cat.usda"
    if root_file.is_file():
        try:
            from scripts.usd.author_cat_physics import setup_cat_physics
            setup_cat_physics(root_file)
            print(f"[Cat USD Runner] USD Physics successfully authored to {root_file}")
        except Exception as e:
            print(f"[Cat USD Runner] Warning: Failed to author USD Physics: {e}", file=sys.stderr)

        try:
            from scripts.usd.author_cat_variants import setup_cat_variants
            setup_cat_variants(root_file)
            print(f"[Cat USD Runner] USD Variants successfully authored to {root_file}")
        except Exception as e:
            print(f"[Cat USD Runner] Warning: Failed to author USD Variants: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
