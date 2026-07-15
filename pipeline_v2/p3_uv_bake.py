"""P3-1 の土台: UV 空間の各テクセルに「3D位置」と「支配ボーン」を焼く。

柄を「背骨の高さ」「肩」「腰」「尾根元」で定義するには、テクスチャのどの画素が
体のどこなのかを知る必要がある。GLB から UV 三角形をラスタライズして、
各テクセルの 3D 位置（レスト姿勢）と支配ボーン名を記録する。

素材の 2枚のテクスチャは RGB が完全に同一（毛シェル用はアルファが付くだけ）なので、
UV レイアウトも共通のはず。両プリミティブを同じマップに焼き、重なりを確認する。

    python pipeline_v2/p3_uv_bake.py --glb output_v2/base/p2_koha.glb

出力:
    output_v2/textures/p3_uv_position.npz   pos(H,W,3) / bone(H,W) / mask(H,W)
    output_v2/reports/p3_uv_debug.png       目視確認用（位置をRGB化・部位を色分け）
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_skin_stretch as q  # noqa: E402

RES = 2048  # 4096 の半分で焼いて最後に拡大する。柄はどれも大きいので十分
NPZ = Path("output_v2/textures/p3_uv_position.npz")
DEBUG = Path("output_v2/reports/p3_uv_debug.png")
FONT = "C:/Windows/Fonts/meiryo.ttc"

# 部位の分類（支配ボーン名 → 部位）
# 首は「頭」に入れない。P3-1 で頭は素材のまま保護するので、首まで保護すると
# 素材のオレンジの帯が首の付け根に残り、どの方向から見ても染みに見える。
TAIL = [f"bone{i:03d}" for i in range(16, 21)]
HEAD = ["bip01_head"]
LEG_KEYS = ("upperarm", "forearm", "hand", "finger", "thigh", "calf", "horselink", "foot", "toe",
            "clavicle")

PART_BODY, PART_HEAD, PART_LEG, PART_TAIL = 1, 2, 3, 4
PART_COLORS = {0: (25, 25, 28), PART_BODY: (210, 210, 200), PART_HEAD: (90, 160, 230),
               PART_LEG: (230, 170, 60), PART_TAIL: (200, 90, 200)}
PART_NAMES = {PART_BODY: "胴", PART_HEAD: "頭・首", PART_LEG: "脚", PART_TAIL: "尻尾"}


def classify(name: str) -> int:
    if name in TAIL:
        return PART_TAIL
    if name in HEAD or name.startswith("bone0"):
        return PART_HEAD
    if any(k in name for k in LEG_KEYS):
        return PART_LEG
    return PART_BODY


def raster(uv, pos, nrm, part, tailt, tris, out_pos, out_nrm, out_part, out_tailt, out_mask):
    """UV 三角形を重心座標で塗る。

    glTF の UV 原点は画像の左上なので、V を反転してはいけない（Blender 流の 1-v は誤り）。
    反転すると顔と尻尾が上下逆の場所に焼かれる。
    """
    H, W = out_mask.shape
    px = np.stack([uv[:, 0] * (W - 1), uv[:, 1] * (H - 1)], axis=1)
    for tri in tris:
        p = px[tri]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0 - 1, 0), max(y0 - 1, 0)
        x1, y1 = min(x1 + 1, W - 1), min(y1 + 1, H - 1)
        if x1 <= x0 or y1 <= y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        v0, v1, v2 = p[0], p[1], p[2]
        d = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        if abs(d) < 1e-9:
            continue
        a = ((v1[1] - v2[1]) * (xs - v2[0]) + (v2[0] - v1[0]) * (ys - v2[1])) / d
        b = ((v2[1] - v0[1]) * (xs - v2[0]) + (v0[0] - v2[0]) * (ys - v2[1])) / d
        c = 1.0 - a - b
        inside = (a >= -0.002) & (b >= -0.002) & (c >= -0.002)
        if not inside.any():
            continue
        yy, xx = ys[inside], xs[inside]
        w = np.stack([a[inside], b[inside], c[inside]], axis=1)
        out_pos[yy, xx] = w @ pos[tri]
        out_nrm[yy, xx] = w @ nrm[tri]
        out_tailt[yy, xx] = w @ tailt[tri]
        # 支配ボーン: 重心座標が最大の頂点のもの
        out_part[yy, xx] = part[tri][np.argmax(w, axis=1)]
        out_mask[yy, xx] = True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default="output_v2/base/p2_koha.glb")
    ap.add_argument("--res", type=int, default=RES)
    a = ap.parse_args()

    gltf, blob = q.load_glb(Path(a.glb))
    nodes = gltf["nodes"]
    joints = gltf["skins"][0]["joints"]
    jnames = [nodes[j].get("name", "") for j in joints]
    jparts = np.array([classify(n) for n in jnames])
    # 尻尾に沿った座標: 尻尾ボーンの序数をウェイトで加重平均する。
    # カール後の尻尾で「根元からの距離」を3D座標から出すのは不安定なので、骨で測る。
    jtail = np.array([TAIL.index(n) if n in TAIL else -1.0 for n in jnames], np.float32)

    H = W = a.res
    out_pos = np.zeros((H, W, 3), np.float32)
    out_nrm = np.zeros((H, W, 3), np.float32)
    out_tailt = np.zeros((H, W), np.float32)
    out_part = np.zeros((H, W), np.uint8)
    out_mask = np.zeros((H, W), bool)

    coverage = {}
    for nd in nodes:
        if "mesh" not in nd or "skin" not in nd:
            continue
        for prim in gltf["meshes"][nd["mesh"]]["primitives"]:
            name = gltf["materials"][prim["material"]]["name"]
            pos = q.read_accessor(gltf, blob, prim["attributes"]["POSITION"]).astype(np.float32)
            nrm = q.read_accessor(gltf, blob, prim["attributes"]["NORMAL"]).astype(np.float32)
            uv = q.read_accessor(gltf, blob, prim["attributes"]["TEXCOORD_0"]).astype(np.float64)
            J = q.read_accessor(gltf, blob, prim["attributes"]["JOINTS_0"]).astype(int)
            Wt = q.read_accessor(gltf, blob, prim["attributes"]["WEIGHTS_0"]).astype(float)
            tris = q.read_accessor(gltf, blob, prim["indices"]).ravel().astype(int).reshape(-1, 3)
            part = jparts[J[np.arange(len(J)), np.argmax(Wt, axis=1)]]

            istail = jtail[J] >= 0.0
            wt = Wt * istail
            denom = wt.sum(1)
            tailt = np.where(denom > 1e-6, (wt * jtail[J]).sum(1) / np.maximum(denom, 1e-6), -1.0)

            before = out_mask.sum()
            raster(uv, pos, nrm, part, tailt.astype(np.float32), tris,
                   out_pos, out_nrm, out_part, out_tailt, out_mask)
            coverage[name] = {"verts": len(pos), "tris": len(tris),
                             "new_texels": int(out_mask.sum() - before),
                             "uv_range": [round(float(uv.min()), 3), round(float(uv.max()), 3)]}

    print(f"焼き込み解像度 {W}x{H}   カバー率 {out_mask.mean():.1%}")
    for k, v in coverage.items():
        print(f"  {k:16} verts={v['verts']:5} tris={v['tris']:5} "
              f"新規テクセル={v['new_texels']:8}  UV範囲={v['uv_range']}")
    print("\n部位別テクセル数:")
    for pid, pname in PART_NAMES.items():
        n = int((out_part == pid).sum())
        print(f"  {pname:6} {n:9}  ({n / max(out_mask.sum(),1):.1%})")

    body = out_mask & (out_part != PART_TAIL) & (out_part != PART_HEAD)
    print("\n胴+脚 テクセルの3D座標分布（glTF系 X=左右 Y=上下 Z=前後, +Z=頭側）:")
    for i, ax in enumerate(("X 左右", "Y 上下", "Z 前後")):
        v = out_pos[body][:, i]
        print(f"  {ax}: min={v.min():+.3f} p10={np.percentile(v,10):+.3f} "
              f"p50={np.percentile(v,50):+.3f} p90={np.percentile(v,90):+.3f} max={v.max():+.3f}")
    ny = out_nrm[body][:, 1]
    print(f"  法線Y（+が背側）: 背側テクセル {float((ny>0.25).mean()):.1%} / "
          f"腹側 {float((ny<-0.25).mean()):.1%}")

    t = out_tailt[out_part == PART_TAIL]
    print(f"  尻尾座標 t: min={t.min():.2f} max={t.max():.2f}（0=尾根元, 4=先端）")

    NPZ.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(NPZ, pos=out_pos, nrm=out_nrm, tailt=out_tailt,
                        part=out_part, mask=out_mask)
    print(f"\n-> {NPZ}")

    # デバッグ画像: 左=位置をRGB化 / 右=部位の色分け
    lo, hi = out_pos[out_mask].min(0), out_pos[out_mask].max(0)
    norm = np.clip((out_pos - lo) / np.maximum(hi - lo, 1e-6), 0, 1)
    posimg = (norm * 255).astype(np.uint8)
    posimg[~out_mask] = (25, 25, 28)

    partimg = np.zeros((H, W, 3), np.uint8)
    for pid, col in PART_COLORS.items():
        partimg[out_part == pid] = col

    src = Image.open("input/cat2/koha9_cat/textures/Koha9Body_baseColor.png").convert("RGB")
    src.thumbnail((W, H))

    sheet = Image.new("RGB", (W * 3 // 2 + 40, H // 2 + 60), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 16)
    for i, (img, lab) in enumerate([
            (src, "素材テクスチャ"),
            (Image.fromarray(posimg), "3D位置 (R=左右 G=上下 B=前後)"),
            (Image.fromarray(partimg), "部位: 白=胴 青=頭 橙=脚 紫=尻尾")]):
        im = img.resize((W // 2, H // 2))
        sheet.paste(im, (i * (W // 2 + 10) + 10, 46))
        d.text((i * (W // 2 + 10) + 12, 24), lab, fill=(255, 235, 120), font=f)
    d.text((10, 4), "P3-1 UV ベイク検証 — 部位が体の正しい場所に対応しているか目で確かめる",
           fill=(255, 235, 120), font=f)
    DEBUG.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(DEBUG)
    print(f"-> {DEBUG}  {sheet.size}  (必ず目視すること)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
