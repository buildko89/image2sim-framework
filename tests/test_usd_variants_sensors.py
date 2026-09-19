"""
tests/test_usd_variants_sensors.py

OpenUSD VariantSets & センサー・BOM 統合 (Phase 3) の pytest 自動テスト。
ドローンおよび猫モデルの VariantSets 切り替え、センサー Prim、BOM 属性を検証する。
"""

from __future__ import annotations

from pathlib import Path
import pytest
from pxr import Usd, UsdGeom, UsdPhysics

REPO_ROOT = Path(__file__).resolve().parents[1]
DRONE_USD_DIR = REPO_ROOT / "output" / "drone2_parametric" / "usd"
CAT_USD_DIR = REPO_ROOT / "output_v2" / "usd"


def test_drone_variantset_propeller_guard():
    """ドローンの PropellerGuard VariantSet 切り替え検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    assert assembly_file.is_file()

    stage = Usd.Stage.Open(str(assembly_file))
    root_prim = stage.GetPrimAtPath("/Drone_Root")
    assert root_prim.IsValid()

    vset = root_prim.GetVariantSet("PropellerGuard")
    assert vset.IsValid(), "VariantSet 'PropellerGuard' not found on /Drone_Root"
    assert set(vset.GetVariantNames()) == {"equipped", "none"}

    # 1. 既定値 (equipped) -> Guards は Active
    assert vset.GetVariantSelection() == "equipped"
    guards_prim = stage.GetPrimAtPath("/Drone_Root/Guards")
    assert guards_prim.IsValid()
    assert guards_prim.IsActive() is True

    # 2. none に切り替え -> Guards は Inactive
    vset.SetVariantSelection("none")
    guards_prim = stage.GetPrimAtPath("/Drone_Root/Guards")
    assert guards_prim.IsValid()
    assert guards_prim.IsActive() is False

    # 3. equipped に復帰 -> Guards は Active
    vset.SetVariantSelection("equipped")
    guards_prim = stage.GetPrimAtPath("/Drone_Root/Guards")
    assert guards_prim.IsValid()
    assert guards_prim.IsActive() is True


def test_drone_variantset_battery():
    """ドローンの Battery VariantSet 切り替え検証 (質量・BOM属性)"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    stage = Usd.Stage.Open(str(assembly_file))
    root_prim = stage.GetPrimAtPath("/Drone_Root")
    battery_prim = stage.GetPrimAtPath("/Drone_Root/Battery")
    assert battery_prim.IsValid(), "/Drone_Root/Battery not found"

    vset = root_prim.GetVariantSet("Battery")
    assert vset.IsValid(), "VariantSet 'Battery' not found on /Drone_Root"
    assert set(vset.GetVariantNames()) == {"1S_300mAh", "2S_450mAh"}

    # 1. 既定値 (1S_300mAh)
    assert vset.GetVariantSelection() == "1S_300mAh"
    mass_api = UsdPhysics.MassAPI(battery_prim)
    assert mass_api
    assert pytest.approx(mass_api.GetMassAttr().Get(), abs=1e-4) == 0.0085
    assert battery_prim.GetAttribute("drone:part_number").Get() == "BT20-1S-300"
    assert battery_prim.GetAttribute("drone:capacity_mah").Get() == 300

    # 2. 2S_450mAh に切り替え
    vset.SetVariantSelection("2S_450mAh")
    assert pytest.approx(mass_api.GetMassAttr().Get(), abs=1e-4) == 0.0130
    assert battery_prim.GetAttribute("drone:part_number").Get() == "LIPO-2S-450"
    assert battery_prim.GetAttribute("drone:capacity_mah").Get() == 450

    # 3. 1S_300mAh に復帰
    vset.SetVariantSelection("1S_300mAh")
    assert pytest.approx(mass_api.GetMassAttr().Get(), abs=1e-4) == 0.0085


