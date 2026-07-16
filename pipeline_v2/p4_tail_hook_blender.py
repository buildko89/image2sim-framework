"""P4-3: 指定アクションで尻尾の先端を前方へカールさせ「?」形にする（既存の揺れは残す）。

ユーザー要望（2026-07-15）: 歩行中に尻尾の先端を前へ曲げて「?」の形に。
尻尾は bone016(根元)〜020(先端)。根元〜中間(016-018)は立った幹のまま、先端(019/020)を
前方(頭側 -Y)へカールさせてフックを作る。各アクションのカーブは独立なので、Walk だけ編集
すれば他アニメに影響しない（bone020 も現状は全アニメでキー済みだが、編集対象は Walk のみ）。

方式: 各キーで既存ポーズにワールド X 回転を加算（頭の位置は保持=罠㉓ swing_inplace）。
立った尻尾(+Z)を +X 回りに回すと先端が -Y(前)へ倒れる。親→子の順に適用。

  blender --background --python pipeline_v2/p4_tail_hook_blender.py -- \
    --input ... --output-blend ... --output-glb ... \
    --action "Armature|Walk" --curl018 8 --curl019 32 --curl020 50
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--action", required=True)
    # 尻尾根元(016)〜先端(020)の各前方カール角(度, world X)。上半分を緩くアーチさせると
    # 開いた「?」になり、先端だけ強く巻くより読みやすい。
    p.add_argument("--curl016", type=float, default=0.0)
    p.add_argument("--curl017", type=float, default=20.0)
    p.add_argument("--curl018", type=float, default=30.0)
    p.add_argument("--curl019", type=float, default=34.0)
    p.add_argument("--curl020", type=float, default=28.0)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def action_fcurves(act):
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cbag in strip.channelbags:
                out.extend(cbag.fcurves)
    return out


def swing_inplace(pb, R) -> None:
    """頭(位置)を保って world 回転 R を姿勢に前掛け（非接続骨の吹き飛び防止・罠㉓）。"""
    loc = pb.matrix.to_translation()
    rot = (R.to_3x3() @ pb.matrix.to_3x3()).to_4x4()
    pb.matrix = Matrix.Translation(loc) @ rot


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    act = bpy.data.actions[a.action]
    arm.animation_data.action = act
    try:
        arm.animation_data.action_slot = act.slots[0]
    except Exception:
        pass

    curls = [("bone016", a.curl016), ("bone017", a.curl017), ("bone018", a.curl018),
             ("bone019", a.curl019), ("bone020", a.curl020)]
    curls = [(b, d) for b, d in curls if abs(d) > 1e-6]
    bones = [b for b, _ in curls]
    fcs = action_fcurves(act)

    # 編集対象ボーンの既存キー時刻（和集合、整数フレーム）
    times = set()
    for b in bones:
        dp = f'pose.bones["{b}"].rotation_quaternion'
        for fc in fcs:
            if fc.data_path == dp:
                for kp in fc.keyframe_points:
                    times.add(int(round(kp.co.x)))
    times = sorted(times)
    f0, f1 = act.frame_range
    print(f"[P4th] {a.action} [{f0:.0f}-{f1:.0f}] 前方アーチ "
          f"{[(b, d) for b, d in curls]}  対象キー {len(times)}")

    # 各フレームで既存ポーズにカールを加算して収集（親→子順）
    collected = {b: [] for b in bones}
    for f in times:
        bpy.context.scene.frame_set(f)
        for b, deg in curls:
            swing_inplace(arm.pose.bones[b], Matrix.Rotation(np.radians(deg), 4, "X"))
            bpy.context.view_layer.update()
        for b in bones:
            q = arm.pose.bones[b].rotation_quaternion.copy()
            collected[b].append((f, (q.w, q.x, q.y, q.z)))

    # 書き戻し（該当ボーンの quaternion キーを既存フレームに上書き）
    for b in bones:
        dp = f'pose.bones["{b}"].rotation_quaternion'
        bcurves = {fc.array_index: fc for fc in fcs if fc.data_path == dp}
        for f, q in collected[b]:
            for i in range(4):
                bcurves[i].keyframe_points.insert(f, q[i])
        for fc in bcurves.values():
            fc.update()

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
