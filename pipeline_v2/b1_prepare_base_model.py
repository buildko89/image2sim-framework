"""B-1: Prepare Base Model Runner

Blender CLI を呼び出してベースモデルを準備する。

使用方法:
  python pipeline_v2/b1_prepare_base_model.py
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


INPUT_MODEL = "input/cat/uploads_files_6085726_FbxBlender/FbxBlender/Leopard_Hybrid_A1.Fbx"
OUTPUT_BLEND = "output_v2/base/cat_base.blend"
OUTPUT_GLB = "output_v2/base/cat_base.glb"
REPORT = "output_v2/reports/b1_prepare_base_model.json"


def load_env(repo_root: Path) -> None:
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


def find_blender() -> str | None:
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    candidates = [
        r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
    ]
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_env(repo_root)

    blender_path = find_blender()
    if not blender_path:
        print("ERROR: Blender executable not found. Set BLENDER_PATH in .env")
        return 1

    blender_script = repo_root / "pipeline_v2" / "b1_prepare_base_model_blender.py"
    input_model = repo_root / INPUT_MODEL
    output_blend = repo_root / OUTPUT_BLEND
    output_glb = repo_root / OUTPUT_GLB
    report = repo_root / REPORT

    if not input_model.exists():
        print(f"ERROR: Input model not found: {input_model}")
        return 1

    print(f"B-1: Prepare Base Model")
    print(f"  Blender: {blender_path}")
    print(f"  Input:   {input_model}")
    print(f"  Output:  {output_glb}")
    print()

    command = [
        blender_path,
        "--background",
        "--python", str(blender_script),
        "--",
        "--input", str(input_model),
        "--output-blend", str(output_blend),
        "--output-glb", str(output_glb),
        "--report", str(report),
    ]

    result = subprocess.run(command, check=False, text=True, timeout=300)

    if result.returncode != 0:
        print(f"\nERROR: Blender exited with code {result.returncode}")
        return result.returncode

    if output_glb.exists():
        size_mb = output_glb.stat().st_size / (1024 * 1024)
        print(f"\nBase model ready: {output_glb} ({size_mb:.1f} MB)")
    else:
        print(f"\nWARNING: GLB was not created at {output_glb}")

    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        after = data.get("after_normalization", {})
        print(f"  Dimensions: {after.get('dimensions_m', 'unknown')}")
        print(f"  Meshes: {after.get('mesh_count', '?')}")
        print(f"  Vertices: {after.get('total_vertices', '?')}")
        print(f"  Animations: {after.get('action_count', '?')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
