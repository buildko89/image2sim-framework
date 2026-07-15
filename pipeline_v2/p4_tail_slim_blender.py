"""P4-尻尾: 尻尾を細くする（全レイヤー一括）。

実測（2026-07-15, p3_koha9face）: プルーム最大径は体メッシュ 0.215×体長、
毛シェル 0.245×体長。P0 仕様（写真実測）は 0.18×体長 — 仕様どおり太い。

方式: 尻尾ボーン鎖（bone016〜020, レスト）の折れ線を中心線とし、各頂点を
最近傍セグメントへ射影して、**軸に垂直な成分だけ** radius_scale 倍に縮める。
UV・ウェイト・ボーンは一切触らないので、テクスチャもアニメもそのまま生きる。

対象レイヤー（尻尾は4層構造。1層でも漏れると細くならない/はみ出す）:
  - Koha9 の尻尾支配頂点（皮膚 + プルームカード Koha9Tail）
  - TailFillCore / TailFillMid（p3e の不透明芯と互い違いカード）
  - FurShell1〜4 の尻尾支配頂点

根元の接続: 縮小率は「尻尾ウェイト合計 × 弧長ランプ(RAMP_S0..RAMP_S1)」で
ブレンドする。ウェイトは尻尾の付け根で連続に 0→1 になるので、腰との段差が出ない。

  blender --background --python pipeline_v2/p4_tail_slim_blender.py -- \
    --input output_v2/base/p3_koha9face.blend \
    --output-blend output_v2/base/p3_koha9face.blend \
    --output-glb output_v2/base/p3_koha9face.glb \
    --radius-scale 0.85
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np

TAIL_BONES = [f"bone{i:03d}" for i in range(16, 21)]
BODY_LEN = 0.35          # 鼻先→尾根元。P0 仕様の基準長
RAMP_S0, RAMP_S1 = 0.005, 0.045   # 根元ブレンド区間（弧長 m）
EXCLUDE = ("Whisker",)   # 触らないオブジェクト


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--radius-scale", type=float, default=0.85)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def centerline(arm) -> tuple[np.ndarray, np.ndarray]:
    """尻尾ボーン鎖の折れ線（ワールド）。点列と各点の弧長を返す。"""
    amw = arm.matrix_world
    pts = []
    for n in TAIL_BONES:
        pts.append(np.array(amw @ arm.data.bones[n].head_local))
    pts.append(np.array(amw @ arm.data.bones[TAIL_BONES[-1]].tail_local))
    pts = np.array(pts)
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    return pts, s


def tail_weights(ob) -> np.ndarray:
    gidx = {vg.index for vg in ob.vertex_groups if vg.name in set(TAIL_BONES)}
    w = np.zeros(len(ob.data.vertices))
    for v in ob.data.vertices:
        w[v.index] = sum(g.weight for g in v.groups if g.group in gidx)
    return np.clip(w, 0.0, 1.0)


def slim(ob, pts: np.ndarray, s_at: np.ndarray, scale: float) -> tuple[int, float, float]:
    """尻尾支配頂点を中心線へ radial 縮小。(処理頂点数, r95前, r95後) を返す。"""
    w = tail_weights(ob)
    sel = w > 1e-4
    if not sel.any():
        return 0, 0.0, 0.0

    nv = len(ob.data.vertices)
    co = np.empty(nv * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    wpos = co @ M[:3, :3].T + M[:3, 3]

    idx = np.where(sel)[0]
    a = pts[:-1]                     # (S,3) セグメント始点
    d = pts[1:] - pts[:-1]           # (S,3)
    dd = (d * d).sum(1)
    seg_len = np.sqrt(dd)

    r_before, r_after = [], []
    for i in idx:
        p = wpos[i]
        t = np.clip(((p - a) * d).sum(1) / dd, 0.0, 1.0)   # (S,)
        q = a + t[:, None] * d
        dist = np.linalg.norm(p - q, axis=1)
        k = int(dist.argmin())
        foot, r = q[k], dist[k]
        s_here = s_at[k] + t[k] * seg_len[k]
        ramp = np.clip((s_here - RAMP_S0) / (RAMP_S1 - RAMP_S0), 0.0, 1.0)
        blend = w[i] * ramp
        f = 1.0 - (1.0 - scale) * blend
        wpos[i] = foot + (p - foot) * f
        r_before.append(r)
        r_after.append(r * f)

    co = (wpos - M[:3, 3]) @ np.linalg.inv(M[:3, :3]).T
    ob.data.vertices.foreach_set("co", co.ravel())
    ob.data.update()
    return len(idx), float(np.percentile(r_before, 95)), float(np.percentile(r_after, 95))


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    pts, s_at = centerline(arm)
    total = s_at[-1]
    print(f"[P4t] 中心線: 全長 {total:.4f} m ({total/BODY_LEN:.3f}×体長)  scale={a.radius_scale}")

    for ob in bpy.data.objects:
        if ob.type != "MESH" or any(x in ob.name for x in EXCLUDE):
            continue
        n, rb, ra = slim(ob, pts, s_at, a.radius_scale)
        if n:
            print(f"[P4t] {ob.name:16s} verts={n:5d}  r95 {rb*1000:5.1f}mm -> {ra*1000:5.1f}mm"
                  f"  (径 {2*rb/BODY_LEN:.3f} -> {2*ra/BODY_LEN:.3f} ×体長)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
