"""P3 の目視ゲート素材: 実物の写真とモデルを4方向で並べる。

    python pipeline_v2/p3_compare_photos.py [--prefix p3] [--anim walk] [--t 45]

向きの規約: 被写体が画面右を向く写真は「左半身」を見せる（newplan/p0_appearance_spec.md）。
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SHOTS = REPO / "output_v2/reports/p1_shots"
FONT = "C:/Windows/Fonts/meiryo.ttc"

# (写真, モデルのビュー, ラベル, 写真のクロップ l,t,r,b 割合 or None)
PAIRS = [
    ("横.png", "left", "左側面", None),
    ("1780491195055.jpg", "right", "右側面", (0.05, 0.28, 0.75, 0.65)),
    ("1763363798733.jpg", "front", "正面", None),
    ("1755598074234.jpg", "back", "背面", (0.25, 0.20, 0.75, 0.85)),
]
CHECKS = "確認: 白優勢 / 背骨の中央が白い / 深いラスト斑 / 黒は尾根元と顔だけ / 太いプルーム尻尾"


def _crop_face(im: Image.Image, size: int = 210, anchor: str = "iris") -> Image.Image:
    """レンダー内の虹彩（黄緑）または鼻（ピンク）を検出して顔を中心にクロップする。

    ポーズごとに頭の位置が違うので、切り出し位置を決め打ちにすると顔を外す。
    横顔では虹彩が小さく写るので、鼻を基準にしたほうが安定する。
    """
    a = np.asarray(im).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if anchor == "nose":
        m = (r > 150) & ((r - g) > 30) & ((g - b) < 25) & (b > 90)
        dy = 0
    else:
        m = (g > 120) & (g > b + 45) & (r > 90) & (r < 240)
        dy = size // 6
    ys, xs = np.nonzero(m)
    if len(xs) < 15:
        cx, cy = im.width // 2, im.height // 2
    else:
        cx, cy = int(np.median(xs)), int(np.median(ys)) + dy
    h = size // 2
    cx = min(max(cx, h), im.width - h)
    cy = min(max(cy, h), im.height - h)
    return im.crop((cx - h, cy - h, cx + h, cy + h))


def face_sheet(prefix: str) -> None:
    """顔の比較。実物の正面2枚と、モデルの正面（顔が見えるフレーム）を並べる。"""
    ft, fs = ImageFont.truetype(FONT, 19), ImageFont.truetype(FONT, 13)
    C = 560
    photos = ["face/1701442043866.jpg", "face/1648460789455.jpg"]
    shots = [("jump", 45), ("idle2", 15)]
    out = Image.new("RGB", (C * 4 + 50, C + 80), (18, 18, 20))
    d = ImageDraw.Draw(out)
    d.text((10, 6), "P3-2 顔: 実物（左2枚）と モデル（右2枚）", fill=(255, 235, 120), font=ft)
    d.text((10, 32), "確認: 広い白ブレーズ / 耳の付け根の橙 / 猫の左(画面右)の額の黒いくさび / "
                     "猫の左のマズルの橙のそばかす / 目は緑",
           fill=(185, 185, 190), font=fs)

    cells = []
    for p in photos:
        im = Image.open(REPO / "input/raw_photos" / p).convert("RGB")
        w, h = im.size
        im = im.crop((0, 0, w, int(h * 0.55)))
        im.thumbnail((C, C))
        cells.append((im, f"実物 {Path(p).name}"))
    for anim, t in shots:
        im = Image.open(SHOTS / f"{prefix}_{anim}_t{t:02d}_front.png").convert("RGB")
        im = _crop_face(im).resize((C, C), Image.LANCZOS)
        cells.append((im, f"モデル {anim} t{t}"))

    for i, (im, lab) in enumerate(cells):
        x = 10 + i * (C + 10)
        out.paste(im, (x, 60 + (C - im.height) // 2))
        d.text((x + 4, 62), lab, fill=(255, 235, 120) if i < 2 else (140, 220, 255), font=fs)

    dst = REPO / f"output_v2/reports/{prefix}_face_vs_photo.png"
    out.save(dst)
    print(f"-> {dst}  {out.size}  (必ず目視すること)")
    _profile_sheet(prefix)


def _profile_sheet(prefix: str) -> None:
    """横顔（マズルの長さ）と俯瞰（頭頂の柄）の比較。"""
    ft, fs = ImageFont.truetype(FONT, 19), ImageFont.truetype(FONT, 13)
    C = 520
    # 頭部はレスト姿勢の専用ショットを使う。ポーズで頭が傾いた全身ショットから
    # 切り出すと、マズルの長さも頭頂の柄も判定できない。
    items = [
        (REPO / "input/raw_photos/face2/1648713873399_frame_001965.jpg", "実物 横顔", False),
        (SHOTS / f"{prefix}_head_right.png", "モデル 横顔（レスト）", True),
        (REPO / "input/raw_photos/face2/1648713873399_frame_002490.jpg", "実物 俯瞰", False),
        (SHOTS / f"{prefix}_head_top.png", "モデル 俯瞰（レスト）", True),
    ]
    out = Image.new("RGB", (C * 4 + 50, C + 80), (18, 18, 20))
    d = ImageDraw.Draw(out)
    d.text((10, 6), "P3-3 マズルの長さ と 頭頂の柄", fill=(255, 235, 120), font=ft)
    d.text((10, 32), "確認: 鼻先が目より前に出ているか / 黒は頭頂の帯で、白いブレーズが割っているか",
           fill=(185, 185, 190), font=fs)
    for i, (p, lab, is_model) in enumerate(items):
        im = Image.open(p).convert("RGB")
        im.thumbnail((C, C))
        x = 10 + i * (C + 10)
        out.paste(im, (x + (C - im.width) // 2, 60 + (C - im.height) // 2))
        d.text((x + 4, 62), lab, fill=(140, 220, 255) if is_model else (255, 235, 120), font=fs)
    dst = REPO / f"output_v2/reports/{prefix}_muzzle_vs_photo.png"
    out.save(dst)
    print(f"-> {dst}  {out.size}  (必ず目視すること)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="p3")
    ap.add_argument("--anim", default="walk")
    ap.add_argument("--t", type=int, default=45)
    a = ap.parse_args()

    CW = CH = 520
    out = Image.new("RGB", (CW * 4 + 50, CH * 2 + 96), (18, 18, 20))
    d = ImageDraw.Draw(out)
    ft, fs = ImageFont.truetype(FONT, 19), ImageFont.truetype(FONT, 13)
    d.text((10, 6), f"P3-1 目視ゲート: 実物 (上) と モデル {a.prefix}_koha (下) を4方向で比較",
           fill=(255, 235, 120), font=ft)
    d.text((10, 32), CHECKS, fill=(185, 185, 190), font=fs)

    for i, (photo, view, label, crop) in enumerate(PAIRS):
        p = Image.open(REPO / "input/raw_photos" / photo).convert("RGB")
        if crop:
            w, h = p.size
            p = p.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        p.thumbnail((CW, CH))
        m = Image.open(SHOTS / f"{a.prefix}_{a.anim}_t{a.t:02d}_{view}.png").convert("RGB")
        m.thumbnail((CW, CH))
        x = 10 + i * (CW + 10)
        out.paste(p, (x + (CW - p.width) // 2, 60 + (CH - p.height) // 2))
        out.paste(m, (x + (CW - m.width) // 2, 60 + CH + 16 + (CH - m.height) // 2))
        d.text((x + 4, 62), f"実物 {label}", fill=(255, 235, 120), font=fs)
        d.text((x + 4, 60 + CH + 18), f"モデル {label}", fill=(140, 220, 255), font=fs)

    dst = REPO / f"output_v2/reports/{a.prefix}_vs_photo.png"
    out.save(dst)
    print(f"-> {dst}  {out.size}  (必ず目視すること)")
    face_sheet(a.prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
