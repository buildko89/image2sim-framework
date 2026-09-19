"""
tests/test_usd_pipeline_phase4.py

OpenUSD マルチエンジン自動ビルド & パイプライン完全統合 (Phase 4) の pytest 自動テスト。
派生 GLB (Godot 4.x 向け) の後方互換性、USDZ パッケージの完全性、およびエクスポートポリシーを検証する。
"""

from __future__ import annotations

from pathlib import Path
import zipfile
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DRONE_USDZ = REPO_ROOT / "output" / "drone2_parametric" / "usd" / "drone2_simready.usdz"
DRONE_GLB = REPO_ROOT / "output" / "godot" / "drone2_derived.glb"
CAT_USDZ = REPO_ROOT / "output_v2" / "usd" / "cat_simready.usdz"
CAT_GLB = REPO_ROOT / "output_v2" / "godot" / "cat_derived.glb"
POLICY_FILE = REPO_ROOT / "docs" / "game_engine_export_policy.md"


def test_export_policy_document():
    """game_engine_export_policy.md が USD SSoT ポリシーに改定されているか検証"""
    assert POLICY_FILE.is_file(), f"Policy file not found: {POLICY_FILE}"
    content = POLICY_FILE.read_text(encoding="utf-8")
    assert "Single Source of Truth: OpenUSD" in content
    assert "最適化 GLB" in content
    assert "Godot 4.x" in content
    assert "NVIDIA Omniverse" in content


def test_drone_derived_glb():
    """ドローンの Godot 向け派生 GLB (drone2_derived.glb) の後方互換・バイナリ検証"""
    assert DRONE_GLB.is_file(), f"Derived GLB not found: {DRONE_GLB}"
    size = DRONE_GLB.stat().st_size
    assert size > 100_000, f"Derived GLB size unexpectedly small: {size} bytes"

    # glTF 2.0 バイナリヘッダの検証 (magic: 0x46546C67 = b"glTF", version: 2)
    with DRONE_GLB.open("rb") as f:
        magic = f.read(4)
        assert magic == b"glTF", f"Invalid glTF magic: {magic}"
        version = int.from_bytes(f.read(4), byteorder="little")
        assert version == 2, f"Expected glTF version 2, got {version}"


def test_cat_derived_glb():
    """猫モデルの Godot 向け派生 GLB (cat_derived.glb) の後方互換・バイナリ検証"""
    assert CAT_GLB.is_file(), f"Derived GLB not found: {CAT_GLB}"
    size = CAT_GLB.stat().st_size
    assert size > 5_000_000, f"Derived GLB size unexpectedly small: {size} bytes"

    with CAT_GLB.open("rb") as f:
        magic = f.read(4)
        assert magic == b"glTF", f"Invalid glTF magic: {magic}"
        version = int.from_bytes(f.read(4), byteorder="little")
        assert version == 2, f"Expected glTF version 2, got {version}"


def test_drone_usdz_package():
    """ドローンの Omniverse/Isaac Sim 向け自己完結型 USDZ パッケージ検証"""
    assert DRONE_USDZ.is_file(), f"USDZ package not found: {DRONE_USDZ}"
    assert DRONE_USDZ.stat().st_size > 50_000

    with zipfile.ZipFile(DRONE_USDZ, "r") as z:
        names = z.namelist()
        assert "drone_assembly.usda" in names or any(n.endswith(".usda") for n in names)
        # 参照されるコンポーネントが含まれているか
        assert any("drone_frame" in n for n in names)
        assert any("drone_rotor" in n for n in names)


def test_cat_usdz_package():
    """猫モデルの Omniverse/Isaac Sim 向け自己完結型 USDZ パッケージ検証"""
    assert CAT_USDZ.is_file(), f"USDZ package not found: {CAT_USDZ}"
    assert CAT_USDZ.stat().st_size > 5_000_000

    with zipfile.ZipFile(CAT_USDZ, "r") as z:
        names = z.namelist()
        assert any(n.endswith(".usda") for n in names)
        # テクスチャが含まれているか
        assert any("textures" in n or ".png" in n for n in names)
