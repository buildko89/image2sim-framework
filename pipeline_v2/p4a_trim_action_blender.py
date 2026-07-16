"""P4-1: アクションの区間切り出し（Jump の跳躍コア抽出など）。

Jump は 581f (9.67s) の複合シーケンスで、ゲームで使える跳躍は f397〜489 の
1.55s だけ（ビート実測 2026-07-15: タメ 397-429 → 跳躍ピーク 441 → 着地 461-473 →
復帰 489。骨盤 Z は全編 0.215 固定 = 元から in-place）。

方式: 境界フレームに現在値のキーを打ってから区間外のキーを削除し、全キーを
frame 1 起点へ平行移動する。Blender 5.0 のスロット化アクション対応
（fcurves は act.layers[].strips[].channelbags[] の下）。ハンドルも一緒に移動する。

  blender --background --python pipeline_v2/p4a_trim_action_blender.py -- \
    --input output_v2/base/p3_koha9face.blend \
    --output-blend output_v2/base/p3_koha9face.blend \
    --output-glb output_v2/base/p3_koha9face.glb \
    --action "Armature|Jump" --start 397 --end 489
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--action", required=True)
    p.add_argument("--start", type=int, required=True)
    p.add_argument("--end", type=int, required=True)
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


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    act = bpy.data.actions[a.action]
    fcurves = action_fcurves(act)
    f0, f1 = act.frame_range
    print(f"[P4a] {a.action}: frames {f0:.0f}-{f1:.0f} -> 切り出し {a.start}-{a.end}"
          f" ({(a.end - a.start) / 60:.2f}s @60fps)  fcurves={len(fcurves)}")
    if not (f0 <= a.start < a.end <= f1):
        raise SystemExit("[P4a] FAIL: 範囲がアクションの外")

    shift = a.start - 1
    for fc in fcurves:
        # 境界に現在値のキーを打つ（切り口のポーズを保存）
        for f in (a.start, a.end):
            fc.keyframe_points.insert(f, fc.evaluate(f))
        # 区間外を削除（後ろから）
        for kp in reversed(fc.keyframe_points):
            if kp.co.x < a.start - 0.5 or kp.co.x > a.end + 0.5:
                fc.keyframe_points.remove(kp)
        # frame 1 起点へ移動（ハンドルも）
        for kp in fc.keyframe_points:
            kp.co.x -= shift
            kp.handle_left.x -= shift
            kp.handle_right.x -= shift
        fc.update()

    nf0, nf1 = act.frame_range
    print(f"[P4a] 結果: frames {nf0:.0f}-{nf1:.0f} ({(nf1 - nf0) / 60:.2f}s)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
