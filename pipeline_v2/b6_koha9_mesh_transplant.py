"""B-6: Koha9 Mesh Transplant Runner

Blender CLI を呼び出して koha9_cat メッシュを Leopard アーマチュアへ移植する。

使用方法:
  python pipeline_v2/b6_koha9_mesh_transplant.py
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


SKELETON_BLEND = "output_v2/base/cat_koha9.blend"
MESH_GLB = "input/cat2/koha9_cat.glb"
OUTPUT_BLEND = "output_v2/base/cat_koha.blend"
OUTPUT_GLB = "output_v2/base/cat_koha.glb"
REPORT = "output_v2/reports/b6_koha9_mesh_transplant.json"


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

    blender_script = repo_root / "pipeline_v2" / "b6_koha9_mesh_transplant_blender.py"
    skeleton = repo_root / SKELETON_BLEND
    mesh = repo_root / MESH_GLB
    output_blend = repo_root / OUTPUT_BLEND
    output_glb = repo_root / OUTPUT_GLB
    report = repo_root / REPORT

    for path, label in ((skeleton, "skeleton blend"), (mesh, "mesh glb")):
        if not path.exists():
            print(f"ERROR: {label} not found: {path}")
            return 1

    print("B-6: Koha9 Mesh Transplant")
    print(f"  Blender:  {blender_path}")
    print(f"  Skeleton: {skeleton}")
    print(f"  Mesh:     {mesh}")
    print(f"  Output:   {output_glb}")
    print()

    command = [
        blender_path,
        "--background",
        "--python", str(blender_script),
        "--",
        "--skeleton", str(skeleton),
        "--mesh", str(mesh),
        "--output-blend", str(output_blend),
        "--output-glb", str(output_glb),
        "--report", str(report),
    ]

    result = subprocess.run(command, check=False, text=True, timeout=900)

    if result.returncode != 0:
        print(f"\nERROR: Blender exited with code {result.returncode}")
        return result.returncode

    if output_glb.exists():
        size_mb = output_glb.stat().st_size / (1024 * 1024)
        print(f"\nTransplanted model ready: {output_glb} ({size_mb:.1f} MB)")

    if report.exists():
        data = json.loads(report.read_text(encoding="utf-8"))
        print(f"  Skinning: {data.get('skinning')}")
        print(f"  Bone fit: {data.get('bone_fit', {}).get('moved')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
