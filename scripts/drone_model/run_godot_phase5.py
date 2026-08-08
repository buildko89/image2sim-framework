from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MODEL_SPECS = {
    "drone2": ("drone2", "drone2.glb"),
    "drone3": ("drone3", "drone3.glb"),
    "hula": ("hula", "hula.glb"),
    "hex6": ("hex6", "hex6_radial.glb"),
}
FORMAL_MODEL_DIRECTORIES = {
    "drone2": "drone2_parametric",
    "drone3": "drone3_parametric",
    "hula": "hula_parametric",
    "hex6": "drone2_parametric/hex6_radial",
}
REFERENCE_EXTENSIONS = {".cs", ".gd", ".tscn", ".tres", ".godot"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage GLBs and run the Phase 5 hierarchy regression in headless Godot."
    )
    parser.add_argument("--godot", help="Path to a Godot 4 executable.")
    parser.add_argument("--input-root", default="output/phase4_review")
    parser.add_argument("--output-root", default="output/phase5_review")
    parser.add_argument("--include-hex6", action="store_true")
    parser.add_argument(
        "--formal-layout",
        action="store_true",
        help="Read the canonical output/*_parametric layout instead of Phase 4 review subdirectories.",
    )
    parser.add_argument("--timeout", type=int, default=180)
    return parser.parse_args()


def read_glb_json(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"GLB is too small: {path}")
    magic, version, declared_length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or declared_length != len(data):
        raise ValueError(f"Invalid GLB header: {path}")
    offset = 12
    while offset < len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:
            return json.loads(chunk.decode("utf-8"))
        offset += 8 + chunk_length
    raise ValueError(f"GLB has no JSON chunk: {path}")


def glb_expectations(document: dict[str, Any]) -> dict[str, Any]:
    nodes = document.get("nodes", [])
    node_names = [str(node.get("name", f"<node:{index}>")) for index, node in enumerate(nodes)]
    if len(node_names) != len(set(node_names)):
        raise ValueError("Phase 5 requires unique GLB node names")
    parents: dict[int, int] = {}
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", []):
            parents[int(child_index)] = parent_index
    expected_nodes = {}
    for index, node in enumerate(nodes):
        expected_nodes[node_names[index]] = {
            "parent": node_names[parents[index]] if index in parents else None,
            "translation": node.get("translation"),
            "rotation": node.get("rotation"),
            "scale": node.get("scale"),
            "matrix": node.get("matrix"),
            "extras": node.get("extras", {}),
        }
    material_names = [
        str(material.get("name", f"<material:{index}>"))
        for index, material in enumerate(document.get("materials", []))
    ]
    return {
        "nodes": expected_nodes,
        "mesh_node_names": sorted(
            node_names[index] for index, node in enumerate(nodes) if "mesh" in node
        ),
        "material_names": sorted(material_names),
    }


