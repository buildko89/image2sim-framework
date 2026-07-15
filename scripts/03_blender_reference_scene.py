from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


DEFAULT_SELECTED_DIR = "input/selected_photos"
DEFAULT_MASKS_DIR = "input/masks"
DEFAULT_RAW_3D_DIR = "output/raw_3d"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_OUTPUT_BLEND = "output/raw_3d/cat_reference_scene.blend"
DEFAULT_OUTPUT_GLB = "output/raw_3d/cat_reference_scene.glb"
DEFAULT_SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".webp"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a Blender-first reference scene from selected/masked images.")
    parser.add_argument("--config", dest="config_path", help="Pipeline config YAML path.")
    parser.add_argument("--selected-dir", help="Directory containing selected source photos.")
    parser.add_argument("--masks-dir", help="Directory containing cutouts and masks.")
    parser.add_argument("--output-blend", help="Output .blend path.")
    parser.add_argument("--output-glb", help="Output .glb path.")
    parser.add_argument("--reports-dir", help="Output reports directory.")
    parser.add_argument("--reference-mode", choices=["planes", "empties"], default="planes")
    parser.add_argument("--source", choices=["both", "masks", "selected"], default="both")
    parser.add_argument("--export-glb", action="store_true", help="Also export a GLB reference scene.")
    parser.add_argument("--dry-run", action="store_true", help="Write a plan report without running Blender.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing .blend/.glb outputs.")
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


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
        return
    except ImportError:
        pass

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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
    background_config = config.get("background_removal") or {}
    blender_config = config.get("blender") or {}
    task_config = config.get("blender_reference_scene") or {}
    if not isinstance(background_config, dict):
        background_config = {}
    if not isinstance(blender_config, dict):
        blender_config = {}
    if not isinstance(task_config, dict):
        task_config = {}

    extensions = task_config.get("supported_extensions") or background_config.get(
        "supported_extensions", DEFAULT_SUPPORTED_EXTENSIONS
    )

    return {
        "selected_dir": task_config.get("selected_dir", config.get("selected_dir", DEFAULT_SELECTED_DIR)),
        "masks_dir": task_config.get("masks_dir", background_config.get("masks_dir", DEFAULT_MASKS_DIR)),
        "reports_dir": task_config.get("reports_dir", config.get("reports_dir", DEFAULT_REPORTS_DIR)),
        "output_blend": task_config.get("output_blend", DEFAULT_OUTPUT_BLEND),
        "output_glb": task_config.get("output_glb", DEFAULT_OUTPUT_GLB),
        "blender_path_env": blender_config.get("path_env", "BLENDER_PATH"),
        "supported_extensions": sorted({str(ext).lower() for ext in extensions}),
    }


def find_image_files(directory: Path, supported_extensions: list[str]) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in supported_extensions
        ],
        key=lambda path: str(path).lower(),
    )


def collect_image_records(
    selected_dir: Path,
    masks_dir: Path,
    supported_extensions: list[str],
    source: str,
) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    seen: set[Path] = set()

    sources: list[tuple[str, Path]] = []
    if source in {"both", "masks"}:
        sources.append(("mask", masks_dir))
    if source in {"both", "selected"}:
        sources.append(("selected", selected_dir))

    for role, directory in sources:
        for path in find_image_files(directory, supported_extensions):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            records.append({"path": str(resolved), "role": role})

    return records


def ensure_output_available(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output already exists. Use --overwrite to replace it: {path}")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def build_report(
    repo_root: Path,
    image_records: list[dict[str, str]],
    selected_dir: Path,
    masks_dir: Path,
    output_blend: Path,
    output_glb: Path,
    reference_mode: str,
    source: str,
    dry_run: bool,
) -> dict[str, Any]:
    return {
        "task": "Task 3 - Blender-first Asset Baseline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "source": source,
        "reference_mode": reference_mode,
        "selected_dir": repo_relative_path(repo_root, selected_dir),
        "masks_dir": repo_relative_path(repo_root, masks_dir),
        "output_blend": repo_relative_path(repo_root, output_blend),
        "output_glb": repo_relative_path(repo_root, output_glb),
        "image_count": len(image_records),
        "images": [
            {
                "path": repo_relative_path(repo_root, Path(record["path"])),
                "role": record["role"],
            }
            for record in image_records
        ],
    }


