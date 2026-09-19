"""
tests/test_usd_physics.py

OpenUSD USD Physics 実装 (Phase 2) の pytest 自動テスト。
ドローンおよび猫モデルの物理スキーマ (RigidBodyAPI, MassAPI, RevoluteJoint, CollisionAPI, Scene)
および YAML 設定との整合性を検証する。
"""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml
from pxr import Usd, UsdGeom, UsdPhysics

REPO_ROOT = Path(__file__).resolve().parents[1]
DRONE_USD_DIR = REPO_ROOT / "output" / "drone2_parametric" / "usd"
CAT_USD_DIR = REPO_ROOT / "output_v2" / "usd"
DRONE_CONFIG = REPO_ROOT / "config" / "drone2_model.yaml"


def test_drone_physics_scene():
    """ドローンステージの PhysicsScene 設定検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    assert assembly_file.is_file()

    stage = Usd.Stage.Open(str(assembly_file))
    scene_prim = stage.GetPrimAtPath("/Drone_Root/PhysicsScene")
    assert scene_prim.IsValid(), "PhysicsScene prim not found"

    scene = UsdPhysics.Scene(scene_prim)
    assert scene, "Failed to cast to UsdPhysics.Scene"

    mag = scene.GetGravityMagnitudeAttr().Get()
    assert pytest.approx(mag, abs=1e-3) == 9.81

    direction = scene.GetGravityDirectionAttr().Get()
    assert pytest.approx(direction[0], abs=1e-3) == 0.0
    assert pytest.approx(direction[1], abs=1e-3) == -1.0
    assert pytest.approx(direction[2], abs=1e-3) == 0.0


def test_drone_rigidbody_and_mass_api():
    """ドローンルートの RigidBodyAPI および MassAPI の属性値が YAML 設定と一致するか検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    assert assembly_file.is_file()
    assert DRONE_CONFIG.is_file()

    with DRONE_CONFIG.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    physics_cfg = config["physics"]
    stage = Usd.Stage.Open(str(assembly_file))
    root_prim = stage.GetPrimAtPath("/Drone_Root")
    assert root_prim.IsValid()

    # RigidBodyAPI
    rb = UsdPhysics.RigidBodyAPI(root_prim)
    assert rb, "RigidBodyAPI not applied to /Drone_Root"
    assert rb.GetRigidBodyEnabledAttr().Get() is True

    # MassAPI
    mass_api = UsdPhysics.MassAPI(root_prim)
    assert mass_api, "MassAPI not applied to /Drone_Root"

    expected_mass_kg = float(physics_cfg["mass_g"]) / 1000.0
    actual_mass = mass_api.GetMassAttr().Get()
    assert pytest.approx(actual_mass, abs=1e-4) == expected_mass_kg

    # 重心 (Blender Z-up -> USD Y-up: [x, z, -y] / 1000)
    com_mm = physics_cfg["center_of_mass_mm"]
    expected_com = (
        com_mm[0] / 1000.0,
        com_mm[2] / 1000.0,
        -com_mm[1] / 1000.0,
    )
    actual_com = mass_api.GetCenterOfMassAttr().Get()
    assert pytest.approx(actual_com[0], abs=1e-4) == expected_com[0]
    assert pytest.approx(actual_com[1], abs=1e-4) == expected_com[1]
    assert pytest.approx(actual_com[2], abs=1e-4) == expected_com[2]

    # 慣性テンソル (Blender [ixx, iyy, izz] -> USD [ixx, izz, iyy])
    inertia_cfg = physics_cfg["inertia_kg_m2"]
    expected_inertia = (
        inertia_cfg["ixx"],
        inertia_cfg["izz"],
        inertia_cfg["iyy"],
    )
    actual_inertia = mass_api.GetDiagonalInertiaAttr().Get()
    assert pytest.approx(actual_inertia[0], rel=1e-3) == expected_inertia[0]
    assert pytest.approx(actual_inertia[1], rel=1e-3) == expected_inertia[1]
    assert pytest.approx(actual_inertia[2], rel=1e-3) == expected_inertia[2]


