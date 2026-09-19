"""
scripts/usd/export_cat_usd_blender.py

Blender 5.2 LTS 内で動作し、猫モデル (p3_koha9face.blend 等) から各コンポーネント
(ジオメトリ、スケルトン、毛シェル4層・髭、マテリアル) を個別の USD レイヤーとしてエクスポートし、
マスターアセット root_cat.usda を pxr を使って合成するスクリプト。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import bpy
from pxr import Usd, UsdGeom, UsdShade, Sdf


def parse_args():
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Export Cat model to OpenUSD layers and master stage.")
    parser.add_argument("--output-dir", required=True, help="Directory to save USD files.")
    parser.add_argument("--root-prim-name", default="KohaCat", help="Root prim name.")
    return parser.parse_args(raw_args)


def export_objects(objects: list[bpy.types.Object], filepath: Path, root_prim_path: str, export_armatures: bool = True):
    """指定したオブジェクト群を USD としてエクスポートする"""
    if not objects:
        return False

    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.usd_export(
        filepath=str(filepath),
        selected_objects_only=True,
        export_materials=True,
        generate_preview_surface=True,
        convert_orientation=True,  # Z-Up -> Y-Up 整合
        export_uvmaps=True,
        export_normals=True,
        export_armatures=export_armatures,
        only_deform_bones=False,
        export_custom_properties=True,
        root_prim_path=root_prim_path,
        relative_paths=True,
    )
    print(f"[Cat USD Export] Exported {len(objects)} objects -> {filepath}")
    return True


def compose_cat_root(output_dir: Path, root_prim_name: str, component_files: dict[str, Path]):
    """
    pxr を使用して各パーツレイヤーを参照 (Reference) するマスターステージ root_cat.usda を合成する。
    """
    master_path = output_dir / "root_cat.usda"
    if master_path.exists():
        master_path.unlink()

    stage = Usd.Stage.CreateNew(str(master_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    root_path = f"/{root_prim_name}"
    root_prim = UsdGeom.Xform.Define(stage, root_path).GetPrim()
    stage.SetDefaultPrim(root_prim)

    # 1. スケルトンとベースジオメトリをルート Prim 配下に参照
    # SkelRoot または Xform 構造
    for comp_name, file_path in component_files.items():
        rel_path = f"./{file_path.name}"
        comp_prim_path = f"{root_path}/{comp_name}"
        comp_prim = UsdGeom.Xform.Define(stage, comp_prim_path).GetPrim()
        comp_prim.GetReferences().AddReference(assetPath=rel_path)
        print(f"[Cat USD Compose] Referenced {rel_path} under {comp_prim_path}")

    stage.GetRootLayer().Save()
    print(f"[Cat USD Compose] Successfully created master cat stage: {master_path}")
    return master_path


def main():
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    root_name = args.root_prim_name
    components = {}

    # 1. Skeleton (Armature)
    armatures = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if armatures:
        skel_file = out_dir / "skeleton.usdc"
        if export_objects(armatures, skel_file, f"/{root_name}/Skeleton", export_armatures=True):
            components["Skeleton"] = skel_file

    # 2. Base Geometry: Koha9, TailFillCore, TailFillMid
    base_geom_names = ["Koha9", "TailFillCore", "TailFillMid"]
    base_objs = [bpy.data.objects[name] for name in base_geom_names if name in bpy.data.objects]
    if base_objs:
        geom_file = out_dir / "geometry.usdc"
        if export_objects(base_objs, geom_file, f"/{root_name}/Geometry", export_armatures=False):
            components["Geometry"] = geom_file

    # 3. Fur Shells & Whiskers: FurShell1..4, Whiskers
    groom_names = ["FurShell1", "FurShell2", "FurShell3", "FurShell4", "Whiskers"]
    groom_objs = [bpy.data.objects[name] for name in groom_names if name in bpy.data.objects]
    if groom_objs:
        groom_file = out_dir / "fur_shells.usdc"
        if export_objects(groom_objs, groom_file, f"/{root_name}/Groom", export_armatures=False):
            components["Groom"] = groom_file
            # Shell Fur のアルファカットオフ (opacityThreshold) を pxr で正確にオーサリング
            tune_fur_shell_materials(groom_file, root_name)

    # 4. Master Stage の合成
    compose_cat_root(out_dir, root_name, components)


def tune_fur_shell_materials(groom_file: Path, root_name: str):
    """
    毛シェルの各層に適切な opacityThreshold を設定し、
    UsdPreviewSurface における段階的な毛束アルファカットオフを保証する。
    """
    threshold_map = {
        "FurShell1": 0.0,
        "FurShell2": 0.32,
        "FurShell3": 0.52,
        "FurShell4": 0.70,
        "Whiskers": 0.0,
    }
    stage = Usd.Stage.Open(str(groom_file))
    materials_scope = f"/{root_name}/Groom/_materials"
    for mat_name, threshold in threshold_map.items():
        shader_path = f"{materials_scope}/{mat_name}/Principled_BSDF"
        shader_prim = stage.GetPrimAtPath(shader_path)
        if shader_prim.IsValid():
            shader = UsdShade.Shader(shader_prim)
            thresh_input = shader.CreateInput("opacityThreshold", Sdf.ValueTypeNames.Float)
            thresh_input.Set(threshold)
            print(f"[Cat USD Material] Set {shader_path} opacityThreshold = {threshold}")

    stage.GetRootLayer().Save()


if __name__ == "__main__":
    main()
