"""
pipeline_v2/run_usd_build.py

OpenUSD をマスター（Single Source of Truth）とし、
全ターゲット（Omniverse/Isaac Sim, Unreal/Unity, Godot 4.x）向けの
SimReady USD アセットおよび最適化派生 GLB をワンコマンドで一括生成する CI/CD ランナー。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path
from pxr import Sdf, UsdUtils

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")

# 入力・出力パス定義
DRONE_CONFIG = REPO_ROOT / "config" / "drone2_model.yaml"
DRONE_BLEND = REPO_ROOT / "output" / "drone2_parametric" / "drone2.blend"
DRONE_USD_DIR = REPO_ROOT / "output" / "drone2_parametric" / "usd"
DRONE_ASSEMBLY = DRONE_USD_DIR / "drone_assembly.usda"
DRONE_USDZ = DRONE_USD_DIR / "drone2_simready.usdz"
DRONE_DERIVED_GLB = REPO_ROOT / "output" / "godot" / "drone2_derived.glb"

CAT_BLEND = REPO_ROOT / "output_v2" / "base" / "p3_koha9face.blend"
CAT_USD_DIR = REPO_ROOT / "output_v2" / "usd"
CAT_ROOT_USD = CAT_USD_DIR / "root_cat.usda"
CAT_USDZ = CAT_USD_DIR / "cat_simready.usdz"
CAT_DERIVED_GLB = REPO_ROOT / "output_v2" / "godot" / "cat_derived.glb"


def run_command(cmd: list[str], desc: str) -> None:
    print(f"\n[CI/CD Build] >>> {desc}")
    print(f"[CI/CD Build] Command: {' '.join(cmd)}")
    t0 = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True)
    dt = time.perf_counter() - t0

    if res.stdout:
        print(res.stdout.strip())
    if res.stderr:
        print(res.stderr.strip(), file=sys.stderr)

    if res.returncode != 0:
        raise RuntimeError(f"Step failed ({desc}) with returncode {res.returncode}")
    print(f"[CI/CD Build] Step completed in {dt:.2f}s")


def package_usdz(input_stage: Path, output_usdz: Path, desc: str) -> None:
    """pxr.UsdUtils を用いて自己完結型 .usdz パッケージを生成する"""
    print(f"\n[CI/CD Build] >>> Packaging USDZ: {desc}")
    t0 = time.perf_counter()
    output_usdz.parent.mkdir(parents=True, exist_ok=True)
    if output_usdz.exists():
        output_usdz.unlink()

    success = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(input_stage)), str(output_usdz))
    dt = time.perf_counter() - t0
    if not success or not output_usdz.is_file():
        raise RuntimeError(f"Failed to create USDZ package: {output_usdz}")
    print(f"[CI/CD Build] Successfully packaged USDZ ({output_usdz.stat().st_size / 1024:.1f} KB) in {dt:.2f}s -> {output_usdz}")


def export_derived_glb(usd_stage: Path, output_glb: Path, blender_path: Path, desc: str) -> None:
    """Blender 経由で USD ステージから Godot 向け派生 GLB を出力する"""
    converter_script = REPO_ROOT / "scripts" / "usd" / "export_derived_glb_blender.py"
    cmd = [
        str(blender_path),
        "--background",
        "--python-exit-code",
        "1",
        "--python",
        str(converter_script),
        "--",
        "--usd-stage",
        str(usd_stage),
        "--output-glb",
        str(output_glb),
    ]
    run_command(cmd, f"Export derived GLB for {desc}")


def build_drone(blender_path: Path, target: str, skip_blender: bool = False) -> None:
    """ドローンアセットの USD マスター構築および派生出力"""
    print("\n=======================================================")
    print("  BUILDING DRONE ASSET (drone2_petron_s)")
    print("=======================================================")

    # 1. Blender からの USD レイヤーエクスポート & Physics / Variants 付与
    if not skip_blender:
        runner_script = REPO_ROOT / "scripts" / "usd" / "export_drone_usd.py"
        cmd = [
            sys.executable,
            str(runner_script),
            "--blend",
            str(DRONE_BLEND),
            "--blender",
            str(blender_path),
            "--output-dir",
            str(DRONE_USD_DIR),
            "--config",
            str(DRONE_CONFIG),
        ]
        run_command(cmd, "Drone USD Export & Physics/Variants Authoring")

    # 2. Omniverse / Isaac Sim 向け USDZ パッケージ生成
    if target in ["all", "omniverse"]:
        package_usdz(DRONE_ASSEMBLY, DRONE_USDZ, "Drone (drone2_simready.usdz)")

    # 3. Godot 4.x 向け派生 GLB 生成
    if target in ["all", "godot"]:
        export_derived_glb(DRONE_ASSEMBLY, DRONE_DERIVED_GLB, blender_path, "Drone (drone2_derived.glb)")


def build_cat(blender_path: Path, target: str, skip_blender: bool = False) -> None:
    """猫アセットの USD マスター構築および派生出力"""
    print("\n=======================================================")
    print("  BUILDING CAT ASSET (Koha Calico Cat)")
    print("=======================================================")

    # 1. Blender からの USD レイヤーエクスポート & Physics / Variants 付与
    if not skip_blender:
        runner_script = REPO_ROOT / "scripts" / "usd" / "export_cat_usd.py"
        cmd = [
            sys.executable,
            str(runner_script),
            "--blend",
            str(CAT_BLEND),
            "--blender",
            str(blender_path),
            "--output-dir",
            str(CAT_USD_DIR),
        ]
        run_command(cmd, "Cat USD Export & Physics/Variants Authoring")

    # 2. Omniverse / Isaac Sim 向け USDZ パッケージ生成
    if target in ["all", "omniverse"]:
        package_usdz(CAT_ROOT_USD, CAT_USDZ, "Cat (cat_simready.usdz)")

    # 3. Godot 4.x 向け派生 GLB 生成
    if target in ["all", "godot"]:
        export_derived_glb(CAT_ROOT_USD, CAT_DERIVED_GLB, blender_path, "Cat (cat_derived.glb)")


def parse_args():
    parser = argparse.ArgumentParser(description="Multi-engine USD Build & Distribution Pipeline.")
    parser.add_argument("--asset", choices=["all", "drone", "cat"], default="all", help="Target asset to build.")
    parser.add_argument("--target", choices=["all", "omniverse", "godot", "unity", "unreal"], default="all", help="Target engine / distribution format.")
    parser.add_argument("--blender", default=str(DEFAULT_BLENDER), help="Path to Blender 5.2 executable.")
    parser.add_argument("--skip-blender", action="store_true", help="Skip Blender export and run packaging/derivation only.")
    return parser.parse_args()


def main():
    args = parse_args()
    blender_path = Path(args.blender).resolve()
    t_start = time.perf_counter()

    print("=======================================================")
    print("  image2sim-framework: Multi-Engine USD Build Pipeline")
    print(f"  Asset : {args.asset}")
    print(f"  Target: {args.target}")
    print("=======================================================")

    if args.asset in ["all", "drone"]:
        build_drone(blender_path, args.target, skip_blender=args.skip_blender)

    if args.asset in ["all", "cat"]:
        build_cat(blender_path, args.target, skip_blender=args.skip_blender)

    total_time = time.perf_counter() - t_start
    print("\n=======================================================")
    print(f"  BUILD SUCCESSFUL! Total Time: {total_time:.2f}s")
    print("=======================================================")


if __name__ == "__main__":
    main()