def find_godot(explicit: str | None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_path = os.environ.get("GODOT4_BIN")
    if env_path:
        candidates.append(Path(env_path))
    for command in ("godot4", "godot"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Godot 4 executable not found. Pass --godot or set GODOT4_BIN.")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def stage_project(
    repo_root: Path,
    input_root: Path,
    output_root: Path,
    include_hex6: bool,
    formal_layout: bool,
) -> tuple[Path, dict[str, Any]]:
    template_dir = repo_root / "scripts" / "drone_model" / "godot_phase5"
    project_dir = output_root / "godot_project"
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("project.godot", "drone_runtime.gd", "phase5_test.gd"):
        shutil.copy2(template_dir / name, project_dir / name)

    selected = ["drone2", "drone3", "hula"]
    if include_hex6:
        selected.append("hex6")
    manifest_models = []
    stable_names: set[str] = {"center_of_mass"}
    for model_id in selected:
        directory_name, glb_name = MODEL_SPECS[model_id]
        source_dir = input_root / (
            FORMAL_MODEL_DIRECTORIES[model_id] if formal_layout else directory_name
        )
        source_glb = source_dir / glb_name
        source_report = source_dir / "build_report.json"
        if not source_glb.is_file() or not source_report.is_file():
            raise FileNotFoundError(f"Missing Phase 4 artifacts for {model_id}: {source_dir}")
        staged_glb = assets_dir / glb_name
        staged_report = assets_dir / f"{model_id}_build_report.json"
        shutil.copy2(source_glb, staged_glb)
        shutil.copy2(source_report, staged_report)
        build_report = json.loads(source_report.read_text(encoding="utf-8"))
        document = read_glb_json(source_glb)
        expectations = glb_expectations(document)
        rotor_ids = list(build_report["motor_axes"].keys())
        for rotor_id in rotor_ids:
            stable_names.add(f"motor_{rotor_id}_axis")
            stable_names.add(f"rotor_{rotor_id}_spin")
        manifest_models.append(
            {
                "id": model_id,
                "scene_path": f"res://assets/{glb_name}",
                "build_report_path": f"res://assets/{model_id}_build_report.json",
                "rotor_ids": rotor_ids,
                **expectations,
            }
        )
    manifest = {
        "schema_version": "1.0",
        "models": manifest_models,
        "stable_names": sorted(stable_names),
    }
    write_json(project_dir / "manifest.json", manifest)
    return project_dir, manifest


def scan_godot_references(repo_root: Path, names: list[str]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    roots = [repo_root / "godot", repo_root / "output_v2" / "godot"]
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in REFERENCE_EXTENSIONS:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, 1):
                referenced = sorted(name for name in names if name in line)
                if referenced:
                    matches.append(
                        {
                            "path": path.relative_to(repo_root).as_posix(),
                            "line": line_number,
                            "names": referenced,
                        }
                    )
    return matches


def run_command(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def main() -> int:
    args = parse_args()
    repo_root = Path(__file__).resolve().parents[2]
    input_root = (repo_root / args.input_root).resolve()
    output_root = (repo_root / args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    godot = find_godot(args.godot)
    project_dir, manifest = stage_project(
        repo_root,
        input_root,
        output_root,
        args.include_hex6,
        args.formal_layout,
    )

    version = run_command([str(godot), "--version"], args.timeout)
    import_result = run_command(
        [
            str(godot),
            "--headless",
            "--editor",
            "--path",
            str(project_dir),
            "--import",
        ],
        args.timeout,
    )
    (output_root / "godot_import.log").write_text(import_result.stdout, encoding="utf-8")
    if import_result.returncode != 0:
        print(import_result.stdout)
        print(f"Godot import failed ({import_result.returncode})")
        return import_result.returncode or 2

    test_result = run_command(
        [
            str(godot),
            "--headless",
            "--path",
            str(project_dir),
            "--script",
            "res://phase5_test.gd",
        ],
        args.timeout,
    )
    (output_root / "godot_test.log").write_text(test_result.stdout, encoding="utf-8")
    godot_report_path = project_dir / "godot_phase5_report.json"
    if not godot_report_path.is_file():
        print(test_result.stdout)
        print("Godot did not produce godot_phase5_report.json")
        return test_result.returncode or 2

    report = json.loads(godot_report_path.read_text(encoding="utf-8"))
    report.update(
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "godot_executable": str(godot),
            "godot_version_output": version.stdout.strip(),
            "input_root": str(input_root.relative_to(repo_root)).replace("\\", "/"),
            "nodepath_scan": {
                "roots": ["godot", "output_v2/godot"],
                "matches": scan_godot_references(repo_root, manifest["stable_names"]),
            },
            "import_exit_code": import_result.returncode,
            "test_exit_code": test_result.returncode,
        }
    )
    final_report_path = output_root / "phase5_report.json"
    write_json(final_report_path, report)
    print(test_result.stdout)
    print(f"Phase 5 report: {final_report_path}")
    return 0 if report.get("status") == "PASS" and test_result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
