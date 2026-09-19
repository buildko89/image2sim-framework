"""
scripts/usd/open_in_blender_gui.py

Blender 5.2 LTS を使って USD アセットを目視確認するスクリプト。
- ボーンや物理コライダの巨大表示を自動非表示化
- --lod オプション対応:
    - simple (既定値): 毛シェル(FurShell)を非表示にし、本来の綺麗なベースメッシュ(Koha9)テクスチャを表示
    - full: 毛シェル4層を表示 (毛並みフリンジ表現)
- メインメッシュに自動フォーカスし、マテリアルプレビューで表示
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")

ASSETS = {
    "drone": REPO_ROOT / "output" / "drone2_parametric" / "usd" / "drone_assembly.usda",
    "cat": REPO_ROOT / "output_v2" / "usd" / "root_cat.usda",
}


def create_blend_from_usd(blender_path: Path, usd_path: Path, output_blend: Path, asset_type: str, lod: str) -> None:
    """バックグラウンドで USD をインポートし、見やすい .blend ファイルとして保存する"""
    hide_shells = "True" if lod == "simple" else "False"

    py_code = f"""
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)

# 1. USD インポート
bpy.ops.wm.usd_import(
    filepath=r"{str(usd_path)}",
    import_subdivision=False,
    create_collection=True,
    import_materials=True,
    import_usd_preview=True,
    import_skeletons=True,
    read_mesh_uvs=True,
)

# 2. ボーン(Armature)および物理コライダ(Paw_*)の非表示化
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        obj.hide_viewport = True
        obj.hide_render = True
    if obj.name.startswith("Paw_") or "Collision" in obj.name:
        obj.hide_viewport = True
    # 毛シェル (FurShell) の表示制御 (LOD: simple では非表示にして影ノイズを防止)
    if 'FurShell' in obj.name:
        obj.hide_viewport = {hide_shells}
        obj.hide_render = {hide_shells}
        if hasattr(obj, 'visible_shadow'):
            obj.visible_shadow = False

# 3. 太陽光ライトの追加 (モデルを明るく自然に照らす)
bpy.ops.object.light_add(type='SUN', location=(2, -2, 5))
sun = bpy.context.active_object
if sun:
    sun.data.energy = 4.0

# 4. メインメッシュに視点を合わせる準備
bpy.ops.object.select_all(action='DESELECT')
main_mesh = None
for obj in bpy.data.objects:
    if obj.type == 'MESH' and ('Koha9' in obj.name or 'body_core' in obj.name or 'Frame' in obj.name):
        obj.select_set(True)
        main_mesh = obj
        break

if not main_mesh:
    for obj in bpy.data.objects:
        if obj.type == 'MESH' and not obj.hide_viewport:
            obj.select_set(True)
            break

# 5. 保存
bpy.ops.wm.save_as_mainfile(filepath=r"{str(output_blend)}")
print("[USD Viewer] Cleaned up view and saved:", r"{str(output_blend)}")
"""
    cmd = [
        str(blender_path),
        "--background",
        "--python-exit-code",
        "1",
        "--python-expr",
        py_code,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(f"Failed to convert USD to .blend: {usd_path}")


def main():
    parser = argparse.ArgumentParser(description="View USD asset in Blender GUI.")
    parser.add_argument("--asset", choices=["drone", "cat"], default="cat", help="Target asset to view (drone / cat).")
    parser.add_argument("--lod", choices=["simple", "full"], default="simple", help="LOD mode: simple (clean base mesh, no shell noise) / full (with fur shells).")
    parser.add_argument("--file", help="Custom USD file path.")
    parser.add_argument("--blender", default=str(DEFAULT_BLENDER), help="Path to blender.exe")
    args = parser.parse_args()

    if args.file:
        usd_path = Path(args.file).resolve()
        output_blend = usd_path.parent / f"_view_{usd_path.stem}_{args.lod}.blend"
    else:
        usd_path = ASSETS[args.asset].resolve()
        output_blend = usd_path.parent / f"_view_{args.asset}_{args.lod}.blend"

    if not usd_path.is_file():
        print(f"Error: USD file not found: {usd_path}", file=sys.stderr)
        sys.exit(1)

    blender_path = Path(args.blender).resolve()
    if not blender_path.is_file():
        print(f"Error: Blender executable not found: {blender_path}", file=sys.stderr)
        sys.exit(1)

    print(f"[Viewer] Preparing clean .blend from USD: {usd_path.name} (LOD: {args.lod})...")
    create_blend_from_usd(blender_path, usd_path, output_blend, args.asset, args.lod)

    print(f"[Viewer] Launching Blender GUI for: {output_blend.name}")
    print("Tip: Change viewport shading to 'Material Preview' (top right sphere icon) to see textures.")
    cmd = [
        str(blender_path),
        str(output_blend),
    ]
    subprocess.Popen(cmd)


if __name__ == "__main__":
    main()
