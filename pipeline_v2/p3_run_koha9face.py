"""koha9face（顔改善版）を1コマンドで通す。p3_run_koha9.py の face 変種。

    python pipeline_v2/p3_run_koha9face.py [--skip-capture]

p3_koha9.* / p3_koha9_* テクスチャは正典として触らず、p3_koha9face_* だけを出力する
（ユーザー指示のリスク回避。2026-07-12）。
koha9 との差分: 目（縮小・伏し目・青磁グリーン）と髭（白く細く・眉髭控えめ）。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")

ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IN_BLEND = REPO / "output_v2/base/p2_koha.blend"
RGB = REPO / "output_v2/textures/p3_koha9face_basecolor.png"
RGBA = REPO / "output_v2/textures/p3_koha9face_basecolor_alpha.png"
FUR = REPO / "output_v2/textures/p3_koha9face_fur_shell.png"
OUT_BLEND = REPO / "output_v2/base/p3_koha9face.blend"
OUT_GLB = REPO / "output_v2/base/p3_koha9face.glb"

# face の髭: 実物（顔検討.png）は白く細く、眉の髭は控えめ
# 第2段階: 「もう少し細く」の指摘で 0.00055 -> 0.0004 (2026-07-15)
WHISKER_RADIUS = "0.0004"
WHISKER_COLOR = "0.95,0.94,0.92"
BROW_SCALE = "0.7"
# P4-尻尾: 「太い」の指摘で径 0.85 倍（実測 0.215×体長 -> 0.183。写真仕様 0.18）(2026-07-15)
TAIL_RADIUS_SCALE = "0.85"
# P4-尻尾: 長さ 1.3 倍（鎖 0.186 -> 0.242m = 0.69×体長。ユーザー承認 2026-07-15、見た目判断中）
TAIL_LENGTH_SCALE = "1.3"


def sh(cmd: list[str], label: str, keys: tuple[str, ...] = ()) -> None:
    print(f"\n=== {label} ===", flush=True)
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV)
    lines = p.stdout.splitlines()
    if keys:
        lines = [ln for ln in lines if any(k in ln for k in keys)]
    print("\n".join(lines[-24:]))
    if p.returncode != 0:
        print(p.stdout[-2500:])
        print(p.stderr[-2500:])
        raise SystemExit(f"{label} failed ({p.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-capture", action="store_true")
    a = ap.parse_args()

    sh([PY, str(REPO / "pipeline_v2/p3_paint_texture_koha9face.py")], "1/6 テクスチャ (face)",
       keys=("目", "->", "塗り替えた"))

    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3_apply_texture_blender.py"), "--",
        "--input", str(IN_BLEND), "--rgb", str(RGB), "--rgba", str(RGBA),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2/6 モデルへ適用", keys=("[P3]", "Saved:", "Exported:", "rror"))

    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3c_add_whiskers_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--root-radius", WHISKER_RADIUS, "--color", WHISKER_COLOR, "--brow-scale", BROW_SCALE],
       "3/6 髭（白く細く）", keys=("[P3c]", "Saved:", "Exported:", "rror"))

    sh([PY, str(REPO / "pipeline_v2/p3_make_fur_alpha.py"),
        "--src", str(RGB), "--out", str(FUR)], "4/6 毛シェルのアルファ", keys=("cutoff", "->"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3d_fur_shells_blender.py"), "--",
        "--input", str(OUT_BLEND), "--fur", str(FUR),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "4.5/6 毛シェル生成", keys=("[P3d]", "FurShell", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3e_tail_densify_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "4.8/6 尻尾の高密度化", keys=("[P3e]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_tail_slim_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--radius-scale", TAIL_RADIUS_SCALE],
       "4.9/6 尻尾の細身化", keys=("[P4t]", "Saved:", "Exported:", "rror"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p4_tail_lengthen_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
        "--length-scale", TAIL_LENGTH_SCALE],
       "4.95/6 尻尾の伸長", keys=("[P4l]", "Saved:", "Exported:", "rror"))

    print("\n=== 5/6 機械ゲート ===", flush=True)
    rc = subprocess.run([PY, str(REPO / "pipeline_v2/qa_skin_stretch.py"),
                         "--glb", str(OUT_GLB),
                         "--json", str(REPO / "output_v2/reports/qa_skin_p3_koha9face.json")],
                        cwd=REPO, text=True).returncode
    rc2 = subprocess.run([PY, str(REPO / "pipeline_v2/qa_belly_bind.py"),
                          "--glb", str(OUT_GLB)],
                         cwd=REPO, text=True).returncode

    if not a.skip_capture:
        sh([PY, str(REPO / "pipeline_v2/p1_capture.py"), "--glb", str(OUT_GLB),
            "--prefix", "p3k9f", "--res", "1440"],
           "6/6 コンタクトシート (1440px)", keys=("SHOTS", "HEADSHOTS", "->"))
    return rc or rc2


if __name__ == "__main__":
    raise SystemExit(main())
