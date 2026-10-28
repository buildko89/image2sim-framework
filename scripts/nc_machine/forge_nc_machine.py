"""forge_nc_machine.py - 加工機モデル統合生成（YAML -> Blender -> GLB/Blend -> MJCF/同期プロファイル/インタフェース -> QA）。

使用法:
    python scripts/nc_machine/run_build.py turning_h_k1
    python scripts/nc_machine/run_build.py all
    python scripts/nc_machine/run_build.py turning_h_k1 --skip-blender      # MJCF などだけ作る

Blender は 5.2 を優先し、無ければ Program Files の Blender Foundation 配下・PATH・環境変数 BLENDER_EXE を探す。
見つからないときは警告して GLB・レンダーを作らずに続ける（--require-blender で失敗にする）。
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parents[1]
TEMPLATES_DIR = REPO_DIR / "config" / "nc_machine_templates"
OUTPUT_DIR = REPO_DIR / "output" / "nc_machine"
BLENDER_SCRIPT = REPO_DIR / "blender" / "nc_machine" / "build_nc_machine.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import blend2mjcf_nc  # noqa: E402
import qa_nc  # noqa: E402

BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    r"C:\Program Files\Blender Foundation\Blender\blender.exe",
]


def find_blender() -> Optional[str]:
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).is_file():
        return env
    for c in BLENDER_CANDIDATES:
        if Path(c).is_file():
            return c
    found = sorted(Path(r"C:\Program Files\Blender Foundation").glob("Blender */blender.exe"), reverse=True)
    if found:
        return str(found[0])
    return shutil.which("blender")


def _deep_merge(base: dict, update: dict) -> None:
    for k, v in update.items():
        if isinstance(v, dict) and k in base and isinstance(base[k], dict):
            _deep_merge(base[k], v)
        else:
            base[k] = copy.deepcopy(v)


def resolve_yaml(yaml_path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    if "template_file" in data:
        merged = resolve_yaml(yaml_path.parent / data["template_file"])
        _deep_merge(merged, {k: v for k, v in data.items() if k != "template_file"})
        return merged
    return data


def list_templates() -> List[str]:
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml") if not p.stem.endswith("_base"))


def run_blender(blender: str, resolved_json: Path) -> None:
    cmd = [blender, "--background", "--factory-startup", "--python", str(BLENDER_SCRIPT), "--",
           "--config-json", str(resolved_json)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if res.returncode != 0:
        print(f"Blender Stdout:\n{res.stdout[-2000:]}")
        print(f"Blender Stderr:\n{res.stderr[-2000:]}")
        raise RuntimeError(f"Blender build failed with exit code {res.returncode}")


def write_report(path: Path, cfg: Dict[str, Any], files: Dict[str, str], qa: Dict[str, Any], blender: Optional[str]) -> None:
    subject = cfg["template_id"]
    lines = [
        f"# BUILD_REPORT — {subject}",
        "",
        f"- 名前: {cfg.get('name', subject)}",
        f"- 種類: {cfg.get('kind')}／LOD {cfg.get('lod', 0)}",
        f"- Blender: {blender or '未使用（GLB・レンダーなし）'}",
        f"- QA: **{'合格' if qa['passed'] else '不合格'}**",
        "",
        "## 出典（provenance）",
        "",
        "| 項目 | 内容 |",
        "|---|---|",
    ]
    for k, v in cfg.get("provenance", {}).items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## QA", "", "| ID | 項目 | 結果 | 詳細 |", "|---|---|---|---|"]
    for c in qa["checks"]:
        lines.append(f"| {c['id']} | {c['title']} | {c['result']} | {c['detail']} |")
    lines += ["", "## 生成物", "", "| 種類 | ファイル |", "|---|---|"]
    for k, v in files.items():
        lines.append(f"| {k} | `{Path(v).name}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def forge(template_name: str, skip_blender: bool = False, require_blender: bool = False,
          out_root: Path = OUTPUT_DIR) -> Dict[str, Any]:
    yaml_file = TEMPLATES_DIR / (template_name if template_name.endswith(".yaml") else f"{template_name}.yaml")
    if not yaml_file.is_file():
        raise FileNotFoundError(f"Template YAML not found: {yaml_file}")
    print(f"[forge_nc_machine] {template_name}")

    cfg = resolve_yaml(yaml_file)
    subject = cfg["template_id"]
    out_dir = out_root / subject
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = out_dir / "resolved_config.json"
    resolved.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  [1/4] resolved: {resolved}")

    blender = None
    if not skip_blender:
        blender = find_blender()
        if blender:
            print(f"  [2/4] Blender: {blender}")
            run_blender(blender, resolved)
        elif require_blender:
            raise RuntimeError("Blender が見つからない（BLENDER_EXE で指定できる）")
        else:
            print("  [2/4] Blender が見つからないため GLB・レンダーは作らない（--skip-blender と同じ）")
    else:
        print("  [2/4] Blender を使わない（--skip-blender）")

    files = blend2mjcf_nc.write_all(cfg, out_dir)
    for name in (f"{subject}.glb", f"{subject}.blend"):
        if (out_dir / name).is_file():
            files[name.split(".")[-1]] = str(out_dir / name)
    print(f"  [3/4] MJCF・プロファイル・インタフェース: {out_dir}")

    qa = qa_nc.run_qa(cfg, out_dir)
    files["qa"] = str(out_dir / "qa_report.json")
    write_report(out_dir / "BUILD_REPORT.md", cfg, files, qa, blender)
    print(f"  [4/4] QA: {'合格' if qa['passed'] else '不合格'}")
    for c in qa["checks"]:
        print(f"        {c['id']} {c['result']:4s} {c['title']}")
    return {"subject": subject, "out_dir": str(out_dir), "passed": qa["passed"], "blender": blender}


def main() -> None:
    p = argparse.ArgumentParser(description="NC machine model forge (image2sim-framework)")
    p.add_argument("target", help="テンプレートID または all")
    p.add_argument("--skip-blender", action="store_true")
    p.add_argument("--require-blender", action="store_true")
    a = p.parse_args()
    targets = list_templates() if a.target == "all" else [a.target]
    results = [forge(t, a.skip_blender, a.require_blender) for t in targets]
    failed = [r["subject"] for r in results if not r["passed"]]
    if failed:
        print(f"QA 不合格: {failed}")
        sys.exit(1)


if __name__ == "__main__":
    main()
