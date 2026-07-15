# -*- coding: utf-8 -*-
"""P4-顔第2段階: メッシュ変形前後の npz（UV→3D ベイク）から、
塗り・髭の 3D アンカーを「同一テクセル対応」で再マップする。

UV は変形で変わらないので、旧 npz で旧アンカーに最も近い表面テクセル群を探し、
同じテクセルの新 npz の位置を読めば、新しいアンカー座標になる。
"""
import sys
import numpy as np

# 使い方: 変形前に現行 npz をコピーして OLD に指定し、ANCHORS を現行スクリプトの値に
# 合わせてから、再ベイク後に実行する。
OLD = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output_v2\backup_p4face2_20260715\p3_uv_position_stage2.npz"
NEW = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output_v2\textures\p3_uv_position.npz"

o = np.load(OLD)
n = np.load(NEW)
po = o["pos"].astype(np.float64)
pn = n["pos"].astype(np.float64)
valid = o["mask"].astype(bool) & n["mask"].astype(bool)
flat_old = po[valid]
flat_new = pn[valid]

K = 48


def remap(pt):
    d = ((flat_old - np.array(pt)) ** 2).sum(-1)
    idx = np.argpartition(d, K)[:K]
    old_med = np.median(flat_old[idx], axis=0)
    new_med = np.median(flat_new[idx], axis=0)
    # アンカーは表面から少し浮いている場合があるので、表面の移動量を足す方式にする
    return np.array(pt) + (new_med - old_med), np.sqrt(d[idx].max())


ANCHORS = {
    # EYES (中心)
    "EYE -X": (-0.0212, 0.2092, 0.1902),
    "EYE +X": (+0.0217, 0.2098, 0.1886),
    # 鼻
    "NOSE": (0.0, 0.196, 0.2227),
    # FACE_BLOBS
    "頭頂の茶": (-0.0113, 0.2450, 0.1500),
    "+X 頭の黒帯(耳へ)": (+0.0323, 0.2400, 0.1560),
    "額の前のこげ茶の帯": (+0.0043, 0.2450, 0.1740),
    "+X 顔の帯 眉〜目尻": (+0.0373, 0.2240, 0.1740),
    "+X 耳の下の黒": (+0.0392, 0.2420, 0.1480),
    "-X 眉の赤茶": (-0.0269, 0.2240, 0.1840),
    "-X 顔の外側のこげ茶": (-0.0480, 0.2200, 0.1660),
    "-X 耳の後ろ: 茶": (-0.0433, 0.2639, 0.1440),
    "+X 耳の後ろ: こげ茶": (+0.0430, 0.2642, 0.1440),
    "+X マズルのそばかす": (+0.0179, 0.1948, 0.2205),
    # 髭の根元 (p3c ROWS: (ax, y, az) を +X 側で)
    "WK 上段": (0.0145, 0.1945, 0.2243),
    "WK 中段": (0.0170, 0.1895, 0.2208),
    "WK 下段": (0.0179, 0.1845, 0.2188),
    "WK 眉": (0.0190, 0.2270, 0.1855),
}

print(f"valid texels: {valid.sum():,}")
for name, pt in ANCHORS.items():
    new_pt, spread = remap(pt)
    d = new_pt - np.array(pt)
    print(f"{name:24s} old=({pt[0]:+.4f},{pt[1]:+.4f},{pt[2]:+.4f})"
          f" -> new=({new_pt[0]:+.4f},{new_pt[1]:+.4f},{new_pt[2]:+.4f})"
          f"  d=({d[0]:+.4f},{d[1]:+.4f},{d[2]:+.4f}) r={spread*1000:.1f}mm")

# 目の保護楕円の X 半径のスケール（頬の拡幅で表面が X に伸びた分）
for name in ("EYE -X", "EYE +X"):
    pt = ANCHORS[name]
    new_pt, _ = remap(pt)
    if abs(pt[0]) > 1e-6:
        print(f"{name} x-scale: {new_pt[0] / pt[0]:.3f}")
