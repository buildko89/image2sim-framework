"""koha9 の目視ゲート素材: 配色2.pdf のリファレンス（右パネル）とモデルを5面で並べる。

    python pipeline_v2/p3_compare_haishoku2.py [--prefix p3k9]

配色2.pdf は「左=glb / 右=リファレンス」の対比。ここではリファレンス側だけを切り出し、
同じ向きのレンダーと並べる。向きの対応（罠⑬: 頭の向きで決める）:
  p1 上面   -> top   （どちらも頭が画面下・画面右が +X）
  p2 正面   -> front / head_front
  p3 後面   -> back
  p4 後側面 -> right （頭が画面左・尾が画面右）
  p5 左側面 -> left  （頭が画面右・尾が画面左）
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parent.parent
SHOTS = REPO / "output_v2/reports/p1_shots"
PDF = REPO / "input/配色2.pdf"
FONT = "C:/Windows/Fonts/meiryo.ttc"

# (ページ番号, リファレンス側のクロップ l,t,r,b（1684x1191 基準の割合）, レンダー, ラベル)
ROWS = [
    (1, (0.485, 0.09, 0.99, 0.91), "{p}_idle1_t15_top.png", "p1 上面: 背中のロゼット / 頭頂"),
    (2, (0.48, 0.09, 0.99, 0.91), "{p}_head_front.png", "p2 正面: 顔の柄（+X=画面右がこげ茶優勢）"),
    (3, (0.44, 0.09, 0.99, 0.91), "{p}_idle1_t15_back.png", "p3 後面: 腰〜腿のフォーン / 下脚クリーム"),
    (4, (0.53, 0.19, 0.99, 0.82), "{p}_idle1_t15_right.png", "p4 後側面: 白地に独立斑"),
    (5, (0.56, 0.13, 0.99, 0.70), "{p}_idle1_t15_left.png", "p5 左側面: 白地に独立斑 / かかとの黒斑"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="p3k9")
    a = ap.parse_args()

    pdf = pdfium.PdfDocument(PDF)
    C = 480
    out = Image.new("RGB", (C * 2 + 30, (C + 40) * len(ROWS) + 50, ), (18, 18, 20))
    d = ImageDraw.Draw(out)
    ft, fs = ImageFont.truetype(FONT, 19), ImageFont.truetype(FONT, 13)
    d.text((10, 6), f"koha9 vs 配色2.pdf — 左=リファレンス / 右=モデル {a.prefix}",
           fill=(255, 235, 120), font=ft)

    for i, (pageno, crop, shot, label) in enumerate(ROWS):
        page = pdf[pageno - 1]
        im = page.render(scale=2.0).to_pil().convert("RGB")
        w, h = im.size
        ref = im.crop((int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h)))
        ref.thumbnail((C, C))
        mdl = Image.open(SHOTS / shot.format(p=a.prefix)).convert("RGB")
        mdl.thumbnail((C, C))
        y = 50 + i * (C + 40)
        d.text((10, y), label, fill=(255, 235, 120), font=fs)
        out.paste(ref, (10 + (C - ref.width) // 2, y + 20 + (C - ref.height) // 2))
        out.paste(mdl, (C + 20 + (C - mdl.width) // 2, y + 20 + (C - mdl.height) // 2))

    dst = REPO / f"output_v2/reports/{a.prefix}_vs_haishoku2.png"
    out.save(dst)
    print(f"-> {dst}  {out.size}  (必ず目視すること)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
