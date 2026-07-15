"""P1-A を1コマンドで通す: 再バインド → アニメーションのリターゲット → 機械ゲート。

    python pipeline_v2/p1a_run.py

順番を間違えると壊れる（rebind が blend を作り、retarget が上書きする）ので、
手で2回叩かずここから実行すること。Blender に渡すパスは必ず絶対パスにする
（相対パスは C:\\ 基準で解決されて "failed to open blend file" になる）。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")

SKELETON = REPO / "output_v2/base/cat_koha9.blend"
MESH = REPO / "input/cat2/koha9_cat.glb"
OUT_BLEND = REPO / "output_v2/base/p1a_koha.blend"
OUT_GLB = REPO / "output_v2/base/p1a_koha.glb"


def run(cmd: list[str], label: str) -> None:
    print(f"\n=== {label} ===", flush=True)
    p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    tail = [ln for ln in p.stdout.splitlines()
            if any(k in ln for k in ("[P1-A]", "[B-6b]", "Saved:", "Exported:", "Error", "ERROR"))]
    print("\n".join(tail[-14:]))
    if p.returncode != 0:
        print(p.stdout[-3000:])
        print(p.stderr[-3000:])
        raise SystemExit(f"{label} failed ({p.returncode})")


def main() -> int:
    if not BLENDER.exists():
        raise SystemExit(f"Blender not found: {BLENDER}")

    run([str(BLENDER), "--background", "--python", str(REPO / "pipeline_v2/p1a_rebind_blender.py"),
         "--",
         "--skeleton", str(SKELETON), "--mesh", str(MESH),
         "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
         "--report", str(REPO / "output_v2/reports/p1a_rebind.json")], "P1-A rebind")

    run([str(BLENDER), "--background", "--python",
         str(REPO / "pipeline_v2/b6b_retarget_animations_blender.py"), "--",
         "--input", str(OUT_BLEND), "--source", str(SKELETON),
         "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
         "--report", str(REPO / "output_v2/reports/p1a_retarget.json")], "P1-A retarget")

    print("\n=== 機械ゲート ===", flush=True)
    gate = subprocess.run(
        [sys.executable, str(REPO / "pipeline_v2/qa_skin_stretch.py"),
         "--glb", str(OUT_GLB), "--json", str(REPO / "output_v2/reports/qa_skin_p1a.json")],
        cwd=REPO, text=True)
    return gate.returncode


if __name__ == "__main__":
    raise SystemExit(main())
