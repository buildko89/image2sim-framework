"""P2 を1コマンドで通す: 再バインド → 尻尾カール → リターゲット → 機械ゲート。

    python pipeline_v2/p2_run.py [--total-deg 125]

順番厳守。カールは「束縛の後・リターゲットの前」でなければならない。
- 束縛前にカールすると、尻尾が背中の直上を通るためボーンヒートが背中を尻尾に吸わせる。
- リターゲット後にカールすると、尻尾の回転キーが二重に効く。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")

SKELETON = REPO / "output_v2/base/cat_koha9.blend"
MESH = REPO / "input/cat2/koha9_cat.glb"
BIND_BLEND = REPO / "output_v2/base/p2_bind.blend"
BIND_GLB = REPO / "output_v2/base/p2_bind.glb"
CURLED = REPO / "output_v2/base/p2_curled.blend"
OUT_BLEND = REPO / "output_v2/base/p2_koha.blend"
OUT_GLB = REPO / "output_v2/base/p2_koha.glb"

KEYS = ("[P1-A]", "[P2]", "[B-6b]", "Saved:", "Exported:", "Error", "ERROR", "Traceback")


def run(script: str, args: list[str], label: str) -> None:
    print(f"\n=== {label} ===", flush=True)
    p = subprocess.run([str(BLENDER), "--background", "--python", str(REPO / "pipeline_v2" / script),
                        "--", *args],
                       cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("\n".join([ln for ln in p.stdout.splitlines() if any(k in ln for k in KEYS)][-16:]))
    # Blender は --background で Python が例外を投げても終了コード 0 を返すことがある。
    # returncode だけを見ていると、**前回の成果物が残ったまま「PASS」と表示される**
    # （実際に踏んだ: center_head_midline が落ちたのに古い p2_koha.glb でゲートが通った）。
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stdout[-3000:])
        print(p.stderr[-3000:])
        raise SystemExit(f"{label} failed (rc={p.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bone-deg", default="81,12,0,2,-10")
    ap.add_argument("--skip-rebind", action="store_true",
                    help="p2_bind.blend を再利用する（カール角の試行錯誤用）")
    a = ap.parse_args()

    if not a.skip_rebind:
        run("p1a_rebind_blender.py",
            ["--skeleton", str(SKELETON), "--mesh", str(MESH),
             "--output-blend", str(BIND_BLEND), "--output-glb", str(BIND_GLB),
             "--report", str(REPO / "output_v2/reports/p2_rebind.json")],
            "1/3 再バインド（尻尾はまっすぐ）")

    run("p2_curl_tail_blender.py",
        ["--input", str(BIND_BLEND), "--output", str(CURLED),
         "--report", str(REPO / "output_v2/reports/p2_curl_tail.json"),
         "--bone-deg", a.bone_deg],
        "2/3 尻尾カール（ボーンポーズ → Apply as Rest Pose）")

    run("b6b_retarget_animations_blender.py",
        ["--input", str(CURLED), "--source", str(SKELETON),
         "--output-blend", str(OUT_BLEND), "--output-glb", str(OUT_GLB),
         "--report", str(REPO / "output_v2/reports/p2_retarget.json")],
        "3/3 アニメーションのリターゲット")

    print("\n=== 機械ゲート ===", flush=True)
    return subprocess.run(
        [sys.executable, str(REPO / "pipeline_v2/qa_skin_stretch.py"),
         "--glb", str(OUT_GLB), "--json", str(REPO / "output_v2/reports/qa_skin_p2.json")],
        cwd=REPO, text=True).returncode


if __name__ == "__main__":
    raise SystemExit(main())
