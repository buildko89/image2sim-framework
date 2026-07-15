from __future__ import annotations

import argparse
import colorsys
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError


DEFAULT_INPUT_DIR = "input/masks"
DEFAULT_OUTPUT = "config/cat_color_palette.yaml"
DEFAULT_REPORT = "output/reports/task80_cat_color_palette.json"
DEFAULT_PREVIEW = "output/reports/task80_cat_color_palette_preview.png"
DEFAULT_NUM_COLORS = 6
DEFAULT_SEED = 0
MAX_PIXELS_PER_IMAGE = 24000
MAX_KMEANS_PIXELS = 180000
ALPHA_THRESHOLD = 200


FALLBACK_PALETTE: dict[str, dict[str, Any]] = {
    "white": {
        "rgb": [0.95, 0.94, 0.91],
        "usage": "chest, belly, paws, nose_bridge",
    },
    "cream": {
        "rgb": [0.86, 0.77, 0.66],
        "usage": "body_base, soft_shadow",
    },
    "warm_brown": {
        "rgb": [0.68, 0.32, 0.08],
        "usage": "calico_patch, ears, back, face_side",
    },
    "dark": {
        "rgb": [0.09, 0.07, 0.06],
        "usage": "calico_patch, tail_stripe, face_side",
    },
    "accent": {
        "rgb": [0.45, 0.22, 0.10],
        "usage": "patch_edge, subtle_variation",
    },
}


@dataclass
class ImageSampleReport:
    file: str
    width: int | None
    height: int | None
    alpha_pixels: int
    accepted_pixels: int
    sampled_pixels: int
    errors: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract a cat color palette from cutout mask images.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--preview", default=DEFAULT_PREVIEW)
    parser.add_argument("--num-colors", type=int, default=DEFAULT_NUM_COLORS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--max-pixels-per-image", type=int, default=MAX_PIXELS_PER_IMAGE)
    return parser.parse_args()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def repo_relative_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path.resolve())


def find_cutouts(input_dir: Path) -> list[Path]:
    return sorted(input_dir.rglob("*_cutout.png"), key=lambda path: str(path).lower())


def brightness(rgb: np.ndarray) -> np.ndarray:
    return rgb[:, 0] * 0.2126 + rgb[:, 1] * 0.7152 + rgb[:, 2] * 0.0722


def saturation(rgb: np.ndarray) -> np.ndarray:
    high = np.max(rgb, axis=1)
    low = np.min(rgb, axis=1)
    return np.divide(high - low, np.maximum(high, 1e-6))


def valid_color_mask(rgb: np.ndarray) -> np.ndarray:
    b = brightness(rgb)
    s = saturation(rgb)
    # Keep white fur, but drop near-black shadows and near-white fully clipped pixels.
    too_dark = b < 0.035
    clipped_white = (b > 0.985) & (s < 0.025)
    return ~(too_dark | clipped_white)


def sample_image_pixels(
    root: Path,
    image_path: Path,
    rng: np.random.Generator,
    max_pixels: int,
) -> tuple[np.ndarray, ImageSampleReport]:
    try:
        with Image.open(image_path) as image:
            rgba = image.convert("RGBA")
            width, height = rgba.size
            data = np.asarray(rgba, dtype=np.float32) / 255.0
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return np.empty((0, 3), dtype=np.float32), ImageSampleReport(
            file=repo_relative_path(root, image_path),
            width=None,
            height=None,
            alpha_pixels=0,
            accepted_pixels=0,
            sampled_pixels=0,
            errors=[f"image_read_error: {exc.__class__.__name__}"],
        )

    alpha_mask = data[:, :, 3] > (ALPHA_THRESHOLD / 255.0)
    alpha_pixels = int(np.count_nonzero(alpha_mask))
    rgb = data[:, :, :3][alpha_mask]
    if rgb.size:
        rgb = rgb[valid_color_mask(rgb)]
    accepted_pixels = int(len(rgb))
    if len(rgb) > max_pixels:
        indices = rng.choice(len(rgb), size=max_pixels, replace=False)
        rgb = rgb[indices]
    return rgb.astype(np.float32), ImageSampleReport(
        file=repo_relative_path(root, image_path),
        width=width,
        height=height,
        alpha_pixels=alpha_pixels,
        accepted_pixels=accepted_pixels,
        sampled_pixels=int(len(rgb)),
        errors=[],
    )


