"""P1 の目視ゲート素材: 4方向 × 全アニメ × 3フレーム のコンタクトシートを作る。

    python pipeline_v2/p1_capture.py --glb output_v2/base/p1a_koha.glb --prefix p1a

カメラのフレーミングは GLB のレスト姿勢から実測して Godot に渡す
（Godot の MeshInstance3D.get_aabb() はスキン付きメッシュで当てにならない）。
機械ゲート（qa_skin_stretch.py）が PASS しても、貫通・めり込み・毛のはみ出しは
数値に出ない。必ずこのシートを目で見ること。
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_skin_stretch as q  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
GODOT = Path(r"D:\Godot_v4.6-stable_mono_win64\Godot_v4.6-stable_mono_win64_console.exe")
GODOT_PROJ = REPO / "output_v2/godot/Godot3dcat"
SHOTS = REPO / "output_v2/reports/p1_shots"
FONT = "C:/Windows/Fonts/meiryo.ttc"
VIEWS = ["front", "left", "right", "back"]
TIMES = [15, 45, 80]
FOV = 45.0
RES = 720


def rest_bounds(glb: Path):
    """レスト姿勢の頂点から、ピボット・カメラ距離・モデル寸法を出す。

    距離はバウンディング球が画角にちょうど収まる値。既定 fov=75 のまま
    対角長を距離にすると、猫がフレームの3割にしか写らずシートで潰れる。
    """
    gltf, blob = q.load_glb(glb)
    pts = []
    for nd in gltf["nodes"]:
        if "mesh" not in nd:
            continue
        for prim in gltf["meshes"][nd["mesh"]]["primitives"]:
            pts.append(q.read_accessor(gltf, blob, prim["attributes"]["POSITION"]).astype(float))
    p = np.vstack(pts)
    lo, hi = p.min(0), p.max(0)
    pivot = (lo + hi) / 2
    pivot[1] = lo[1] + (hi[1] - lo[1]) * 0.45
    extent = float(np.linalg.norm(hi - lo))
    bounding_radius = extent / 2.0
    dist = bounding_radius / np.tan(np.radians(FOV / 2.0)) * 1.05
    return pivot, float(dist), extent


def head_bounds(glb: Path):
    """頭部（前方 Z が大きい側）のレスト頂点から、クローズアップ用のピボットと距離を出す。"""
    gltf, blob = q.load_glb(glb)
    pts = []
    for nd in gltf["nodes"]:
        if "mesh" not in nd:
            continue
        for prim in gltf["meshes"][nd["mesh"]]["primitives"]:
            pts.append(q.read_accessor(gltf, blob, prim["attributes"]["POSITION"]).astype(float))
    p = np.vstack(pts)
    head = p[p[:, 2] > p[:, 2].max() - 0.085]
    lo, hi = head.min(0), head.max(0)
    pivot = (lo + hi) / 2
    br = float(np.linalg.norm(hi - lo)) / 2.0
    dist = br / np.tan(np.radians(30.0 / 2.0)) * 1.05   # 頭部は fov=30 で撮る
    return pivot, float(dist)


def capture(glb: Path, prefix: str) -> None:
    shutil.copy(glb, GODOT_PROJ / glb.name)
    subprocess.run([str(GODOT), "--headless", "--path", str(GODOT_PROJ), "--import"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    pivot, radius, extent = rest_bounds(glb)
    hp, hr = head_bounds(glb)
    print(f"[{prefix}] pivot={np.round(pivot,4).tolist()} dist={radius:.4f} extent={extent:.4f}")
    print(f"[{prefix}] head pivot={np.round(hp,4).tolist()} dist={hr:.4f}")

    p = subprocess.run([
        str(GODOT), "--path", str(GODOT_PROJ), "res://scenes/CaptureGrid.tscn", "--",
        f"--model=res://{glb.name}", f"--prefix={prefix}", f"--out={SHOTS.as_posix()}",
        f"--pivot={pivot[0]},{pivot[1]},{pivot[2]}", f"--radius={radius}", f"--extent={extent}",
        f"--fov={FOV}", f"--res={RES}",
        f"--headpivot={hp[0]},{hp[1]},{hp[2]}", f"--headradius={hr}",
    ], capture_output=True, text=True, encoding="utf-8", errors="replace")
    for ln in p.stdout.splitlines():
        if re.search(r"FRAMING|SHOTS|HEADSHOTS|DONE|ERROR|error", ln):
            print("  " + ln)
    if "DONE" not in p.stdout:
        print(p.stdout[-2000:])
        print(p.stderr[-2000:])
        raise SystemExit("capture failed")


def _grid(title: str, sub: str, rows: list[tuple[str, list[Path]]], col_labels: list[str],
          cell: int, dst: Path) -> Path:
    lab_w, hdr_h, lab_h = 120, 62, 18
    W = lab_w + len(col_labels) * cell
    H = hdr_h + len(rows) * (cell + lab_h)
    out = Image.new("RGB", (W, H), (18, 18, 20))
    d = ImageDraw.Draw(out)
    f_t, f_s, f_l = (ImageFont.truetype(FONT, 18), ImageFont.truetype(FONT, 12),
                     ImageFont.truetype(FONT, 14))
    d.text((10, 8), title, fill=(255, 235, 120), font=f_t)
    d.text((10, 34), sub, fill=(185, 185, 190), font=f_s)
    for ci, cl in enumerate(col_labels):
        d.text((lab_w + ci * cell + 6, hdr_h - 16), cl, fill=(150, 200, 220), font=f_s)
    for ri, (rl, paths) in enumerate(rows):
        y = hdr_h + ri * (cell + lab_h)
        d.text((8, y + cell // 2 - 8), rl, fill=(255, 235, 120), font=f_l)
        for ci, p in enumerate(paths):
            if not p.exists():
                continue
            im = Image.open(p).convert("RGB")
            im.thumbnail((cell, cell))
            out.paste(im, (lab_w + ci * cell + (cell - im.width) // 2,
                           y + (cell - im.height) // 2))
    out.save(dst)
    print(f"  -> {dst.name}  {out.size}")
    return dst


def sheets(prefix: str) -> None:
    # <prefix>_head_<view>.png はレスト姿勢の頭部クローズアップ。アニメではない。
    files = [f for f in sorted(SHOTS.glob(f"{prefix}_*.png"))
             if not f.stem.startswith(f"{prefix}_head_")]
    anims = sorted({f.stem.split("_t")[0][len(prefix) + 1:] for f in files})
    if not anims:
        raise SystemExit(f"no shots for {prefix}")
    note = "破片・欠損・貫通・接地ずれを探す。緑（背景）が体の内側に見えたら穴。"

    # 全体像: 各アニメ × 4方向（中間フレーム）
    _grid(f"{prefix}  概観  —  全アニメ × 4方向 (t45)", note,
          [(a, [SHOTS / f"{prefix}_{a}_t45_{v}.png" for v in VIEWS]) for a in anims],
          VIEWS, 300, REPO / f"output_v2/reports/p1_contact_{prefix}_overview.png")

    # アニメ別: 3フレーム × 4方向
    for a in anims:
        _grid(f"{prefix}  {a}  —  3フレーム × 4方向", note,
              [(f"t{t}", [SHOTS / f"{prefix}_{a}_t{t:02d}_{v}.png" for v in VIEWS])
               for t in TIMES],
              VIEWS, 340, REPO / f"output_v2/reports/p1_contact_{prefix}_{a}.png")


def main() -> int:
    global RES
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--skip-capture", action="store_true")
    ap.add_argument("--res", type=int, default=RES,
                    help="キャプチャ解像度。ゴミ・毛の確認はユーザーの実機に合わせ 1440 で行う")
    a = ap.parse_args()
    RES = a.res

    SHOTS.mkdir(parents=True, exist_ok=True)
    if not a.skip_capture:
        capture(Path(a.glb), a.prefix)
    sheets(a.prefix)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
