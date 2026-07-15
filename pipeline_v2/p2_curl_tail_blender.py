"""P2: 尻尾をボーンのポーズで巻き上げ、Apply as Rest Pose でレストに焼く。

B-6 は尻尾メッシュの頂点を155°の累積カーブで直接曲げた（`curl_tail_mesh`）。
その結果、背面から見るとトゲ状に破綻した（`png/test/back.png`）。
ここでは頂点を一切触らず、**尻尾ボーンを回してポーズを作り、それをレストにする**。
メッシュはスキニングで自動的に追従する。

実行位置: 束縛（P1-A）の後、アニメーションのリターゲット（b6b）の前。
b6b は「尻尾の元キーはカール済みレストへの相対適用が正しい」前提で書かれているため、
この順番でなければならない。

回転軸: 尻尾ボーンは roll のせいでローカル Z がほぼワールド -X を向く。軸を決め打ちせず、
ワールド X 軸（左右軸）まわりの回転をボーンのレスト基底に共役変換して適用する。
符号は実測で決める（先端が下がったら反転してやり直す）。

角度の決め方: `input/raw_photos/横.png` にグリッドを重ねて尻尾の各区間の傾きを読むと、
**根元から先端までほぼ 65〜78°（水平から）で、ほぼ直線**だった。バナナ状には曲がらない。
累積角を配分する方式（B-6 の 155° 累積カール）だと根元が寝て先端が前へ行き過ぎる。
そこで「各ボーンの最終的な水平からの角度」が写真と一致するよう、ボーンごとの
デルタ角を直接指定する。レスト角は bone016 から順に -11°, -23.5°, -22.4°, -24.4°, -6.8°。

  blender --background --python pipeline_v2/p2_curl_tail_blender.py -- \
    --input output_v2/base/p2_bind.blend --output output_v2/base/p2_curled.blend \
    --report output_v2/reports/p2_curl_tail.json --bone-deg 81,12,0,2,-10
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

TAIL_BONES = [f"bone{i:03d}" for i in range(16, 21)]
# ボーンごとのデルタ角（度）。根元をほぼ全部曲げ、以降は軸をまっすぐ保ち、
# 先端だけ少し戻して写真のプルームの反りに合わせる。
DEFAULT_BONE_DEG = [81.0, 12.0, 0.0, 2.0, -10.0]
# 目標: 各ボーンの最終角（水平から）が 70° 前後、先端のみ 78° 前後。
TARGET_DEG = 70.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--bone-deg", default=",".join(str(v) for v in DEFAULT_BONE_DEG),
                   help="尻尾ボーン5本のデルタ角をカンマ区切りで")
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    a = p.parse_args(argv)
    a.bone_deg = [float(v) for v in a.bone_deg.split(",")]
    if len(a.bone_deg) != len(TAIL_BONES):
        raise SystemExit(f"--bone-deg は {len(TAIL_BONES)} 個必要")
    return a


def tail_tip(arm: bpy.types.Object) -> Vector:
    return arm.matrix_world @ arm.data.bones[TAIL_BONES[-1]].tail_local


def posed_tip(arm: bpy.types.Object) -> Vector:
    bpy.context.view_layer.update()
    pb = arm.pose.bones[TAIL_BONES[-1]]
    return arm.matrix_world @ pb.matrix @ Vector((0.0, pb.bone.length, 0.0))


def apply_curl(arm: bpy.types.Object, bone_deg: list[float], sign: float) -> None:
    """各尻尾ボーンに、ワールドX軸まわり delta_i の回転をレスト基底で与える。"""
    bpy.ops.object.mode_set(mode="POSE")
    for name, deg in zip(TAIL_BONES, bone_deg):
        pb = arm.pose.bones[name]
        pb.rotation_mode = "QUATERNION"
        world_rot = Matrix.Rotation(math.radians(deg) * sign, 3, "X")
        rest = pb.bone.matrix_local.to_3x3()          # アーマチュア空間でのボーン基底
        basis = rest.inverted() @ world_rot @ rest    # 共役変換してボーン基底へ
        pb.rotation_quaternion = basis.to_quaternion()
    bpy.ops.object.mode_set(mode="OBJECT")


def bone_elevations(arm: bpy.types.Object, posed: bool) -> list[float]:
    """各尻尾ボーンの、水平（YZ平面での Y 軸）からの仰角（度）。"""
    out = []
    for n in TAIL_BONES:
        if posed:
            pb = arm.pose.bones[n]
            d = (arm.matrix_world.to_3x3() @ pb.matrix.to_3x3()).col[1]
        else:
            b = arm.data.bones[n]
            d = (arm.matrix_world @ b.tail_local) - (arm.matrix_world @ b.head_local)
        out.append(round(math.degrees(math.atan2(d.z, abs(d.y))), 1))
    return out


def clear_pose(arm: bpy.types.Object) -> None:
    bpy.ops.object.mode_set(mode="POSE")
    for name in TAIL_BONES:
        arm.pose.bones[name].rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_pose_to_rest(mesh: bpy.types.Object, arm: bpy.types.Object) -> None:
    """メッシュに現ポーズを焼き込み、アーマチュアの現ポーズをレストにする。

    Armature モディファイアの複製を1つ適用してメッシュ形状を確定させてから
    pose.armature_apply する。これをやらないとメッシュだけ元に戻る。
    """
    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    bpy.context.view_layer.objects.active = mesh
    armmod = next(m for m in mesh.modifiers if m.type == "ARMATURE")
    bpy.ops.object.modifier_copy(modifier=armmod.name)
    copy_name = next(m.name for m in mesh.modifiers if m.name != armmod.name and m.type == "ARMATURE")
    bpy.ops.object.modifier_apply(modifier=copy_name)

    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode="OBJECT")


def reset_pose(arm: bpy.types.Object) -> int:
    """全ボーンのポーズを消し、アクションを外す。

    **これをやらないと、尻尾カールと一緒に「たまたま割り当たっていたアクションの
    第1フレームのポーズ」までレストに焼き込まれる。** 実測: スケルトンの blend には
    `Armature|Walkback` が割り当たったままで、101 本中 94 本のボーンが非単位ポーズを持ち、
    `bip01_head` は約 30° 回っていた。そのため焼き込み後のレストで頭が傾き、
    鼻が中心から +9mm ずれていた（配色.pdf p5 の「鼻の位置が右にずれている」の原因）。
    """
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
    mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")

    cleared = reset_pose(arm)
    print(f"[P2] レスト前にポーズを消去: 非単位だったボーン {cleared} 本"
          f"（アクションの第1フレームがレストに焼かれるのを防ぐ）")

    bpy.context.view_layer.objects.active = arm
    root = arm.matrix_world @ arm.data.bones[TAIL_BONES[0]].head_local
    before = tail_tip(arm)
    back_top = max((mesh.matrix_world @ v.co).z for v in mesh.data.vertices)
    rest_elev = bone_elevations(arm, posed=False)

    # 符号を実測で決める: +1 で先端が上がるか試し、下がったら反転
    apply_curl(arm, a.bone_deg, +1.0)
    tip_pos = posed_tip(arm)
    sign = 1.0
    if tip_pos.z < before.z:
        clear_pose(arm)
        apply_curl(arm, a.bone_deg, -1.0)
        tip_pos = posed_tip(arm)
        sign = -1.0
    if tip_pos.z <= before.z:
        raise RuntimeError("どちらの符号でも先端が上がらない。軸の想定が誤っている。")

    posed_elev = bone_elevations(arm, posed=True)
    print(f"[P2] curl sign={sign:+.0f} bone_deg={a.bone_deg}")
    print(f"[P2] 仰角(度) レスト: {rest_elev}")
    print(f"[P2] 仰角(度) カール後: {posed_elev}   (写真の目標: 根元〜先端 65〜78°)")
    print(f"[P2] 尻尾先端 Z: {before.z:.4f} -> {tip_pos.z:.4f}  (尾根元 Z={root.z:.4f}, 背 Z={back_top:.4f})")

    bake_pose_to_rest(mesh, arm)

    after = tail_tip(arm)
    rise = after.z - root.z
    body_len = 0.35  # 鼻先→尾根元。P0 仕様の基準長
    print(f"[P2] 焼き込み後の先端: {tuple(round(v,4) for v in after)}")
    print(f"[P2] 立ち上がり = {rise:.4f} m = 体長の {rise/body_len:.3f}（P0 仕様の目標 0.45）")

    out = Path(a.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print(f"  Saved: {out}")

    rep = Path(a.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps({
        "task": "P2: curl tail via bone pose + Apply as Rest Pose",
        "method": "頂点は一切触らない。ボーンを回してレストに焼き、メッシュはスキニングで追従。",
        "bone_deg": a.bone_deg,
        "sign": sign,
        "elevation_rest_deg": rest_elev,
        "elevation_curled_deg": posed_elev,
        "elevation_target_deg": "根元〜先端 65〜78（横.png の実測）",
        "tail_root_z": round(root.z, 4),
        "tip_z_before": round(before.z, 4),
        "tip_z_after": round(after.z, 4),
        "rise_over_body_length": round(rise / body_len, 3),
        "spec_target": 0.45,
        "back_top_z": round(back_top, 4),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