def test_drone_sensors_and_bom():
    """ドローンの FPV カメラ、IMU センサー Prim および BOM 属性検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    stage = Usd.Stage.Open(str(assembly_file))

    # 1. FPV カメラ
    cam_prim = stage.GetPrimAtPath("/Drone_Root/Sensors/FrontFPVCamera")
    assert cam_prim.IsValid(), "FrontFPVCamera prim not found"
    cam = UsdGeom.Camera(cam_prim)
    assert cam
    assert pytest.approx(cam.GetFocalLengthAttr().Get(), abs=1e-3) == 2.1
    assert pytest.approx(cam.GetHorizontalApertureAttr().Get(), abs=1e-3) == 3.6
    assert pytest.approx(cam.GetVerticalApertureAttr().Get(), abs=1e-3) == 2.7
    clip = cam.GetClippingRangeAttr().Get()
    assert pytest.approx(clip[0], abs=1e-3) == 0.01
    assert pytest.approx(clip[1], abs=1e-3) == 1000.0

    # 2. IMU センサー
    imu_prim = stage.GetPrimAtPath("/Drone_Root/Sensors/IMU")
    assert imu_prim.IsValid(), "IMU prim not found"
    assert imu_prim.GetAttribute("sensor:type").Get() == "6axis_gyro_accel"
    assert pytest.approx(imu_prim.GetAttribute("sensor:rate_hz").Get(), abs=1e-1) == 1000.0

    # 3. BOM メタデータ
    root_prim = stage.GetPrimAtPath("/Drone_Root")
    assert root_prim.GetAttribute("drone:model").Get() == "drone2_petron_s"
    assert root_prim.GetAttribute("drone:vendor").Get() == "Byrobot"
    assert root_prim.GetAttribute("drone:version").Get() == "1.0"

    frame_prim = stage.GetPrimAtPath("/Drone_Root/Frame")
    assert frame_prim.GetAttribute("drone:part_number").Get() == "FRM-PETRON-01"
    assert frame_prim.GetAttribute("drone:material").Get() == "CarbonFiber_Polycarbonate"

    guards_prim = stage.GetPrimAtPath("/Drone_Root/Guards")
    assert guards_prim.GetAttribute("drone:part_number").Get() == "GRD-PETRON-01"
    assert guards_prim.GetAttribute("drone:supplier").Get() == "BetaFPV"

    rotor_fl = stage.GetPrimAtPath("/Drone_Root/Rotor_FL")
    assert rotor_fl.GetAttribute("drone:part_number").Get() == "MTR-0820-BRUSHED"


def test_cat_variantsets():
    """猫モデルの LOD および CoatColor VariantSet 切り替え検証"""
    root_file = CAT_USD_DIR / "root_cat.usda"
    assert root_file.is_file()

    stage = Usd.Stage.Open(str(root_file))
    root_prim = stage.GetPrimAtPath("/KohaCat")
    assert root_prim.IsValid()

    # 1. LOD VariantSet
    vset_lod = root_prim.GetVariantSet("LOD")
    assert vset_lod.IsValid(), "VariantSet 'LOD' not found on /KohaCat"
    assert set(vset_lod.GetVariantNames()) == {"Full_Groom", "Simple_Mesh"}

    # 既定値 (Full_Groom) -> Groom は Active
    assert vset_lod.GetVariantSelection() == "Full_Groom"
    groom_prim = stage.GetPrimAtPath("/KohaCat/Groom")
    assert groom_prim.IsValid()
    assert groom_prim.IsActive() is True

    # Simple_Mesh に切り替え -> Groom は Inactive
    vset_lod.SetVariantSelection("Simple_Mesh")
    groom_prim = stage.GetPrimAtPath("/KohaCat/Groom")
    assert groom_prim.IsValid()
    assert groom_prim.IsActive() is False

    # Full_Groom に復帰
    vset_lod.SetVariantSelection("Full_Groom")
    assert stage.GetPrimAtPath("/KohaCat/Groom").IsActive() is True

    # 2. CoatColor VariantSet
    vset_coat = root_prim.GetVariantSet("CoatColor")
    assert vset_coat.IsValid(), "VariantSet 'CoatColor' not found on /KohaCat"
    assert set(vset_coat.GetVariantNames()) == {"Koha_Calico", "Brown_Tabby", "White"}

    # 既定値 (Koha_Calico)
    assert vset_coat.GetVariantSelection() == "Koha_Calico"
    assert root_prim.GetAttribute("cat:coat_style").Get() == "Calico_TriColor"

    # Brown_Tabby に切り替え
    vset_coat.SetVariantSelection("Brown_Tabby")
    assert root_prim.GetAttribute("cat:coat_style").Get() == "Brown_Tabby_Striped"

    # White に切り替え
    vset_coat.SetVariantSelection("White")
    assert root_prim.GetAttribute("cat:coat_style").Get() == "Solid_White"

    # 復帰
    vset_coat.SetVariantSelection("Koha_Calico")
    assert root_prim.GetAttribute("cat:coat_style").Get() == "Calico_TriColor"
