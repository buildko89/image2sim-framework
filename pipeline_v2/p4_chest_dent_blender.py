"""P4-胸: 前胸の張り出しを凹ませる（全レイヤー一括、頂点のみ移動）。

指摘（2026-07-16, jump_left.gif）: 立ち上がると顎の下から前脚の間の胸が
丸く大きく前へ張り出し、喉のくびれが無い。約1/2に凹ませたい。

実測（p3_koha9face, レスト, 正中線 |X|<0.015 の前縁 = 各Z帯で最小Y）:
  Z0.05 Y-0.137 / Z0.07 -0.155 / Z0.09 -0.187 / Z0.11 -0.204(頂点) /
  Z0.13 -0.202 / Z0.15 -0.198 / Z0.17 -0.221(顎) / Z0.19 -0.228(鼻)
座標系（Blender world）: X=左右, Y=前(-)/後(+)=体軸, Z=上下。
肩（前脚付け根 bip01_l/r_clavicle）は Y=-0.109。胸頂点は肩より 0.095 m 前。

方式: 前胸帯の頂点を、肩ライン Y=Y_HINGE を基準に「前へ出た分（hinge より前）」
だけ pull_frac 倍して後方(+Y)へ引く。移動量は
  dy = pull_frac * max(0, Y_HINGE - Y) * wz(Z) * wx(|X|)
- wz: Z方向の滑らかな窓（下=腹、上=顎/首 へ 0 にフェード）。喉のくびれもここで生まれる。
- wx: 左右方向の窓（脇・前脚の付け根へ 0 にフェード）。
肩より後ろ（Y>=hinge）は max(0,...) で自動的に不動。UV・ウェイト・ボーンは触らないので
テクスチャもアニメもそのまま生きる（尻尾細身化 p4_tail_slim と同じ原理）。

対象: 体メッシュ Koha9 + 毛シェル FurShell1〜4（前胸は毛シェルも張り出すため一括）。
髭は除外。尻尾(+Y)や TailFill は窓の外なので自動的に不動。

  blender --background --python pipeline_v2/p4_chest_dent_blender.py -- \
    --input output_v2/base/p3_koha9face.blend \
    --output-blend output_v2/base/p3_koha9face.blend \
    --output-glb output_v2/base/p3_koha9face.glb \
    --pull-frac 0.5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

EXCLUDE = ("Whisker",)   # 触らないオブジェクト

# 前胸帯の窓（world 座標, m）。プロファイル実測から決定。
# 窓を広めに取って変形勾配を緩めてある: 狭い窓（0.05,0.075/0.14,0.17/0.03,0.052）だと
# pull0.5 で Jump の皮膚破断が 0.468%->0.503% と閾値0.5%を越えるが、この広い窓なら
# 同じ pull0.5・同じ apex(-0.157) で 0.487% に収まる（縮む辺が分散するため）(2026-07-16)。
Y_HINGE = -0.11          # 肩（前脚付け根）ライン。ここより前の張り出しだけを対象にする
Z_LO, Z_FULL0 = 0.035, 0.085  # 下（腹）側の立ち上がり
Z_FULL1, Z_HI = 0.13, 0.19    # 上（喉→顎）側のフェードアウト。顎(Z0.19+)は不動
X_FULL, X_ZERO = 0.022, 0.062  # 中央で全効き、脇でフェード


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--pull-frac", type=float, default=0.5,
                   help="肩より前の張り出しを後方へ引く割合（0.5 = 半分に凹ませる）")
    # 窓（既定は本文コメントの実測値）。広げるほど変形勾配が緩み、Jump の破断辺が減る。
    p.add_argument("--zwin", type=float, nargs=4, default=[Z_LO, Z_FULL0, Z_FULL1, Z_HI],
                   metavar=("Z_LO", "Z_FULL0", "Z_FULL1", "Z_HI"))
    p.add_argument("--xwin", type=float, nargs=2, default=[X_FULL, X_ZERO],
                   metavar=("X_FULL", "X_ZERO"))
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def dent(ob, pull: float, zwin, xwin) -> tuple[int, float, float]:
    """前胸帯を後方へ引く。(移動頂点数, apex前Y, apex後Y) を返す。"""
    z_lo, z_f0, z_f1, z_hi = zwin
    x_full, x_zero = xwin
    nv = len(ob.data.vertices)
    co = np.empty(nv * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    w = co @ M[:3, :3].T + M[:3, 3]
    X, Y, Z = w[:, 0], w[:, 1], w[:, 2]

    wz = smoothstep(z_lo, z_f0, Z) * (1.0 - smoothstep(z_f1, z_hi, Z))
    wx = 1.0 - smoothstep(x_full, x_zero, np.abs(X))
    protr = np.clip(Y_HINGE - Y, 0.0, None)          # 肩より前へ出た量
    dy = pull * protr * wz * wx                       # 後方(+Y)へ
    moved = dy > 1e-5
    if not moved.any():
        return 0, 0.0, 0.0

    # apex（最も前へ出ていた midline 頂点）の前後を記録
    midchest = (np.abs(X) < 0.015) & (Z > 0.08) & (Z < 0.14)
    apex_before = float(Y[midchest].min()) if midchest.any() else 0.0

    w[:, 1] = Y + dy
    apex_after = float(w[midchest, 1].min()) if midchest.any() else 0.0

    co = (w - M[:3, 3]) @ np.linalg.inv(M[:3, :3]).T
    ob.data.vertices.foreach_set("co", co.ravel())
    ob.data.update()
    return int(moved.sum()), apex_before, apex_after


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    print(f"[P4c] pull_frac={a.pull_frac}  hinge Y={Y_HINGE}  "
          f"Z窓{a.zwin}  X窓{a.xwin}")

    for ob in bpy.data.objects:
        if ob.type != "MESH" or any(x in ob.name for x in EXCLUDE):
            continue
        n, ab, aa = dent(ob, a.pull_frac, a.zwin, a.xwin)
        if n:
            print(f"[P4c] {ob.name:16s} moved={n:5d}  apex(midline) Y {ab:+.4f} -> {aa:+.4f}"
                  f"  ({(ab - aa)*1000:+.1f}mm 後退)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
