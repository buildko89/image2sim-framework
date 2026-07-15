"""P0: raw_photos から koha の参照シートを組む。

左右前後 + 顔 + 尻尾 の6面を1枚にまとめる。以降のフェーズの目視ゲートは、
必ずこのシートと並べて判定する。素材アセットのレンダー（png/reference_asset_renders/）は
目標ではないので、ここには含めない。

  python pipeline_v2/p0_build_reference_sheet.py

向きの規約: 被写体が画面右を向いている写真はその「左半身」がカメラに向く。
（顔の柄で検証済み: koha の左頬は濃い焦茶の面マスク、右頬は黒＋オレンジの混合）
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SRC = Path("input/raw_photos")
OUT = Path("newplan/reference_sheet.png")

# PIL のデフォルトフォントは CJK を持たず、日本語がすべて豆腐になる。
FONT_PATH = "C:/Windows/Fonts/meiryo.ttc"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)

# (ファイル, ラベル, 説明, クロップ(l,t,r,b の割合) or None)
PANELS = [
    ("横.png", "LEFT FLANK  左側面",
     "立位・尻尾を立てる。肩〜背のオレンジ斑、腰の黒斑、白い腹。", None),
    ("1780491195055.jpg", "RIGHT FLANK  右側面",
     "肩と腰にオレンジ斑。前脚・後脚の足首上に黒い斑。やや被写体ブレ。", (0.05, 0.28, 0.75, 0.65)),
    ("1763363798733.jpg", "FRONT  正面",
     "白い胸毛が大きく張り出す。長毛。尻尾のリング柄がよく見える。", None),
    ("1755598074234.jpg", "BACK / TOP  背面・俯瞰",
     "背は白優勢。肩に丸いオレンジ斑、尾根元に黒斑、それを挟む腰のオレンジ。", (0.25, 0.20, 0.75, 0.85)),
    ("1763363798733.jpg", "FACE  顔（柄の左右差）",
     "画面右=猫の左頬: 濃い焦茶の面マスク / 画面左=猫の右頬: 黒＋オレンジ混合。鼻筋に橙の点。", (0.22, 0.13, 0.62, 0.37)),
    ("1763363798733.jpg", "TAIL  尻尾",
     "太いプルーム。タン地に濃褐色のリングが並ぶ。先端は淡い。", (0.62, 0.52, 1.00, 0.66)),
]

CELL_W, CELL_H = 620, 460
COLS = 3
PAD = 12
HDR = 74
LAB = 62


def load(name: str, crop) -> Image.Image:
    im = Image.open(SRC / name).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((int(crop[0] * w), int(crop[1] * h),
                      int(crop[2] * w), int(crop[3] * h)))
    im.thumbnail((CELL_W, CELL_H))
    return im


def wrap(d: ImageDraw.ImageDraw, text: str, width: int, f) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def main() -> None:
    f_title, f_sub, f_lab, f_note, f_src = (font(18), font(13), font(16), font(12), font(11))
    rows = (len(PANELS) + COLS - 1) // COLS
    W = COLS * (CELL_W + PAD) + PAD
    H = HDR + rows * (CELL_H + LAB + PAD) + PAD
    sheet = Image.new("RGB", (W, H), (18, 18, 20))
    d = ImageDraw.Draw(sheet)

    d.text((PAD + 4, 12), "koha 参照シート  —  出典: input/raw_photos のみ",
           fill=(255, 235, 120), font=f_title)
    d.text((PAD + 4, 40),
           "これが唯一の外見目標。素材アセットのレンダー（png/reference_asset_renders/）は目標ではない。",
           fill=(190, 190, 195), font=f_sub)

    for i, (name, label, note, crop) in enumerate(PANELS):
        cx = PAD + (i % COLS) * (CELL_W + PAD)
        cy = HDR + (i // COLS) * (CELL_H + LAB + PAD)
        d.rectangle([cx, cy, cx + CELL_W, cy + CELL_H + LAB], outline=(70, 70, 78))
        im = load(name, crop)
        sheet.paste(im, (cx + (CELL_W - im.width) // 2, cy + (CELL_H - im.height) // 2))
        d.text((cx + 8, cy + CELL_H + 5), label, fill=(255, 235, 120), font=f_lab)
        y = cy + CELL_H + 26
        for line in wrap(d, note, CELL_W - 18, f_note):
            d.text((cx + 8, y), line, fill=(185, 185, 190), font=f_note)
            y += 15
        d.text((cx + CELL_W - 8 - d.textlength(name, font=f_src), cy + 5), name,
               fill=(140, 140, 150), font=f_src)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"{OUT}  {sheet.size}")


if __name__ == "__main__":
    main()
