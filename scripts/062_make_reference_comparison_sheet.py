from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "output" / "reports" / "task62_tripo_reference_comparison_sheet.jpg"

ITEMS = [
    ("Real side", REPO_ROOT / "input" / "raw_photos" / "横.png"),
    ("Current rigged side", REPO_ROOT / "output" / "reports" / "cat_fluffy_shortleg_side_preview.png"),
    ("Tripo v2.5 side", REPO_ROOT / "output" / "reports" / "task61_tripo_v25_side_preview.png"),
    ("Real front", REPO_ROOT / "input" / "selected_photos" / "reference_front_face_1763363798733.jpg"),
    ("Current rigged front", REPO_ROOT / "output" / "reports" / "cat_fluffy_shortleg_front_preview.png"),
    ("Tripo v2.5 front", REPO_ROOT / "output" / "reports" / "task61_tripo_v25_front_preview.png"),
]


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/meiryo.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def fit_image(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (238, 238, 238))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.paste(image, (x, y))
    return canvas


def main() -> int:
    cell_w, cell_h = 520, 360
    label_h = 44
    margin = 24
    gap = 18
    cols = 3
    rows = 2
    width = margin * 2 + cols * cell_w + (cols - 1) * gap
    height = margin * 2 + rows * (cell_h + label_h) + (rows - 1) * gap

    sheet = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(sheet)
    font = load_font(22)
    small_font = load_font(16)

    for index, (label, path) in enumerate(ITEMS):
        row = index // cols
        col = index % cols
        x = margin + col * (cell_w + gap)
        y = margin + row * (cell_h + label_h + gap)
        draw.rectangle((x, y, x + cell_w, y + label_h), fill=(32, 36, 40))
        draw.text((x + 12, y + 10), label, fill=(255, 255, 255), font=font)
        image = fit_image(path, (cell_w, cell_h))
        sheet.paste(image, (x, y + label_h))
        draw.rectangle((x, y, x + cell_w, y + label_h + cell_h), outline=(170, 170, 170), width=1)

    note = "Purpose: decide which visual traits from Tripo v2.5 should influence the rigged cat model."
    draw.text((margin, height - margin + 2), note, fill=(70, 70, 70), font=small_font)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUTPUT, quality=92)
    print(f"Wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