def initial_centers(samples: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    if len(samples) <= k:
        pad_count = k - len(samples)
        if pad_count <= 0:
            return samples.copy()
        pad = np.repeat(samples[-1:], pad_count, axis=0) if len(samples) else np.zeros((pad_count, 3), dtype=np.float32)
        return np.vstack([samples, pad])

    b = brightness(samples)
    quantiles = np.linspace(0.05, 0.95, k)
    centers = []
    for q in quantiles:
        target = np.quantile(b, q)
        idx = int(np.argmin(np.abs(b - target)))
        centers.append(samples[idx])
    centers = np.asarray(centers, dtype=np.float32)

    # Jitter duplicate centers deterministically if quantiles collapsed.
    for index in range(1, len(centers)):
        if np.any(np.linalg.norm(centers[index] - centers[:index], axis=1) < 1e-4):
            centers[index] = samples[int(rng.integers(0, len(samples)))]
    return centers


def kmeans(samples: np.ndarray, k: int, seed: int, iterations: int = 24) -> tuple[np.ndarray, np.ndarray]:
    if len(samples) == 0:
        return np.empty((0, 3), dtype=np.float32), np.empty((0,), dtype=np.int64)
    rng = np.random.default_rng(seed)
    if len(samples) > MAX_KMEANS_PIXELS:
        indices = rng.choice(len(samples), size=MAX_KMEANS_PIXELS, replace=False)
        samples = samples[indices]
    k = max(1, min(k, len(samples)))
    centers = initial_centers(samples, k, rng)
    labels = np.zeros((len(samples),), dtype=np.int64)
    for _ in range(iterations):
        distances = np.sum((samples[:, None, :] - centers[None, :, :]) ** 2, axis=2)
        labels = np.argmin(distances, axis=1)
        next_centers = centers.copy()
        for index in range(k):
            members = samples[labels == index]
            if len(members):
                next_centers[index] = np.mean(members, axis=0)
        if np.allclose(next_centers, centers, atol=1e-5):
            break
        centers = next_centers
    counts = np.bincount(labels, minlength=k)
    order = np.argsort(brightness(centers))
    centers = centers[order]
    remap = {old: new for new, old in enumerate(order)}
    labels = np.asarray([remap[int(label)] for label in labels], dtype=np.int64)
    counts = counts[order]
    return centers, counts


def rgb_to_hsv_tuple(rgb: np.ndarray) -> tuple[float, float, float]:
    return colorsys.rgb_to_hsv(float(rgb[0]), float(rgb[1]), float(rgb[2]))


def cluster_records(centers: np.ndarray, counts: np.ndarray) -> list[dict[str, Any]]:
    records = []
    total = max(1, int(np.sum(counts)))
    for index, center in enumerate(centers):
        h, s, v = rgb_to_hsv_tuple(center)
        records.append(
            {
                "index": index,
                "rgb": [round(float(value), 6) for value in center],
                "hex": rgb_hex(center),
                "count": int(counts[index]) if index < len(counts) else 0,
                "ratio": round(float(counts[index]) / total, 6) if index < len(counts) else 0.0,
                "brightness": round(float(brightness(center.reshape(1, 3))[0]), 6),
                "saturation": round(float(saturation(center.reshape(1, 3))[0]), 6),
                "hue": round(float(h), 6),
                "value": round(float(v), 6),
            }
        )
    return records


def rgb_hex(rgb: np.ndarray | list[float] | tuple[float, float, float]) -> str:
    values = [max(0, min(255, int(round(float(value) * 255)))) for value in rgb]
    return "#{:02x}{:02x}{:02x}".format(*values)


def color_distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def choose_palette(clusters: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    available = [
        {
            **cluster,
            "rgb_array": np.asarray(cluster["rgb"], dtype=np.float32),
        }
        for cluster in clusters
    ]
    selected: dict[str, dict[str, Any]] = {}
    diagnostics: dict[str, Any] = {"assignments": []}

    def assign(name: str, candidates: list[dict[str, Any]], score_key: str, reverse: bool = True) -> None:
        if not candidates:
            fallback = FALLBACK_PALETTE[name]
            selected[name] = {
                "name": name,
                "rgb": fallback["rgb"],
                "usage": fallback["usage"],
                "source": "fallback",
                "cluster_index": None,
                "hex": rgb_hex(fallback["rgb"]),
            }
            diagnostics["assignments"].append({"name": name, "source": "fallback", "reason": "no_candidate"})
            return
        ordered = sorted(candidates, key=lambda item: item[score_key], reverse=reverse)
        chosen = ordered[0]
        selected[name] = {
            "name": name,
            "rgb": [round(float(value), 6) for value in chosen["rgb"]],
            "usage": FALLBACK_PALETTE[name]["usage"],
            "source": "extracted",
            "cluster_index": chosen["index"],
            "hex": chosen["hex"],
        }
        diagnostics["assignments"].append({"name": name, "source": "extracted", "cluster_index": chosen["index"]})

    # White: brightest plausible fur cluster.
    white_candidates = [c for c in available if c["brightness"] >= 0.62]
    for c in white_candidates:
        c["white_score"] = c["brightness"] - c["saturation"] * 0.12
    assign("white", white_candidates, "white_score")

    # Dark: darkest plausible cluster.
    dark_candidates = [c for c in available if c["brightness"] <= 0.40]
    for c in dark_candidates:
        c["dark_score"] = -c["brightness"] + c["saturation"] * 0.08
    assign("dark", dark_candidates, "dark_score")

    # Warm brown: warm hue or red-dominant medium/dark cluster.
    warm_candidates = []
    for c in available:
        rgb = c["rgb_array"]
        hue = c["hue"]
        warm_hue = hue <= 0.16 or hue >= 0.93
        red_dominant = rgb[0] > rgb[1] * 0.90 and rgb[0] > rgb[2] * 1.25
        if c["brightness"] <= 0.68 and (warm_hue or red_dominant):
            c["warm_score"] = (rgb[0] - rgb[2]) + c["saturation"] * 0.35 - abs(c["brightness"] - 0.35) * 0.35
            warm_candidates.append(c)
    assign("warm_brown", warm_candidates, "warm_score")

    # Cream: bright warm cluster distinct from white when possible.
    selected_white = np.asarray(selected["white"]["rgb"], dtype=np.float32)
    cream_candidates = []
    for c in available:
        if c["brightness"] < 0.45 or c["brightness"] > 0.92:
            continue
        if color_distance(c["rgb_array"], selected_white) < 0.08:
            continue
        rgb = c["rgb_array"]
        c["cream_score"] = c["brightness"] - c["saturation"] * 0.18 + max(0.0, float(rgb[0] - rgb[2])) * 0.15
        cream_candidates.append(c)
    assign("cream", cream_candidates, "cream_score")

    # Accent: choose a warm mid-tone not already selected; fallback if all clusters are duplicates.
    used_indices = {value["cluster_index"] for value in selected.values() if value["cluster_index"] is not None}
    accent_candidates = []
    for c in available:
        if c["index"] in used_indices:
            continue
        rgb = c["rgb_array"]
        if c["brightness"] <= 0.62:
            c["accent_score"] = (rgb[0] - rgb[2]) + c["saturation"] * 0.25
            accent_candidates.append(c)
    assign("accent", accent_candidates, "accent_score")

    order = ["white", "cream", "warm_brown", "dark", "accent"]
    return [selected[name] for name in order], diagnostics


def image_thumbnail(path: Path, size: tuple[int, int]) -> Image.Image:
    try:
        with Image.open(path) as image:
            thumb = image.convert("RGBA")
            thumb.thumbnail(size)
            canvas = Image.new("RGBA", size, (245, 245, 245, 255))
            x = (size[0] - thumb.width) // 2
            y = (size[1] - thumb.height) // 2
            canvas.alpha_composite(thumb, (x, y))
            return canvas.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        return Image.new("RGB", size, (220, 220, 220))


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: tuple[int, int, int] = (35, 35, 35)) -> None:
    draw.text(xy, text, fill=fill)


def write_preview(
    root: Path,
    preview_path: Path,
    source_images: list[Path],
    clusters: list[dict[str, Any]],
    palette: list[dict[str, Any]],
) -> None:
    width = 1200
    thumb_size = (150, 115)
    margin = 24
    row_gap = 18
    swatch_w = 120
    swatch_h = 58
    thumbnails = source_images[:6]
    height = 760
    image = Image.new("RGB", (width, height), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    draw_text(draw, (margin, 18), "Task 80 Cat Color Palette Preview")

    y = 56
    draw_text(draw, (margin, y), "Source cutouts")
    y += 24
    x = margin
    for path in thumbnails:
        thumb = image_thumbnail(path, thumb_size)
        image.paste(thumb, (x, y))
        label = repo_relative_path(root, path).split("/")[-1]
        draw_text(draw, (x, y + thumb_size[1] + 4), label[:24])
        x += thumb_size[0] + 28

    y += thumb_size[1] + 48
    draw_text(draw, (margin, y), "Extracted clusters")
    y += 24
    x = margin
    for cluster in clusters[:10]:
        color = tuple(max(0, min(255, int(round(value * 255)))) for value in cluster["rgb"])
        draw.rectangle((x, y, x + swatch_w, y + swatch_h), fill=color, outline=(80, 80, 80))
        text_fill = (255, 255, 255) if cluster["brightness"] < 0.42 else (30, 30, 30)
        draw_text(draw, (x + 6, y + 6), cluster["hex"], fill=text_fill)
        draw_text(draw, (x + 6, y + 24), f"{cluster['ratio']:.2%}", fill=text_fill)
        x += swatch_w + 16
        if x + swatch_w > width - margin:
            x = margin
            y += swatch_h + 36

    y += swatch_h + 46
    draw_text(draw, (margin, y), "Final palette")
    y += 24
    x = margin
    for entry in palette:
        color = tuple(max(0, min(255, int(round(value * 255)))) for value in entry["rgb"])
        draw.rectangle((x, y, x + 170, y + 78), fill=color, outline=(80, 80, 80))
        avg = sum(color) / 3
        text_fill = (255, 255, 255) if avg < 108 else (30, 30, 30)
        draw_text(draw, (x + 8, y + 6), entry["name"], fill=text_fill)
        draw_text(draw, (x + 8, y + 25), entry["hex"], fill=text_fill)
        draw_text(draw, (x + 8, y + 44), entry["source"], fill=text_fill)
        x += 190

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(preview_path)


def build_output_yaml(palette: list[dict[str, Any]], source_images: list[str], num_colors: int, seed: int) -> dict[str, Any]:
    return {
        "palette": [
            {
                "name": entry["name"],
                "rgb": entry["rgb"],
                "usage": entry["usage"],
                "source": entry["source"],
            }
            for entry in palette
        ],
        "source_images": source_images,
        "num_colors": num_colors,
        "seed": seed,
    }


def main() -> int:
    args = parse_args()
    root = repo_root()
    input_dir = resolve_path(root, args.input_dir)
    output_path = resolve_path(root, args.output)
    report_path = resolve_path(root, args.report)
    preview_path = resolve_path(root, args.preview)
    rng = np.random.default_rng(args.seed)

    image_paths = find_cutouts(input_dir)
    samples_by_image = []
    image_reports = []
    for image_path in image_paths:
        samples, sample_report = sample_image_pixels(root, image_path, rng, args.max_pixels_per_image)
        if len(samples):
            samples_by_image.append(samples)
        image_reports.append(sample_report)

    all_samples = np.vstack(samples_by_image) if samples_by_image else np.empty((0, 3), dtype=np.float32)
    centers, counts = kmeans(all_samples, max(1, int(args.num_colors)), args.seed)
    clusters = cluster_records(centers, counts)
    palette, diagnostics = choose_palette(clusters)
    source_images = [repo_relative_path(root, path) for path in image_paths]

    output_data = build_output_yaml(palette, source_images, int(args.num_colors), int(args.seed))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(output_data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    report = {
        "task": "Task 80: Cat Color Palette Extraction",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": repo_relative_path(root, input_dir),
        "output": repo_relative_path(root, output_path),
        "preview": repo_relative_path(root, preview_path),
        "num_colors": int(args.num_colors),
        "seed": int(args.seed),
        "summary": {
            "cutout_images_found": len(image_paths),
            "valid_images": sum(1 for item in image_reports if not item.errors),
            "sampled_pixels": int(len(all_samples)),
            "clusters": len(clusters),
            "fallback_palette_entries": sum(1 for entry in palette if entry["source"] == "fallback"),
        },
        "palette": palette,
        "clusters": clusters,
        "assignment_diagnostics": diagnostics,
        "images": [item.__dict__ for item in image_reports],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    write_preview(root, preview_path, image_paths, clusters, palette)

    print("Task 80 cat color palette extraction")
    print(f"- Input cutouts: {len(image_paths)}")
    print(f"- Sampled pixels: {len(all_samples)}")
    print(f"- Palette: {output_path}")
    print(f"- Report: {report_path}")
    print(f"- Preview: {preview_path}")
    for entry in palette:
        print(f"  - {entry['name']}: {entry['hex']} ({entry['source']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
