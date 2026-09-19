"""
scripts/usd/author_cat_physics.py

猫モデル (root_cat.usda) に対し、USD Physics スキーマ (pxr.UsdPhysics) による
物理補助（尻尾チェーンジョイント、足裏・胴体コライダ、物理シーン）を付与するスクリプト。
"""

from __future__ import annotations

import argparse
from pathlib import Path
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CAT_STAGE = REPO_ROOT / "output_v2" / "usd" / "root_cat.usda"


def setup_cat_physics(stage_path: Path | str) -> bool:
    """
    指定された猫モデル USD ステージに対し、USD Physics をオーサリングする。
    """
    stage_path = Path(stage_path)
    if not stage_path.is_file():
        raise FileNotFoundError(f"USD stage not found: {stage_path}")

    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        raise RuntimeError(f"Failed to open USD stage: {stage_path}")

    root_prim = stage.GetPrimAtPath("/KohaCat")
    if not root_prim.IsValid():
        raise RuntimeError(f"Root prim /KohaCat not found in {stage_path}")

    # 1. PhysicsScene の定義
    scene_path = "/KohaCat/PhysicsScene"
    scene = UsdPhysics.Scene.Define(stage, scene_path)
    scene.CreateGravityMagnitudeAttr(9.81)
    scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, -1.0, 0.0))
    print(f"[USD Physics] Authored PhysicsScene at {scene_path}")

    # 2. 物理補助用 Xform の作成
    physics_root_path = "/KohaCat/Physics"
    UsdGeom.Xform.Define(stage, physics_root_path)

    # 3. 尻尾のチェーンジョイント (Tail Revolute Joints)
    # bone016 -> bone017 -> bone018 -> bone019 -> bone020
    tail_segments = ["bone016", "bone017", "bone018", "bone019", "bone020"]
    for i in range(len(tail_segments) - 1):
        joint_path = f"{physics_root_path}/TailJoint_{i}"
        joint = UsdPhysics.RevoluteJoint.Define(stage, joint_path)
        joint.CreateAxisAttr("X")  # 主なしなり軸
        # 自由回転、またはバネダンパ
        joint.GetPrim().CreateAttribute("physics:jointEnabled", Sdf.ValueTypeNames.Bool).Set(True)
        print(f"[USD Physics] Created Tail RevoluteJoint at {joint_path} (segment {tail_segments[i]} -> {tail_segments[i+1]})")

    # 4. 足裏コライダ (Paw Colliders)
    # 猫の4足位置に接触球コライダを配置
    paw_positions = {
        "Paw_FL": Gf.Vec3f(0.045, 0.02, 0.12),
        "Paw_FR": Gf.Vec3f(-0.045, 0.02, 0.12),
        "Paw_RL": Gf.Vec3f(0.05, 0.02, -0.12),
        "Paw_RR": Gf.Vec3f(-0.05, 0.02, -0.12),
    }

    for paw_name, pos in paw_positions.items():
        paw_path = f"{physics_root_path}/Colliders/{paw_name}"
        sphere = UsdGeom.Sphere.Define(stage, paw_path)
        sphere.CreateRadiusAttr(0.025)  # 半径 25mm
        sphere.AddTranslateOp().Set(pos)

        col_api = UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())
        col_api.CreateCollisionEnabledAttr(True)
        print(f"[USD Physics] Created Paw Collider at {paw_path} (pos: {pos}, r=25mm)")

    # 5. 胴体コライダ (Body Mesh Collision)
    body_path = "/KohaCat/Geometry/Geometry/Armature/Koha9/Koha9/Koha9Body"
    body_prim = stage.GetPrimAtPath(body_path)
    if body_prim.IsValid():
        b_col = UsdPhysics.CollisionAPI.Apply(body_prim)
        b_col.CreateCollisionEnabledAttr(True)
        b_mesh = UsdPhysics.MeshCollisionAPI.Apply(body_prim)
        b_mesh.CreateApproximationAttr("convexHull")
        print(f"[USD Physics] Applied CollisionAPI & MeshCollisionAPI to {body_path}")

    stage.GetRootLayer().Save()
    print(f"[USD Physics] Successfully saved cat physics authoring to {stage_path}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Author USD Physics schemas to Koha cat master stage.")
    parser.add_argument("--stage", default=str(DEFAULT_CAT_STAGE), help="Path to root_cat.usda")
    return parser.parse_args()


def main():
    args = parse_args()
    setup_cat_physics(Path(args.stage))


if __name__ == "__main__":
    main()
