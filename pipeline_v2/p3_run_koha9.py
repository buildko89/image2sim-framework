"""koha9 (配色2.pdf 対応) を1コマンドで通す: 塗り替え → モデルへ適用 → 機械ゲート → キャプチャ。

    python pipeline_v2/p3_run_koha9.py [--bake] [--skip-capture]

p3_run.py の koha9 変種。p3_koha.glb / p3_koha.blend は正典として触らず、
p3_koha9.blend / p3_koha9.glb だけを出力する。
UV ベイク（p3_uv_bake.py）の成果物 p3_uv_position.npz はメッシュが同じ限り共用できる。
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
RGB = REPO / "output_v2/textures/p3_koha9_basecolor.png"
RGBA = REPO / "output_v2/textures/p3_koha9_basecolor_alpha.png"
OUT_BLEND = REPO / "output_v2/base/p3_koha9.blend"
OUT_GLB = REPO / "output_v2/base/p3_koha9.glb"


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
    ap.add_argument("--bake", action="store_true", help="UV→3D のベイクからやり直す")
    ap.add_argument("--skip-capture", action="store_true", help="ゲートまでで止める")
    a = ap.parse_args()

    if a.bake:
        sh([PY, str(REPO / "pipeline_v2/p3_uv_bake.py")], "0/5 UV→3D ベイク")

    sh([PY, str(REPO / "pipeline_v2/p3_paint_texture_koha9.py")], "1/5 テクスチャ塗り替え (koha9)",
       keys=("斑 ", "顔 ", "->", "塗り替えた"))

    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3_apply_texture_blender.py"), "--",
        "--input", str(IN_BLEND), "--rgb", str(RGB), "--rgba", str(RGBA),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2/5 モデルへ適用", keys=("[P3]", "->", "Saved:", "Exported:", "rror"))

    # 髭の生成（髭対応.png, 2026-07-12）。p3 適用で blend が作り直されるので毎回入れる
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3c_add_whiskers_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2.5/5 髭の生成", keys=("[P3c]", "Saved:", "Exported:", "rror"))

    # 毛シェル（prompt5.md, 2026-07-12）: 胸のタック + 3層シェル
    sh([PY, str(REPO / "pipeline_v2/p3_make_fur_alpha.py")], "2.6/5 毛シェルのアルファ生成",
       keys=("cutoff", "->"))
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3d_fur_shells_blender.py"), "--",
        "--input", str(OUT_BLEND), "--fur", str(REPO / "output_v2/textures/p3_koha9_fur_shell.png"),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2.7/5 毛シェル生成", keys=("[P3d]", "FurShell", "Saved:", "Exported:", "rror"))

    # 尻尾のプルームの透けを塞ぐ（prompt: 後ろから先端が透ける, 2026-07-12）
    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3e_tail_densify_blender.py"), "--",
        "--input", str(OUT_BLEND),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2.8/5 尻尾の高密度化", keys=("[P3e]", "Saved:", "Exported:", "rror"))

    print("\n=== 3/5 機械ゲート qa_skin_stretch ===", flush=True)
    rc = subprocess.run([PY, str(REPO / "pipeline_v2/qa_skin_stretch.py"),
                         "--glb", str(OUT_GLB),
                         "--json", str(REPO / "output_v2/reports/qa_skin_p3_koha9.json")],
                        cwd=REPO, text=True).returncode

    print("\n=== 4/5 機械ゲート qa_belly_bind ===", flush=True)
    rc2 = subprocess.run([PY, str(REPO / "pipeline_v2/qa_belly_bind.py"),
                          "--glb", str(OUT_GLB)],
                         cwd=REPO, text=True).returncode

    if not a.skip_capture:
        sh([PY, str(REPO / "pipeline_v2/p1_capture.py"), "--glb", str(OUT_GLB),
            "--prefix", "p3k9"],
           "5/5 コンタクトシート", keys=("SHOTS", "HEADSHOTS", "->"))
    return rc or rc2


if __name__ == "__main__":
    raise SystemExit(main())
