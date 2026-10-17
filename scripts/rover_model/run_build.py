"""パラメトリックローバモデルを生成する（vehicle_type: rover）。

    python scripts/rover_model/run_build.py --config config/lunar_cruiser_model.yaml --overwrite

1. 機体 YAML をテンプレートと合成（scripts/drone_model/run_build.py と同じ継承の仕組み）
2. Blender（blender/rover_model/build_rover.py）で .blend / .glb / 6 方向レンダ / build_report.json
3. 寸法の QA（measurements と組み上がった形を突き合わせる）→ qa_report.json・BUILD_REPORT.md・6 方向の一覧画像
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "drone_model"))
from run_build import font, load_model_config, resolve_repo_path, sha256_file  # noqa: E402

DEFAULT_BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
VIEWS = ("front", "back", "left", "right", "top", "bottom")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="パラメトリックローバモデルを生成します。")
    p.add_argument("--config", default=str(REPO / "config" / "lunar_cruiser_model.yaml"))
    p.add_argument("--blender", default=str(DEFAULT_BLENDER))
    p.add_argument("--overwrite", action="store_true")
    return p.parse_args()


def validate(cfg: dict[str, Any]) -> None:
    if cfg.get("vehicle_type") != "rover":
        raise ValueError("vehicle_type: rover の設定ではありません")
    if cfg.get("coordinate_system", {}).get("front_axis") != "+Y":
        raise ValueError("ローバは front_axis: +Y に固定（下流の blend2mjcf 系が前提にする）")
    axles = cfg["wheels"]["axles"]
    ys = [float(a["y_mm"]) for a in axles]
    if ys != sorted(ys, reverse=True):
        raise ValueError("wheels.axles は前から後ろの順（y_mm が大きい順）に並べること")
    n = cfg.get("measurements", {}).get("wheel_count", {}).get("value")
    if n is not None and int(n) != 2 * len(axles):
        raise ValueError(f"車輪の数が合いません（measurements: {n}、axles×2: {2 * len(axles)}）")


def qa(cfg: dict[str, Any], rep: dict[str, Any]) -> dict[str, Any]:
    """measurements（採寸）と組み上がった形を比べる。許容差は measurements の tolerance_pct。"""
    meas = cfg.get("measurements", {})
    checks = []

    def check(name: str, actual: float, key: str) -> None:
        if key not in meas:
            return
        want = float(meas[key]["value"])
        tol = float(meas[key].get("tolerance_pct", 5.0))
        err = (actual - want) / want * 100.0
        checks.append({"name": name, "want": want, "actual": round(actual, 1), "error_pct": round(err, 2),
                       "tolerance_pct": tol, "pass": abs(err) <= tol})

    wheels = {w["id"]: w for w in rep["wheels"]}
    ys = sorted({w["location_mm"][1] for w in rep["wheels"]}, reverse=True)
    check("軸間 前↔中", ys[0] - ys[1], "axle_spacing_front_mid_mm")
    check("軸間 中↔後", ys[1] - ys[2], "axle_spacing_mid_rear_mm")
    xs = [w["location_mm"][0] for w in rep["wheels"]]
    check("トレッド", max(xs) - min(xs), "track_mm")
    check("車輪半径", wheels[rep["wheels"][0]["id"]]["location_mm"][2], "wheel_radius_mm")
    b = rep["bounds_body_mm"]
    check("車体の幅", b["max"][0] - b["min"][0], "body_width_mm")
    check("車体の高さ", b["max"][2], "body_height_mm")
    # 長さは前面の張り出し（バンパー）を含むので、採寸（角〜後端）＋張り出しと比べる
    nose = float(cfg["body"]["nose"]["bumper_protrusion_mm"])
    if "body_length_mm" in meas:
        want = float(meas["body_length_mm"]["value"]) + nose
        actual = b["max"][1] - b["min"][1]
        err = (actual - want) / want * 100.0
        tol = float(meas["body_length_mm"].get("tolerance_pct", 5.0))
        checks.append({"name": "車体の長さ（＋前面の張り出し）", "want": want, "actual": round(actual, 1),
                       "error_pct": round(err, 2), "tolerance_pct": tol, "pass": abs(err) <= tol})
    # 向き：前（+Y）に前照灯・前のカメラがあること（名前ではなく位置で確かめる）
    front_mount = [m for m in rep["mounts"] if m["id"].startswith("cam_front")]
    checks.append({"name": "前のカメラが +Y 側にある", "pass": bool(front_mount) and front_mount[0]["location_mm"][1] > 0})
    checks.append({"name": "最前の車軸が +Y 側", "pass": ys[0] > 0 > ys[-1]})
    steer = sorted(w["id"] for w in rep["wheels"] if w["steer"])
    checks.append({"name": "操舵する車輪", "value": steer, "pass": len(steer) > 0})
    return {"pass": all(c["pass"] for c in checks), "checks": checks}


def contact_sheet(out: Path) -> Path:
    cells = [Image.open(out / "renders" / f"{v}.png").convert("RGB") for v in VIEWS]
    s = cells[0].width
    sheet = Image.new("RGB", (s * 3, (s + 40) * 2), (30, 30, 34))
    d = ImageDraw.Draw(sheet)
    for i, (v, im) in enumerate(zip(VIEWS, cells)):
        x, y = (i % 3) * s, (i // 3) * (s + 40)
        d.text((x + 10, y + 8), v, fill=(255, 255, 255), font=font(24))
        sheet.paste(im, (x, y + 40))
    path = out / "views_sheet.png"
    sheet.save(path)
    return path


def cg_comparison(cfg: dict[str, Any], out: Path) -> Path | None:
    """公式 CG（input/ にあれば）と比較用レンダを左右に並べる。CG を含むので git 管理外の output/rover_measure/ へ。"""
    cg_dir = REPO / "input" / "raw_photos" / cfg["subject_id"]
    views = cfg["output"].get("comparison_views", [])
    if not views or not cg_dir.is_dir():
        return None
    rows = []
    for v in views:
        cg = cg_dir / v["cg_file"]
        rd = out / "renders" / f"cmp_{v['name']}.png"
        if cg.is_file() and rd.is_file():
            a, b = Image.open(cg).convert("RGB"), Image.open(rd).convert("RGB")
            h = 600
            a = a.resize((int(a.width * h / a.height), h))
            b = b.resize((int(b.width * h / b.height), h))
            row = Image.new("RGB", (a.width + b.width, h), (0, 0, 0))
            row.paste(a, (0, 0))
            row.paste(b, (a.width, 0))
            rows.append(row)
    if not rows:
        return None
    sheet = Image.new("RGB", (max(r.width for r in rows), sum(r.height for r in rows)), (0, 0, 0))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height
    dst = REPO / "output" / "rover_measure" / cfg["subject_id"] / "cg_vs_model.jpg"
    dst.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dst, quality=85)
    return dst


def write_markdown(cfg: dict[str, Any], rep: dict[str, Any], q: dict[str, Any], out: Path) -> Path:
    lines = [f"# {cfg['subject_id']} 生成レポート", "",
             f"- 生成: {datetime.now(timezone.utc).isoformat()}",
             f"- 設定: `{cfg.get('template_metadata', {}).get('subject_config', '')}`",
             f"- QA: **{'合格' if q['pass'] else '不合格'}**", "",
             "## 寸法の突き合わせ（採寸 → モデル）", "", "| 項目 | 採寸 | モデル | 差 | 許容 | 判定 |", "|---|---|---|---|---|---|"]
    for c in q["checks"]:
        if "want" in c:
            lines.append(f"| {c['name']} | {c['want']:.0f} mm | {c['actual']:.0f} mm | {c['error_pct']:+.1f}% | "
                         f"±{c['tolerance_pct']:.0f}% | {'✅' if c['pass'] else '❌'} |")
        else:
            lines.append(f"| {c['name']} | — | {c.get('value', '')} | — | — | {'✅' if c['pass'] else '❌'} |")
    lines += ["", "## 車輪", "", "| id | 位置 [mm] | 操舵 |", "|---|---|---|"]
    lines += [f"| {w['id']} | {w['location_mm']} | {'○' if w['steer'] else '—'} |" for w in rep["wheels"]]
    lines += ["", "## 動く外装・取付点", ""]
    lines += [f"- deploy `{d['id']}`（{d['type']}・{d['joint']}）" for d in rep["deployables"]]
    lines += [f"- mount `{m['id']}`（{m['type']}）{m['location_mm']}" for m in rep["mounts"]]
    lines += ["", f"全体の外形 {rep['bounds_all_mm']}、メッシュ {rep['mesh_count']} 個。"]
    path = out / cfg["output"]["report_markdown"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # Windows のコンソール（cp932）対策
    a = parse_args()
    cfg_path = resolve_repo_path(a.config)
    cfg = load_model_config(cfg_path)
    validate(cfg)
    out = resolve_repo_path(cfg["output"]["directory"])
    out.mkdir(parents=True, exist_ok=True)
    if not a.overwrite and (out / cfg["output"]["glb"]).exists():
        raise FileExistsError("既存成果物があります。更新する場合は --overwrite")
    cfg["output"]["directory"] = str(out.resolve())
    resolved = out / cfg["output"]["resolved_config"]
    resolved.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    cmd = [a.blender, "--background", "--factory-startup", "--python-exit-code", "1",
           "--python", str(REPO / "blender" / "rover_model" / "build_rover.py"), "--", "--config-json", str(resolved)]
    cp = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    (out / "blender_stdout.log").write_text(cp.stdout or "", encoding="utf-8")
    (out / "blender_stderr.log").write_text(cp.stderr or "", encoding="utf-8")
    if cp.returncode != 0 or "Traceback" in (cp.stdout or "") + (cp.stderr or ""):
        print((cp.stdout or "")[-3000:])
        print((cp.stderr or "")[-3000:], file=sys.stderr)
        return cp.returncode or 1
    rep = json.loads((out / cfg["output"]["build_report"]).read_text(encoding="utf-8"))
    q = qa(cfg, rep)
    (out / cfg["output"]["qa_report"]).write_text(json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")
    sheet = contact_sheet(out)
    md = write_markdown(cfg, rep, q, out)
    cmp_path = cg_comparison(cfg, out)
    if cmp_path:
        print(f"[run_build] CG との比較（git 管理外）: {cmp_path}")
    manifest = {"config": str(cfg_path), "config_sha256": sha256_file(cfg_path),
                "glb": str(out / cfg["output"]["glb"]), "glb_sha256": sha256_file(out / cfg["output"]["glb"]),
                "qa_pass": q["pass"]}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md.read_text(encoding="utf-8"))
    print(f"[run_build] sheet: {sheet}")
    return 0 if q["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
