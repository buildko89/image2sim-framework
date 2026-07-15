"""腹が脚ボーンに吸われる問題の原因調査: 脚ボーンがメッシュのどこに置かれているかを測る。

症状: walk / idle2 で右の腹底が 4.8cm 引き上がり、右側面のシルエットがくびれる。
辺は裂けないので qa_skin_stretch は PASS する。

仮説: fit_bones が脚の付け根（upperarm / thigh）を胴の内部・正中線寄りに置いており、
ボーンヒートが腹の頂点を脚ボーンに割り当てている。

  blender --background --python pipeline_v2/p4_inspect_legbones_blender.py -- <blend>
"""
from __future__ import annotations

import sys

import bpy
from mathutils import Vector

LEG_ROOTS = ["bip01_l_upperarm", "bip01_r_upperarm", "bip01_l_thigh", "bip01_r_thigh"]
PAWS = ["bip01_l_hand", "bip01_r_hand", "bip01_l_foot", "bip01_r_foot"]


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.open_mainfile(filepath=argv[0])
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    amw = arm.matrix_world

    vs = [v.co.copy() for v in mesh.data.vertices]
    ground = min(v.z for v in vs)
    top = max(v.z for v in vs)
    print(f"メッシュ（Blender系 -Y=前, +Z=上）: Z {ground:.4f}..{top:.4f}  "
          f"X {min(v.x for v in vs):+.4f}..{max(v.x for v in vs):+.4f}")

    # 足先クラスタ: 接地から 3cm 以内の頂点を前後・左右で4分割
    low = [v for v in vs if v.z < ground + 0.030]
    mid_y = (min(v.y for v in low) + max(v.y for v in low)) / 2
    print("\n足先クラスタ（接地+3cm 以内）の X 中心:")
    paw_x = {}
    for label, sel in (("前脚 左(-X)", [v for v in low if v.y < mid_y and v.x < 0]),
                       ("前脚 右(+X)", [v for v in low if v.y < mid_y and v.x > 0]),
                       ("後脚 左(-X)", [v for v in low if v.y >= mid_y and v.x < 0]),
                       ("後脚 右(+X)", [v for v in low if v.y >= mid_y and v.x > 0])):
        if not sel:
            continue
        cx = sum(v.x for v in sel) / len(sel)
        paw_x[label] = cx
        print(f"  {label}: {len(sel):4}頂点  X中心={cx:+.4f}")

    # 胴の断面（脚を除く高さ帯）から腹底と背高を出す
    print("\n胴の断面（Y スライスごと、|X|<0.02 の正中線付近）:")
    for y0 in [-0.10, -0.05, 0.0, 0.05, 0.10]:
        sel = [v for v in vs if y0 <= v.y < y0 + 0.05 and abs(v.x) < 0.02]
        if len(sel) < 20:
            continue
        zs = sorted(v.z for v in sel)
        print(f"  Y[{y0:+.2f},{y0+0.05:+.2f}) 腹底Z={zs[len(zs)//50]:.4f} 背高Z={zs[-len(zs)//50-1]:.4f}")

    print("\n脚ボーンのワールド位置:")
    for n in LEG_ROOTS + PAWS:
        b = arm.data.bones[n]
        h = amw @ b.head_local
        print(f"  {n:20} head=({h.x:+.4f}, {h.y:+.4f}, {h.z:+.4f})")

    print("\n判定:")
    for root, paw in (("bip01_l_upperarm", "前脚 左(-X)"), ("bip01_r_upperarm", "前脚 右(+X)"),
                      ("bip01_l_thigh", "後脚 左(-X)"), ("bip01_r_thigh", "後脚 右(+X)")):
        h = amw @ arm.data.bones[root].head_local
        if paw in paw_x:
            print(f"  {root:20} X={h.x:+.4f}  足先X={paw_x[paw]:+.4f}  "
                  f"→ 付け根が正中線に {abs(paw_x[paw]) - abs(h.x):+.4f} m 寄っている")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
