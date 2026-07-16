"""P4 の目視ゲート素材: 各アニメのフレーム連番 → GIF + コンタクトシート。

    python pipeline_v2/p4_capture_strips.py --glb output_v2/base/p3_koha9face.glb

capture_grid の3コマでは歩様・振り・タメが判断できない。ここでは
CaptureStrip.tscn で等間隔サンプリング（既定 12fps・最大60コマ）した連番から、

  - <anim>_<view>.gif        実時間再生の GIF（ユーザー確認用）
  - sheet_<anim>_<view>.png  20コマのコンタクトシート（チャットで読む用）

を output_v2/reports/p4_strips/ に作る。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from p1_capture import GODOT, GODOT_PROJ, rest_bounds  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "output_v2/reports/p4_strips"
FOV = 45.0


def capture(glb: Path, prefix: str, views: str, res: int, fps: float,
            only: str = "") -> None:
    import shutil
    shutil.copy(glb, GODOT_PROJ / glb.name)
    subprocess.run([str(GODOT), "--headless", "--path", str(GODOT_PROJ), "--import"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pivot, radius, extent = rest_bounds(glb)
    # 注意: 撮影本体は --headless 不可（frame_post_draw が発火せず永久待ちになる）
    p = subprocess.run([
        str(GODOT), "--path", str(GODOT_PROJ), "res://scenes/CaptureStrip.tscn", "--",
        f"--model=res://{glb.name}", f"--prefix=p4s", f"--out={OUT.as_posix()}",
        f"--pivot={pivot[0]},{pivot[1]},{pivot[2]}", f"--radius={radius}",
        f"--extent={extent}", f"--fov={FOV}", f"--res={res}",
        f"--views={views}", f"--fps={fps}", f"--only={only}",
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    for ln in p.stdout.splitlines():
        if re.search(r"FRAMING|STRIP|SHOTS|DONE|error", ln):
            print("  " + ln)
    if "DONE" not in p.stdout:
        print(p.stdout[-2000:])
        print(p.stderr[-2000:])
        raise SystemExit("capture failed")


def assemble(views: str) -> None:
    frames: dict[tuple[str, str], list[Path]] = {}
    for f in sorted(OUT.glob("p4s_*_f*_*.png")):
        m = re.match(r"p4s_(.+)_f(\d+)_(\w+)\.png", f.name)
        if not m:
            continue
        frames.setdefault((m.group(1), m.group(3)), []).append(f)

    # アニメの実時間を GIF に反映するため、blend 実測の長さ（秒）
    length = {"atk1": 1.50, "atk2": 1.67, "idle1": 2.50, "idle2": 7.50,
              "jump": 1.53, "run": 0.50, "walk": 1.33, "walkback": 1.33,
              "loaf": 2.50, "sit": 2.50}

    for (anim, view), files in sorted(frames.items()):
        imgs = [Image.open(f).convert("RGB") for f in files]
        dur_ms = int(length.get(anim, 2.0) / len(imgs) * 1000)
        gif = OUT / f"{anim}_{view}.gif"
        small = [im.resize((360, 360)) for im in imgs]
        small[0].save(gif, save_all=True, append_images=small[1:],
                      duration=max(dur_ms, 20), loop=0)
        print(f"  -> {gif.name}  {len(imgs)}f x {dur_ms}ms")

        # 20コマのシート（5x4）
        pick = [imgs[round(i * (len(imgs) - 1) / 19)] for i in range(20)]
        cell = 300
        sheet = Image.new("RGB", (cell * 5, cell * 4), (18, 18, 20))
        for i, im in enumerate(pick):
            sheet.paste(im.resize((cell, cell)), ((i % 5) * cell, (i // 5) * cell))
        sp = OUT / f"sheet_{anim}_{view}.png"
        sheet.save(sp)
        print(f"  -> {sp.name}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", default=str(REPO / "output_v2/base/p3_koha9face.glb"))
    ap.add_argument("--views", default="left,front")
    ap.add_argument("--res", type=int, default=480)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--only", default="", help="部分一致でアニメを絞る（例: jump）")
    ap.add_argument("--skip-capture", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if not a.skip_capture:
        if a.only:
            for f in OUT.glob(f"p4s_{a.only}*_f*_*.png"):
                f.unlink()   # 旧フレームが混ざると GIF が壊れる
        capture(Path(a.glb), "p4s", a.views, a.res, a.fps, a.only)
    assemble(a.views)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
