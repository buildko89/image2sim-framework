"""
scripts/usd/export_derived_glb_blender.py

Blender 5.2 LTS 内で動作し、マスター USD ステージ (.usda) をインポートして
Godot 4.x / Web プレビュー向けに最適化された単一派生 GLB (.glb) を出力するスクリプト。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import bpy


def parse_args():
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Export USD stage to optimized GLB.")
    parser.add_argument("--usd-stage", required=True, help="Path to input USD stage (.usda / .usdc)")
    parser.add_argument("--output-glb", required=True, help="Path to output GLB file (.glb)")
    return parser.parse_args(raw_args)


def main():
    args = parse_args()
    usd_path = Path(args.usd_stage).resolve()
    glb_path = Path(args.output_glb).resolve()

    if not usd_path.is_file():
        raise FileNotFoundError(f"USD stage not found: {usd_path}")

    glb_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. クリーンなシーンの初期化
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # 2. USD ステージのインポート
    print(f"[USD->GLB] Importing USD stage: {usd_path}")
    bpy.ops.wm.usd_import(
        filepath=str(usd_path),
        import_subdivision=False,
        create_collection=True,
        import_materials=True,
        import_usd_preview=True,
        import_skeletons=True,
        read_mesh_uvs=True,
    )

    # 3. 最適化 GLB のエクスポート (Godot 4.x / Web 互換)
    print(f"[USD->GLB] Exporting optimized GLB: {glb_path}")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_path),
        export_format="GLB",
        export_materials="EXPORT",
        export_yup=True,
        export_apply=False,
    )

    print(f"[USD->GLB] Successfully exported derived GLB to {glb_path}")


if __name__ == "__main__":
    main()
