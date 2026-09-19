"""
tests/test_usd_export.py

OpenUSD エクスポート基盤 (Phase 1) の pytest 自動テスト。
ドローンおよび猫モデルの USD ステージ、Prim パス、Reference、マテリアル設定を検証する。
"""

from __future__ import annotations

from pathlib import Path
import pytest
from pxr import Usd, UsdGeom, UsdShade

REPO_ROOT = Path(__file__).resolve().parents[1]
DRONE_USD_DIR = REPO_ROOT / "output" / "drone2_parametric" / "usd"
CAT_USD_DIR = REPO_ROOT / "output_v2" / "usd"


def test_drone_usd_assembly():
    """ドローンマスターアセンブリ (drone_assembly.usda) の構造・参照検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    assert assembly_file.is_file(), f"drone_assembly.usda not found at {assembly_file}"

    stage = Usd.Stage.Open(str(assembly_file))
    assert stage, "Failed to open drone_assembly.usda"

    # メタデータ検証
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0

    # ルート Prim 検証
    root_prim = stage.GetDefaultPrim()
    assert root_prim.IsValid()
    assert root_prim.GetPath().pathString == "/Drone_Root"

    # 各コンポーネント Prim の存在検証
    expected_components = [
        "/Drone_Root/Frame",
        "/Drone_Root/Guards",
        "/Drone_Root/LandingGear",
        "/Drone_Root/Rotor_FL",
        "/Drone_Root/Rotor_FR",
        "/Drone_Root/Rotor_RL",
        "/Drone_Root/Rotor_RR",
        "/Drone_Root/Collision",
    ]
    for path in expected_components:
        prim = stage.GetPrimAtPath(path)
        assert prim.IsValid(), f"Expected component prim not found: {path}"
        assert prim.HasAuthoredReferences(), f"Prim {path} should have authored references"


def test_cat_usd_root():
    """猫モデルマスターステージ (root_cat.usda) の構造・参照検証"""
    root_file = CAT_USD_DIR / "root_cat.usda"
    assert root_file.is_file(), f"root_cat.usda not found at {root_file}"

    stage = Usd.Stage.Open(str(root_file))
    assert stage, "Failed to open root_cat.usda"

    # メタデータ検証
    assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.y
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0

    # ルート Prim 検証
    root_prim = stage.GetDefaultPrim()
    assert root_prim.IsValid()
    assert root_prim.GetPath().pathString == "/KohaCat"

    # レイヤー Prim 検証
    for path in ["/KohaCat/Skeleton", "/KohaCat/Geometry", "/KohaCat/Groom"]:
        prim = stage.GetPrimAtPath(path)
        assert prim.IsValid(), f"Expected cat component prim not found: {path}"
        assert prim.HasAuthoredReferences(), f"Prim {path} should have authored references"


def test_cat_fur_shell_materials():
    """毛シェル (fur_shells.usdc) の UsdPreviewSurface および opacityThreshold 検証"""
    groom_file = CAT_USD_DIR / "fur_shells.usdc"
    assert groom_file.is_file(), f"fur_shells.usdc not found at {groom_file}"

    stage = Usd.Stage.Open(str(groom_file))
    assert stage, "Failed to open fur_shells.usdc"

    expected_thresholds = {
        "FurShell1": 0.0,
        "FurShell2": 0.32,
        "FurShell3": 0.52,
        "FurShell4": 0.70,
        "Whiskers": 0.0,
    }

    for mat_name, expected_val in expected_thresholds.items():
        shader_path = f"/KohaCat/Groom/_materials/{mat_name}/Principled_BSDF"
        prim = stage.GetPrimAtPath(shader_path)
        assert prim.IsValid(), f"Shader prim not found: {shader_path}"

        shader = UsdShade.Shader(prim)
        thresh_input = shader.GetInput("opacityThreshold")
        assert thresh_input, f"opacityThreshold input missing on {shader_path}"
        assert pytest.approx(thresh_input.Get(), abs=1e-3) == expected_val
