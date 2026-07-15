"""P3-1 を1コマンドで通す: 塗り替え → モデルへ適用 → 機械ゲート → コンタクトシート → 写真比較。

    python pipeline_v2/p3_run.py [--skip-bake]

UV ベイク（p3_uv_bake.py）は P2 のモデルが変わらない限り一度で足りるので、
既定では省略する（`--bake` で強制）。
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

# 子プロセスの stdout はパイプに繋ぐと既定でロケール（cp932）になる。utf-8 で
# デコードすると日本語が U+FFFD になり、それを cp932 の端末へ出す時点で落ちる。
# 親も子も utf-8 に揃える。
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

IN_BLEND = REPO / "output_v2/base/p2_koha.blend"
RGB = REPO / "output_v2/textures/p3_koha_basecolor.png"
RGBA = REPO / "output_v2/textures/p3_koha_basecolor_alpha.png"
OUT_BLEND = REPO / "output_v2/base/p3_koha.blend"
OUT_GLB = REPO / "output_v2/base/p3_koha.glb"


def sh(cmd: list[str], label: str, keys: tuple[str, ...] = ()) -> None:
    print(f"\n=== {label} ===", flush=True)
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=ENV)
    lines = p.stdout.splitlines()
    if keys:
        lines = [ln for ln in lines if any(k in ln for k in keys)]
    print("\n".join(lines[-18:]))
    if p.returncode != 0:
        print(p.stdout[-2500:])
        print(p.stderr[-2500:])
        raise SystemExit(f"{label} failed ({p.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bake", action="store_true", help="UV→3D のベイクからやり直す")
    a = ap.parse_args()

    if a.bake:
        sh([PY, str(REPO / "pipeline_v2/p3_uv_bake.py")], "0/4 UV→3D ベイク")

    sh([PY, str(REPO / "pipeline_v2/p3_paint_texture.py")], "1/4 テクスチャ塗り替え",
       keys=("斑 ", "顔 ", "->", "塗り替えた"))

    sh([str(BLENDER), "--background", "--python",
        str(REPO / "pipeline_v2/p3_apply_texture_blender.py"), "--",
        "--input", str(IN_BLEND), "--rgb", str(RGB), "--rgba", str(RGBA),
        "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB)],
       "2/4 モデルへ適用", keys=("[P3]", "->", "Saved:", "Exported:", "rror"))

    print("\n=== 3/4 機械ゲート ===", flush=True)
    rc = subprocess.run([PY, str(REPO / "pipeline_v2/qa_skin_stretch.py"),
                         "--glb", str(OUT_GLB),
                         "--json", str(REPO / "output_v2/reports/qa_skin_p3.json")],
                        cwd=REPO, text=True).returncode

    sh([PY, str(REPO / "pipeline_v2/p1_capture.py"), "--glb", str(OUT_GLB), "--prefix", "p3"],
       "4/4 コンタクトシート", keys=("SHOTS", "->"))
    sh([PY, str(REPO / "pipeline_v2/p3_compare_photos.py")], "写真との4面比較")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
