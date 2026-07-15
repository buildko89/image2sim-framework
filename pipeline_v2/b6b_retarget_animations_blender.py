"""B-6b: Retarget Animations to Fitted Skeleton (Blender CLI script)

B-6 でボーンのレスト方向を大きく変えた（koha9 体型へのワープ + 尻尾カール）ため、
元の回転キーをそのまま再生するとメッシュが爆発する。また Copy Rotation 制約による
絶対回転コピーも不正（レスト方向が違うので絶対姿勢では形が崩れる）。

正しい方式 = ワールド差分リターゲット:
  ΔR(bone, frame) = R_src_pose_world @ R_src_rest_world⁻¹
  R_tgt_pose_world = ΔR @ R_tgt_rest_world
を全フレーム解析的にFK計算し、rotation_quaternion キーとしてベイクする。
位置キーは作らない（全ボーンが新レスト位置に留まり、全アニメが in-place になる）。
尻尾ボーン (bone016-020) はカールしたレストへの相対適用が正しいので、
元アクションの回転キーをそのままコピーする。

使用方法:
  blender --background --python pipeline_v2/b6b_retarget_animations_blender.py -- \
    --input output_v2/base/cat_koha.blend \
    --source output_v2/base/cat_koha9.blend \
    --output-blend output_v2/base/cat_koha.blend \
    --output-glb output_v2/base/cat_koha.glb \
    --report output_v2/reports/b6b_retarget_animations.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

TAIL_BONES = [f"bone{i:03d}" for i in range(16, 21)]

# リターゲット対象: デフォームボーン（尻尾以外）+ その祖先チェーン
ANCESTOR_BONES = ["RL_BoneRoot", "Snow_leopard_Idle", "CC_Base_Pivot", "Armature", "bip01"]
DEFORM_BONES = (
    ["bip01_pelvis", "bip01_spine", "bip01_spine1", "bip01_spine2",
     "bip01_neck", "bip01_neck1", "bip01_head",
     "bone005", "bone007", "bone014", "bone015"]
    + [f"bip01_{s}_{p}" for s in ("l", "r")
       for p in ("clavicle", "upperarm", "forearm", "hand", "thigh", "calf", "horselink", "foot")]
)
RETARGET_BONES = ANCESTOR_BONES + DEFORM_BONES

# 回転差分の減衰係数。ヒョウの長い脚用の大きな振り角を短足にそのまま適用すると
# 足先がメッシュの脚ボリュームを大きく越えて裂けるため、脚ほど強く減衰する。
#
# 前脚は 0.7 → 0.55 に強めた（P1 の脚ボーン再配置後）。Jump のヒョウの前脚は大きくたたみ込むが、
# 寸胴で短い前脚と厚い胸ではその折り目を受け止めきれず、脇の下が裂ける
# （破綻辺 0.50%、閾値 0.5%。基準線の cat_base は 0.13%）。平滑化を 18 回まで上げても
# 0.501% で頭打ちだった。
DAMP_FACTORS = {}
for _s in ("l", "r"):
    for _p, _f in (("clavicle", 0.70), ("upperarm", 0.55), ("forearm", 0.55),
                   ("hand", 0.40), ("thigh", 0.70), ("calf", 0.70),
                   ("horselink", 0.50), ("foot", 0.50)):
        DAMP_FACTORS[f"bip01_{_s}_{_p}"] = _f


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Retarget leopard animations onto the fitted skeleton.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--report", required=True)
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


def get_fcurves(action: bpy.types.Action):
    """Blender 5.0 のスロット式アクション対応。旧 `action.fcurves` 相当を返す。"""
    if hasattr(action, "fcurves"):
        return action.fcurves
    layer = action.layers[0]
    strip = layer.strips[0]
    slot = action.slots[0]
    return strip.channelbag(slot, ensure=True).fcurves


def append_source_armature(blend_path: str) -> bpy.types.Object:
    before = set(bpy.data.objects)
    with bpy.data.libraries.load(blend_path) as (src, dst):
        dst.objects = [n for n in src.objects]
    src_arm = None
    for obj in set(bpy.data.objects) - before:
        if obj is None:
            continue
        if obj.type == "ARMATURE" and src_arm is None:
            src_arm = obj
            bpy.context.scene.collection.objects.link(obj)
        else:
            bpy.data.objects.remove(obj, do_unlink=True)
    if src_arm is None:
        raise RuntimeError("Source armature not found in " + blend_path)
    src_arm.name = "Armature_RetargetSrc"
    if src_arm.animation_data is None:
        src_arm.animation_data_create()
    return src_arm


def topo_sort(names: list[str], arm: bpy.types.Object) -> list[str]:
    """親→子の順に並べる（対象セット内の親のみ考慮。祖先は全て対象セットに含まれる前提）"""
    name_set = set(names)
    result: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        bone = arm.data.bones[name]
        if bone.parent and bone.parent.name in name_set:
            visit(bone.parent.name)
        visited.add(name)
        result.append(name)

    for n in names:
        visit(n)
    return result


def copy_tail_fcurves(src_action: bpy.types.Action, dst_action: bpy.types.Action, tail_set: set[str]) -> int:
    dst_fcurves = get_fcurves(dst_action)
    copied = 0
    for fc in get_fcurves(src_action):
        if not fc.data_path.startswith('pose.bones["'):
            continue
        bone_name = fc.data_path.split('"')[1]
        if bone_name not in tail_set or "rotation" not in fc.data_path:
            continue
        nfc = dst_fcurves.new(fc.data_path, index=fc.array_index)
        nfc.keyframe_points.add(len(fc.keyframe_points))
        for i, kp in enumerate(fc.keyframe_points):
            nkp = nfc.keyframe_points[i]
            nkp.co = kp.co
            nkp.interpolation = kp.interpolation
        nfc.update()
        copied += 1
    return copied


def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.input)

    new_arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    if new_arm.animation_data is None:
        new_arm.animation_data_create()

    # 高速化: リターゲット中はメッシュのアーマチュア変形を無効化
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    mod.show_viewport = False
                    mod.show_render = False

    original_actions = list(bpy.data.actions)
    print(f"[B-6b] actions to retarget: {[a.name for a in original_actions]}")

    src_arm = append_source_armature(args.source)

    order = topo_sort(RETARGET_BONES, new_arm)
    tail_set = set(TAIL_BONES)
    parent_of = {n: (new_arm.data.bones[n].parent.name if new_arm.data.bones[n].parent else None) for n in order}

    # レスト行列（アーマチュア空間）。両アーマチュアはオブジェクト変換が同一なので
    # アーマチュア空間の差分回転はワールド空間の差分回転と等価。
    rest_tgt = {n: new_arm.data.bones[n].matrix_local.copy() for n in order}
    rest_src = {n: src_arm.data.bones[n].matrix_local.copy() for n in order}
    rest_src_inv = {n: m.inverted() for n, m in rest_src.items()}
    rest_offset = {
        n: (rest_tgt[parent_of[n]].inverted() @ rest_tgt[n]) if parent_of[n] in rest_tgt else None
        for n in order
    }

    scene = bpy.context.scene
    baked_pairs = []
    for action in original_actions:
        src_arm.animation_data.action = action
        start, end = (int(action.frame_range[0]), int(action.frame_range[1]))

        new_action = bpy.data.actions.new(action.name + "_retarget")
        new_arm.animation_data.action = new_action

        prev_quat: dict[str, Quaternion] = {}
        for f in range(start, end + 1):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            src_ev = src_arm.evaluated_get(dg)
            src_pose = {n: src_ev.pose.bones[n].matrix.copy() for n in order}

            pose_mat: dict[str, Matrix] = {}
            identity_q = Quaternion()
            for n in order:
                delta = (src_pose[n] @ rest_src_inv[n]).to_quaternion()
                damp = DAMP_FACTORS.get(n, 1.0)
                if damp < 1.0:
                    delta = identity_q.slerp(delta, damp)
                r_des = (delta.to_matrix().to_4x4() @ rest_tgt[n]).to_quaternion()
                parent = parent_of[n]
                if parent in pose_mat:
                    m_ref = pose_mat[parent] @ rest_offset[n]
                    t = m_ref.to_translation()
                else:
                    m_ref = rest_tgt[n]
                    t = rest_tgt[n].to_translation()
                m_pose = Matrix.LocRotScale(t, r_des, Vector((1.0, 1.0, 1.0)))
                pose_mat[n] = m_pose

                basis = m_ref.inverted() @ m_pose
                q = basis.to_quaternion()
                if n in prev_quat and q.dot(prev_quat[n]) < 0.0:
                    q.negate()
                prev_quat[n] = q.copy()

                pb = new_arm.pose.bones[n]
                pb.rotation_mode = "QUATERNION"
                pb.rotation_quaternion = q
                pb.keyframe_insert("rotation_quaternion", frame=f)

        copied_tail = copy_tail_fcurves(action, new_action, tail_set)
        baked_pairs.append({"source": action.name, "baked": new_action.name,
                            "frames": [start, end], "tail_fcurves": copied_tail})
        print(f"[B-6b] baked {action.name} ({start}-{end}), tail fcurves: {copied_tail}")

    # 元スケルトン・元アクションを削除し、ベイク版を元の名前へ
    bpy.data.objects.remove(src_arm, do_unlink=True)
    expected = []
    for action in original_actions:
        name = action.name
        bpy.data.actions.remove(action)
        baked = bpy.data.actions[name + "_retarget"]
        baked.name = name
        expected.append(name)
    for action in list(bpy.data.actions):
        if action.name not in expected:
            bpy.data.actions.remove(action)
    # ユーザーゼロのアクションは blend 保存時に消えるため fake user を立てる
    for action in bpy.data.actions:
        action.use_fake_user = True
    new_arm.animation_data.action = None

    # アーマチュア変形を戻す
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    mod.show_viewport = True
                    mod.show_render = True

    out_blend = Path(args.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    out_glb = Path(args.output_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format="GLB",
        use_selection=True,
        export_animation_mode="ACTIONS",
    )
    print(f"  Exported: {out_glb}")

    report = {
        "task": "B-6b: Retarget Animations (world-delta rotation)",
        "retargeted_bones": len(order),
        "baked_actions": baked_pairs,
        "notes": [
            "World-delta retarget: R_tgt = (R_src_pose @ R_src_rest^-1) @ R_tgt_rest, analytic FK per frame.",
            "Rotation-only bake: all animations are now in-place (Jump root motion removed).",
            "Tail bones keep original delta rotations applied to the curled rest pose.",
        ],
        "final_actions": [a.name for a in bpy.data.actions],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
