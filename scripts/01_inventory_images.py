from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from PIL import ExifTags, Image, UnidentifiedImageError


DEFAULT_INPUT_DIR = "input/raw_photos"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_SUPPORTED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
DEFAULT_LOW_RESOLUTION_THRESHOLD = 1024
DEFAULT_SMALL_FILE_SIZE_THRESHOLD_BYTES = 100000
DEFAULT_MIN_ASPECT_RATIO = 0.5
DEFAULT_MAX_ASPECT_RATIO = 2.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an image inventory report.")
    parser.add_argument("--input", dest="input_dir", help="Input image directory.")
    parser.add_argument("--output", dest="output_dir", help="Output reports directory.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    return parser.parse_args()


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


def settings_from_config(config: dict[str, Any]) -> dict[str, Any]:
    inventory_config = config.get("image_inventory") or {}
    if not isinstance(inventory_config, dict):
        inventory_config = {}

    extensions = inventory_config.get("supported_extensions", DEFAULT_SUPPORTED_EXTENSIONS)
    normalized_extensions = sorted({str(ext).lower() for ext in extensions})

    return {
        "input_dir": config.get("input_dir", DEFAULT_INPUT_DIR),
        "reports_dir": config.get("reports_dir", DEFAULT_REPORTS_DIR),
        "supported_extensions": normalized_extensions,
        "low_resolution_threshold": int(
            inventory_config.get("low_resolution_threshold", DEFAULT_LOW_RESOLUTION_THRESHOLD)
        ),
        "small_file_size_threshold_bytes": int(
            inventory_config.get(
                "small_file_size_threshold_bytes",
                DEFAULT_SMALL_FILE_SIZE_THRESHOLD_BYTES,
            )
        ),
        "min_aspect_ratio": float(inventory_config.get("min_aspect_ratio", DEFAULT_MIN_ASPECT_RATIO)),
        "max_aspect_ratio": float(inventory_config.get("max_aspect_ratio", DEFAULT_MAX_ASPECT_RATIO)),
    }


def exif_key_names(image: Image.Image) -> list[str]:
    exif = image.getexif()
    names = []
    for key in exif.keys():
        names.append(str(ExifTags.TAGS.get(key, key)))
    return sorted(names)


def collect_image_metadata(
    repo_root: Path,
    image_path: Path,
    settings: dict[str, Any],
) -> dict[str, Any]:
    stat = image_path.stat()
    extension = image_path.suffix.lower()
    record: dict[str, Any] = {
        "file": repo_relative_path(repo_root, image_path),
        "absolute_path": str(image_path.resolve()),
        "filename": image_path.name,
        "extension": extension,
        "file_size_bytes": stat.st_size,
        "width": None,
        "height": None,
        "aspect_ratio": None,
        "mode": None,
        "has_exif": False,
        "exif_keys": [],
        "warnings": [],
        "errors": [],
    }

    try:
        with Image.open(image_path) as image:
            image.load()
            width, height = image.size
            aspect_ratio = round(width / height, 4) if height else None
            exif_keys = exif_key_names(image)

            record.update(
                {
                    "width": width,
                    "height": height,
                    "aspect_ratio": aspect_ratio,
                    "mode": image.mode,
                    "has_exif": bool(exif_keys),
                    "exif_keys": exif_keys,
                }
            )
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        record["errors"].append(f"image_read_error: {exc.__class__.__name__}")
        return record

    if record["width"] < settings["low_resolution_threshold"] or record["height"] < settings["low_resolution_threshold"]:
        record["warnings"].append("low_resolution")

    if (
        record["aspect_ratio"] is not None
        and (
            record["aspect_ratio"] < settings["min_aspect_ratio"]
            or record["aspect_ratio"] > settings["max_aspect_ratio"]
        )
    ):
        record["warnings"].append("extreme_aspect_ratio")

    if record["file_size_bytes"] < settings["small_file_size_threshold_bytes"]:
        record["warnings"].append("small_file_size")

    if record["mode"] in {"RGBA", "LA"}:
        record["warnings"].append("has_alpha_channel")

    if not record["has_exif"]:
        record["warnings"].append("missing_exif")

    return record


def find_image_files(input_dir: Path, supported_extensions: list[str]) -> tuple[int, list[Path]]:
    all_files = [path for path in input_dir.rglob("*") if path.is_file()]
    image_files = [
        path for path in all_files if path.suffix.lower() in supported_extensions
    ]
    return len(all_files), sorted(image_files, key=lambda path: str(path).lower())


def write_json_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv_report(report_path: Path, images: list[dict[str, Any]]) -> None:
    fieldnames = [
        "file",
        "filename",
        "extension",
        "file_size_bytes",
        "width",
        "height",
        "aspect_ratio",
        "mode",
        "has_exif",
        "warnings",
        "errors",
    ]
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for image in images:
            row = {field: image.get(field) for field in fieldnames}
            row["warnings"] = ";".join(image.get("warnings", []))
            row["errors"] = ";".join(image.get("errors", []))
            writer.writerow(row)


def build_report(
    repo_root: Path,
    input_dir: Path,
    images: list[dict[str, Any]],
    total_files_scanned: int,
) -> dict[str, Any]:
    invalid_images = sum(1 for image in images if image["errors"])
    warning_count = sum(len(image["warnings"]) for image in images)

    return {
        "project": "image2sim-framework",
        "task": "Task 1 - Image Inventory",
        "schema_version": "0.1",
        "input_dir": repo_relative_path(repo_root, input_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_files_scanned": total_files_scanned,
            "image_files_found": len(images),
            "valid_images": len(images) - invalid_images,
            "invalid_images": invalid_images,
            "warning_count": warning_count,
        },
        "images": images,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent

    config = load_config(repo_root, args.config_path)
    settings = settings_from_config(config)

    input_dir_value = args.input_dir or settings["input_dir"]
    reports_dir_value = args.output_dir or settings["reports_dir"]
    input_dir = resolve_path(repo_root, input_dir_value)
    reports_dir = resolve_path(repo_root, reports_dir_value)

    input_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    total_files_scanned, image_files = find_image_files(input_dir, settings["supported_extensions"])
    images = [
        collect_image_metadata(repo_root, image_path, settings)
        for image_path in image_files
    ]
    report = build_report(repo_root, input_dir, images, total_files_scanned)

    json_path = reports_dir / "image_inventory.json"
    csv_path = reports_dir / "image_inventory.csv"
    write_json_report(json_path, report)
    write_csv_report(csv_path, images)

    print("Image inventory")
    print(f"- Input directory: {repo_relative_path(repo_root, input_dir)}")
    print(f"- Total files scanned: {report['summary']['total_files_scanned']}")
    print(f"- Image files found: {report['summary']['image_files_found']}")
    print(f"- Valid images: {report['summary']['valid_images']}")
    print(f"- Invalid images: {report['summary']['invalid_images']}")
    print(f"- Warnings: {report['summary']['warning_count']}")
    print(f"- JSON report: {json_path}")
    print(f"- CSV report: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
