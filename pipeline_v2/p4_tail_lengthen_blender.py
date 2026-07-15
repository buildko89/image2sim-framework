"""P4-尻尾: 尻尾を伸ばす（ボーンポーズのYスケール → Apply as Rest Pose）。

P2 のカールと同じ機構。頂点は一切触らず、尻尾ボーン5本（bone016〜020）を
ポーズでローカル Y（骨方向）に length_scale 倍し、それをレストに焼き込む。
メッシュ（皮膚・プルームカード・TailFill・毛シェル）はスキニングで追従する。
アニメの回転キーはレスト長に依存しないので、リターゲット済みキーはそのまま生きる。

要点:
  - 罠⑯: 焼き込み前に reset_pose（アクション解除 + 全ボーンのポーズ消去）。
    やらないと割り当たっていたアクションの第1フレームまでレストに焼かれる。
  - 罠⑤: Apply as Rest Pose の前に、**Armature モディファイアを持つ全メッシュ**に
    モディファイアの複製を適用して形状を確定させる（p2 は体メッシュ1つだったが、
    今は FurShell×4 / TailFill×2 / Whiskers も追従させる必要がある）。
  - 尻尾ボーンの inherit_scale を一時的に NONE にして、スケールの累積
    （1.3^n で先端ほど伸びる）を防ぐ。焼き込み後に元へ戻す。
  - 焼き込み後に鎖の全長を実測し、期待値（元×scale）から 1% 超ずれたら失敗させる。

  blender --background --python pipeline_v2/p4_tail_lengthen_blender.py -- \
    --input output_v2/base/p3_koha9face.blend \
    --output-blend output_v2/base/p3_koha9face.blend \
    --output-glb output_v2/base/p3_koha9face.glb \
    --length-scale 1.3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

TAIL_BONES = [f"bone{i:03d}" for i in range(16, 21)]
BODY_LEN = 0.35  # 鼻先→尾根元。P0 仕様の基準長


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--length-scale", type=float, default=1.3)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def chain_length(arm) -> float:
    amw = arm.matrix_world
    total = 0.0
    for n in TAIL_BONES:
        b = arm.data.bones[n]
        total += ((amw @ b.tail_local) - (amw @ b.head_local)).length
    return total


def reset_pose(arm) -> int:
    """罠⑯: アクションを外し、全ボーンのポーズを単位化する。"""
    if arm.animation_data:
        arm.animation_data.action = None
    n = 0
    for pb in arm.pose.bones:
        if pb.matrix_basis != Matrix.Identity(4):
            n += 1
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return n


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    amw = arm.matrix_world
    meshes = [o for o in bpy.context.scene.objects
              if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
    print(f"[P4l] scale={a.length_scale}  追従メッシュ: {[m.name for m in meshes]}")

    cleared = reset_pose(arm)
    print(f"[P4l] レスト前にポーズを消去: 非単位だったボーン {cleared} 本")

    len_before = chain_length(arm)
    tip_before = amw @ arm.data.bones[TAIL_BONES[-1]].tail_local

    # スケールの累積を防ぐ（子は親の Y スケールを継承すると 1.3^n になる）
    old_inherit = {}
    for n in TAIL_BONES:
        old_inherit[n] = arm.data.bones[n].inherit_scale
        arm.data.bones[n].inherit_scale = "NONE"

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    for n in TAIL_BONES:
        arm.pose.bones[n].scale = (1.0, a.length_scale, 1.0)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    # ポーズ時点の先端位置で伸びを事前検証
    pb = arm.pose.bones[TAIL_BONES[-1]]
    posed_tip = amw @ pb.matrix @ pb.bone.tail.copy()
    posed_len_est = (posed_tip - (amw @ arm.data.bones[TAIL_BONES[0]].head_local)).length
    print(f"[P4l] 先端(ポーズ): {tuple(round(v,4) for v in tip_before)} -> {tuple(round(v,4) for v in posed_tip)}")

    # 罠⑤: 全メッシュに Armature モディファイアの複製を適用して形状を確定
    for mesh in meshes:
        bpy.ops.object.select_all(action="DESELECT")
        mesh.select_set(True)
        bpy.context.view_layer.objects.active = mesh
        armmod = next(m for m in mesh.modifiers if m.type == "ARMATURE")
        bpy.ops.object.modifier_copy(modifier=armmod.name)
        copy_name = next(m.name for m in mesh.modifiers
                         if m.type == "ARMATURE" and m.name != armmod.name)
        bpy.ops.object.modifier_apply(modifier=copy_name)

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    for n, v in old_inherit.items():
        arm.data.bones[n].inherit_scale = v

    len_after = chain_length(arm)
    tip_after = amw @ arm.data.bones[TAIL_BONES[-1]].tail_local
    expect = len_before * a.length_scale
    print(f"[P4l] 鎖の全長: {len_before:.4f} -> {len_after:.4f} m (期待 {expect:.4f})"
          f"  {len_after/BODY_LEN:.3f}×体長")
    print(f"[P4l] 先端(レスト): Z {tip_before.z:.4f} -> {tip_after.z:.4f}"
          f"  立ち上がり {(tip_after.z - (amw @ arm.data.bones[TAIL_BONES[0]].head_local).z)/BODY_LEN:.3f}×体長")
    if abs(len_after - expect) > 0.01 * expect:
        raise SystemExit(f"[P4l] FAIL: 鎖の全長が期待値から 1% 超ずれた ({len_after:.4f} vs {expect:.4f})")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
