"""forge_ship.py - 船舶モデル統合自動生成パイプライン (YAML -> Blender -> GLB/Blend -> MJCF/MMG/Profile)。

使用法:
    python tools/forge_ship.py container_749gt
    python tools/forge_ship.py fishing_boat
    python tools/forge_ship.py all
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parents[1]
TEMPLATES_DIR = REPO_DIR / "config" / "ship_templates"
OUTPUT_DIR = REPO_DIR / "output"
BLENDER_SCRIPT = REPO_DIR / "blender" / "ship_model" / "build_ship.py"
BLEND2MJCF_SCRIPT = SCRIPT_DIR / "blend2mjcf_ship.py"

# Blender 5.2 実行ファイルの検索
BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
]


def find_blender() -> str:
    for c in BLENDER_CANDIDATES:
        if Path(c).is_file():
            return c
    # PATH からの検索
    import shutil
    b = shutil.which("blender")
    if b:
        return b
    raise RuntimeError("Blender 5.2 executable not found in Program Files or PATH.")


def resolve_yaml(yaml_path: Path) -> Dict[str, Any]:
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if "template_file" in data:
        parent_path = yaml_path.parent / data["template_file"]
        parent_data = resolve_yaml(parent_path)
        merged = copy.deepcopy(parent_data)
        _deep_merge(merged, data)
        return merged
    return data


def _deep_merge(base: dict, update: dict) -> None:
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_merge(base[k], v)
        else:
            base[k] = copy.deepcopy(v)


def forge_vessel(template_name: str, skip_blender: bool = False) -> Dict[str, Any]:
    if template_name.endswith(".yaml"):
        yaml_file = TEMPLATES_DIR / template_name
    else:
        yaml_file = TEMPLATES_DIR / f"{template_name}.yaml"

    if not yaml_file.is_file():
        raise FileNotFoundError(f"Template YAML not found: {yaml_file}")

    print(f"\n=======================================================")
    print(f"[forge_ship] Building vessel: {template_name}")
    print(f"=======================================================")

    # 1. YAML 継承解決
    resolved = resolve_yaml(yaml_file)
    subject = resolved.get("template_id", template_name)

    # 出力先ディレクトリ
    out_dir = OUTPUT_DIR / subject
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_json_path = out_dir / "resolved_config.json"
    with resolved_json_path.open("w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2, ensure_ascii=False)
    print(f"  [1/4] Resolved config: {resolved_json_path}")

    # 2. Blender ヘッドレスビルド (.blend, .glb, レンダリング)
    if not skip_blender:
        blender_exe = find_blender()
        cmd = [
            blender_exe,
            "--background",
            "--factory-startup",
            "--python", str(BLENDER_SCRIPT),
            "--",
            "--config-json", str(resolved_json_path)
        ]
        print(f"  [2/4] Running Blender 5.2 headless build...")
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if res.returncode != 0:
            print(f"Blender Stdout:\n{res.stdout[-1000:]}")
            print(f"Blender Stderr:\n{res.stderr[-1000:]}")
            raise RuntimeError(f"Blender build failed with exit code {res.returncode}")
        print(f"  [2/4] Blender build completed: {out_dir / f'{subject}.blend'}")
    else:
        print(f"  [2/4] Skipping Blender build (--skip-blender).")

    # 3. MJCF XML, hydro_mmg.json, ship_sync.profile.json の生成
    mjcf_path = out_dir / f"{subject}.xml"
    hydro_path = out_dir / "hydro_mmg.json"
    profile_path = out_dir / "ship_sync.profile.json"

    print(f"  [3/4] Generating MJCF, hydro MMG and sync profile...")
    cmd_mjcf = [
        sys.executable,
        str(BLEND2MJCF_SCRIPT),
        "--config-json", str(resolved_json_path),
        "--out-mjcf", str(mjcf_path),
        "--out-hydro", str(hydro_path),
        "--out-profile", str(profile_path)
    ]
    res_mjcf = subprocess.run(cmd_mjcf, capture_output=True, text=True, encoding="utf-8")
    if res_mjcf.returncode != 0:
        print(res_mjcf.stderr)
        raise RuntimeError("blend2mjcf_ship failed.")
    print(f"  [3/4] Physics assets generated.")

    # 4. マークダウンレポート (BUILD_REPORT.md) の作成
    report_md_path = out_dir / "BUILD_REPORT.md"
    _generate_markdown_report(report_md_path, resolved, out_dir)
    print(f"  [4/4] Report generated: {report_md_path}")

    return {
        "subject": subject,
        "out_dir": str(out_dir),
        "blend": str(out_dir / f"{subject}.blend"),
        "glb": str(out_dir / f"{subject}.glb"),
        "mjcf": str(mjcf_path),
        "hydro": str(hydro_path),
        "profile": str(profile_path),
    }


def _generate_markdown_report(path: Path, cfg: dict, out_dir: Path) -> None:
    subject = cfg.get("template_id", "")
    dim = cfg["dimensions"]
    sig = cfg.get("signatures", {})

    lines = [
        f"# Vessel Build Report: {subject}",
        f"",
        f"- **Name**: {cfg.get('name', '')}",
        f"- **Class**: {cfg.get('ship_class', '')}",
        f"- **Provenance**: {json.dumps(cfg.get('provenance', {}), indent=2, ensure_ascii=False)}",
        f"",
        f"## 1. Principal Dimensions",
        f"",
        f"| Parameter | Value | Unit |",
        f"|---|---|---|",
        f"| Length Overall ($L_{{OA}}$) | {dim.get('length_oa_m', 0.0):.2f} | m |",
        f"| Length Between Perpendiculars ($L_{{PP}}$) | {dim.get('length_pp_m', 0.0):.2f} | m |",
        f"| Beam ($B$) | {dim.get('beam_m', 0.0):.2f} | m |",
        f"| Depth ($D$) | {dim.get('depth_m', 0.0):.2f} | m |",
        f"| Design Draft ($d$) | {dim.get('draft_m', 0.0):.2f} | m |",
        f"| Block Coefficient ($C_b$) | {dim.get('block_coefficient', 0.0):.3f} | - |",
        f"| Displacement | {dim.get('displacement_tonnes', 0.0):.1f} | tonnes |",
        f"",
        f"## 2. Signatures & AIS",
        f"",
        f"- **Radar Cross Section (RCS)**: $\\sigma = {sig.get('radar_cross_section_m2', 0.0):.1f}\\text{{ m}}^2$",
        f"- **Has AIS**: `{sig.get('has_ais', False)}`",
        f"- **AIS Class**: `{sig.get('ais_class', 'NONE')}`",
        f"- **MMSI**: `{sig.get('mmsi', 0)}`",
        f"",
        f"## 3. Generated Deliverables",
        f"",
        f"- Blender 3D Scene: `[{subject}.blend]({subject}.blend)`",
        f"- 3D Model (glTF 2.0): `[{subject}.glb]({subject}.glb)`",
        f"- MuJoCo Physics Model: `[{subject}.xml]({subject}.xml)`",
        f"- MMG Hydrodynamics: `[hydro_mmg.json](hydro_mmg.json)`",
        f"- Viewer Sync Profile: `[ship_sync.profile.json](ship_sync.profile.json)`",
        f"",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(prog="forge_ship.py")
    p.add_argument("target", help="Template name (e.g. container_749gt, fishing_boat, or 'all')")
    p.add_argument("--skip-blender", action="store_true", help="Skip running Blender 3D build")
    args = p.parse_args()

    targets = []
    if args.target == "all":
        targets = ["container_749gt", "container_700teu", "ferry_seto", "fishing_boat"]
    else:
        targets = [args.target]

    for t in targets:
        forge_vessel(t, skip_blender=args.skip_blender)

    print("\n[forge_ship] All target vessels forged successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
