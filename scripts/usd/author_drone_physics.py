"""
scripts/usd/author_drone_physics.py

ドローンの OpenUSD マスターアセンブリ (drone_assembly.usda) に対し、
YAML 設定に基づいて USD Physics スキーマ (pxr.UsdPhysics) を自動付与するスクリプト。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import yaml
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE = REPO_ROOT / "output" / "drone2_parametric" / "usd" / "drone_assembly.usda"
DEFAULT_CONFIG = REPO_ROOT / "config" / "drone2_model.yaml"


def load_yaml_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def setup_drone_physics(stage_path: Path | str, config_path_or_dict: Path | str | dict[str, Any]) -> bool:
    """
    指定された USD ステージに対し、YAML 設定に基づいて USD Physics をオーサリングする。
    """
    stage_path = Path(stage_path)
    if not stage_path.is_file():
        raise FileNotFoundError(f"USD stage not found: {stage_path}")

    if isinstance(config_path_or_dict, (str, Path)):
        config = load_yaml_config(Path(config_path_or_dict))
    else:
        config = config_path_or_dict

    physics_cfg = config.get("physics", {})
    if not physics_cfg.get("enabled", True):
        print("[USD Physics] Physics is disabled in config, skipping.")
        return False

    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {stage_path}")

    root_prim = stage.GetPrimAtPath("/Drone_Root")
    if not root_prim.IsValid():
        raise RuntimeError(f"Root prim /Drone_Root not found in {stage_path}")

    # 1. PhysicsScene の定義
    scene_cfg = physics_cfg.get("scene", {})
    scene_path = "/Drone_Root/PhysicsScene"
    scene = UsdPhysics.Scene.Define(stage, scene_path)
    gravity_mag = float(scene_cfg.get("gravity_magnitude", 9.81))
    gravity_dir = scene_cfg.get("gravity_direction", [0.0, -1.0, 0.0])
    scene.CreateGravityMagnitudeAttr(gravity_mag)
    scene.CreateGravityDirectionAttr(Gf.Vec3f(*gravity_dir))
    print(f"[USD Physics] Authored PhysicsScene at {scene_path} (gravity: {gravity_mag} m/s^2, dir: {gravity_dir})")

    # 2. 機体全体の剛体化 (RigidBodyAPI)
    rigid_body = UsdPhysics.RigidBodyAPI.Apply(root_prim)
    rigid_body.CreateRigidBodyEnabledAttr(True)
    print(f"[USD Physics] Applied RigidBodyAPI to {root_prim.GetPath()}")

    # 3. 質量・重心・慣性テンソルの設定 (MassAPI)
    mass_api = UsdPhysics.MassAPI.Apply(root_prim)
    mass_g = float(physics_cfg.get("mass_g", 48.5) or 48.5)
    mass_kg = mass_g / 1000.0
    mass_api.CreateMassAttr(mass_kg)

    # 重心座標変換: Blender (x, y, z) -> USD Y-up (x, z, -y)
    com_mm = physics_cfg.get("center_of_mass_mm", [0.0, 0.0, 3.5])
    com_usd = Gf.Vec3f(
        float(com_mm[0]) / 1000.0,
        float(com_mm[2]) / 1000.0,
        -float(com_mm[1]) / 1000.0,
    )
    mass_api.CreateCenterOfMassAttr(com_usd)

    # 慣性モーメント変換: Blender (ixx, iyy, izz) -> USD Y-up (ixx, izz, iyy)
    inertia_cfg = physics_cfg.get("inertia_kg_m2", {})
    if isinstance(inertia_cfg, dict) and "ixx" in inertia_cfg:
        ixx = float(inertia_cfg.get("ixx", 2.1e-5))
        iyy = float(inertia_cfg.get("iyy", 2.3e-5))
        izz = float(inertia_cfg.get("izz", 3.8e-5))
        inertia_usd = Gf.Vec3f(ixx, izz, iyy)
        mass_api.CreateDiagonalInertiaAttr(inertia_usd)

    print(f"[USD Physics] Applied MassAPI to {root_prim.GetPath()} (mass: {mass_kg} kg, CoM: {com_usd})")

    # 4. 各ローターへの回転ジョイント設定 (RevoluteJoint)
    rotors_cfg = physics_cfg.get("rotors", {})
    prop_directions = config.get("propeller", {}).get("directions", {
        "fl": "ccw", "fr": "cw", "rl": "cw", "rr": "ccw"
    })
    max_rpm = float(rotors_cfg.get("max_rpm", 35000.0))
    axis = str(rotors_cfg.get("axis", "Z"))

    for rotor_id in ["fl", "fr", "rl", "rr"]:
        rotor_prim_name = f"Rotor_{rotor_id.upper()}"
        joint_path = f"/Drone_Root/{rotor_prim_name}/RevoluteJoint_{rotor_id.upper()}"
        motor_path = f"/Drone_Root/{rotor_prim_name}/{rotor_prim_name}/drone_root/rotor_{rotor_id}/motor_{rotor_id}"
        prop_path = f"/Drone_Root/{rotor_prim_name}/{rotor_prim_name}/drone_root/rotor_{rotor_id}/rotor_{rotor_id}_spin"

        joint = UsdPhysics.RevoluteJoint.Define(stage, joint_path)
        joint.CreateBody0Rel().SetTargets([Sdf.Path(motor_path)])
        joint.CreateBody1Rel().SetTargets([Sdf.Path(prop_path)])
        joint.CreateAxisAttr(axis)

        # カスタム属性 (RPM, 回転方向)
        direction = prop_directions.get(rotor_id, "ccw")
        joint.GetPrim().CreateAttribute("drone:max_rpm", Sdf.ValueTypeNames.Double).Set(max_rpm)
        joint.GetPrim().CreateAttribute("drone:spin_direction", Sdf.ValueTypeNames.String).Set(direction)

        print(f"[USD Physics] Created RevoluteJoint at {joint_path} (axis: {axis}, dir: {direction}, max_rpm: {max_rpm})")

    # 5. 衝突判定 (CollisionAPI & MeshCollisionAPI) の適用
    collision_prims = [
        "/Drone_Root/Collision",
        "/Drone_Root/Guards",
        "/Drone_Root/LandingGear",
        "/Drone_Root/Frame",
    ]
    approx = physics_cfg.get("collision", {}).get("default_approximation", "convexHull")

    for cpath in collision_prims:
        cprim = stage.GetPrimAtPath(cpath)
        if cprim.IsValid():
            col_api = UsdPhysics.CollisionAPI.Apply(cprim)
            col_api.CreateCollisionEnabledAttr(True)
            mesh_col_api = UsdPhysics.MeshCollisionAPI.Apply(cprim)
            mesh_col_api.CreateApproximationAttr(approx)
            print(f"[USD Physics] Applied CollisionAPI & MeshCollisionAPI to {cpath} (approx: {approx})")

    stage.GetRootLayer().Save()
    print(f"[USD Physics] Successfully saved physics authoring to {stage_path}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Author USD Physics schemas to drone master assembly.")
    parser.add_argument("--stage", default=str(DEFAULT_STAGE), help="Path to drone_assembly.usda")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to drone YAML config")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_drone_physics(Path(args.stage), Path(args.config))


if __name__ == "__main__":
    main()
