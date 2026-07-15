"""P3-1: 素材テクスチャを koha の柄に塗り替える（印象合わせ）。

方針: **塗り直すのではなく「塗り替える」。**
素材の 4096² baseColor には手描きの毛の流れ・陰影・目・鼻・肉球が描き込まれている。
これを捨てるとのっぺりする。そこで各テクセルの明度から「局所的な陰影の比」を取り出し、
その比を目標色に掛ける。毛のディテールは残したまま色だけが変わる。

    detail = L / blur(L)        （局所シェーディング比）
    out    = target_color * detail

目標色は `config/cat_color_palette_v3_raw_photos.yaml`（写真からWB補正して実測）。
柄の位置は `pipeline_v2/p3_uv_bake.py` が焼いた「テクセル → 3D位置」から定義する。

素材の2枚のテクスチャは RGB が完全に同一（毛シェル用はアルファが付くだけ）なので、
1枚塗って両方に使い回す。

    python pipeline_v2/p3_paint_texture.py

出力:
    output_v2/textures/p3_koha_basecolor.png        （胴用 RGB）
    output_v2/textures/p3_koha_basecolor_alpha.png  （毛シェル用 RGBA）
    output_v2/reports/p3_texture_debug.png          （目視確認用）
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pathlib import Path

SRC_RGB = Path("input/cat2/koha9_cat/textures/Koha9Body_baseColor.png")
SRC_ALPHA = Path("input/cat2/koha9_cat/textures/Koha9Tail_baseColor.png")
NPZ = Path("output_v2/textures/p3_uv_position.npz")
OUT_RGB = Path("output_v2/textures/p3_koha_basecolor.png")
OUT_RGBA = Path("output_v2/textures/p3_koha_basecolor_alpha.png")
DEBUG = Path("output_v2/reports/p3_texture_debug.png")
FONT = "C:/Windows/Fonts/meiryo.ttc"

PART_BODY, PART_HEAD, PART_LEG, PART_TAIL = 1, 2, 3, 4

# config/cat_color_palette_v3_raw_photos.yaml の実測値（中央値）
WHITE = np.array([222, 219, 217], float)
RUST = np.array([118, 77, 44], float)        # 標準（腰）
RUST_CORE = np.array([95, 59, 31], float)    # 斑の中心（肩）
BLACK = np.array([45, 39, 33], float)        # 顔のマスク由来。採光の良い黒
# 尻尾は「うす茶色と黒を混ぜた感じ」（配色.pdf p1）。従来の TAN は白っぽく、BROWN も
# 中途半端な褐色で、写真の「淡い茶 × 黒」のコントラストが出ていなかった。
TAN = np.array([168, 138, 104], float)       # 尻尾の淡いリング（うす茶）
BROWN = np.array([48, 42, 38], float)        # 尻尾の濃いリング（黒に寄せる）
TAIL_BASE = np.array([127, 90, 56], float)   # 尾根元の橙み
LEG_DARK = np.array([58, 48, 40], float)     # 左前脚の後ろ「黒と茶色が混じった色」

# 柄の位置（glTF系 X=左右 Y=上下 Z=前後, +Z=頭側, **+X が猫の左**）。単位 m。
#
# 出典（2026-07-11 にユーザーが追加した写真）:
#   俯瞰      input/raw_photos/all/P_20260710_213926.jpg
#   俯瞰(左)  input/raw_photos/all/P_20260710_212422.jpg
#   俯瞰(右)  input/raw_photos/all/P_20260710_212431.jpg
#   背面      input/raw_photos/all/1679530488364.jpg
#   左側面    input/raw_photos/all/leftreg.png
#
# 写真から読み取れる配置（頭 -> 尾）:
#   肩にジンジャー → **その後ろの背中に大きな黒** → 背骨の中央は白 → 腰に左右のジンジャー
#   → 尾根元に黒。黒い背中の斑はこれまでモデルに無く、写真で最も目立つ塊だった。
#
# 背側の表面は実測で Y≈0.174〜0.194（Z=-0.08〜+0.07）。Y=0.20 に置くと体表の上空になり効かない。
BLOBS = [
    # (名前, 中心 xyz, 半径 xyz, 色, 法線ゲート)
    ("肩のジンジャー",       (-0.008, 0.182, 0.060), (0.042, 0.058, 0.042), RUST_CORE, "dorsal"),
    ("背中の黒い斑",         (+0.010, 0.186, 0.008), (0.036, 0.055, 0.042), BLACK, "dorsal"),
    # 真後ろから見ると **腰から腿まで全体が茶色**（配色.pdf p1「全体的に茶色にする」）。
    # 従来は腰に小さな斑を置くだけで、後ろ姿がほとんど白かった。
    # 腹側ゲートを外して腿の外側まで回り込ませ、白く残すのは正中の細い筋だけにする。
    ("猫の右の腰〜腿のジンジャー", (-0.042, 0.115, -0.105), (0.040, 0.090, 0.070), RUST, "dorsal_low"),
    ("猫の左の腰〜腿のジンジャー", (+0.042, 0.115, -0.105), (0.040, 0.090, 0.070), RUST, "dorsal_low"),
    ("尾根元の黒斑",         (0.000, 0.152, -0.116), (0.030, 0.052, 0.046), BLACK, "dorsal"),
    # 前脚の後ろの「黒と茶色が混じった色」（配色.pdf p3 で +X の脚に追加を指示、
    # p4 で -X の脚のものは「逆側の足にある。削除」と指示された）。
    #
    # **どちら側かは、ユーザーが丸を付けた glb のレンダーがどちら向きかで決める。**
    # p3 の glb は猫が画面左を向く = +X のカメラ。p4 の glb は画面右を向く = -X のカメラ。
    # 左右の呼び名は骨（bip01_l_* が +X）とキャプチャのラベル（VIEWS["left"] = -X）とで
    # 食い違っているので、名前で決めてはいけない。
    #
    # 断面は Y=0.05 で Z 0.066(後)〜0.117(前), |X| 0.030〜0.067。斑は脚の **後ろの外側の角** に
    # 置く。真後ろを向いた面だけに置くと側面から見たとき脚の外皮に隠れて見えない。
    ("+X 前脚の後ろの黒褐色", (+0.052, 0.048, 0.074), (0.022, 0.030, 0.016), LEG_DARK, "rear"),
]

DORSAL_GATE = -0.15   # 法線Y がこれ未満（＝腹側）には背側の斑を置かない
DORSAL_LOW_GATE = -0.55   # 腰〜腿は腹の下まで回り込ませる（後ろ姿を茶色にするため）
# 脚の斑は「後ろ〜横」を向いた面に乗せる。真後ろだけに絞ると側面から見えない。
REAR_GATE = (0.35, 0.05)   # 法線Z がこれ以上（＝前向き）で 0、以下で 1
# 頭の範囲（Z = 前後、+Z が頭側）。
# ボーンで判定してはいけない: ウェイト平滑化のせいで顔のテクセルの支配ボーンは
# bip01_head ではなく bip01_neck になっており、骨で切ると顔が真っ白になる（失敗済み）。
HEAD_KEEP_Z = (0.099, 0.140)

# ---- 顔 ----
# 素材の顔は目の周りまで黒く「アライグマ」寄り。koha は白いブレーズが額の中央から
# 鼻筋・マズル・顎まで一続きに広く、色は耳の付け根と目の外側にしか乗らない。
# 参照: input/raw_photos/face/1701442043866.jpg, 1648460789455.jpg
#
# 頭の UV は鏡像共有ではない（左右の対応点の UV 距離 中央値 0.103、同一なのは 2.6%）。
# よって左右非対称の顔をテクスチャで作れる。**猫の左は +X 側**（正面レンダーでは画面右）。
#
# 上から見た写真 input/raw_photos/face2/1648713873399_frame_002490.jpg で分かったこと:
#   **黒は頭頂を横切る帯**であって、目の周りではない。白いブレーズが鼻から額を通って
#   頭頂まで伸び、その黒帯を左右に割る。ジンジャーは両方の眉〜こめかみに広く乗る。
#   目の下の頬は白い。暗色は顔の外側（耳の下）にだけ回り込む。
#
# 3D ランドマーク（**2026-07-11 に頭を 1.10 倍・耳を高く・喉を引っ込めた後で再実測**）:
#   鼻先 (+0.0114, 0.1881, 0.2272) / 鼻(ピンク)の中心 (+0.0119, 0.1897, 0.2254)
#   虹彩 右(-0.0150, 0.2090, 0.1973) 左(+0.0217, 0.2137, 0.1922)
#     ※素材の目は 3D で左右対称に描かれていない（メッシュを対称化しても UV は非対称のまま）。
#       中心は必ず左右それぞれ実測する。片方の値を鏡像にすると保護がずれ、
#       素材の黒いアイマスクの縁が灰色の輪として顔に浮き出る。
#   頭頂 Y=0.246 で |X|max 0.044, Z 0.130〜0.176
#   耳の板 Y 0.255〜0.284, |X| 0.019〜0.053, Z 0.136〜0.158（背が 16mm -> 29mm に伸びた）
FACE_ORANGE = np.array([150, 100, 55], float)
FACE_DARK = np.array([72, 64, 58], float)
FACE_BLACK = np.array([38, 34, 32], float)
FRECKLE = np.array([168, 118, 78], float)
EYE_LINER = np.array([48, 42, 38], float)    # 目のふち。写真の koha は目の周りが濃く縁取られる
EAR_FLESH = np.array([198, 158, 148], float)  # 耳の前（内側）: 肌色に近い（配色.pdf p8）
EAR_BROWN = np.array([135, 88, 52], float)    # 耳の後ろの茶（配色.pdf p9）

# 目の中心（p2 のレストのポーズ汚染を直したあとに再実測。左右がほぼ鏡像になった）。
# 保護は素材の目の絵をぎりぎり覆う大きさにする。大きすぎると素材の黒いアイマスクが残り、
# 白い顔に黒いゴーグルを掛けたようになる。
#
# 「目は左右とももう少し大きめ」「もう少し横長」（配色.pdf p8）に応えるため、
# **素材の目の絵をテクセル空間で拡大する**（EYE_ART_*）。保護の半径もそれに合わせて広げ、
# 横（X）を縦（Y）より大きく取って横長にする。
EYES = [((-0.0197, 0.2107, 0.1893), (0.0108, 0.0090, 0.0100)),
        ((+0.0202, 0.2120, 0.1879), (0.0108, 0.0090, 0.0100))]

# 素材の目の絵の拡大率。主軸（虹彩の長軸 = 目の横方向）を強めに伸ばして横長にする。
# 大きくしすぎると素材の瞳（暗色）まで拡大されて真っ黒な目になる。
EYE_ART_MAJOR = 1.38
EYE_ART_MINOR = 1.16
EYE_ART_SPAN = 1.8      # 目の中心からこの正規化距離まで拡大する（保護の外は白で塗り潰される）

# アイライン: 素材の目の絵の **縁の上** に重ねる。保護の外側（f>1.02）に置くと、
# 目の絵と輪の間に白い隙間ができて「白目を黒く縁取ったアニメ目」になる（実測）。
EYE_LINER_R = (0.86, 1.10)

# 素材の虹彩は黄緑 (146,180,108)。写真の koha はもっと落ち着いた緑なので、
# 保護した目のうち虹彩（緑が赤より強いテクセル）だけを緑側へ寄せる。
IRIS_TINT = np.array([0.88, 1.00, 1.25], float)

# ---- 耳の UV 分離（p1a_rebind_blender.EAR_UV_OFFSET と必ず同じ値にすること）----
# +X の耳の UV 島を空き領域へ逃がしたので、**素材テクスチャの絵も同じ分だけ複製する**。
# これをやらないと、移動先には素材の絵が無く、毛のディテールも耳の内側のピンクも失われる。
EAR_UV_OFFSET = (-0.015137, -0.318604)

# 後に置いたものが上書きする。眉のジンジャー → 外側の暗色 → 耳のジンジャー →
# 頭頂の黒帯 → そばかす。
#
# 三毛なので左右非対称であることが koha の顔の特徴（1648460789455.jpg では猫の左が暗色優勢、
# 猫の右がジンジャー優勢）。顔の UV は鏡像共有ではないので、そのまま作れる。
#
# ただし **耳の板だけは左右が同じ UV 島を使う**（鏡像対応点の UV 距離 中央値 0.0046）。
# ベイクは後勝ちなので mask に残るのは -X 側の耳の座標だけ。+X 側に斑を置いても
# 実効面積 0.00% になる（実測）。耳は -X の座標で1つ置けば両耳に乗る。
# 頭の柄（配色.pdf p7 / p9 / p10 / p11 の指摘）。
#
# **-X 側が黒優勢、+X 側が茶優勢** で一貫している:
#   p7 (正面)   画面左(-X) が黒 / 画面右(+X) が茶と黒
#   p9 (俯瞰)   -X の耳の後ろは上が茶・下が黒 / +X の耳の後ろは茶単色
#   p10(俯瞰)   -X は半分くらいが黒 / +X は半分くらいが茶で前側が黒
# 正面像・俯瞰像とも **画面右が +X**（そばかすが +X にあり画面右に写ることで確認）。
#
# 白いブレーズは正中に残す（|X| < 0.010 あたり）。
# 後に置いたものが上書きする。頭 -> 顔の外側 -> 耳の後ろ -> 耳の前 -> そばかす の順。
FACE_BLOBS = [
    # --- 頭頂・額: -X は黒、+X は茶（前側だけ黒） ---
    ("-X 頭の黒", (-0.028, 0.2400, 0.1580), (0.026, 0.030, 0.036), FACE_BLACK, None),
    ("+X 頭の茶", (+0.029, 0.2410, 0.1540), (0.027, 0.030, 0.036), FACE_ORANGE, None),
    ("+X 頭の前側の黒", (+0.023, 0.2330, 0.1820), (0.019, 0.021, 0.020), FACE_BLACK, None),
    # --- 顔の外側（頬の毛）: 三角に張り出した部分 ---
    ("-X 顔の外側の黒", (-0.046, 0.2190, 0.1680), (0.014, 0.026, 0.030), FACE_BLACK, None),
    ("+X 顔の外側の茶", (+0.047, 0.2190, 0.1660), (0.014, 0.026, 0.030), FACE_ORANGE, None),
    ("+X 顔の外側の黒（混じり）", (+0.046, 0.2270, 0.1520), (0.011, 0.014, 0.016), FACE_BLACK, None),
    # --- 耳の後ろ（UV を左右で分離したので別々に塗れる） ---
    ("-X 耳の後ろ 上: 茶", (-0.036, 0.2720, 0.1440), (0.018, 0.012, 0.015), EAR_BROWN, "back"),
    ("-X 耳の後ろ 下: 黒", (-0.036, 0.2590, 0.1440), (0.018, 0.011, 0.015), FACE_BLACK, "back"),
    ("+X 耳の後ろ: 茶単色", (+0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_BROWN, "back"),
    # --- 耳の前（内側）: 肌色に近い。柄の後に置いて必ず上に来るようにする ---
    ("-X 耳の前: 肌色", (-0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_FLESH, "front"),
    ("+X 耳の前: 肌色", (+0.036, 0.2660, 0.1440), (0.018, 0.017, 0.015), EAR_FLESH, "front"),
    # --- そばかす: 鼻のすぐ脇（+X 側） ---
    # マズル表面は X が外へ行くほど後退する（実測: X=0.013 で Z≈0.2155, X=0.019 で Z≈0.2112）。
    # 表面から外れた座標に置くと実効面積 0% になる。
    ("+X マズルの橙のそばかす", (+0.0175, 0.1945, 0.2120), (0.0058, 0.0045, 0.0055), FRECKLE, None),
]

# 耳の板は薄いので、1つの楕円体が前面と後面の両方に当たる。法線 Z の符号で切り分ける。
FACE_GATES = {
    "front": (-0.05, 0.30),   # 法線Z がこれ以上（前向き）で 1
    "back": (0.05, -0.30),    # 法線Z がこれ以下（後ろ向き）で 1
}
DETAIL_SIGMA = 22     # 局所シェーディング比のぼかし半径（4096px 基準）
# 黒いサドル領域は明度が 25 前後しかなく、素の lum/blur は 8bit 量子化で相対ノイズが暴れる。
# そのまま白に掛けるとギラついた金属質の白になる。オフセットを足して暗部の比を鈍らせる。
DETAIL_OFFSET = 25.0
DETAIL_CLAMP = (0.60, 1.50)   # 白がのっぺりしないよう毛の陰影を強めに残す
TAIL_RINGS = 5.5

# 顔だけ別の陰影比を使う。半径22pxのぼかしでは素材の黒いアイマスクの「輪郭」が
# 比に残り、白く塗った顔に灰色の亡霊として浮き出る。細かいぼかし＋狭いクランプで、
# 毛の細部だけを拾い、大きな柄の縁は拾わない。
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
    return smoothstep(1.02, 0.72, f)   # f<0.72 で完全に内側、1.02 で消える


def ring_alpha(pos, center, radii, r0, r1):
    """正規化距離 r0〜r1 の殻。目の保護（f<1.02）の外側にアイラインを敷くのに使う。"""
    d = (pos - np.array(center)) / np.array(radii)
    f = np.sqrt((d ** 2).sum(-1))
    return smoothstep(r0, r0 + 0.10, f) * smoothstep(r1, r1 - 0.15, f)


EAR_REGION = {"y": 0.250, "z": (0.115, 0.175)}   # 耳の板（実測: Y 0.255〜0.280, Z 0.136〜0.152）


def copy_ear_art(rgb: np.ndarray, pos: np.ndarray, mask: np.ndarray):
    """+X の耳の UV 島を移した先へ、素材テクスチャの絵をそのまま複製する。

    p1a_rebind_blender.separate_ear_uvs は UV を平行移動しただけなので、テクセルも同じ
    ピクセル数だけずらしてコピーすれば、毛の流れも耳の内側のピンクも保たれる。
    複製しないと移動先は素材の空き領域になり、+X の耳だけディテールの無いのっぺりした板になる。

    p3_uv_bake は行 = v*(H-1), 列 = u*(W-1)（V 反転なし。罠⑥）なので、UV の平行移動は
    そのままテクセルの平行移動になる。
    """
    N = rgb.shape[0]
    drow = int(round(EAR_UV_OFFSET[1] * (N - 1)))
    dcol = int(round(EAR_UV_OFFSET[0] * (N - 1)))
    shifted = np.roll(rgb, (drow, dcol), axis=(0, 1))

    dest = (mask & (pos[..., 0] > 0.0) & (pos[..., 1] > EAR_REGION["y"])
            & (pos[..., 2] > EAR_REGION["z"][0]) & (pos[..., 2] < EAR_REGION["z"][1]))
    out = np.where(dest[..., None], shifted, rgb)
    return out, int(dest.sum())


def magnify_eye_art(rgb: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """素材の目の絵をテクセル空間で拡大する（主軸＝横方向を強めに伸ばして横長にする）。

    「目は左右とももう少し大きめ」「もう少し横長」（配色.pdf p8）への対応。
    目の絵は素材テクスチャに描かれていて 3D の斑では大きくできないので、絵そのものを拡大する。
    保護の外側は後で白く塗り潰されるため、拡大の縁が粗くても見えない。
    """
    N = rgb.shape[0]
    ii, jj = np.meshgrid(np.arange(N), np.arange(N), indexing="ij")
    out = rgb.copy()
    for c, rad in EYES:
        span = blob_alpha(pos, c, tuple(r * EYE_ART_SPAN for r in rad)) > 0.01
        if not span.any():
            continue

        # 拡大の中心は **虹彩の重心**。span（3D の楕円体）のテクセル重心を中心にすると、
        # UV の歪みのせいで目の絵の中心とずれ、暗いまぶたの側から拡大してしまう。
        # 実際それをやって、瞳が巨大化した真っ黒な目になった。
        iris = span & (rgb[..., 1] > rgb[..., 0] + 25) & (rgb[..., 1] > 130)
        if iris.sum() < 20:
            continue
        py, px = np.nonzero(iris)
        cy, cx = py.mean(), px.mean()

        cov = np.cov(np.stack([py - cy, px - cx]))
        major = np.linalg.eigh(cov)[1][:, -1]
        minor = np.array([-major[1], major[0]])

        # 出力テクセル -> 入力テクセル（縮めて引くと絵が拡大される）
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

    # --- 素材の加工は、陰影比と保護マスクを取る **前** に済ませる ---
    # 耳の絵を移動先へ複製し、目の絵を拡大しておく。detail も keep_pink も加工後の
    # 素材から取らないと、+X の耳が無地になり、拡大した目の縁が保護からはみ出す。
    rgb, ear_texels = copy_ear_art(rgb, pos, mask)
    print(f"  +X の耳へ素材の絵を複製: {ear_texels:,} テクセル")
    rgb = magnify_eye_art(rgb, pos)
    print(f"  目の絵を拡大: 主軸 x{EYE_ART_MAJOR} / 副軸 x{EYE_ART_MINOR}")

    # --- 局所シェーディング比（毛の流れを残すための素） ---
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    # PIL の GaussianBlur は mode F を受け付けないので 8bit で掛ける（この用途には十分）
    blur = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(DETAIL_SIGMA))).astype(float)
    detail = np.clip((lum + DETAIL_OFFSET) / (blur + DETAIL_OFFSET), *DETAIL_CLAMP)[..., None]

    # --- 保護領域: 頭（目・鼻・柄）と、ピンクの部位（肉球・鼻・耳の内側） ---
    # ピンクの判定は g-b で行う。素材のオレンジ毛は (198,139,66) で g-b≈73、
    # ピンクは (196,148,157) で g-b≈-9。r と b だけで見ると橙をピンクと誤検出し、
    # 元の橙帯がそのまま残ってしまう（初回の失敗）。
    head = smoothstep(HEAD_KEEP_Z[0], HEAD_KEEP_Z[1], pos[..., 2])
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    keep_pink = (r > 140) & ((r - g) > 25) & ((g - b) < 20)   # 肉球・鼻・口・耳の内側
    # 目（虹彩＋瞳孔＋まぶた）は塗らずに残す
    keep_eye = np.zeros(pos.shape[:2], float)
    for c, rad in EYES:
        keep_eye = np.maximum(keep_eye, blob_alpha(pos, c, rad))
    keep = np.clip(np.maximum(keep_eye, keep_pink.astype(float)), 0, 1)
    print(f"  素材を残すテクセル: 目 {float((keep_eye>0.5)[mask].mean()):.2%} / "
          f"ピンク(肉球・鼻・耳内) {float(keep_pink[mask].mean()):.2%}")

    # --- 胴・脚: 白を土台に、深いラスト色の斑を置く ---
    out = np.broadcast_to(WHITE, rgb.shape).copy()
    gates = {
        "dorsal": smoothstep(DORSAL_GATE, DORSAL_GATE + 0.30, nrm[..., 1]),
        "dorsal_low": smoothstep(DORSAL_LOW_GATE, DORSAL_LOW_GATE + 0.30, nrm[..., 1]),
        "rear": smoothstep(REAR_GATE[0], REAR_GATE[1], nrm[..., 2]),
    }
    paintable = mask & (keep < 0.5) & (part != PART_TAIL)
    for name, c, rad, col, gate in BLOBS:
        a = blob_alpha(pos, c, rad)
        if gate:
            a = a * gates[gate]
        out = out * (1 - a[..., None]) + col * a[..., None]
        cov = float((a[paintable] > 0.5).sum()) / max(paintable.sum(), 1)
        print(f"  斑 {name:22} 実効面積 {cov:6.2%}（胴・脚の塗り替え領域に対して）")

    out = out * detail

    # --- 尻尾: タン地に濃褐色のぼやけたリング ---
    # 素材の尻尾には毛のムラが描き込まれている。硬い縞で上書きすると理髪店のポールになる
    # （初回の失敗）。素材の明度を TAN↔BROWN のランプに写し、リングは軽い変調に留める。
    #
    # 尻尾に沿った座標: bone019/020 にウェイトが無く骨ベースの座標は t<=2 で頭打ちになるため、
    # 尾根元からの3D距離を使う。P2 で尻尾はほぼ直線（仰角 69〜78°）なので弧長の良い近似。
    tail = part == PART_TAIL
    if tail.any():
        root = pos[tail][np.argsort(pos[tail][:, 1])[:200]].mean(0)  # 最も低い＝尾根元
        dist = np.linalg.norm(pos - root, axis=-1)
        tlen = np.percentile(dist[tail], 98)
        t = np.clip(dist / max(tlen, 1e-6), 0, 1)

        lo, hi = np.percentile(lum[tail], [8, 92])
        ln = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1)          # 素材の毛のムラ

        # リングの位相を少し揺らして規則性を崩す
        wobble = 0.10 * (np.sin(pos[..., 0] * 190.0) + np.sin(pos[..., 2] * 130.0))
        ring = 0.5 + 0.5 * np.sin((t * TAIL_RINGS + wobble) * 2 * np.pi)
        ring = smoothstep(0.30, 0.85, ring)

        mix = np.clip(0.70 * (1 - ln) + 0.40 * ring - 0.12, 0, 1)[..., None]
        tail_col = TAN * (1 - mix) + BROWN * mix

        # 根元は橙み、さらに根元の直近は胴の色へ溶かして境目を消す
        tail_col = tail_col * (1 - smoothstep(0.34, 0.08, t)[..., None]) \
            + TAIL_BASE * smoothstep(0.34, 0.08, t)[..., None]
        blend = smoothstep(0.015, 0.09, t)[..., None]
        tail_col = out * (1 - blend) + tail_col * blend

        out = np.where(tail[..., None], tail_col, out)

    # --- 顔: 白いブレーズを広く取り、色は耳の付け根と目の外側だけに置く ---
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

    # アイライン: 保護した目のすぐ外側を濃く縁取る。柄より後に置いて必ず上に来るようにする。
    liner = np.zeros(pos.shape[:2], float)
    for c, rad in EYES:
        liner = np.maximum(liner, ring_alpha(pos, c, rad, *EYE_LINER_R))
    a = liner[..., None]
    face_col = face_col * (1 - a) + (EYE_LINER * fdetail) * a
    print(f"  顔 アイライン                     実効面積 {float((liner>0.5)[head>0.5].mean()):6.2%}")

    hm = (head * (1.0 - keep))[..., None]
    out = out * (1 - hm) + face_col * hm

    # 目・鼻・肉球は素材のまま。ただし虹彩（緑が赤より強いテクセル）だけ緑側へ寄せる。
    iris = (keep_eye > 0.5) & (rgb[..., 1] > rgb[..., 0] + 10)
    src_keep = np.where(iris[..., None], np.clip(rgb * IRIS_TINT, 0, 255), rgb)
    print(f"  目 虹彩の色を緑側へ: {int(iris.sum()):,} テクセル")

    k = keep[..., None]
    out = out * (1 - k) + src_keep * k
    out = np.where(mask[..., None], out, rgb)   # UV の空きは素材のまま
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

    cells = [(src, "素材（黒いサドルが背中を覆う）"),
             (Image.fromarray(regions), "柄の定義: 斑=実測色 / 紫=尻尾 / 黄=保護(顔・肉球)"),
             (Image.fromarray(out), "P3-1 出力（白優勢 + 深いラスト斑）")]
    cw = 1000
    sheet = Image.new("RGB", (cw * 3 + 40, cw + 60), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    f = ImageFont.truetype(FONT, 17)
    d.text((10, 6), "P3-1 テクスチャ塗り替え検証 — 毛のディテールを残したまま色だけ入れ替える",
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