def test_drone_revolute_joints():
    """各ローターの RevoluteJoint の body0/body1 ターゲットおよび回転軸・諸元検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    stage = Usd.Stage.Open(str(assembly_file))

    for rotor_id in ["fl", "fr", "rl", "rr"]:
        rotor_name = f"Rotor_{rotor_id.upper()}"
        joint_path = f"/Drone_Root/{rotor_name}/RevoluteJoint_{rotor_id.upper()}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        assert joint_prim.IsValid(), f"RevoluteJoint not found at {joint_path}"

        joint = UsdPhysics.RevoluteJoint(joint_prim)
        assert joint.GetAxisAttr().Get() == "Z"

        # body0 (motor)
        body0_targets = joint.GetBody0Rel().GetTargets()
        assert len(body0_targets) == 1
        body0_prim = stage.GetPrimAtPath(body0_targets[0])
        assert body0_prim.IsValid(), f"Joint body0 target {body0_targets[0]} is invalid"

        # body1 (propeller spin)
        body1_targets = joint.GetBody1Rel().GetTargets()
        assert len(body1_targets) == 1
        body1_prim = stage.GetPrimAtPath(body1_targets[0])
        assert body1_prim.IsValid(), f"Joint body1 target {body1_targets[0]} is invalid"

        # カスタム属性
        max_rpm_attr = joint_prim.GetAttribute("drone:max_rpm")
        assert max_rpm_attr.IsValid()
        assert max_rpm_attr.Get() == 35000.0

        spin_dir_attr = joint_prim.GetAttribute("drone:spin_direction")
        assert spin_dir_attr.IsValid()
        assert spin_dir_attr.Get() in ["cw", "ccw"]


def test_drone_collision_schemas():
    """ドローンの各コンポーネントに対する CollisionAPI & MeshCollisionAPI の検証"""
    assembly_file = DRONE_USD_DIR / "drone_assembly.usda"
    stage = Usd.Stage.Open(str(assembly_file))

    checked_prims = [
        "/Drone_Root/Collision",
        "/Drone_Root/Guards",
        "/Drone_Root/LandingGear",
        "/Drone_Root/Frame",
    ]
    for path in checked_prims:
        prim = stage.GetPrimAtPath(path)
        assert prim.IsValid(), f"Prim {path} not found"

        col_api = UsdPhysics.CollisionAPI(prim)
        assert col_api, f"CollisionAPI not applied to {path}"
        assert col_api.GetCollisionEnabledAttr().Get() is True

        mesh_col_api = UsdPhysics.MeshCollisionAPI(prim)
        assert mesh_col_api, f"MeshCollisionAPI not applied to {path}"
        assert mesh_col_api.GetApproximationAttr().Get() == "convexHull"


def test_cat_physics_authoring():
    """猫モデル (root_cat.usda) の物理補助 (PhysicsScene, TailJoints, Paw Colliders) 検証"""
    root_file = CAT_USD_DIR / "root_cat.usda"
    assert root_file.is_file()

    stage = Usd.Stage.Open(str(root_file))

    # PhysicsScene
    scene_prim = stage.GetPrimAtPath("/KohaCat/PhysicsScene")
    assert scene_prim.IsValid()
    scene = UsdPhysics.Scene(scene_prim)
    assert pytest.approx(scene.GetGravityMagnitudeAttr().Get(), abs=1e-3) == 9.81

    # 尻尾ジョイント (4セグメント)
    for i in range(4):
        joint_path = f"/KohaCat/Physics/TailJoint_{i}"
        joint_prim = stage.GetPrimAtPath(joint_path)
        assert joint_prim.IsValid(), f"Tail joint {joint_path} not found"
        joint = UsdPhysics.RevoluteJoint(joint_prim)
        assert joint.GetAxisAttr().Get() == "X"

    # 足裏コライダ (4足)
    paws = ["Paw_FL", "Paw_FR", "Paw_RL", "Paw_RR"]
    for paw in paws:
        paw_path = f"/KohaCat/Physics/Colliders/{paw}"
        paw_prim = stage.GetPrimAtPath(paw_path)
        assert paw_prim.IsValid(), f"Paw collider {paw_path} not found"

        sphere = UsdGeom.Sphere(paw_prim)
        assert pytest.approx(sphere.GetRadiusAttr().Get(), abs=1e-3) == 0.025

        col_api = UsdPhysics.CollisionAPI(paw_prim)
        assert col_api.GetCollisionEnabledAttr().Get() is True

    # 胴体コライダ
    body_path = "/KohaCat/Geometry/Geometry/Armature/Koha9/Koha9/Koha9Body"
    body_prim = stage.GetPrimAtPath(body_path)
    assert body_prim.IsValid()
    assert UsdPhysics.CollisionAPI(body_prim).GetCollisionEnabledAttr().Get() is True
    assert UsdPhysics.MeshCollisionAPI(body_prim).GetApproximationAttr().Get() == "convexHull"
