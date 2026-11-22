"""forge_camera.py - カメラモデルの統合生成（センサー設定＋テンプレート -> Blender -> GLB / USD -> QA）。

使用法:
    python scripts/camera_model/run_build.py irvision_2d
    python scripts/camera_model/run_build.py irvision_2d --sensor-config <path/to/irvision_2d_gray_8mm.json>
    python scripts/camera_model/run_build.py irvision_2d --publish <コピー先フォルダ>

光学・外形・質量は hakoniwa-mujoco-sensor の設定 JSON（正本）から読む。見た目の細部はテンプレート YAML。
Blender は 5.2 を使う（環境変数 BLENDER_EXE、PATH、既定の場所の順に探す）。USD の組み立てと QA は
Blender 同梱の Python（pxr）で動かすので、Blender が無いときは resolved_config.json だけ作って止まる。

出力: output/camera_model/<id>/（Git 管理外）
    resolved_config.json, <id>.blend, <id>.glb, <id>_visual.usdc, <id>.usda, renders/, build_report.json,
    qa_report.json, BUILD_REPORT.md
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_DIR = SCRIPT_DIR.parents[1]
OUTPUT_DIR = REPO_DIR / "output" / "camera_model"
BUILD_SCRIPT = REPO_DIR / "blender" / "camera_model" / "build_camera.py"
AUTHOR_SCRIPT = SCRIPT_DIR / "author_camera_usd.py"
QA_SCRIPT = SCRIPT_DIR / "qa_camera.py"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import camera_geometry as cg  # noqa: E402

BLENDER_CANDIDATES = [
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
    "/usr/local/bin/blender-5.2.4-linux-x64/blender",
]
PUBLISH_FILES = ["{id}.usda", "{id}_visual.usdc", "{id}.glb", "resolved_config.json", "qa_report.json",
                 "BUILD_REPORT.md"]


def find_blender() -> Optional[str]:
    env = os.environ.get("BLENDER_EXE")
    if env and Path(env).is_file():
        return env
    for c in BLENDER_CANDIDATES:
        if Path(c).is_file():
            return c
    return shutil.which("blender")


def run_blender(blender: str, script: Path, cfg_json: Path) -> None:
    cmd = [blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(script),
           "--", "--config-json", str(cfg_json)]
    print(f"[forge_camera] {script.name}")
    res = subprocess.run(cmd, capture_output=True, text=True)
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith(("[", "  [")) and "Blender" not in ln]
    print("\n".join(lines))
    if res.returncode != 0:
        print(res.stdout[-4000:])
        print(res.stderr[-4000:], file=sys.stderr)
        raise SystemExit(f"{script.name} failed (exit {res.returncode})")


def write_report(out_dir: Path, cfg: dict) -> Path:
    qa = json.loads((out_dir / "qa_report.json").read_text(encoding="utf-8"))
    build = json.loads((out_dir / "build_report.json").read_text(encoding="utf-8"))
    o = cfg["optics"]
    import math
    lines = [
        f"# {cfg['display_name']} — 生成レポート",
        "",
        f"- テンプレート: `config/camera_templates/{cfg['template_id']}.yaml`",
        f"- センサー設定（正本）: `{Path(cfg['sensor_config']).name}`",
        f"- Blender: {build['blender_version']}、USD（QA）: {'.'.join(map(str, qa['usd_version']))}",
        "",
        "| 項目 | 値 |",
        "|---|---|",
        f"| 外形 | {cfg['housing_mm']['width']} × {cfg['housing_mm']['length']} × {cfg['housing_mm']['height']} mm"
        f"（幅 × 長さ × 高さ）、{cfg['mass_kg']} kg |",
        f"| 画像 | {o['image_size'][0]} × {o['image_size'][1]}、{o['image_format']}、{o['update_rate_hz']} Hz |",
        f"| 光学 | 焦点距離 {o['focal_length_mm']} mm、撮像 {o['sensor_size_mm'][0]:.3f} × {o['sensor_size_mm'][1]:.3f} mm |",
        f"| 画角 | 横 {math.degrees(o['horizontal_fov_rad']):.2f}°、縦 {math.degrees(o['vertical_fov_rad']):.2f}° |",
        f"| LED | {o['led_color']} |",
        "",
        f"## QA: {qa['n_checks'] - qa['n_failed']}/{qa['n_checks']} 合格",
        "",
        "| ID | 検査 | 結果 |",
        "|---|---|---|",
    ]
    lines += [f"| {c['id']} | {c['name']} | {'✅' if c['ok'] else '❌'} |" for c in qa["checks"]]
    lines += ["", "## レンダー", ""]
    lines += [f"![{k}](renders/{k}.png)" for k in build["renders"]]
    path = out_dir / "BUILD_REPORT.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def publish(out_dir: Path, dest: Path, tid: str) -> List[str]:
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for pat in PUBLISH_FILES:
        src = out_dir / pat.format(id=tid)
        shutil.copy2(src, dest / src.name)
        copied.append(src.name)
    if (out_dir / "renders").is_dir():
        shutil.copytree(out_dir / "renders", dest / "renders", dirs_exist_ok=True)
        copied.append("renders/")
    return copied


def build(template_id: str, sensor_config: Optional[str], publish_dir: Optional[str], require_blender: bool) -> int:
    cfg = cg.resolve(template_id, sensor_config)
    out_dir = OUTPUT_DIR / template_id
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_json = out_dir / "resolved_config.json"
    cfg_json.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[forge_camera] {template_id}: {cfg_json}")

    blender = find_blender()
    if not blender:
        msg = "Blender 5.2 が見つかりません（BLENDER_EXE を設定）。resolved_config.json だけ作りました"
        if require_blender:
            raise SystemExit(msg)
        print("[forge_camera] WARNING: " + msg)
        return 0
    run_blender(blender, BUILD_SCRIPT, cfg_json)
    run_blender(blender, AUTHOR_SCRIPT, cfg_json)
    try:
        run_blender(blender, QA_SCRIPT, cfg_json)
        qa_ok = True
    except SystemExit:
        qa_ok = False
    report = write_report(out_dir, cfg)
    print(f"[forge_camera] report: {report}")
    if not qa_ok:
        print("[forge_camera] QA failed — not published")
        return 1
    if publish_dir:
        files = publish(out_dir, Path(publish_dir), template_id)
        print(f"[forge_camera] published to {publish_dir}: {', '.join(files)}")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="カメラモデルの統合生成")
    ap.add_argument("template", help="テンプレートID（例: irvision_2d）")
    ap.add_argument("--sensor-config", help="センサーの設定 JSON（既定は兄弟フォルダの hakoniwa-mujoco-sensor）")
    ap.add_argument("--publish", help="合格したら USD・GLB・レポートをこのフォルダへコピーする")
    ap.add_argument("--require-blender", action="store_true")
    args = ap.parse_args()
    if args.template not in cg.list_templates():
        raise SystemExit(f"unknown template {args.template!r}: {cg.list_templates()}")
    sys.exit(build(args.template, args.sensor_config, args.publish, args.require_blender))


if __name__ == "__main__":
    main()
