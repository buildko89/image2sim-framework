"""P3-6 (koha9): 配色2.pdf のリファレンスに合わせて素材テクスチャを塗り替える。

p3_paint_texture.py の koha9 変種。仕組み（局所シェーディング比 × 目標色）は同一で、
柄の配置と色だけを 2026-07-12 の `input/配色2.pdf` に合わせて置き換えた。
p3_koha.glb / p3_koha_basecolor*.png は正典として残し、このスクリプトは
p3_koha9_* だけを出力する。

配色2.pdf から読み取った柄（赤丸の指摘箇所）:
  p1 上面: 背中の中央に「黒い斑を茶色の斑が取り囲む」ロゼット。肩は白。
  p1 上面: 頭頂は茶が広く、+X 側(猫の左)に黒帯が耳まで走る。
  p2 正面: 白いブレーズ広い。+X がこげ茶優勢 / -X は眉に赤茶の斑。**従来と左右が逆**。
           鼻の +X 脇に赤茶のそばかす（従来どおり）。耳の内側は肌色、縁は茶。
  p3 後面: 腰〜腿の後面は明るいフォーン一色。かかとから下はクリーム。黒斑なし。
  p4/p5 側面: 白地に独立した中間ラストの斑（腰の上・後腿）。背骨の尾側に細い黒帯。
              後脚のかかとに小さな黒斑。

色はリファレンス画像（レンダー）の実測中央値から採った:
  白地 (223,217,208) / 斑ラスト 明部 (174,132,104)〜陰 (85,45,30) / ロゼット黒 (13,13,13)
  後面フォーン (179,130,90) / 顔こげ茶 (68,55,45) / 耳内側 (195,160,146)

    python pipeline_v2/p3_paint_texture_koha9.py

出力:
    output_v2/textures/p3_koha9_basecolor.png
    output_v2/textures/p3_koha9_basecolor_alpha.png
    output_v2/reports/p3_koha9_texture_debug.png
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pathlib import Path

SRC_RGB = Path("input/cat2/koha9_cat/textures/Koha9Body_baseColor.png")
SRC_ALPHA = Path("input/cat2/koha9_cat/textures/Koha9Tail_baseColor.png")
NPZ = Path("output_v2/textures/p3_uv_position.npz")
OUT_RGB = Path("output_v2/textures/p3_koha9_basecolor.png")
OUT_RGBA = Path("output_v2/textures/p3_koha9_basecolor_alpha.png")
DEBUG = Path("output_v2/reports/p3_koha9_texture_debug.png")
FONT = "C:/Windows/Fonts/meiryo.ttc"

PART_BODY, PART_HEAD, PART_LEG, PART_TAIL = 1, 2, 3, 4

# 配色2.pdf のリファレンス実測（陰影込みのレンダー値から、中間〜明部を採用）
WHITE = np.array([223, 217, 208], float)
RUST = np.array([166, 110, 70], float)       # 脇腹・腰の独立斑（中間ラスト）
RUST_RING = np.array([150, 96, 60], float)   # 背中ロゼットの輪
BLACK = np.array([22, 20, 18], float)        # ロゼット中心・尾側の背骨の帯（ほぼ純黒）
FAWN = np.array([186, 138, 100], float)      # 後面（腰〜腿の後ろ）の明るいフォーン
HEEL_DARK = np.array([58, 50, 44], float)    # 後脚かかとの小斑
# 配色3.pdf (2026-07-12): 下腹の斑。p2(+X)はラスト寄り、p3(-X)はフォーン寄りの実測
BELLY_RUST = np.array([162, 108, 68], float)
BELLY_FAWN = np.array([182, 130, 92], float)
# 尻尾は今回の対応範囲外（この後に別途相談）。従来の色をそのまま使う。
TAN = np.array([168, 138, 104], float)
BROWN = np.array([48, 42, 38], float)
TAIL_BASE = np.array([127, 90, 56], float)
LEG_DARK = np.array([58, 48, 40], float)     # +X 前脚の後ろ（配色.pdf 由来。今回は変更なし）

# 柄の位置（glTF系 X=左右 Y=上下 Z=前後, +Z=頭側, **+X が猫の左**）。単位 m。
# 背側の表面は実測で Y≈0.174〜0.194（Z=-0.08〜+0.07）。
#
# 後に置いたものが上書きする。後面フォーン → 独立斑 → ロゼット輪 → ロゼット黒 →
# 尾側の黒帯 → 脚の斑。
BLOBS = [
    # 後面: 腰〜腿の後ろ向きの面をフォーン一色にする（p3）。かかとから下は
    # 楕円体の Y 範囲外になり白（クリーム）のまま残る。
    # ゲートを緩めにしないと尻の中央・尾根元の脇が白く残る（v1 で実測）。
    ("後面のフォーン",        (0.000, 0.115, -0.145), (0.085, 0.095, 0.070), FAWN, "rear_face"),
    # 白地に独立した斑（p4/p5）。腰の上（背骨の脇）と後腿の側面。
    # 後腿の斑は not_rear ゲートで後ろ向きの面から外す。真後ろ(p3)から見える縁が
    # 濃いラストになるとフォーン一色のリファレンスと合わない（v1 で実測）。
    ("+X 腰の斑",            (+0.046, 0.152, -0.096), (0.026, 0.040, 0.032), RUST, "dorsal"),
    ("-X 腰の斑",            (-0.046, 0.152, -0.096), (0.026, 0.040, 0.032), RUST, "dorsal"),
    ("+X 後腿の斑",          (+0.054, 0.092, -0.112), (0.024, 0.042, 0.048), RUST, "not_rear"),
    ("-X 後腿の斑",          (-0.054, 0.092, -0.112), (0.024, 0.042, 0.048), RUST, "not_rear"),
    # 腰のサドル（配色3.pdf p1 丸1）: 実物写真では尾根元〜黒斑の間の背骨上は白い筋ではなく
    # ラスト一続き。従来の「尾根元の黒帯」は実物に無いので削除し、サドルで置き換えた。
    ("腰のサドル",           (-0.005, 0.160, -0.112), (0.048, 0.055, 0.042), RUST_RING, "dorsal"),
    # 背中のロゼット: 黒斑の頭側(肩側)は白（配色3.pdf p1 丸2）。ただし
    # 修正上面.png (2026-07-12) で2箇所の白→茶の指示:
    #   丸1: サドルと黒斑の間の背骨上（-X 寄り）は白い筋ではなく茶が続く
    #   丸2: 黒斑の頭側の -X に、白で区切られた丸い茶斑がある
    ("サドル〜黒斑の間の茶", (-0.012, 0.180, -0.058), (0.035, 0.055, 0.032), RUST_RING, "dorsal"),
    ("ロゼット輪 +X後",      (+0.040, 0.176, -0.024), (0.033, 0.055, 0.034), RUST_RING, "dorsal"),
    ("ロゼット輪 -X後",      (-0.040, 0.176, -0.024), (0.033, 0.055, 0.034), RUST_RING, "dorsal"),
    ("-X 黒斑の頭側の丸斑",  (-0.038, 0.180, +0.050), (0.028, 0.055, 0.028), RUST, "dorsal"),
    ("ロゼット中心の黒",     (0.000, 0.186, +0.010), (0.030, 0.055, 0.034), BLACK, "dorsal"),
    # 下腹の斑（配色3.pdf p2/p3）: 下腹の縁に柔らかい斑。+X はラスト、-X はフォーン。
    ("+X 下腹のラスト",      (+0.054, 0.070, +0.005), (0.024, 0.038, 0.062), BELLY_RUST, None),
    ("-X 下腹のフォーン",    (-0.058, 0.075, -0.045), (0.020, 0.032, 0.045), BELLY_FAWN, None),
    # +X 前脚の後ろ（配色.pdf p3 指示のまま。今回の赤丸範囲外なので変更しない）
    ("+X 前脚の後ろの黒褐色", (+0.052, 0.048, 0.074), (0.022, 0.030, 0.016), LEG_DARK, "rear"),
    # 後脚のかかとの小さな黒斑（p4/p5 の赤丸内）
    # 後脚の実測: かかと(Z 最小側)は |X| 0.03〜0.05, Y 0〜0.03, Z -0.13〜-0.145
    # かかとは heel ゲート（rear より厳しい）。rear だと足の横〜前まで回り込む（実測）
    ("+X かかとの黒斑",      (+0.038, 0.022, -0.138), (0.014, 0.018, 0.014), HEEL_DARK, "heel"),
    ("-X かかとの黒斑",      (-0.038, 0.022, -0.138), (0.014, 0.018, 0.014), HEEL_DARK, "heel"),
]

DORSAL_GATE = -0.15   # 法線Y がこれ未満（＝腹側）には背側の斑を置かない
REAR_GATE = (0.35, 0.05)   # 法線Z がこれ以上（＝前向き）で 0、以下で 1
REAR_FACE_GATE = (0.15, -0.20)   # 法線Z がこれ以下（＝後ろ向き）で 1。後面フォーン用
HEAD_KEEP_Z = (0.099, 0.140)

# ---- 顔（配色2.pdf p1/p2）----
# **従来と左右が逆**: +X(猫の左, 正面レンダーの画面右) がこげ茶優勢、
# -X(猫の右) は眉に赤茶の斑。頭頂は茶が広く、額の前(耳の間)をこげ茶の帯が横切り、
# 白いブレーズはその帯の下で終わる。
# 左右の判定は罠⑬のとおり「リファレンスと同じ向きに写るレンダーはどれか」で行った:
#   正面像は画面右が +X（そばかすの側で確認済み）。配色2.pdf p2 では画面右がこげ茶優勢。
FACE_RUST = np.array([150, 100, 55], float)   # 眉の赤茶
CROWN_RUST = np.array([132, 86, 48], float)   # 頭頂の赤茶（真上からの光で飛ぶぶん濃いめ）
FACE_DARK = np.array([68, 54, 44], float)     # こげ茶の帯（黒ではなく暖色の焦げ茶）
FACE_BLACK = np.array([45, 38, 32], float)    # 耳の下など最暗部
FRECKLE = np.array([170, 110, 65], float)     # 鼻の +X 脇の赤茶のそばかす（p2 にもある）
EYE_LINER = np.array([48, 42, 38], float)
EAR_FLESH = np.array([205, 168, 152], float)  # 耳の前（内側）: 肌色
EAR_BROWN = np.array([140, 100, 72], float)   # -X 耳の後ろの茶
EAR_DARK = np.array([95, 70, 52], float)      # +X 耳の後ろ（こげ茶側の耳は暗い）

EYES = [((-0.0197, 0.2107, 0.1893), (0.0108, 0.0090, 0.0100)),
        ((+0.0202, 0.2120, 0.1879), (0.0108, 0.0090, 0.0100))]

EYE_ART_MAJOR = 1.38
EYE_ART_MINOR = 1.16
EYE_ART_SPAN = 1.8
EYE_LINER_R = (0.86, 1.10)
# 配色3.pdf: 目はリファレンスのオリーブ/ヘーゼルに合わせる。
# 素材の虹彩 (146,180,108) × このティントで目標 (150,145,95) 付近になる。
IRIS_TINT = np.array([1.03, 0.81, 0.88], float)

# ---- 耳の UV 分離（p1a_rebind_blender.EAR_UV_OFFSET と必ず同じ値にすること）----
EAR_UV_OFFSET = (-0.015137, -0.318604)

# 後に置いたものが上書きする。頭頂の茶 → 額の帯 → 顔の側面 → 耳の後ろ → 耳の前 → そばかす。
FACE_BLOBS = [
    # --- 頭頂: 茶が広く（-X 寄りで正中を跨ぐ）、+X に黒帯が耳へ走る ---
    # 頭頂は真上からの光で色が飛ぶので、少し濃い赤茶を広めに置く（v1 では白筋が残った）
    ("頭頂の茶",             (-0.008, 0.2450, 0.1500), (0.040, 0.030, 0.040), CROWN_RUST, None),
    ("+X 頭の黒帯(耳へ)",    (+0.032, 0.2400, 0.1560), (0.022, 0.028, 0.038), FACE_DARK, None),
    # --- 額の前(耳の間)を横切るこげ茶の帯。白いブレーズはこの下で終わる ---
    ("額の前のこげ茶の帯",   (+0.004, 0.2450, 0.1740), (0.030, 0.016, 0.020), FACE_DARK, None),
    # --- +X(猫の左): 耳の下から眉・目尻へ続く広いこげ茶の帯 ---
    ("+X 顔の帯 眉〜目尻",   (+0.036, 0.2240, 0.1740), (0.015, 0.024, 0.028), FACE_DARK, None),
    # 耳の付け根 +X の実測: X 0.022〜0.042, Y 0.230〜0.260, Z 0.130〜0.166
    ("+X 耳の下の黒",        (+0.034, 0.2420, 0.1480), (0.014, 0.016, 0.020), FACE_BLACK, None),
    # --- -X(猫の右): 眉の赤茶の斑 + 顔の外側のこげ茶 ---
    ("-X 眉の赤茶",          (-0.026, 0.2240, 0.1840), (0.013, 0.014, 0.016), FACE_RUST, None),
    ("-X 顔の外側のこげ茶",  (-0.046, 0.2200, 0.1660), (0.013, 0.024, 0.028), FACE_DARK, None),
    # --- 耳の後ろ ---
    ("-X 耳の後ろ: 茶",      (-0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_BROWN, "back"),
    ("+X 耳の後ろ: こげ茶",  (+0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_DARK, "back"),
    # --- 耳の前（内側）: 肌色。柄の後に置いて必ず上に来るようにする ---
    ("-X 耳の前: 肌色",      (-0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_FLESH, "front"),
    ("+X 耳の前: 肌色",      (+0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_FLESH, "front"),
    # --- そばかす: 鼻のすぐ脇（+X 側）。p2 のリファレンスにもある ---
    ("+X マズルのそばかす",  (+0.0172, 0.1948, 0.2122), (0.0066, 0.0050, 0.0060), FRECKLE, None),
]

FACE_GATES = {
    "front": (-0.05, 0.30),
    "back": (0.05, -0.30),
}
DETAIL_SIGMA = 22
DETAIL_OFFSET = 25.0
DETAIL_CLAMP = (0.60, 1.50)
TAIL_RINGS = 5.5

FACE_DETAIL_SIGMA = 6
FACE_DETAIL_CLAMP = (0.85, 1.15)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def upsample(a: np.ndarray, size: int) -> np.ndarray:
    """(H,W) または (H,W,C) を size×size へ。マスク・部位は最近傍、連続量は双一次。"""
    if a.dtype == bool or a.dtype == np.uint8:
        im = Image.fromarray(a.astype(np.uint8))
        return np.asarray(im.resize((size, size), Image.NEAREST)).astype(a.dtype)
    if a.ndim == 2:
        im = Image.fromarray(a.astype(np.float32))
        return np.asarray(im.resize((size, size), Image.BILINEAR))
    return np.stack([upsample(a[..., i], size) for i in range(a.shape[2])], axis=-1)


def blob_alpha(pos, center, radii):
    d = (pos - np.array(center)) / np.array(radii)
    f = np.sqrt((d ** 2).sum(-1))
    return smoothstep(1.02, 0.72, f)


def ring_alpha(pos, center, radii, r0, r1):
    d = (pos - np.array(center)) / np.array(radii)
    f = np.sqrt((d ** 2).sum(-1))
    return smoothstep(r0, r0 + 0.10, f) * smoothstep(r1, r1 - 0.15, f)


EAR_REGION = {"y": 0.250, "z": (0.115, 0.175)}


def copy_ear_art(rgb: np.ndarray, pos: np.ndarray, mask: np.ndarray):
    """+X の耳の UV 島を移した先へ、素材テクスチャの絵をそのまま複製する。"""
    N = rgb.shape[0]
    drow = int(round(EAR_UV_OFFSET[1] * (N - 1)))
    dcol = int(round(EAR_UV_OFFSET[0] * (N - 1)))
    shifted = np.roll(rgb, (drow, dcol), axis=(0, 1))

    dest = (mask & (pos[..., 0] > 0.0) & (pos[..., 1] > EAR_REGION["y"])
            & (pos[..., 2] > EAR_REGION["z"][0]) & (pos[..., 2] < EAR_REGION["z"][1]))
    out = np.where(dest[..., None], shifted, rgb)
    return out, int(dest.sum())


def magnify_eye_art(rgb: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """素材の目の絵をテクセル空間で拡大する（拡大の中心は虹彩の重心。罠⑱）。"""
    N = rgb.shape[0]
    ii, jj = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
    out = rgb.copy()
    for c, rad in EYES:
        span = blob_alpha(pos, c, tuple(r * EYE_ART_SPAN for r in rad)) > 0.01
        if not span.any():
            continue

        iris = span & (rgb[..., 1] > rgb[..., 0] + 25) & (rgb[..., 1] > 130)
        if iris.sum() < 20:
            continue
        py, px = np.nonzero(iris)
        cy, cx = py.mean(), px.mean()

        cov = np.cov(np.stack([py - cy, px - cx]))
        major = np.linalg.eigh(cov)[1][:, -1]
        minor = np.array([-major[1], major[0]])

        dy, dx = ii - cy, jj - cx
        a = (dy * major[0] + dx * major[1]) / EYE_ART_MAJOR
        b = (dy * minor[0] + dx * minor[1]) / EYE_ART_MINOR
        si = np.clip(np.rint(cy + a * major[0] + b * minor[0]).astype(int), 0, N - 1)
        sj = np.clip(np.rint(cx + a * major[1] + b * minor[1]).astype(int), 0, N - 1)
        out = np.where(span[..., None], rgb[si, sj], out)
    return out


def main() -> int:
    src = Image.open(SRC_RGB).convert("RGB")
    N = src.size[0]
    rgb = np.asarray(src).astype(float)

    z = np.load(NPZ)
    pos = upsample(z["pos"], N)
    nrm = upsample(z["nrm"], N)
    part = upsample(z["part"], N)
    mask = upsample(z["mask"].astype(np.uint8), N).astype(bool)

    rgb, ear_texels = copy_ear_art(rgb, pos, mask)
    print(f"  +X の耳へ素材の絵を複製: {ear_texels:,} テクセル")
    rgb = magnify_eye_art(rgb, pos)
    print(f"  目の絵を拡大: 主軸 x{EYE_ART_MAJOR} / 副軸 x{EYE_ART_MINOR}")

    # --- 局所シェーディング比（毛の流れを残すための素） ---
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    blur = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(DETAIL_SIGMA))).astype(float)
    detail = np.clip((lum + DETAIL_OFFSET) / (blur + DETAIL_OFFSET), *DETAIL_CLAMP)[..., None]
    # 素材の黒いサドルの「境界」は |lum - blur| が毛の細部よりずっと大きく、比に残ると
    # 白地に灰色の筋のゴーストになる（配色3.pdf p1 丸2 で指摘された筋の正体）。
    # 大きな段差だけ比を 1 に寄せ、毛の細部（小さな段差）は残す。
    edge = np.abs(lum - blur)
    ghost = 1.0 - smoothstep(45.0, 95.0, edge)[..., None]
    detail = 1.0 + (detail - 1.0) * ghost
    # さらに、旧サドル内部（素材が暗い領域）の粗い毛のうねりは中程度の段差なので上の
    # 抑制をすり抜け、白地に灰色の波状の筋として残る。素材が暗い領域だけ、比の振幅を
    # 顔と同じ ±15% に絞る（明るい領域の毛の細部はそのまま）。
    wbright = smoothstep(60.0, 130.0, blur)[..., None]
    tight = np.clip(detail, 0.85, 1.15)
    detail = tight + (detail - tight) * wbright

    # --- 保護領域: 頭（目・鼻・柄）と、ピンクの部位（肉球・鼻・耳の内側） ---
    head = smoothstep(HEAD_KEEP_Z[0], HEAD_KEEP_Z[1], pos[..., 2])
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    keep_pink = (r > 140) & ((r - g) > 25) & ((g - b) < 20)
    keep_eye = np.zeros(pos.shape[:2], float)
    for c, rad in EYES:
        keep_eye = np.maximum(keep_eye, blob_alpha(pos, c, rad))
    keep = np.clip(np.maximum(keep_eye, keep_pink.astype(float)), 0, 1)
    print(f"  素材を残すテクセル: 目 {float((keep_eye>0.5)[mask].mean()):.2%} / "
          f"ピンク(肉球・鼻・耳内) {float(keep_pink[mask].mean()):.2%}")

    # --- 胴・脚: 白を土台に、リファレンスの斑を置く ---
    out = np.broadcast_to(WHITE, rgb.shape).copy()
    gates = {
        "dorsal": smoothstep(DORSAL_GATE, DORSAL_GATE + 0.30, nrm[..., 1]),
        "rear": smoothstep(REAR_GATE[0], REAR_GATE[1], nrm[..., 2]),
        "heel": smoothstep(0.00, -0.35, nrm[..., 2]),
        "rear_face": smoothstep(REAR_FACE_GATE[0], REAR_FACE_GATE[1], nrm[..., 2]),
    }
    gates["not_rear"] = 1.0 - gates["rear_face"]
    paintable = mask & (keep < 0.5) & (part != PART_TAIL)
    for name, c, rad, col, gate in BLOBS:
        a = blob_alpha(pos, c, rad)
        if gate:
            a = a * gates[gate]
        out = out * (1 - a[..., None]) + col * a[..., None]
        cov = float((a[paintable] > 0.5).sum()) / max(paintable.sum(), 1)
        print(f"  斑 {name:22} 実効面積 {cov:6.2%}（胴・脚の塗り替え領域に対して）")

    out = out * detail

    # --- 尻尾: 今回の対応範囲外。従来の p3 と同じ塗り（この後に別途相談） ---
    tail = part == PART_TAIL
    if tail.any():
        root = pos[tail][np.argsort(pos[tail][:, 1])[:200]].mean(0)
        dist = np.linalg.norm(pos - root, axis=-1)
        tlen = np.percentile(dist[tail], 98)
        t = np.clip(dist / max(tlen, 1e-6), 0, 1)

        lo, hi = np.percentile(lum[tail], [8, 92])
        ln = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1)

        wobble = 0.10 * (np.sin(pos[..., 0] * 190.0) + np.sin(pos[..., 2] * 130.0))
        ring = 0.5 + 0.5 * np.sin((t * TAIL_RINGS + wobble) * 2 * np.pi)
        ring = smoothstep(0.30, 0.85, ring)

        mix = np.clip(0.70 * (1 - ln) + 0.40 * ring - 0.12, 0, 1)[..., None]
        tail_col = TAN * (1 - mix) + BROWN * mix

        tail_col = tail_col * (1 - smoothstep(0.34, 0.08, t)[..., None]) \
            + TAIL_BASE * smoothstep(0.34, 0.08, t)[..., None]
        blend = smoothstep(0.015, 0.09, t)[..., None]
        tail_col = out * (1 - blend) + tail_col * blend

        out = np.where(tail[..., None], tail_col, out)

    # --- 顔: 白いブレーズ + 配色2.pdf の左右非対称の柄 ---
    fblur = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                       .filter(ImageFilter.GaussianBlur(FACE_DETAIL_SIGMA))).astype(float)
    fdetail = np.clip((lum + DETAIL_OFFSET) / (fblur + DETAIL_OFFSET), *FACE_DETAIL_CLAMP)[..., None]

    fgates = {k: smoothstep(lo, hi, nrm[..., 2]) for k, (lo, hi) in FACE_GATES.items()}
    face_col = np.broadcast_to(WHITE, rgb.shape).copy() * fdetail
    for name, c, rad, col, gate in FACE_BLOBS:
        a = blob_alpha(pos, c, rad)
        if gate:
            a = a * fgates[gate]
        a = a[..., None]
        face_col = face_col * (1 - a) + (col * fdetail) * a
        print(f"  顔 {name:24} 実効面積 {float((a[...,0]>0.5)[head>0.5].mean()):6.2%}")

    liner = np.zeros(pos.shape[:2], float)
    for c, rad in EYES:
        liner = np.maximum(liner, ring_alpha(pos, c, rad, *EYE_LINER_R))
    a = liner[..., None]
    face_col = face_col * (1 - a) + (EYE_LINER * fdetail) * a
    print(f"  顔 アイライン                     実効面積 {float((liner>0.5)[head>0.5].mean()):6.2%}")

    hm = (head * (1.0 - keep))[..., None]
    out = out * (1 - hm) + face_col * hm

    iris = (keep_eye > 0.5) & (rgb[..., 1] > rgb[..., 0] + 10)
    src_keep = np.where(iris[..., None], np.clip(rgb * IRIS_TINT, 0, 255), rgb)
    print(f"  目 虹彩の色を緑側へ: {int(iris.sum()):,} テクセル")

    k = keep[..., None]
    out = out * (1 - k) + src_keep * k
    out = np.where(mask[..., None], out, rgb)
    out = np.clip(out, 0, 255).astype(np.uint8)

    OUT_RGB.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(OUT_RGB)
    alpha = np.asarray(Image.open(SRC_ALPHA).convert("RGBA"))[..., 3]
    Image.fromarray(np.dstack([out, alpha])).save(OUT_RGBA)
    print(f"-> {OUT_RGB}")
    print(f"-> {OUT_RGBA}")

    # --- 目視用デバッグシート ---
    regions = np.zeros_like(out)
    regions[mask] = (60, 60, 62)
    for _, c, rad, col, gate in BLOBS:
        a = blob_alpha(pos, c, rad) * (gates[gate] if gate else 1.0)
        regions = (regions * (1 - a[..., None]) + col * a[..., None]).astype(np.uint8)
    regions[tail] = (200, 90, 200)
    for _, c, rad, col, gate in FACE_BLOBS:
        a = blob_alpha(pos, c, rad) * (head > 0.5) * (fgates[gate] if gate else 1.0)
        regions = (regions * (1 - a[..., None]) + col * a[..., None]).astype(np.uint8)
    a = liner * (head > 0.5)
    regions = (regions * (1 - a[..., None]) + EYE_LINER * a[..., None]).astype(np.uint8)
    regions[keep > 0.5] = (240, 230, 90)

    cells = [(src, "素材"),
             (Image.fromarray(regions), "柄の定義: 斑=目標色 / 紫=尻尾(据え置き) / 黄=保護"),
             (Image.fromarray(out), "koha9 出力（配色2.pdf 準拠）")]
    cw = 1000
    sheet = Image.new("RGB", (cw * 3 + 40, cw + 60), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 17)
    d.text((10, 6), "koha9 テクスチャ塗り替え検証 — 配色2.pdf のロゼット/後面フォーン/顔の左右反転",
           fill=(255, 235, 120), font=f)
    for i, (img, lab) in enumerate(cells):
        sheet.paste(img.resize((cw, cw)), (i * (cw + 10) + 10, 50))
        d.text((i * (cw + 10) + 12, 30), lab, fill=(255, 235, 120), font=f)
    DEBUG.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(DEBUG)
    print(f"-> {DEBUG}  {sheet.size}  (必ず目視すること)")

    painted = mask & (keep < 0.5)
    print(f"\n塗り替えたテクセル: {painted.sum():,} / {mask.sum():,} "
          f"({painted.sum()/mask.sum():.1%})   保護: {int((mask & (keep >= 0.5)).sum()):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
