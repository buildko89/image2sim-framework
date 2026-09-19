"""
scripts/usd/export_drone_usd_blender.py

Blender 5.2 LTS 内で動作し、ドローンの .blend ファイルから各コンポーネントを
個別の USD レイヤーとしてエクスポートし、マスターアセンブリ drone_assembly.usda を
pxr (または USD コンポジション) を使って合成するスクリプト。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
import bpy
from pxr import Usd, UsdGeom, Sdf


def parse_args():
    # blender --background <blend_file> --python export_drone_usd_blender.py -- <args>
    raw_args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description="Export Drone to OpenUSD layers and assembly.")
    parser.add_argument("--output-dir", required=True, help="Directory to save USD files.")
    parser.add_argument("--root-prim-name", default="Drone_Root", help="Root prim name.")
    return parser.parse_args(raw_args)


def export_collection_to_usd(collection_name: str, filepath: Path, root_prim_path: str):
    """指定したコレクションのオブジェクトのみを USD としてエクスポートする"""
    if collection_name not in bpy.data.collections:
        print(f"[USD Export] Collection not found: {collection_name}, skipping.")
        return False

    col = bpy.data.collections[collection_name]
    if not col.objects:
        print(f"[USD Export] Collection is empty: {collection_name}, skipping.")
        return False

    # 全オブジェクトの選択解除
    bpy.ops.object.select_all(action="DESELECT")

    # 対象コレクションのオブジェクトを選択
    for obj in col.objects:
        obj.select_set(True)

    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Blender 5.2 の usd_export を実行
    bpy.ops.wm.usd_export(
        filepath=str(filepath),
        selected_objects_only=True,
        export_materials=True,
        generate_preview_surface=True,
        convert_orientation=True,  # Z-Up -> Y-Up 整合
        export_uvmaps=True,
        export_normals=True,
        export_custom_properties=True,
        root_prim_path=root_prim_path,
        relative_paths=True,
    )
    print(f"[USD Export] Exported {collection_name} -> {filepath}")
    return True


def export_objects_to_usd(objects: list[bpy.types.Object], filepath: Path, root_prim_path: str):
    """指定したオブジェクトリストを USD としてエクスポートする"""
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
        convert_orientation=True,
        export_uvmaps=True,
        export_normals=True,
        export_custom_properties=True,
        root_prim_path=root_prim_path,
        relative_paths=True,
    )
    print(f"[USD Export] Exported {len(objects)} objects -> {filepath}")
    return True


def compose_drone_assembly(output_dir: Path, root_prim_name: str, component_files: dict[str, Path]):
    """
    pxr を使用して各部品レイヤーを参照 (Reference) するマスターステージ drone_assembly.usda を合成する。
    """
    assembly_path = output_dir / "drone_assembly.usda"
    if assembly_path.exists():
        assembly_path.unlink()

    stage = Usd.Stage.CreateNew(str(assembly_path))
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    root_path = f"/{root_prim_name}"
    root_prim = UsdGeom.Xform.Define(stage, root_path).GetPrim()
    stage.SetDefaultPrim(root_prim)

    # 各コンポーネントを子 Prim またはルートに対する Reference として追加
    for comp_name, file_path in component_files.items():
        rel_path = f"./{file_path.name}"
        comp_prim_path = f"{root_path}/{comp_name}"
        comp_prim = UsdGeom.Xform.Define(stage, comp_prim_path).GetPrim()
        comp_prim.GetReferences().AddReference(assetPath=rel_path)
        print(f"[USD Compose] Referenced {rel_path} under {comp_prim_path}")

    stage.GetRootLayer().Save()
    print(f"[USD Compose] Successfully created master assembly: {assembly_path}")
    return assembly_path


def main():
    args = parse_args()
    out_dir = Path(args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    root_name = args.root_prim_name

    # 1. コンポーネントごとのエクスポート定義
    # - Frame (Body + Arms)
    # - Guards
    # - LandingGear
    # - Rotors (Motor + Propellers)
    # - Collisions (Collision primitives)
    components = {}

    # Frame: VIS_BODY + VIS_ARMS
    frame_objs = []
    for col_name in ["VIS_BODY", "VIS_ARMS", "VIS_STRUCTURE"]:
        if col_name in bpy.data.collections:
            frame_objs.extend(bpy.data.collections[col_name].objects)
    if frame_objs:
        frame_file = out_dir / "drone_frame.usdc"
        if export_objects_to_usd(frame_objs, frame_file, f"/{root_name}/Frame"):
            components["Frame"] = frame_file

    # Guards
    if "VIS_GUARDS" in bpy.data.collections and bpy.data.collections["VIS_GUARDS"].objects:
        guard_file = out_dir / "drone_guards.usdc"
        if export_collection_to_usd("VIS_GUARDS", guard_file, f"/{root_name}/Guards"):
            components["Guards"] = guard_file

    # Landing Gear
    if "VIS_LANDING_GEAR" in bpy.data.collections and bpy.data.collections["VIS_LANDING_GEAR"].objects:
        landing_file = out_dir / "drone_landing_gear.usdc"
        if export_collection_to_usd("VIS_LANDING_GEAR", landing_file, f"/{root_name}/LandingGear"):
            components["LandingGear"] = landing_file

    # Rotors: 各ローターごとにエクスポート (fl, fr, rl, rr)
    for rotor_id in ["fl", "fr", "rl", "rr"]:
        col_name = f"VIS_ROTOR_{rotor_id}"
        if col_name in bpy.data.collections and bpy.data.collections[col_name].objects:
            rotor_file = out_dir / f"drone_rotor_{rotor_id}.usdc"
            if export_collection_to_usd(col_name, rotor_file, f"/{root_name}/Rotor_{rotor_id.upper()}"):
                components[f"Rotor_{rotor_id.upper()}"] = rotor_file

    # Collisions
    col_objs = []
    for col_name in ["COLLISION_BODY", "COLLISION_STRUCTURE", "COLLISION_LANDING_GEAR"]:
        if col_name in bpy.data.collections:
            col_objs.extend(bpy.data.collections[col_name].objects)
    if col_objs:
        col_file = out_dir / "drone_collision.usdc"
        if export_objects_to_usd(col_objs, col_file, f"/{root_name}/Collision"):
            components["Collision"] = col_file

    # 2. マスターアセンブリステージの合成
    compose_drone_assembly(out_dir, root_name, components)


if __name__ == "__main__":
    main()