def run_blender(
    blender_path: str,
    blender_script: Path,
    images_json: Path,
    output_blend: Path,
    output_glb: Path,
    reference_mode: str,
    export_glb: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        blender_path,
        "-b",
        "--python",
        str(blender_script),
        "--",
        "--images-json",
        str(images_json),
        "--output-blend",
        str(output_blend),
        "--reference-mode",
        reference_mode,
    ]
    if export_glb:
        command.extend(["--output-glb", str(output_glb), "--export-glb"])

    return subprocess.run(command, check=False, capture_output=True, text=True, timeout=180)


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parent.parent
    load_env_file(repo_root / ".env")
    config = load_config(repo_root, args.config_path)
    settings = settings_from_config(config)

    selected_dir = resolve_path(repo_root, args.selected_dir or settings["selected_dir"])
    masks_dir = resolve_path(repo_root, args.masks_dir or settings["masks_dir"])
    reports_dir = resolve_path(repo_root, args.reports_dir or settings["reports_dir"])
    output_blend = resolve_path(repo_root, args.output_blend or settings["output_blend"])
    output_glb = resolve_path(repo_root, args.output_glb or settings["output_glb"])
    image_records = collect_image_records(selected_dir, masks_dir, settings["supported_extensions"], args.source)

    report = build_report(
        repo_root,
        image_records,
        selected_dir,
        masks_dir,
        output_blend,
        output_glb,
        args.reference_mode,
        args.source,
        args.dry_run,
    )

    plan_path = reports_dir / "blender_reference_scene_plan.json"
    write_json(plan_path, report)

    print("Blender-first reference scene")
    print(f"- Images found: {len(image_records)}")
    print(f"- Reference mode: {args.reference_mode}")
    print(f"- Output blend: {output_blend}")
    print(f"- Output glb: {output_glb if args.export_glb else 'not requested'}")
    print(f"- Plan: {plan_path}")

    if args.dry_run:
        print("- Dry-run: Blender was not executed.")
        return 0

    if not image_records:
        print("ERROR: No selected or masked images were found. Complete Task 1.5 and Task 2 first.")
        return 2

    ensure_output_available(output_blend, args.overwrite)
    if args.export_glb:
        ensure_output_available(output_glb, args.overwrite)

    blender_path = os.environ.get(settings["blender_path_env"], "")
    if not blender_path:
        print(f"ERROR: {settings['blender_path_env']} is not set. Add it to .env or run with --dry-run.")
        return 2
    if not Path(blender_path).exists():
        print(f"ERROR: Blender executable was not found: {blender_path}")
        return 2

    blender_script = repo_root / "blender" / "create_reference_scene.py"
    images_json = reports_dir / "blender_reference_scene_inputs.json"
    write_json(images_json, image_records)

    completed = run_blender(
        blender_path,
        blender_script,
        images_json,
        output_blend,
        output_glb,
        args.reference_mode,
        args.export_glb,
    )

    report["blender"] = {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    report["outputs"] = {
        "blend_exists": output_blend.exists(),
        "glb_exists": output_glb.exists() if args.export_glb else False,
    }
    write_json(reports_dir / "blender_reference_scene.json", report)

    if completed.stdout:
        print(completed.stdout)
    if completed.stderr:
        print(completed.stderr, file=sys.stderr)
    if completed.returncode != 0:
        print(f"ERROR: Blender returned exit code {completed.returncode}.")
        return completed.returncode

    print(f"- Report: {reports_dir / 'blender_reference_scene.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
