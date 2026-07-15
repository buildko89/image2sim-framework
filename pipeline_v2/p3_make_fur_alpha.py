"""P3-10: 毛シェル用の RGBA テクスチャを作る（prompt5.md / prompt6.md モフモフ対応）。

シェルに貼る毛のアルファを「房（タフト）」の場として作る。
v1 はピクセル単位のまばらな点で、外層の点が体から離れて**浮遊するゴミ**に見えた
（prompt6.md で指摘）。v2 の設計:

- 房 = 低周波ブロブの多段合成。**ピクセルディザは入れない**（点ゴミの原因）。
- 3層とも同じ場を使い、cutoff を上げると各房が中心へ縮む → 先細りのスパイクに見える。
- 内層はほぼ全面（肌が透けない）、外層は房の芯だけが残る。
- 部位変調: 腹は密度を上げ（スカートを密に）、背中は下げる（短毛。浮き毛を出さない）。
  テクセル→3D は p3_uv_position.npz で引く。

    python pipeline_v2/p3_make_fur_alpha.py

出力: output_v2/textures/p3_koha9_fur_shell.png  (2048², RGB=basecolor, A=房の濃度)
"""
from __future__ import annotations

import argparse

import numpy as np
from PIL import Image, ImageFilter
from pathlib import Path

SRC = Path("output_v2/textures/p3_koha9_basecolor.png")
NPZ = Path("output_v2/textures/p3_uv_position.npz")
OUT = Path("output_v2/textures/p3_koha9_fur_shell.png")
N = 2048
HP_SIGMA = 3
CUTOFFS = (0.12, 0.32, 0.52, 0.70)   # p3d_fur_shells_blender.LAYERS と揃えて被覆率を確認する


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def blobs(rng, cells: int) -> np.ndarray:
    a = rng.random((cells, cells)).astype(np.float32)
    im = Image.fromarray((a * 255).astype(np.uint8)).resize((N, N), Image.BICUBIC)
    return np.asarray(im).astype(np.float32) / 255.0


def main() -> int:
    global SRC, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    SRC, OUT = Path(a.src), Path(a.out)

    src = Image.open(SRC).convert("RGB").resize((N, N), Image.LANCZOS)
    rgb = np.asarray(src).astype(np.float32)
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)

    blur = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(HP_SIGMA))).astype(np.float32)
    hp = lum - blur
    lo, hi = np.percentile(hp, [8, 92])
    strands = np.clip((hp - lo) / max(hi - lo, 1e-6), 0, 1)

    # 房の場: 大きな房 + 小さな房の「塊」を土台に、毛筋を塊の中の変調として掛ける。
    # 毛筋を足し算で強くすると細い破片が孤立して点ゴミに戻る（v2→v3 の教訓）。
    # 掛け算なら房のつながりを保ったまま、房の縁が毛筋方向にギザつく＝毛束に見える。
    rng = np.random.default_rng(9)
    d = 0.55 * blobs(rng, 72) + 0.45 * blobs(rng, 200)
    lo, hi = np.percentile(d, [2, 98])
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)
    d = d * (0.70 + 0.60 * strands)
    lo, hi = np.percentile(d, [2, 98])
    d = np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1)

    # 部位変調（npz は 2048² なのでそのまま使える）
    z = np.load(NPZ)
    pos, mask = z["pos"], z["mask"].astype(bool)
    assert pos.shape[0] == N, f"npz {pos.shape[0]} != {N}"
    gy, gz, gx = pos[..., 1], pos[..., 2], pos[..., 0]
    belly = smoothstep(0.105, 0.06, gy) * smoothstep(-0.13, -0.09, gz) * smoothstep(0.12, 0.07, gz)
    back = smoothstep(0.13, 0.165, gy) * smoothstep(0.065, 0.045, np.abs(gx)) \
        * smoothstep(-0.145, -0.11, gz) * smoothstep(0.09, 0.06, gz)
    d = np.clip(d * (1.0 + 0.50 * belly) * (1.0 - 0.25 * back) + 0.18 * belly, 0, 1)
    d = np.where(mask, d, 0.0)

    # 擬似AO: 体の腹は落ち影で暗いのに、外へ張り出した房は影から外れて明るいまま
    # 「白い毛だけ色が違う」ように見える（実機で指摘）。腹の下ほどシェルの RGB を
    # 暗くして、下の体の陰影と揃える。
    ao = 1.0 - 0.16 * smoothstep(0.100, 0.045, gy)
    rgb = rgb * np.where(mask, ao, 1.0)[..., None]

    out = np.dstack([rgb.astype(np.uint8), (d * 255).astype(np.uint8)])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out, "RGBA").save(OUT)
    for c in CUTOFFS:
        print(f"  cutoff {c:.2f}: 毛の被覆率 {(d[mask] > c).mean():.1%}")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
