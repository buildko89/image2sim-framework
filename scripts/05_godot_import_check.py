from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_INPUT_GLB = "output/clean_3d/cat_clean.glb"
DEFAULT_GODOT_OUTPUT_DIR = "output/godot"
DEFAULT_REPORTS_DIR = "output/reports"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a GLB asset for manual Godot import/display check.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    parser.add_argument("--input", dest="input_glb", help="Input GLB asset path.")
    parser.add_argument("--output-dir", dest="godot_output_dir", help="Directory for Godot-ready copied assets.")
    parser.add_argument("--reports-dir", help="Output reports directory.")
    parser.add_argument("--dry-run", action="store_true", help="Write a plan report without copying files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite an existing copied GLB.")
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


def settings_from_config(config: dict[str, Any]) -> dict[str, str]:
    godot_config = config.get("godot_import_check") or {}
    if not isinstance(godot_config, dict):
        godot_config = {}

    return {
        "input_glb": str(godot_config.get("input_glb", DEFAULT_INPUT_GLB)),
        "godot_output_dir": str(godot_config.get("output_dir", DEFAULT_GODOT_OUTPUT_DIR)),
        "reports_dir": str(godot_config.get("reports_dir", config.get("reports_dir", DEFAULT_REPORTS_DIR))),
    }


def build_report(
    repo_root: Path,
    input_glb: Path,
    copied_glb: Path,
    reports_dir: Path,
    dry_run: bool,
    copied: bool,
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "task": "Task 5 - Godot Import Check",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "input_glb": repo_relative_path(repo_root, input_glb),
        "input_exists": input_glb.exists(),
        "godot_output_dir": repo_relative_path(repo_root, copied_glb.parent),
        "copied_glb": repo_relative_path(repo_root, copied_glb),
        "copied": copied,
        "reports_dir": repo_relative_path(repo_root, reports_dir),
        "manual_check": {
            "guide": "godot/GodotImportGuide.md",
            "expected_action": "Copy or keep the prepared GLB in a Godot project and instantiate it in a scene.",
            "expected_result": "The asset is visible in the Godot viewport, with scale and origin suitable for review.",
        },
        "warnings": warnings,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    config = load_config(repo_root, args.config_path)
    settings = settings_from_config(config)

    input_glb = resolve_path(repo_root, args.input_glb or settings["input_glb"])
    godot_output_dir = resolve_path(repo_root, args.godot_output_dir or settings["godot_output_dir"])
    reports_dir = resolve_path(repo_root, args.reports_dir or settings["reports_dir"])
    copied_glb = godot_output_dir / input_glb.name

    warnings: list[str] = []
    copied = False

    if not input_glb.exists():
        warnings.append("Input GLB does not exist. Complete Task 4 export before running the actual Godot check.")
    elif input_glb.suffix.lower() != ".glb":
        warnings.append("Input asset is not a .glb file. Godot MVP import check expects GLB.")

    if not args.dry_run and input_glb.exists():
        godot_output_dir.mkdir(parents=True, exist_ok=True)
        if copied_glb.exists() and not args.overwrite:
            raise FileExistsError(f"Copied GLB already exists. Use --overwrite to replace it: {copied_glb}")
        shutil.copy2(input_glb, copied_glb)
        copied = True

    report = build_report(repo_root, input_glb, copied_glb, reports_dir, args.dry_run, copied, warnings)
    report_name = "godot_import_check_plan.json" if args.dry_run else "godot_import_check.json"
    report_path = reports_dir / report_name
    write_json(report_path, report)

    print("Godot import check preparation")
    print(f"- Input GLB: {input_glb}")
    print(f"- Input exists: {input_glb.exists()}")
    print(f"- Godot output directory: {godot_output_dir}")
    print(f"- Copied GLB: {copied_glb}")
    print(f"- Copied: {copied}")
    print(f"- Report: {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if args.dry_run:
        print("- Dry-run: no file was copied.")
    return 0 if not warnings or args.dry_run else 2


if __name__ == "__main__":
    raise SystemExit(main())
