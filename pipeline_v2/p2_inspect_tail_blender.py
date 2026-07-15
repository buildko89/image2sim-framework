"""P2 前提調査: 尻尾ボーンのレスト姿勢と軸の向きを測る。

ローカル回転で巻き上げるには、どの軸が「上下に曲げる軸」なのかを知る必要がある。
Blender のボーンはローカル Y が骨方向、ローカル X 回りの回転がピッチ（上下）だが、
roll によって符号が変わる。実測して決める。

  blender --background --python pipeline_v2/p2_inspect_tail_blender.py -- <blend>
"""
from __future__ import annotations

import sys

import bpy

TAIL_BONES = [f"bone{i:03d}" for i in range(16, 21)]


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    bpy.ops.wm.open_mainfile(filepath=argv[0])
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    amw = arm.matrix_world

    print(f"\nArmature: {arm.name}  scale={tuple(round(v, 5) for v in arm.scale)}")
    print("\n尻尾ボーン（ワールド座標。この猫は +Z=上, -Y=前）")
    for n in TAIL_BONES:
        b = arm.data.bones[n]
        h, t = amw @ b.head_local, amw @ b.tail_local
        d = (t - h).normalized()
        # ボーンローカル軸をワールドへ
        mw = amw.to_3x3() @ b.matrix_local.to_3x3()
        ax = mw.col[0].normalized()
        ay = mw.col[1].normalized()
        az = mw.col[2].normalized()
        print(f"  {n}  parent={b.parent.name if b.parent else None}  connect={b.use_connect}")
        print(f"    head={tuple(round(v,4) for v in h)}  tail={tuple(round(v,4) for v in t)}"
              f"  len={round((t-h).length,4)}")
        print(f"    dir ={tuple(round(v,3) for v in d)}")
        print(f"    localX(world)={tuple(round(v,3) for v in ax)}"
              f"  localY={tuple(round(v,3) for v in ay)}  localZ={tuple(round(v,3) for v in az)}")

    # 尻尾メッシュ頂点の範囲
    mesh = next(o for o in bpy.context.scene.objects if o.type == "MESH")
    root_z = (amw @ arm.data.bones["bone016"].head_local).z
    tip = amw @ arm.data.bones["bone020"].tail_local
    print(f"\n尻尾根元 Z={root_z:.4f}   先端 Z={tip.z:.4f}  Y={tip.y:.4f}")
    zs = [v.co.z for v in mesh.data.vertices]
    ys = [v.co.y for v in mesh.data.vertices]
    print(f"メッシュ全体: Z {min(zs):.4f}..{max(zs):.4f}   Y {min(ys):.4f}..{max(ys):.4f}")
    print(f"背の高さ(Zmax) = {max(zs):.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
