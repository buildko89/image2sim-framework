"""P0: raw_photos から koha の実測パレットを取り直す。

既存の config/cat_color_palette.yaml は全6色が source: koha_render_b3v2、
すなわち素材アセット（koha9_cat）の宣材レンダー由来で、実物の写真から取られていない。
ここでは input/raw_photos の2枚から直接サンプリングし直す。

各写真に写り込んだ白壁を使ってホワイトバランスを補正する（B-2 の知見:
照明の色被りを補正せずに色を取ると青や茶に転ぶ）。

  python pipeline_v2/p0_sample_palette.py

出力:
  output_v2/reports/p0_palette_samples.png   サンプリング位置の検証用オーバーレイ（必ず目視すること）
  config/cat_color_palette_v3_raw_photos.yaml
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont

SRC = Path("input/raw_photos")
OVERLAY = Path("output_v2/reports/p0_palette_samples.png")
YAML_OUT = Path("config/cat_color_palette_v3_raw_photos.yaml")
FONT = "C:/Windows/Fonts/meiryo.ttc"

# 写真ごと: 白壁のWB基準ボックスと、色サンプルのボックス (l, t, r, b)
# 枠の位置は output_v2/reports/p0_palette_samples.png を目視して確定させた。
# 顔のオレンジ（頬・額）は影で沈み (55,47,44) 程度にしかならないので、
# オレンジの代表値には使わない。オレンジは背面写真の肩・腰から、
# リング柄は正面写真の床に伸びた尻尾（良好な採光）から取る。
SHEETS = [
    {
        "image": "1763363798733.jpg",
        "note": "正面座位。背景の白レンガをWB基準に使う。",
        "wb": (660, 110, 720, 160),
        "samples": {
            "white_body": (410, 590, 490, 670),
            "white_bright": (445, 340, 475, 365),      # 眉間のブレーズ（最も明るい白）
            "black_mask": (575, 375, 615, 435),        # 猫の左頬の濃い焦茶マスク
            "nose_freckle": (481, 434, 497, 451),      # 鼻筋の橙の点
            "tail_base_orange": (845, 845, 875, 875),  # 尾根元寄りの橙みの帯
            "tail_tan": (975, 830, 1005, 870),         # 尻尾の淡いリング
            "tail_brown": (1035, 820, 1060, 860),      # 尻尾の濃いリング
        },
    },
    {
        "image": "1755598074234.jpg",
        "note": "背面・俯瞰。背景の白壁をWB基準に使う。",
        "wb": (760, 120, 820, 170),
        "samples": {
            "white_back": (476, 592, 508, 640),
            "orange_core": (543, 528, 568, 558),   # 肩の斑の中心（最も濃い）
            "orange_hip_l": (466, 762, 496, 798),
            "orange_hip_r": (626, 774, 656, 806),
            "black_rump": (556, 738, 596, 786),    # 影で潰れる。下の注記参照
        },
    },
]

# black_rump は写真上 (4,4,2) まで潰れる（猫自身の影 + JPEG）。
# ベースカラーとしてそのまま使ってはいけない。採光の良い black_mask を黒の代表値にする。
CRUSHED = {"black_rump"}


def median_rgb(im: np.ndarray, box) -> np.ndarray:
    l, t, r, b = box
    return np.median(im[t:b, l:r].reshape(-1, 3), axis=0)


def p85_rgb(im: np.ndarray, box) -> np.ndarray:
    """毛の谷間の影を避けた「当たっている面」の色。median と併記して判断材料にする。"""
    l, t, r, b = box
    return np.percentile(im[t:b, l:r].reshape(-1, 3), 85, axis=0)


def main() -> None:
    f_big, f_small = ImageFont.truetype(FONT, 17), ImageFont.truetype(FONT, 12)
    panels, results = [], {}

    for sheet in SHEETS:
        pil = Image.open(SRC / sheet["image"]).convert("RGB")
        arr = np.asarray(pil).astype(float)

        wb = median_rgb(arr, sheet["wb"])
        # 白パッチ補正: 白壁が無彩色になるゲインを全体にかける
        gain = wb.mean() / np.maximum(wb, 1.0)

        d = ImageDraw.Draw(pil)
        d.rectangle(sheet["wb"], outline=(0, 255, 255), width=3)
        d.text((sheet["wb"][0], sheet["wb"][1] - 20), "WB", fill=(0, 255, 255), font=f_small)

        for name, box in sheet["samples"].items():
            med = np.clip(median_rgb(arr, box) * gain, 0, 255)
            lit = np.clip(p85_rgb(arr, box) * gain, 0, 255)
            results[name] = {
                "image": sheet["image"],
                "median": [int(v) for v in med.round()],
                "lit_p85": [int(v) for v in lit.round()],
            }
            if name in CRUSHED:
                results[name]["warning"] = "影で潰れている。ベースカラーに使わないこと。"
            col = (255, 60, 60) if name in CRUSHED else (255, 0, 255)
            d.rectangle(box, outline=col, width=3)
            d.text((box[0], box[1] - 16), name, fill=(255, 240, 90), font=f_small)

        pil.thumbnail((760, 1010))
        panels.append((pil, sheet["image"], f"WB gain = {gain.round(3).tolist()}"))

    # 検証用オーバーレイ（左: 写真とサンプル枠 / 右: 抽出色のスウォッチ）
    sw_w = 430
    W = sum(p.width for p, _, _ in panels) + 30 + sw_w
    H = max(p.height for p, _, _ in panels) + 60
    canvas = Image.new("RGB", (W, H), (20, 20, 22))
    d = ImageDraw.Draw(canvas)
    x = 10
    for pil, name, ginfo in panels:
        canvas.paste(pil, (x, 46))
        d.text((x, 8), name, fill=(255, 235, 120), font=f_big)
        d.text((x, 28), ginfo, fill=(160, 200, 210), font=f_small)
        x += pil.width + 10

    d.text((x + 6, 8), "抽出色（左=中央値 / 右=p85「光の当たった面」）",
           fill=(255, 235, 120), font=f_big)
    y = 50
    for name, r in results.items():
        d.rectangle([x + 6, y, x + 76, y + 30], fill=tuple(r["median"]))
        d.rectangle([x + 80, y, x + 150, y + 30], fill=tuple(r["lit_p85"]))
        c = (255, 120, 120) if "warning" in r else (225, 225, 230)
        d.text((x + 160, y + 1), name + ("  ← 影で潰れ" if "warning" in r else ""),
               fill=c, font=f_small)
        d.text((x + 160, y + 16), f"{tuple(r['median'])}  /  {tuple(r['lit_p85'])}",
               fill=(150, 150, 158), font=f_small)
        y += 36

    OVERLAY.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OVERLAY)
    print(f"overlay -> {OVERLAY}  (必ず目視して枠の位置を確認すること)")
    for name, r in results.items():
        flag = "  ← 影で潰れ" if "warning" in r else ""
        print(f"  {name:18} median={tuple(r['median'])!s:18} lit={tuple(r['lit_p85'])}{flag}")

    YAML_OUT.parent.mkdir(parents=True, exist_ok=True)
    YAML_OUT.write_text(yaml.safe_dump({
        "samples": results,
        "source_images": [f"input/raw_photos/{s['image']}" for s in SHEETS],
        "method": "白壁パッチでWB補正後、各領域の中央値と85パーセンタイル。",
        "supersedes": "config/cat_color_palette.yaml (全色 source: koha_render_b3v2 = 素材アセットのレンダー由来)",
        "notes": [
            "koha のオレンジは明るい橙ではなく深いラスト（錆色）。肩の斑の中心が最も濃い。",
            "黒斑は背面写真では影で (4,4,2) まで潰れる。黒の代表値は正面写真の black_mask を使う。",
            "顔のオレンジ（頬・額）は影で沈むため面積色として使えない。",
        ],
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"yaml -> {YAML_OUT}")


if __name__ == "__main__":
    main()
