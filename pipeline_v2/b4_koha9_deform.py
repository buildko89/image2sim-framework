"""B-4: Koha9 Body Deform Runner

Blender CLI を呼び出して三毛猫モデルを koha9 体型へ変形する。

使用方法:
  python pipeline_v2/b4_koha9_deform.py
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


INPUT_BLEND = "output_v2/base/cat_calico.blend"
OUTPUT_BLEND = "output_v2/base/cat_koha9.blend"
OUTPUT_GLB = "output_v2/base/cat_koha9.glb"
REPORT = "output_v2/reports/b4_koha9_deform.json"


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

    blender_script = repo_root / "pipeline_v2" / "b4_koha9_deform_blender.py"
    input_blend = repo_root / INPUT_BLEND
    output_blend = repo_root / OUTPUT_BLEND
    output_glb = repo_root / OUTPUT_GLB
    report = repo_root / REPORT

    if not input_blend.exists():
        print(f"ERROR: Input blend not found: {input_blend}")
        return 1

    print("B-4: Koha9 Body Deform")
    print(f"  Blender: {blender_path}")
    print(f"  Input:   {input_blend}")
    print(f"  Output:  {output_glb}")
    print()

    command = [
        blender_path,
        "--background",
        "--python", str(blender_script),
        "--",
        "--input", str(input_blend),
        "--output-blend", str(output_blend),
        "--output-glb", str(output_glb),
        "--report", str(report),
    ]

    result = subprocess.run(command, check=False, text=True, timeout=600)

    if result.returncode != 0:
        print(f"\nERROR: Blender exited with code {result.returncode}")
        return result.returncode

    if output_glb.exists():
        size_mb = output_glb.stat().st_size / (1024 * 1024)
        print(f"\nKoha9 model ready: {output_glb} ({size_mb:.1f} MB)")

    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        print(f"  Dimensions before: {data.get('dimensions_before')}")
        print(f"  Dimensions after:  {data.get('dimensions_after')}")
        print(f"  Deformed counts:   {data.get('deformed_vertex_counts')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
