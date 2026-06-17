from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INVENTORY_FILE = "output/reports/image_inventory.json"
DEFAULT_SELECTED_DIR = "input/selected_photos"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_QUALITY_SCORE = 3
VALID_VIEW_HINTS = [
    "front",
    "front_left",
    "front_right",
    "side_left",
    "side_right",
    "back",
    "back_left",
    "back_right",
    "top",
    "diagonal",
    "unknown",
]
DEFAULT_REJECT_WARNINGS = [
    "low_resolution",
    "extreme_aspect_ratio",
    "small_file_size",
    "has_alpha_channel",
]
DEFAULT_ALLOW_WARNINGS = ["missing_exif"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select images for 3D generation input.")
    parser.add_argument("--inventory", dest="inventory_file", help="Image inventory JSON path.")
    parser.add_argument("--selected-dir", dest="selected_dir", help="Directory for copied selected photos.")
    parser.add_argument("--output", dest="reports_dir", help="Output reports directory.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Use the MVP fallback selection policy without prompts.",
    )
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
    selection_config = config.get("image_selection") or {}
    if not isinstance(selection_config, dict):
        selection_config = {}

    non_interactive = selection_config.get("non_interactive") or {}
    if not isinstance(non_interactive, dict):
        non_interactive = {}

    return {
        "inventory_file": selection_config.get("inventory_file", DEFAULT_INVENTORY_FILE),
        "selected_dir": selection_config.get("selected_dir", config.get("selected_dir", DEFAULT_SELECTED_DIR)),
        "reports_dir": selection_config.get("reports_dir", config.get("reports_dir", DEFAULT_REPORTS_DIR)),
        "default_quality_score": int(selection_config.get("default_quality_score", DEFAULT_QUALITY_SCORE)),
        "valid_view_hints": list(selection_config.get("valid_view_hints", VALID_VIEW_HINTS)),
        "reject_warnings": list(non_interactive.get("reject_warnings", DEFAULT_REJECT_WARNINGS)),
        "allow_warnings": list(non_interactive.get("allow_warnings", DEFAULT_ALLOW_WARNINGS)),
    }


def load_inventory(inventory_path: Path) -> dict[str, Any]:
    if not inventory_path.exists():
        raise FileNotFoundError(
            f"Inventory file was not found: {inventory_path}. Run Task 1 first: "
            "python scripts/01_inventory_images.py"
        )

    with inventory_path.open("r", encoding="utf-8") as handle:
        inventory = json.load(handle)

    if not isinstance(inventory, dict):
        raise ValueError(f"Inventory file must contain a JSON object: {inventory_path}")

    images = inventory.get("images", [])
    if not isinstance(images, list):
        raise ValueError(f"Inventory field 'images' must be a list: {inventory_path}")

    return inventory


def valid_candidates(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        image
        for image in inventory.get("images", [])
        if isinstance(image, dict) and not image.get("errors")
    ]


def prompt_yes_no(prompt: str) -> bool:
    while True:
        value = input(prompt).strip().lower()
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Enter y or n.")


def prompt_view_hint(valid_view_hints: list[str]) -> str:
    print("View hints:")
    for index, view_hint in enumerate(valid_view_hints, start=1):
        print(f"  {index}. {view_hint}")

    while True:
        value = input("view_hint: ").strip().lower()
        if value.isdigit():
            index = int(value)
            if 1 <= index <= len(valid_view_hints):
                return valid_view_hints[index - 1]
        if value in valid_view_hints:
            return value
        print("Enter a valid view_hint name or number.")


def prompt_quality_score(required: bool) -> int | None:
    while True:
        value = input("quality_score (1-5): ").strip()
        if not value and not required:
            return None
        try:
            score = int(value)
        except ValueError:
            print("Enter an integer from 1 to 5.")
            continue
        if 1 <= score <= 5:
            return score
        print("Enter an integer from 1 to 5.")


def prompt_required_text(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field is required.")


def unique_destination_path(selected_dir: Path, view_hint: str, source_path: Path) -> Path:
    base_name = f"{view_hint}_{source_path.stem}"
    extension = source_path.suffix
    candidate = selected_dir / f"{base_name}{extension}"
    counter = 1
    while candidate.exists():
        candidate = selected_dir / f"{base_name}_{counter:03d}{extension}"
        counter += 1
    return candidate


def copy_selected_image(
    repo_root: Path,
    source_file: str,
    selected_dir: Path,
    view_hint: str,
) -> tuple[str | None, list[str]]:
    errors: list[str] = []
    source_path = resolve_path(repo_root, source_file)
    if not source_path.exists():
        return None, ["source_file_missing"]

    selected_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_destination_path(selected_dir, view_hint, source_path)
    try:
        shutil.copy2(source_path, destination)
    except OSError as exc:
        errors.append(f"copy_failed: {exc.__class__.__name__}")
        return None, errors

    return repo_relative_path(repo_root, destination), errors


def build_manual_selection(
    repo_root: Path,
    image: dict[str, Any],
    selected_dir: Path,
    valid_view_hints: list[str],
) -> dict[str, Any]:
    source_file = image.get("file", "")
    print()
    print(f"Image: {source_file}")
    print(f"  size: {image.get('width')}x{image.get('height')}")
    print(f"  warnings: {', '.join(image.get('warnings', [])) or 'none'}")

    selected = prompt_yes_no("select? (y/n): ")
    view_hint = prompt_view_hint(valid_view_hints)
    quality_score = prompt_quality_score(required=selected)
    reason = prompt_required_text("reason: ") if selected else input("reason: ").strip()
    notes = input("notes: ").strip()

    selected_file = None
    errors: list[str] = []
    source_path = resolve_path(repo_root, source_file)
    if not source_path.exists():
        errors.append("source_file_missing")
        selected = False
    elif selected:
        selected_file, errors = copy_selected_image(repo_root, source_file, selected_dir, view_hint)
        if errors:
            selected = False

    return {
        "source_file": source_file,
        "selected": selected,
        "selected_file": selected_file,
        "view_hint": view_hint,
        "quality_score": quality_score,
        "reason": reason,
        "notes": notes,
        "warnings": list(image.get("warnings", [])),
        "errors": errors,
        "camera_pose_estimate": None,
    }


def non_interactive_decision(
    repo_root: Path,
    image: dict[str, Any],
    selected_dir: Path,
    settings: dict[str, Any],
) -> dict[str, Any]:
    source_file = image.get("file", "")
    warnings = list(image.get("warnings", []))
    reject_warnings = set(settings["reject_warnings"])
    allow_warnings = set(settings["allow_warnings"])
    warning_set = set(warnings)
    source_path = resolve_path(repo_root, source_file)

    selected = False
    reason = "rejected by non-interactive fallback"
    quality_score = None
    selected_file = None
    errors: list[str] = []

    if not source_path.exists():
        errors.append("source_file_missing")
    elif warning_set & reject_warnings:
        reason = "rejected by non-interactive fallback due to warnings"
    elif warning_set - allow_warnings:
        reason = "rejected by non-interactive fallback due to unsupported warnings"
    else:
        selected = True
        quality_score = settings["default_quality_score"]
        reason = "auto-selected by non-interactive fallback"
        selected_file, errors = copy_selected_image(repo_root, source_file, selected_dir, "unknown")
        if errors:
            selected = False
            quality_score = None
            reason = "rejected by non-interactive fallback due to copy error"

    return {
        "source_file": source_file,
        "selected": selected,
        "selected_file": selected_file,
        "view_hint": "unknown",
        "quality_score": quality_score,
        "reason": reason,
        "notes": "",
        "warnings": warnings,
        "errors": errors,
        "camera_pose_estimate": None,
    }


def view_hint_counts(selections: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for selection in selections:
        if not selection["selected"]:
            continue
        view_hint = selection["view_hint"]
        counts[view_hint] = counts.get(view_hint, 0) + 1
    return dict(sorted(counts.items()))


def build_report(
    repo_root: Path,
    inventory_path: Path,
    settings: dict[str, Any],
    selections: list[dict[str, Any]],
) -> dict[str, Any]:
    selected_images = sum(1 for selection in selections if selection["selected"])
    copied_images = sum(1 for selection in selections if selection["selected_file"])

    return {
        "project": "image2sim-framework",
        "task": "Task 1.5 - Image Selection",
        "schema_version": "0.1",
        "source_inventory": repo_relative_path(repo_root, inventory_path),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "candidate_images": len(selections),
            "selected_images": selected_images,
            "rejected_images": len(selections) - selected_images,
            "copied_images": copied_images,
            "view_hint_counts": view_hint_counts(selections),
        },
        "selection_policy": {
            "mode": "manual",
            "valid_view_hints": settings["valid_view_hints"],
        },
        "images": selections,
    }


def write_json_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv_report(path: Path, selections: list[dict[str, Any]]) -> None:
    fieldnames = [
        "source_file",
        "selected",
        "selected_file",
        "view_hint",
        "quality_score",
        "reason",
        "notes",
        "warnings",
        "errors",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for selection in selections:
            row = {field: selection.get(field) for field in fieldnames}
            row["warnings"] = ";".join(selection.get("warnings", []))
            row["errors"] = ";".join(selection.get("errors", []))
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent

    try:
        config = load_config(repo_root, args.config_path)
        settings = settings_from_config(config)

        inventory_value = args.inventory_file or settings["inventory_file"]
        selected_dir_value = args.selected_dir or settings["selected_dir"]
        reports_dir_value = args.reports_dir or settings["reports_dir"]

        inventory_path = resolve_path(repo_root, inventory_value)
        selected_dir = resolve_path(repo_root, selected_dir_value)
        reports_dir = resolve_path(repo_root, reports_dir_value)

        inventory = load_inventory(inventory_path)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, yaml.YAMLError) as exc:
        print(f"ERROR: {exc}")
        return 1

    reports_dir.mkdir(parents=True, exist_ok=True)
    selected_dir.mkdir(parents=True, exist_ok=True)
    candidates = valid_candidates(inventory)

    if args.non_interactive:
        selections = [
            non_interactive_decision(repo_root, image, selected_dir, settings)
            for image in candidates
        ]
    else:
        selections = [
            build_manual_selection(repo_root, image, selected_dir, settings["valid_view_hints"])
            for image in candidates
        ]

    report = build_report(repo_root, inventory_path, settings, selections)
    if args.non_interactive:
        report["selection_policy"]["mode"] = "non-interactive-fallback"

    json_path = reports_dir / "image_selection.json"
    csv_path = reports_dir / "image_selection.csv"
    write_json_report(json_path, report)
    write_csv_report(csv_path, selections)

    print("Image selection")
    print(f"- Source inventory: {repo_relative_path(repo_root, inventory_path)}")
    print(f"- Candidate images: {report['summary']['candidate_images']}")
    print(f"- Selected images: {report['summary']['selected_images']}")
    print(f"- Rejected images: {report['summary']['rejected_images']}")
    print(f"- Copied images: {report['summary']['copied_images']}")
    print(f"- JSON report: {json_path}")
    print(f"- CSV report: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
