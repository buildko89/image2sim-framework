"""
scripts/usd/author_drone_variants_sensors.py

ドローンの OpenUSD マスターアセンブリ (drone_assembly.usda) に対し、
VariantSets (PropellerGuard, Battery) およびセンサー Prim (Camera, IMU)・
BOM (部品表メタデータ) をオーサリングするスクリプト。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE = REPO_ROOT / "output" / "drone2_parametric" / "usd" / "drone_assembly.usda"


def setup_drone_variants_and_sensors(stage_path: Path | str) -> bool:
    stage_path = Path(stage_path)
    if not stage_path.is_file():
        raise FileNotFoundError(f"USD stage not found: {stage_path}")

    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {stage_path}")

    root_prim = stage.GetPrimAtPath("/Drone_Root")
    if not root_prim.IsValid():
        raise RuntimeError(f"Root prim /Drone_Root not found in {stage_path}")

    # 1. BOM メタデータの付与
    root_prim.CreateAttribute("drone:model", Sdf.ValueTypeNames.String).Set("drone2_petron_s")
    root_prim.CreateAttribute("drone:vendor", Sdf.ValueTypeNames.String).Set("Byrobot")
    root_prim.CreateAttribute("drone:version", Sdf.ValueTypeNames.String).Set("1.0")

    frame_prim = stage.GetPrimAtPath("/Drone_Root/Frame")
    if frame_prim.IsValid():
        frame_prim.CreateAttribute("drone:part_number", Sdf.ValueTypeNames.String).Set("FRM-PETRON-01")
        frame_prim.CreateAttribute("drone:material", Sdf.ValueTypeNames.String).Set("CarbonFiber_Polycarbonate")

    guards_prim = stage.GetPrimAtPath("/Drone_Root/Guards")
    if guards_prim.IsValid():
        guards_prim.CreateAttribute("drone:part_number", Sdf.ValueTypeNames.String).Set("GRD-PETRON-01")
        guards_prim.CreateAttribute("drone:supplier", Sdf.ValueTypeNames.String).Set("BetaFPV")

    for rotor_id in ["FL", "FR", "RL", "RR"]:
        rotor_prim = stage.GetPrimAtPath(f"/Drone_Root/Rotor_{rotor_id}")
        if rotor_prim.IsValid():
            rotor_prim.CreateAttribute("drone:part_number", Sdf.ValueTypeNames.String).Set("MTR-0820-BRUSHED")
            rotor_prim.CreateAttribute("drone:motor_type", Sdf.ValueTypeNames.String).Set("coreless_brushed")

    print("[USD Variants/Sensors] Authored BOM metadata to Drone components.")

    # 2. センサー Prim の配置
    sensors_xform = UsdGeom.Xform.Define(stage, "/Drone_Root/Sensors")

    # 2.1 FPV カメラ (UsdGeom.Camera)
    cam_path = "/Drone_Root/Sensors/FrontFPVCamera"
    cam = UsdGeom.Camera.Define(stage, cam_path)
    cam.CreateFocalLengthAttr(2.1)
    cam.CreateHorizontalApertureAttr(3.6)
    cam.CreateVerticalApertureAttr(2.7)
    cam.CreateClippingRangeAttr(Gf.Vec2f(0.01, 1000.0))
    cam.CreateProjectionAttr(UsdGeom.Tokens.perspective)
    # 機首前方上部に配置 (USD Y-Up)
    cam.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.015, -0.025))
    print(f"[USD Variants/Sensors] Authored FPV Camera at {cam_path}")

    # 2.2 IMU 慣性計測ノード
    imu_path = "/Drone_Root/Sensors/IMU"
    imu = UsdGeom.Xform.Define(stage, imu_path)
    imu.GetPrim().CreateAttribute("sensor:type", Sdf.ValueTypeNames.Token).Set("6axis_gyro_accel")
    imu.GetPrim().CreateAttribute("sensor:rate_hz", Sdf.ValueTypeNames.Double).Set(1000.0)
    imu.GetPrim().CreateAttribute("sensor:accel_noise_density", Sdf.ValueTypeNames.Double).Set(0.0001)
    imu.GetPrim().CreateAttribute("sensor:gyro_noise_density", Sdf.ValueTypeNames.Double).Set(0.00005)
    # 重心位置に配置
    imu.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0035, 0.0))
    print(f"[USD Variants/Sensors] Authored IMU sensor at {imu_path}")

    # 3. VariantSets の構築
    # 3.1 PropellerGuard VariantSet
    vset_guard = root_prim.GetVariantSets().AddVariantSet("PropellerGuard")
    vset_guard.AddVariant("equipped")
    vset_guard.AddVariant("none")

    vset_guard.SetVariantSelection("equipped")
    with vset_guard.GetVariantEditContext():
        if guards_prim.IsValid():
            guards_prim.SetActive(True)

    vset_guard.SetVariantSelection("none")
    with vset_guard.GetVariantEditContext():
        if guards_prim.IsValid():
            guards_prim.SetActive(False)

    # 既定値を equipped に設定
    vset_guard.SetVariantSelection("equipped")
    print("[USD Variants/Sensors] Configured VariantSet 'PropellerGuard' (equipped / none)")

    # 3.2 Battery VariantSet
    battery_path = "/Drone_Root/Battery"
    battery_prim = UsdGeom.Xform.Define(stage, battery_path).GetPrim()
    vset_battery = root_prim.GetVariantSets().AddVariantSet("Battery")
    vset_battery.AddVariant("1S_300mAh")
    vset_battery.AddVariant("2S_450mAh")

    vset_battery.SetVariantSelection("1S_300mAh")
    with vset_battery.GetVariantEditContext():
        b_mass = UsdPhysics.MassAPI.Apply(battery_prim)
        b_mass.CreateMassAttr(0.0085)  # 8.5g
        battery_prim.CreateAttribute("drone:part_number", Sdf.ValueTypeNames.String).Set("BT20-1S-300")
        battery_prim.CreateAttribute("drone:capacity_mah", Sdf.ValueTypeNames.Int).Set(300)

    vset_battery.SetVariantSelection("2S_450mAh")
    with vset_battery.GetVariantEditContext():
        b_mass = UsdPhysics.MassAPI.Apply(battery_prim)
        b_mass.CreateMassAttr(0.0130)  # 13.0g
        battery_prim.CreateAttribute("drone:part_number", Sdf.ValueTypeNames.String).Set("LIPO-2S-450")
        battery_prim.CreateAttribute("drone:capacity_mah", Sdf.ValueTypeNames.Int).Set(450)

    # 既定値を 1S_300mAh に設定
    vset_battery.SetVariantSelection("1S_300mAh")
    print("[USD Variants/Sensors] Configured VariantSet 'Battery' (1S_300mAh / 2S_450mAh)")

    stage.GetRootLayer().Save()
    print(f"[USD Variants/Sensors] Successfully saved variants and sensors to {stage_path}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Author VariantSets and Sensors to Drone USD.")
    parser.add_argument("--stage", default=str(DEFAULT_STAGE), help="Path to drone_assembly.usda")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_drone_variants_and_sensors(Path(args.stage))


if __name__ == "__main__":
    main()
