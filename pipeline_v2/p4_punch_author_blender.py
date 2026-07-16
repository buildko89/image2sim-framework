"""P4-2: アタックに「猫パンチ」をオーサリングする（振り方 mode 対応）。

素の Atk は左前脚の弱い「持ち上げ」で、前方へ振り出すと下→前→上を通る=ボクシングの
アッパーになってしまう（ユーザー指摘 2026-07-16）。猫の自然な猫パンチは
  - downward : 前足を上げてから上から下へ振り下ろす（叩く）
  - hook     : 前足を前へ出し、横へ薙ぐ（左手=左→右 / 右手=右→左）
座標系は Blender world: X=左右, Y=前(-)/後(+), Z=上下。前脚はレストで下(-Z)を向く。
各フレームで前脚を「レスト＋ワールド回転」に置き換え、プロファイルで振り方を焼く。
体幹・頭・尻尾の元カーブは二次モーションとして残す。最後に speed 倍で時間圧縮。

  blender --background --python pipeline_v2/p4_punch_author_blender.py -- \
    --input ... --output-blend ... --output-glb ... \
    --action "Armature|Atk1" --side l --mode downward --speed 1.4
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix

# --- プロファイル（τ=正規化時間 -> 値）。振り方ごとに前脚の姿勢を決める ---
# downward: 上腕角(絶対度)。0→上げ(raise)→振り下ろし(strike)→保持→戻し
DN_T = [0.0, 0.25, 0.45, 0.60, 0.90, 1.0]
# hook: lift 包絡（前へ水平に出す量）と sweep（横薙ぎ量: +で振り出し側→-で薙ぎ切る）
HK_ENV_T = [0.0, 0.18, 0.38, 0.62, 0.85, 1.0]
HK_ENV_M = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]
HK_SW_T = [0.0, 0.30, 0.42, 0.60, 0.82, 1.0]
HK_SW_M = [0.0, 1.0, 1.0, -1.0, 0.0, 0.0]
# uppercut(旧): 上腕角 = up_deg * 倍率
UC_T = [0.0, 0.20, 0.45, 0.62, 0.90, 1.0]
UC_M = [0.0, -0.25, 1.00, 1.00, 0.0, 0.0]
# 前腕の追従包絡（全 mode 共通）
FORE_T = [0.0, 0.22, 0.42, 0.60, 0.85, 1.0]
FORE_M = [0.0, 0.0, 1.0, 1.0, 0.0, 0.0]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--side", default="l", choices=["l", "r"])
    p.add_argument("--mode", default="downward", choices=["downward", "hook", "uppercut"])
    # downward
    p.add_argument("--raise-deg", type=float, default=-140.0, help="[downward]振りかぶりの上腕角(前上)")
    p.add_argument("--strike-deg", type=float, default=-30.0, help="[downward]振り下ろし到達角(前下)")
    # hook
    p.add_argument("--lift-deg", type=float, default=-92.0, help="[hook]前へ水平に出す上腕角")
    p.add_argument("--sweep-deg", type=float, default=48.0, help="[hook]横薙ぎの振り幅(片側)")
    # uppercut
    p.add_argument("--up-deg", type=float, default=-100.0, help="[uppercut]上腕の前方角")
    # 共通
    p.add_argument("--fore-deg", type=float, default=-30.0, help="前腕の追従角")
    p.add_argument("--speed", type=float, default=1.4, help="時間圧縮率(>1で速く)")
    p.add_argument("--samples", type=int, default=40)
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
    """ボーンの頭(位置)を保ったまま world 回転 R を姿勢に前掛け（非接続骨の吹き飛び防止・罠㉓）。"""
    loc = pb.matrix.to_translation()
    rot = (R.to_3x3() @ pb.matrix.to_3x3()).to_4x4()
    pb.matrix = Matrix.Translation(loc) @ rot


def upper_rotation(mode: str, tau: float, a, side_sign: float):
    """上腕に掛ける world 回転。"""
    if mode == "downward":
        ang = np.interp(tau, DN_T, [0.0, a.raise_deg, a.strike_deg, a.strike_deg, 0.0, 0.0])
        return Matrix.Rotation(np.radians(ang), 4, "X")
    if mode == "hook":
        env = np.interp(tau, HK_ENV_T, HK_ENV_M)
        phi = np.interp(tau, HK_SW_T, HK_SW_M) * a.sweep_deg * side_sign
        lift = Matrix.Rotation(np.radians(a.lift_deg) * env, 4, "X")
        sweep = Matrix.Rotation(np.radians(phi), 4, "Z")
        return sweep @ lift
    m = np.interp(tau, UC_T, UC_M)   # uppercut
    return Matrix.Rotation(np.radians(a.up_deg) * m, 4, "X")


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

    s = a.side
    side_sign = 1.0 if s == "l" else -1.0
    upper, fore, hand = f"bip01_{s}_upperarm", f"bip01_{s}_forearm", f"bip01_{s}_hand"
    swung = [upper, fore, hand]

    f0, f1 = [int(x) for x in act.frame_range]
    frames = [int(round(f0 + (f1 - f0) * i / (a.samples - 1))) for i in range(a.samples)]
    print(f"[P4pa] {a.action}: frames {f0}-{f1}  side={s}  mode={a.mode} speed={a.speed}")

    collected = {b: [] for b in swung}
    for f in frames:
        bpy.context.scene.frame_set(f)
        tau = (f - f0) / max(f1 - f0, 1)
        for b in swung:
            arm.pose.bones[b].rotation_quaternion = (1, 0, 0, 0)
        bpy.context.view_layer.update()
        swing_inplace(arm.pose.bones[upper], upper_rotation(a.mode, tau, a, side_sign))
        bpy.context.view_layer.update()
        fore_ang = np.radians(a.fore_deg) * np.interp(tau, FORE_T, FORE_M)
        swing_inplace(arm.pose.bones[fore], Matrix.Rotation(fore_ang, 4, "X"))
        bpy.context.view_layer.update()
        for b in swung:
            q = arm.pose.bones[b].rotation_quaternion.copy()
            collected[b].append((f, (q.w, q.x, q.y, q.z)))

    fcs = action_fcurves(act)
    for b in swung:
        dp = f'pose.bones["{b}"].rotation_quaternion'
        bcurves = {fc.array_index: fc for fc in fcs if fc.data_path == dp}
        for fc in bcurves.values():
            for kp in reversed(fc.keyframe_points):
                fc.keyframe_points.remove(kp)
        for f, q in collected[b]:
            for i in range(4):
                bcurves[i].keyframe_points.insert(f, q[i])
        for fc in bcurves.values():
            fc.update()

    sc = 1.0 / a.speed
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.co.x = 1.0 + (kp.co.x - 1.0) * sc
            kp.handle_left.x = 1.0 + (kp.handle_left.x - 1.0) * sc
            kp.handle_right.x = 1.0 + (kp.handle_right.x - 1.0) * sc
        fc.update()
    nf0, nf1 = act.frame_range
    print(f"[P4pa] 完了: frames {nf0:.0f}-{nf1:.0f} ({(nf1-nf0)/60:.2f}s)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
