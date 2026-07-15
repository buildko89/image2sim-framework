"""B-0: Cat Model Asset Inspection Runner

Blender CLI を呼び出してモデル棚卸しを実行する。
Blender がインストールされていない場合はエラーメッセージを表示する。

使用方法:
  python pipeline_v2/b0_inspect_cat_assets.py
  python pipeline_v2/b0_inspect_cat_assets.py --blender "C:\\path\\to\\blender.exe"
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run cat model asset inspection via Blender CLI.")
    parser.add_argument("--blender", help="Path to Blender executable. Defaults to BLENDER_PATH env var.")
    parser.add_argument("--output", default="output_v2/reports/b0_asset_inspection.json",
                        help="Output JSON report path (relative to repo root)")
    return parser.parse_args()


def load_env(repo_root: Path) -> None:
    """Load .env file if present."""
    env_path = repo_root / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def find_blender(explicit_path: str | None) -> str | None:
    """Blender 実行ファイルのパスを探す。"""
    if explicit_path and Path(explicit_path).exists():
        return explicit_path

    env_path = os.environ.get("BLENDER_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # よくあるインストール場所を探す
    candidates = [
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path

    return None


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    load_env(repo_root)

    blender_path = find_blender(args.blender)
    if not blender_path:
        print("ERROR: Blender executable not found.")
        print("  Set BLENDER_PATH in .env or pass --blender <path>")
        return 1

    blender_script = repo_root / "pipeline_v2" / "b0_inspect_cat_assets_blender.py"
    output_path = repo_root / args.output

    print(f"Blender: {blender_path}")
    print(f"Script:  {blender_script}")
    print(f"Output:  {output_path}")
    print()

    command = [
        blender_path,
        "--background",
        "--python",
        str(blender_script),
        "--",
        "--output",
        str(output_path),
    ]

    result = subprocess.run(command, check=False, capture_output=False, text=True, timeout=600)

    if result.returncode != 0:
        print(f"\nERROR: Blender exited with code {result.returncode}")
        return result.returncode

    if output_path.exists():
        report = json.loads(output_path.read_text(encoding="utf-8"))
        print(f"\n{'='*60}")
        print(f"Inspection complete. Report: {output_path}")
        recommended = report.get("recommended")
        if recommended:
            print(f"\n🏆 Recommended base model: {recommended['filename']}")
            print(f"   Path: {recommended['relative_path']}")
            print(f"   Rig: {recommended['has_rig']}, Animations: {recommended['action_count']}")
            print(f"   Vertices: {recommended['total_vertices']}, Polygons: {recommended['total_polygons']}")
    else:
        print(f"\nWARNING: Report file was not created at {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
