from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from PIL import Image, UnidentifiedImageError


DEFAULT_SELECTED_DIR = "input/selected_photos"
DEFAULT_MASKS_DIR = "input/masks"
DEFAULT_REVIEW_DIR = "input/masks_review"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_MODEL_CACHE_DIR = "output/model_cache/u2net"
DEFAULT_SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
DEFAULT_MODEL = "u2net"
DEFAULT_MIN_FOREGROUND_COVERAGE = 0.05
DEFAULT_MAX_FOREGROUND_COVERAGE = 0.95
U2NET_MODELS = {
    "u2net": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx",
        "known_hash": "md5:60024c5c889badc19c04ad937298a77b",
    },
    "u2netp": {
        "url": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx",
        "known_hash": "md5:8e83ca70e441ab06c318d82300c84806",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Remove image backgrounds and create mask review outputs.")
    parser.add_argument("--input", dest="selected_dir", help="Directory containing selected source photos.")
    parser.add_argument("--masks-dir", dest="masks_dir", help="Directory for transparent cutouts and masks.")
    parser.add_argument("--review-dir", dest="review_dir", help="Directory for mask review images.")
    parser.add_argument("--output", dest="reports_dir", help="Output reports directory.")
    parser.add_argument("--model-cache-dir", dest="model_cache_dir", help="Directory for downloaded ONNX models.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    parser.add_argument("--model", dest="model_name", help="rembg model name.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing generated files.")
    return parser.parse_args()


def resolve_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return repo_root / path


def repo_relative_path(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return str(path.resolve())


def load_config(repo_root: Path, config_path: str | None) -> dict[str, Any]:
    if not config_path:
        return {}

    path = resolve_path(repo_root, config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file was not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    return data


def settings_from_config(config: dict[str, Any]) -> dict[str, Any]:
    removal_config = config.get("background_removal") or {}
    if not isinstance(removal_config, dict):
        removal_config = {}

    extensions = removal_config.get("supported_extensions", DEFAULT_SUPPORTED_EXTENSIONS)
    normalized_extensions = sorted({str(ext).lower() for ext in extensions})

    return {
        "selected_dir": removal_config.get("selected_dir", config.get("selected_dir", DEFAULT_SELECTED_DIR)),
        "masks_dir": removal_config.get("masks_dir", DEFAULT_MASKS_DIR),
        "review_dir": removal_config.get("review_dir", DEFAULT_REVIEW_DIR),
        "reports_dir": removal_config.get("reports_dir", config.get("reports_dir", DEFAULT_REPORTS_DIR)),
        "model_cache_dir": removal_config.get("model_cache_dir", DEFAULT_MODEL_CACHE_DIR),
        "supported_extensions": normalized_extensions,
        "model_name": str(removal_config.get("model_name", DEFAULT_MODEL)),
        "min_foreground_coverage": float(
            removal_config.get("min_foreground_coverage", DEFAULT_MIN_FOREGROUND_COVERAGE)
        ),
        "max_foreground_coverage": float(
            removal_config.get("max_foreground_coverage", DEFAULT_MAX_FOREGROUND_COVERAGE)
        ),
    }


def find_image_files(input_dir: Path, supported_extensions: list[str]) -> list[Path]:
    if not input_dir.exists():
        return []

    return sorted(
        [
            path
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in supported_extensions
        ],
        key=lambda path: str(path).lower(),
    )


def unique_output_path(directory: Path, stem: str, suffix: str, extension: str, overwrite: bool) -> Path:
    candidate = directory / f"{stem}_{suffix}{extension}"
    if overwrite or not candidate.exists():
        return candidate

    counter = 1
    while True:
        candidate = directory / f"{stem}_{suffix}_{counter:03d}{extension}"
        if not candidate.exists():
            return candidate
        counter += 1


def checkerboard(size: tuple[int, int], cell_size: int = 24) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, (238, 238, 238))
    dark = (190, 190, 190)

    for y in range(0, height, cell_size):
        for x in range(0, width, cell_size):
            if ((x // cell_size) + (y // cell_size)) % 2:
                image.paste(dark, (x, y, min(x + cell_size, width), min(y + cell_size, height)))

    return image


def create_review_image(cutout: Image.Image) -> Image.Image:
    rgba = cutout.convert("RGBA")
    background = checkerboard(rgba.size)
    background.paste(rgba, mask=rgba.getchannel("A"))
    return background


def alpha_metrics(alpha: Image.Image) -> dict[str, Any]:
    width, height = alpha.size
    total_pixels = width * height
    histogram = alpha.histogram()
    transparent_pixels = sum(histogram[:6])
    opaque_pixels = sum(histogram[250:])
    foreground_pixels = total_pixels - histogram[0]
    bbox = alpha.getbbox()

    return {
        "width": width,
        "height": height,
        "foreground_coverage": round(foreground_pixels / total_pixels, 6) if total_pixels else 0,
        "opaque_coverage": round(opaque_pixels / total_pixels, 6) if total_pixels else 0,
        "transparent_coverage": round(transparent_pixels / total_pixels, 6) if total_pixels else 0,
        "alpha_bbox": list(bbox) if bbox else None,
    }


def coverage_warnings(metrics: dict[str, Any], settings: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    coverage = metrics["foreground_coverage"]
    if coverage < settings["min_foreground_coverage"]:
        warnings.append("low_foreground_coverage")
    if coverage > settings["max_foreground_coverage"]:
        warnings.append("high_foreground_coverage")
    if not metrics["alpha_bbox"]:
        warnings.append("empty_alpha_mask")
    return warnings


class U2NetBackgroundRemover:
    def __init__(self, model_name: str, model_cache_dir: Path) -> None:
        try:
            import numpy as np
            import onnxruntime as ort
            import pooch
        except ImportError as exc:
            raise RuntimeError(
                "Background removal dependencies are not installed. "
                "Install dependencies with: pip install -r requirements.txt"
            ) from exc

        if model_name not in U2NET_MODELS:
            supported = ", ".join(sorted(U2NET_MODELS))
            raise ValueError(f"Unsupported background removal model '{model_name}'. Supported models: {supported}")

        self.np = np
        model = U2NET_MODELS[model_name]
        model_path = pooch.retrieve(
            model["url"],
            known_hash=None if os.getenv("MODEL_CHECKSUM_DISABLED") else model["known_hash"],
            fname=f"{model_name}.onnx",
            path=model_cache_dir,
            progressbar=True,
        )
        self.session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def remove(self, image: Image.Image) -> Image.Image:
        source = image.convert("RGBA")
        mask = self.predict_mask(source)
        empty = Image.new("RGBA", source.size, 0)
        return Image.composite(source, empty, mask)

    def predict_mask(self, image: Image.Image) -> Image.Image:
        np = self.np
        rgb = image.convert("RGB").resize((320, 320), Image.Resampling.LANCZOS)
        array = np.asarray(rgb, dtype=np.float32)
        array = array / max(float(np.max(array)), 1e-6)
        normalized = np.zeros((320, 320, 3), dtype=np.float32)
        normalized[:, :, 0] = (array[:, :, 0] - 0.485) / 0.229
        normalized[:, :, 1] = (array[:, :, 1] - 0.456) / 0.224
        normalized[:, :, 2] = (array[:, :, 2] - 0.406) / 0.225
        tensor = normalized.transpose((2, 0, 1))
        output = self.session.run(None, {self.input_name: np.expand_dims(tensor, 0)})[0]

        pred = output[:, 0, :, :]
        maximum = np.max(pred)
        minimum = np.min(pred)
        denominator = maximum - minimum
        if denominator == 0:
            mask_array = np.zeros(pred.shape[-2:], dtype=np.uint8)
        else:
            pred = (pred - minimum) / denominator
            mask_array = (np.squeeze(pred).clip(0, 1) * 255).astype(np.uint8)

        mask = Image.fromarray(mask_array)
        return mask.resize(image.size, Image.Resampling.LANCZOS)


def load_background_remover(model_name: str, model_cache_dir: Path) -> U2NetBackgroundRemover:
    try:
        return U2NetBackgroundRemover(model_name, model_cache_dir)
    except ValueError:
        raise


def process_image(
    repo_root: Path,
    image_path: Path,
    masks_dir: Path,
    review_dir: Path,
    settings: dict[str, Any],
    remover: U2NetBackgroundRemover,
    overwrite: bool,
) -> dict[str, Any]:
    stem = image_path.stem
    cutout_path = unique_output_path(masks_dir, stem, "cutout", ".png", overwrite)
    mask_path = unique_output_path(masks_dir, stem, "mask", ".png", overwrite)
    review_path = unique_output_path(review_dir, stem, "review", ".jpg", overwrite)

    record: dict[str, Any] = {
        "source_file": repo_relative_path(repo_root, image_path),
        "source_filename": image_path.name,
        "cutout_file": None,
        "mask_file": None,
        "review_file": None,
        "model_name": settings["model_name"],
        "width": None,
        "height": None,
        "foreground_coverage": None,
        "opaque_coverage": None,
        "transparent_coverage": None,
        "alpha_bbox": None,
        "warnings": [],
        "errors": [],
    }

    try:
        with Image.open(image_path) as source:
            source.load()
            cutout = remover.remove(source).convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        record["errors"].append(f"image_processing_error: {exc.__class__.__name__}")
        return record

    alpha = cutout.getchannel("A")
    metrics = alpha_metrics(alpha)
    record.update(metrics)
    record["warnings"] = coverage_warnings(metrics, settings)

    masks_dir.mkdir(parents=True, exist_ok=True)
    review_dir.mkdir(parents=True, exist_ok=True)
    cutout.save(cutout_path)
    alpha.save(mask_path)
    create_review_image(cutout).save(review_path, quality=92)

    record["cutout_file"] = repo_relative_path(repo_root, cutout_path)
    record["mask_file"] = repo_relative_path(repo_root, mask_path)
    record["review_file"] = repo_relative_path(repo_root, review_path)
    return record


def build_report(
    repo_root: Path,
    selected_dir: Path,
    masks_dir: Path,
    review_dir: Path,
    settings: dict[str, Any],
    images: list[dict[str, Any]],
) -> dict[str, Any]:
    failed_images = sum(1 for image in images if image["errors"])
    warning_count = sum(len(image["warnings"]) for image in images)

    return {
        "project": "image2sim-framework",
        "task": "Task 2 - Background Removal",
        "schema_version": "0.1",
        "selected_dir": repo_relative_path(repo_root, selected_dir),
        "masks_dir": repo_relative_path(repo_root, masks_dir),
        "review_dir": repo_relative_path(repo_root, review_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settings": {
            "model_name": settings["model_name"],
            "model_cache_dir": settings["model_cache_dir"],
            "min_foreground_coverage": settings["min_foreground_coverage"],
            "max_foreground_coverage": settings["max_foreground_coverage"],
        },
        "summary": {
            "input_images": len(images),
            "processed_images": len(images) - failed_images,
            "failed_images": failed_images,
            "warning_count": warning_count,
        },
        "images": images,
    }


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv_report(path: Path, images: list[dict[str, Any]]) -> None:
    fieldnames = [
        "source_file",
        "cutout_file",
        "mask_file",
        "review_file",
        "model_name",
        "width",
        "height",
        "foreground_coverage",
        "opaque_coverage",
        "transparent_coverage",
        "alpha_bbox",
        "warnings",
        "errors",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for image in images:
            row = {field: image.get(field) for field in fieldnames}
            row["alpha_bbox"] = json.dumps(row["alpha_bbox"]) if row["alpha_bbox"] else ""
            row["warnings"] = ";".join(image.get("warnings", []))
            row["errors"] = ";".join(image.get("errors", []))
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent

    try:
        config = load_config(repo_root, args.config_path)
        settings = settings_from_config(config)
        if args.model_name:
            settings["model_name"] = args.model_name

        selected_dir = resolve_path(repo_root, args.selected_dir or settings["selected_dir"])
        masks_dir = resolve_path(repo_root, args.masks_dir or settings["masks_dir"])
        review_dir = resolve_path(repo_root, args.review_dir or settings["review_dir"])
        reports_dir = resolve_path(repo_root, args.reports_dir or settings["reports_dir"])
        model_cache_dir = resolve_path(repo_root, args.model_cache_dir or settings["model_cache_dir"])
        settings["model_cache_dir"] = repo_relative_path(repo_root, model_cache_dir)
    except (FileNotFoundError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 1

    reports_dir.mkdir(parents=True, exist_ok=True)
    image_files = find_image_files(selected_dir, settings["supported_extensions"])
    if image_files:
        try:
            remover = load_background_remover(settings["model_name"], model_cache_dir)
        except (RuntimeError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 1

        images = [
            process_image(
                repo_root,
                image_path,
                masks_dir,
                review_dir,
                settings,
                remover,
                args.overwrite,
            )
            for image_path in image_files
        ]
    else:
        images = []
    report = build_report(repo_root, selected_dir, masks_dir, review_dir, settings, images)

    json_path = reports_dir / "background_removal.json"
    csv_path = reports_dir / "background_removal.csv"
    write_json_report(json_path, report)
    write_csv_report(csv_path, images)

    print("Background removal")
    print(f"- Selected directory: {repo_relative_path(repo_root, selected_dir)}")
    print(f"- Input images: {report['summary']['input_images']}")
    print(f"- Processed images: {report['summary']['processed_images']}")
    print(f"- Failed images: {report['summary']['failed_images']}")
    print(f"- Warnings: {report['summary']['warning_count']}")
    print(f"- Masks directory: {repo_relative_path(repo_root, masks_dir)}")
    print(f"- Review directory: {repo_relative_path(repo_root, review_dir)}")
    print(f"- JSON report: {json_path}")
    print(f"- CSV report: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
