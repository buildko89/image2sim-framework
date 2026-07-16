# -*- coding: utf-8 -*-
"""P5: マズル（口元）の短縮。頂点のみ移動（UV・ウェイト・ボーン不変 =
テクスチャ/アニメ保全。尻尾細身化・胸凹ませと同じ原理）。

背景: 胸の凹ませ（p4_chest_dent）で相対的にマズルが長く見えるとの指摘
（ユーザー 2026-07-16「1/3 くらい短くしたい」）。

方式: 目の前面 Y_HINGE より前の頂点を dy = pull_frac * (Y_HINGE - y) * wz(z)
で後方(+Y)へ引く。pull_frac=1/3 なら「目の面→鼻先」が一様に 2/3 に縮む。
Z 窓でマズル帯（鼻・口）だけに掛け、眉庇・額の彫りは保つ。

Whiskers は根元がマズル表面に埋まっているので同じ場で動かすが、
鼻先より前（毛の自由端）は鼻先と同じ移動量で頭打ちにして
「髭は形を保ったまま口元ごと後退」させる（毛自体は縮めない）。

対象: Koha9（体）+ Whiskers。FurShell/TailFill は顔に面が無いので対象外。
"""
import argparse
import sys
from pathlib import Path

import bpy

Y_HINGE = -0.185   # 目の前面（bip01_head tail Y≈-0.184 実測）。これより前を圧縮
# Z 窓: [完全0になる下端, 全効き下端, 全効き上端, 完全0になる上端]
Z_WIN = (0.12, 0.14, 0.20, 0.23)

TARGETS = ("Koha9", "Whiskers")


def log(msg: str) -> None:
    print("[P5mz] " + msg, flush=True)


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--pull-frac", type=float, default=0.33,
                   help="目の面〜鼻先の圧縮率（0.33 = 1/3 短縮）")
    p.add_argument("--zwin", type=float, nargs=4, default=list(Z_WIN))
    return p.parse_args(argv)


def wz(z: float, zw) -> float:
    z0, zf0, zf1, z1 = zw
    if z <= z0 or z >= z1:
        return 0.0
    if z < zf0:
        return (z - z0) / (zf0 - z0)
    if z > zf1:
        return (z1 - z) / (z1 - zf1)
    return 1.0


def shorten(ob, pull: float, zw, nose_y: float, clamp_at_nose: bool):
    mw = ob.matrix_world
    inv = mw.inverted()
    moved = 0
    max_dy = 0.0
    for v in ob.data.vertices:
        c = mw @ v.co
        if c.y >= Y_HINGE:
            continue
        w = wz(c.z, zw)
        if w <= 0.0:
            continue
        # 髭の自由端（鼻先より前）は鼻先と同じ量で頭打ち = 形を保って平行移動
        y_eff = max(c.y, nose_y) if clamp_at_nose else c.y
        dy = pull * (Y_HINGE - y_eff) * w
        if dy <= 1e-9:
            continue
        c.y += dy
        v.co = inv @ c
        moved += 1
        max_dy = max(max_dy, dy)
    ob.data.update()
    return moved, max_dy


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)

    body = bpy.data.objects.get("Koha9")
    if body is None:
        raise RuntimeError("body mesh 'Koha9' not found")
    mwb = body.matrix_world
    nose_y = min((mwb @ v.co).y for v in body.data.vertices)
    log(f"pull_frac={a.pull_frac}  hinge Y={Y_HINGE}  Z窓={a.zwin}  "
        f"nose tip Y={nose_y:.4f}")

    for name in TARGETS:
        ob = bpy.data.objects.get(name)
        if ob is None or ob.type != "MESH":
            log(f"{name}: skipped (missing)")
            continue
        n, mx = shorten(ob, a.pull_frac, a.zwin, nose_y,
                        clamp_at_nose=(name == "Whiskers"))
        log(f"{name}: moved={n}  max_dy={mx * 1000:.1f}mm")

    nose_after = min((mwb @ v.co).y for v in body.data.vertices)
    log(f"nose tip Y {nose_y:.4f} -> {nose_after:.4f} "
        f"({(nose_after - nose_y) * 1000:+.1f}mm 後退)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
