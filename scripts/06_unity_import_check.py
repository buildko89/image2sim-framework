from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_GLB = "output/clean_3d/cat_shape_pass.glb"
DEFAULT_INPUT_FBX = "output/clean_3d/cat_shape_pass.fbx"
DEFAULT_OUTPUT_DIR = "output/unity"
DEFAULT_REPORTS_DIR = "output/reports"
DEFAULT_UNITY_PROJECT = "unity/CatImportCheck"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage animated cat assets for Unity import/playback check.")
    parser.add_argument("--input-glb", default=DEFAULT_INPUT_GLB)
    parser.add_argument("--input-fbx", default=DEFAULT_INPUT_FBX)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR)
    parser.add_argument("--unity-project", default=DEFAULT_UNITY_PROJECT)
    parser.add_argument("--copy-to-project", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
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


def copy_file(source: Path, destination: Path, overwrite: bool, dry_run: bool) -> bool:
    if dry_run:
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists. Use --overwrite to replace it: {destination}")
    shutil.copy2(source, destination)
    return True


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_glb = resolve_path(repo_root, args.input_glb)
    input_fbx = resolve_path(repo_root, args.input_fbx)
    output_dir = resolve_path(repo_root, args.output_dir)
    reports_dir = resolve_path(repo_root, args.reports_dir)
    unity_project = resolve_path(repo_root, args.unity_project)
    project_assets_dir = unity_project / "Assets" / "Image2Sim"

    staged = {
        input_glb: output_dir / input_glb.name,
        input_fbx: output_dir / input_fbx.name,
    }
    project_targets = {
        input_glb: project_assets_dir / input_glb.name,
        input_fbx: project_assets_dir / input_fbx.name,
    }

    warnings: list[str] = []
    copied: list[str] = []
    project_copied: list[str] = []
    for source in staged:
        if not source.exists():
            warnings.append(f"Input asset is missing: {repo_relative_path(repo_root, source)}")

    if args.copy_to_project and not unity_project.exists():
        warnings.append(
            "Unity project directory does not exist yet. Create/open a Unity project at "
            f"{repo_relative_path(repo_root, unity_project)} before using --copy-to-project."
        )

    if not warnings:
        for source, destination in staged.items():
            if copy_file(source, destination, args.overwrite, args.dry_run):
                copied.append(repo_relative_path(repo_root, destination))
        if args.copy_to_project:
            for source, destination in project_targets.items():
                if copy_file(source, destination, args.overwrite, args.dry_run):
                    project_copied.append(repo_relative_path(repo_root, destination))

    report = {
        "task": "Task 6: Unity Animated Import Check",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "inputs": {
            "glb": repo_relative_path(repo_root, input_glb),
            "fbx": repo_relative_path(repo_root, input_fbx),
        },
        "input_exists": {
            "glb": input_glb.exists(),
            "fbx": input_fbx.exists(),
        },
        "output_dir": repo_relative_path(repo_root, output_dir),
        "staged_assets": [repo_relative_path(repo_root, path) for path in staged.values()],
        "copied": copied,
        "unity_project": repo_relative_path(repo_root, unity_project),
        "copy_to_project": args.copy_to_project,
        "project_assets_dir": repo_relative_path(repo_root, project_assets_dir),
        "project_copied": project_copied,
        "manual_check": {
            "guide": "unity/UnityImportGuide.md",
            "expected_result": "Unity imports the GLB or FBX, shows the skinned cat-like model, and exposes Idle, Walk, and Jump_ToIdle animations.",
        },
        "warnings": warnings,
    }
    report_name = "unity_import_check_plan.json" if args.dry_run else "unity_import_check.json"
    report_path = reports_dir / report_name
    write_json(report_path, report)

    print("Unity import check preparation")
    print(f"- Input GLB: {input_glb}")
    print(f"- Input FBX: {input_fbx}")
    print(f"- Output directory: {output_dir}")
    print(f"- Unity project: {unity_project}")
    print(f"- Copied: {len(copied)}")
    print(f"- Project copied: {len(project_copied)}")
    print(f"- Report: {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if args.dry_run:
        print("- Dry-run: no files were copied.")
    return 0 if not warnings or args.dry_run else 2


if __name__ == "__main__":
    raise SystemExit(main())
