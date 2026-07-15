"""P1-A: koha9_cat メッシュを「標準手法だけ」で Leopard アーマチュアに束縛し直す。

B-6 との差分はただ一点、**束縛（bind）の方法**である。

  B-6 (失敗): 距離ゲート + ガウシアンカーネル + Union-Find による毛房剛体化 + ラプラシアン平滑化
              を自作。結果: ウェイトを持つボーン 20/98、脚は2関節のみ、全8アニメで破綻辺 1.4〜3.9%。

  P1-A     : Blender 標準モディファイアのみ。
              1. 重複頂点の統合（8,764頂点 → 主外皮 6,659頂点 + 小片）
              2. 主外皮だけを取り出したプロキシに Automatic Weights（ボーンヒート）
                 ※ B-6 が「毛房の非連結パーツで全滅」したのは、毛房ごと一括で
                   バインドしようとしたため。主外皮だけなら通る。
              3. 実メッシュ（毛シェル・小片を含む）へ Data Transfer でウェイトを転写
                 （Vertex Group / Nearest Face Interpolated）
              4. Limit Total 4 + Normalize All

骨フィットとアニメーションのリターゲットは B-6 のものをそのまま使う
（レストポーズは B-6 でも無傷であり、壊れていたのは束縛だけだと実測済み）。
ただし尻尾のカールは P2 に回すため、ここでは尻尾ボーンをメッシュの尻尾軸に沿って
まっすぐ配置する（1フェーズ=1関心事）。

  blender --background --python pipeline_v2/p1a_rebind_blender.py -- \
    --skeleton output_v2/base/cat_koha9.blend \
    --mesh input/cat2/koha9_cat.glb \
    --output-blend output_v2/base/p1a_koha.blend \
    --output-glb output_v2/base/p1a_koha.glb \
    --report output_v2/reports/p1a_rebind.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from b6_koha9_mesh_transplant_blender import (  # noqa: E402
    HEAD_BONES, LEG_CHAINS, NECK_BONES, TAIL_BONES, TARGET_BODY_LENGTH,
    measure_landmarks, piecewise_linear,
)

LEOPARD_MESH = "Leopard_Hybrid"
MESH_NAME = "Koha9"
PROXY_NAME = "_BindProxy"
MERGE_DIST = 1e-4
WEIGHT_LIMIT = 4

# 脚チェーンの付け根の横位置（足先の |X| に対する割合）。
# 1.0（足先の真上）だと肩の骨が胸壁の内側ぎりぎりに来て、Jump で胸の正中線が裂ける
# （破綻辺 131本のうち 105頂点が上腕・前腕の支配だった）。腹は koha_belly_* が
# 引き受けるようになったので、付け根をここまで外へ出す必要はもう無い。
ROOT_X_FRAC = 0.65
SMOOTH_FACTOR = 0.5
SMOOTH_REPEAT = 18

# デフォームさせないボーン。
#
# bone001-015: ヒョウ由来の頭部補助ボーン（顎・目・耳・ヒゲ台座）。koha9 の頭に対しては
#   意味のある対応先が無く、ボーンヒートが無関係な頂点を掴んで裂ける。
#   初回計測: bone003/007/012/013/015 が破綻頂点の支配ボーン上位を占めた。
#   頭は bip01_head に剛体追従させるのが正しい（顎も耳も動かさない）。
#
# s_fx* / s_hs* / b_hs: ヒョウの補助ボーン。b6b のリターゲット対象（DEFORM_BONES）に
#   入っていないためレストに取り残されるのに、ボーンヒートは胸〜首の頂点を掴む。
#   親が動くと必ず裂ける。**リターゲットされないボーンはデフォームさせてはならない。**
NO_DEFORM_BONES = ([f"bone{i:03d}" for i in range(1, 16)]
                   + ["s_fxtop", "s_fxtop_0", "s_fxmid", "s_fxmid_0"]
                   + ["b_hs", "s_hs", "s_hs1", "s_hs2", "s_hs_0", "s_hs1_0", "s_hs2_0"])

# 頭の整形（shape_head 参照）。Blender 座標の高さ z に対する横幅の倍率。
MUZZLE_EXTEND = 0.025   # 鼻先を前へ (m)。P4-顔第2段階（顔検討.png）で 0.017 -> 0.025
MUZZLE_NARROW = 0.05    # マズルを細く（横幅の倍率 1-この値）
EAR_BASE_Z = 0.252      # ここより上は耳の板。縮めずに平行移動させる

# 横幅は「目の高さの幅で割った先細り比」で写真と合わせる。目の間隔で正規化すると
# 写真では毛の輪郭を、モデルでは地肌の輪郭を測ることになり、比較にならなかった。
#
#            耳の付け根  こめかみ  目   顎
#   写真平均     0.758     0.864  1.00  0.858   （face2 の正面2枚）
#   モデル       0.846     0.912  1.00  1.059   （樽型: 上も下も太い）
#
# → 目の高さ（頬骨）だけを残して上下を締める。これで写真どおり、目の高さに
#   毛の膨らみのピークが立つ。前回 (0.168,1.15) と顎を広げたのは、写真の
#   「胸の襟毛」を顎の幅として測っていた誤りだった。
# 写真の顔は「頬の左右に毛が張り出した三角形」に見える（配色.pdf p6/p7 の指摘)。
# 頬（目の高さ）を強く広げ、頭頂へ向けて締めると、正面のシルエットが三角になる。
# P4-顔第2段階（顔検討.png 右の実物正面）: 1.12 のピークでは実物の三角形に未達。
# 頬（目の高さ）をさらに強く張り出させ、上下の締めは保って楔形を強調する。
HEAD_WIDTH_PROFILE = [(0.168, 0.92),   # 顎
                      (0.182, 0.97),
                      (0.196, 1.10),
                      (0.206, 1.22),   # 目・頬骨: 毛の張り出しのピーク（三角の底辺）
                      (0.216, 1.10),
                      (0.228, 0.92),
                      (0.240, 0.84),
                      (0.252, 0.80)]   # 頭頂・耳の付け根: 締める（三角の頂点）

# ---- 耳（EAR_BASE_Z より上の板）----
# 参照 input/raw_photos/all/1732010580228.jpg: 耳は背が高く、間隔が広く、外へ開く。
# 素材の耳の板は高さ 16mm しかなく（実測 z 0.252〜0.268）、頭頂の黒帯を置く面もほぼ無い。
EAR_TOP_Z = 0.268        # 素材の耳の先端（実測）
# P4-顔第2段階（顔検討.png）: 実物の耳は低く、間隔が広く、外へ倒れる。
# 1.55 の背高・直立は正面で目立ちすぎた → 低く (1.30)、付け根から外へ、先端はさらに外へ。
EAR_TALL = 1.30          # 板の高さの倍率（付け根 EAR_BASE_Z は動かさない）
EAR_SPREAD_BASE = 0.009  # 付け根を外へ (m)
EAR_SPREAD_TIP = 0.020   # 先端を外へ (m)
EAR_SPREAD_FADE = 0.014  # 付け根の広げを頭頂側へなじませる帯 (m)。段差で裂けないように
# 顔検討2.png (2026-07-15): 実物の耳はもっと幅広。板を耳ごとの中心から広げる。
EAR_WIDEN = 1.30         # 板の横幅の倍率（耳ごとの X 重心まわり）
# 耳の板は前後2枚のカードで、先端が開いて正面から V に割れて見える（Godot で指摘）。
# 上部を先端の重心へ収束させて1点の尖りにする。
EAR_WELD_FROM = 0.70     # 付け根→先端の高さのこの割合から収束を始める
EAR_TIP_WELD = 0.85      # 先端での収束率（1.0で完全に1点）

# ---- 眉庇（おでこ）----
# 顔検討2.png: 実物はおでこが前に出て目が彫り深く見える。glb は顔が平板。
# 目のすぐ上の帯を前へ出して眉庇を作る（目の高さ 0.209 には掛けない）。
BROW_OUT = 0.0055        # 前へ出す量 (m)
BROW_H = (0.212, 0.248)  # 高さ帯（Blender z）。bump で中央が最大

# ---- 喉のふくらみ / 胸の襟毛 ----
# 素材は顎の下（z 0.132〜0.180）が fore 0.205 まで前へ張り出し、鼻先 (0.218) とほとんど
# 同じ高さに来る。頭と胸がひと続きの塊になり、ユーザーが赤丸で指摘した部分になる
# （input/raw_photos/all/p3_head_left変更.png, p3_head_right変更.png）。
# 写真 1763363798733.jpg では喉は引っ込み、毛のふさふさは **もっと下（胸）** で広がる。
# そこで喉の帯を後ろへ引き、その分を胸の帯で前・横へ出す（毛を下へ移す）。
THROAT_Z = (0.132, 0.180)    # 喉: 引っ込める高さ帯
THROAT_TUCK = 0.016          # 後ろへ引く量 (m)
RUFF_Z = (0.092, 0.132)      # 胸の襟毛: 出す高さ帯
RUFF_OUT = 0.009             # 前へ出す量 (m)
RUFF_WIDE = 0.07             # 横に広げる倍率
RUFF_FRONT = (0.120, 0.180)  # 前面だけに効かせる fore の帯（首の後ろは動かさない）

# ---- 頭の大きさ ----
# 首の付け根を支点に頭だけを拡大する。高さのゲートで喉・胸を除くので襟毛は巻き戻らない。
# 1.10 は行き過ぎで「顔全体がもう少し小さい」と指摘された（配色.pdf p6）。
# 頬を広げた分（HEAD_WIDTH_PROFILE）で顔は大きく見えるので、全体倍率は下げる。
HEAD_SCALE = 1.04
HEAD_PIVOT_F = 0.128           # 支点 fore（後頭部の下、首の付け根）
HEAD_PIVOT_Z = 0.196           # 支点 z
HEAD_SCALE_Z = (0.150, 0.185)  # この高さ帯で頭に効かせる

# ---- 頭の正中線を X=0 に戻す ----
# 素材のマズルは +X 側へ曲がっており、鼻先が X=+0.0117 にある（実測。胴は ±0.001 で中心）。
# symmetrize_body は「正中で変位が 0」を境界条件にするので **正中線そのものは動かない**。
# そのため対称化しても鼻だけが右にずれたままになる（配色.pdf p5 の指摘）。
HEAD_CENTER_FADE = (0.100, 0.140)   # この fore 帯で 0 -> 1 に立ち上げる（首から頭へ）
HEAD_CENTER_SLICES = 14


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--skeleton", required=True)
    p.add_argument("--mesh", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--report", required=True)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def activate(obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


# ---------------------------------------------------------------- mesh prep

def import_and_prepare_mesh(glb_path: str) -> tuple[bpy.types.Object, dict]:
    """GLB を取り込み、シェイプキー除去 → ワールド焼き込み → 重複頂点統合 → 結合。"""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    imported = [o for o in bpy.context.scene.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh in GLB")

    stats = {"before": sum(len(o.data.vertices) for o in meshes)}
    for obj in meshes:
        if obj.data.shape_keys:
            obj.shape_key_clear()
        mw = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.data.transform(mw)
        obj.data.update()

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=MERGE_DIST)
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update()
    stats["after_merge"] = sum(len(o.data.vertices) for o in meshes)

    for obj in [o for o in imported if o.type == "EMPTY"]:
        bpy.data.objects.remove(obj, do_unlink=True)

    main = max(meshes, key=lambda o: len(o.data.vertices))
    bpy.ops.object.select_all(action="DESELECT")
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = main
    bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = mesh.data.name = MESH_NAME

    for action in list(bpy.data.actions):
        if action.name.startswith("Object_"):
            bpy.data.actions.remove(action)
    stats["joined"] = len(mesh.data.vertices)
    return mesh, stats


def normalize_mesh(mesh: bpy.types.Object) -> float:
    lm = measure_landmarks(mesh)
    scale = TARGET_BODY_LENGTH / (lm["tail_root_y"] - lm["nose_y"])
    mesh.data.transform(Matrix.Diagonal((scale, scale, scale, 1.0)))
    mesh.data.update()
    lm2 = measure_landmarks(mesh)
    mesh.data.transform(Matrix.Translation(Vector((0.0, 0.0, -lm2["ground_z"]))))
    mesh.data.update()
    return scale


def largest_component_verts(mesh: bpy.types.Object) -> set[int]:
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    bm.verts.ensure_lookup_table()
    seen, best = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], []
        seen.add(v.index)
        while stack:
            cur = stack.pop()
            comp.append(cur.index)
            for e in cur.link_edges:
                o = e.other_vert(cur)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        if len(comp) > len(best):
            best = comp
    bm.free()
    return set(best)


# ---------------------------------------------------------------- bone fit

def tail_axis_points(mesh: bpy.types.Object, lm: dict, n: int) -> list[Vector]:
    """メッシュの尻尾を Y スライスして重心を辿る折れ線。カールはしない（P2 の担当）。"""
    tail = [v.co.copy() for v in mesh.data.vertices if v.co.y >= lm["tail_root_y"]]
    y0, y1 = lm["tail_root_y"], max(v.y for v in tail)
    half = (y1 - y0) / (n - 1)
    pts = []
    for i in range(n):
        y = y0 + (y1 - y0) * i / (n - 1)
        sel = [v for v in tail if abs(v.y - y) <= half]
        if len(sel) < 3:
            sel = sorted(tail, key=lambda v: abs(v.y - y))[:8]
        pts.append(Vector((
            sum(v.x for v in sel) / len(sel),
            y,
            sum(v.z for v in sel) / len(sel),
        )))
    return pts


def smoothstep(e0: float, e1: float, x: float) -> float:
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def bump(a: float, b: float, x: float) -> float:
    """帯 [a, b] の内側で 1、外側で 0 になる滑らかな山。"""
    m = (a + b) / 2.0
    return smoothstep(a, m, x) * smoothstep(b, m, x)


# ---------------------------------------------------------------- symmetry

# 素材メッシュは左右非対称である（実測）:
#   ・猫の右 (-X) が左 (+X) より胴・腰で一貫して 3〜6mm 太い
#   ・左前足が右前足より 15mm 後ろにある（歩きかけの姿勢）
# 正面レンダーでは左半身がつぶれて見え、ユーザーの指摘「左側がつぶれている／
# 右側のボリュームが理想形」そのものになる。
#
# 直し方: **右半分 (-X) を正として、左半分 (+X) をその鏡像へ射影する。**
# 頂点を動かすだけで頂点の同一性と UV は保つので、三毛の左右非対称な柄は壊れない。
# Blender の Symmetrize オペレータは UV ごと複製するため使ってはいけない。左右が UV 島を
# 共有してしまい（耳がまさにそれで、罠⑪）、非対称な柄が焼けなくなる。
#
# 対象は **主外皮の胴体だけ**。尻尾の房（Koha9Tail の 78 個の毛束と主外皮の尾）は
# 左右に対応する相手を持たないため、射影すると一点につぶれる（実測で 1mm セルに 20 点超）。
SYM_MIDLINE_EPS = 0.006   # 中央帯: この X までの面も「右半分」に含め、正中で連続にする
SYM_TAIL_FADE = 0.045     # 尻尾根元の手前この距離で効果を 0 に落とす（尾との継ぎ目を作らない）

# 変位場のラプラシアン平滑化。**これが無いとバインドが全滅する。**
# 生の最近傍射影は足先で頂点を寄せ集め、面積ゼロの面を作る（実測 3 個 -> 20 個）。
# するとボーンヒートの連立方程式が特異になり "Bone Heat Weighting: failed to find
# solution" で **全 8,764 頂点のウェイトが 0** になる（qa 以前に GLB から skin が消える）。
# 平滑化は平行移動（＝左前足が 15mm 後ろにある歩幅のずれ）を保存したまま、
# 頂点の寄せ集めだけを均す。定数場は平滑化の不動点なので、直したい低周波成分は残る。
SYM_SMOOTH_LAMBDA = 0.5
SYM_SMOOTH_ITERS = 12

# 足先の歩幅ずれ（左前足が右前足より 15mm 後ろ）は、鏡像射影ではなく **平均へ寄せて** 直す。
# 右足に合わせて左足を 15mm 前へ出すと、place_leg_chains が足先の真上に脚チェーンを置く仕様
# なので脚ボーンごと 7.5mm 前へ動き、ボーンヒートが胸の皮を上腕に取られて
# Jump の破綻辺が 0.481% -> 0.529% とゲート(0.5%)を割る（実測）。
# 左右を平均へ half ずつ寄せれば足先の平均は変わらず、脚ボーンは元の位置に留まる。
STRIDE_FADE_Z = (0.14, 0.05)     # この高さ帯で効果を 0 -> 1 に（足先で最大、肩で 0）
STRIDE_FADE_X = (0.015, 0.030)   # 正中の腹を引きずらないよう、脚の |X| だけに効かせる


def equalize_stride(mesh: bpy.types.Object) -> dict:
    """前脚・後脚それぞれの左右の足先を、その平均の前後位置で揃える。"""
    V = [v.co.copy() for v in mesh.data.vertices]
    ground = min(p.z for p in V)
    low = [p for p in V if p.z < ground + 0.030]
    mid_y = (min(p.y for p in low) + max(p.y for p in low)) / 2.0

    fore_y = {}
    for key, sel in (("front_l", [p for p in low if p.y < mid_y and p.x > 0]),
                     ("front_r", [p for p in low if p.y < mid_y and p.x < 0]),
                     ("hind_l", [p for p in low if p.y >= mid_y and p.x > 0]),
                     ("hind_r", [p for p in low if p.y >= mid_y and p.x < 0])):
        fore_y[key] = sum(p.y for p in sel) / len(sel) if sel else 0.0

    shift = {}
    for grp in ("front", "hind"):
        target = (fore_y[f"{grp}_l"] + fore_y[f"{grp}_r"]) / 2.0
        shift[f"{grp}_l"] = target - fore_y[f"{grp}_l"]
        shift[f"{grp}_r"] = target - fore_y[f"{grp}_r"]

    for v in mesh.data.vertices:
        w = (smoothstep(STRIDE_FADE_Z[0], STRIDE_FADE_Z[1], v.co.z)
             * smoothstep(STRIDE_FADE_X[0], STRIDE_FADE_X[1], abs(v.co.x)))
        if w <= 0.0:
            continue
        grp = "front" if v.co.y < mid_y else "hind"
        side = "l" if v.co.x > 0 else "r"
        v.co.y += shift[f"{grp}_{side}"] * w
    mesh.data.update()

    return {"stride_shift_mm": {k: round(s * 1000, 2) for k, s in shift.items()}}


def symmetrize_body(mesh: bpy.types.Object) -> dict:
    """左半分を右半分の鏡像へ射影して、左右のボリュームを揃える。"""
    lm = measure_landmarks(mesh)
    tail_y = lm["tail_root_y"]
    skin = largest_component_verts(mesh)
    V = [v.co.copy() for v in mesh.data.vertices]
    n = len(V)

    # 右半分（+ 中央帯）の面だけを鏡像にした BVH。毛束や尾は入れない。
    rv, rf, idx = [], [], {}
    for poly in mesh.data.polygons:
        vs = list(poly.vertices)
        if not all(i in skin for i in vs):
            continue
        c = sum((V[i] for i in vs), Vector()) / len(vs)
        if c.x >= SYM_MIDLINE_EPS or c.y >= tail_y:
            continue
        f = []
        for i in vs:
            if i not in idx:
                idx[i] = len(rv)
                p = V[i]
                rv.append(Vector((-p.x, p.y, p.z)))
            f.append(idx[i])
        for k in range(1, len(f) - 1):
            rf.append((f[0], f[k], f[k + 1]))
    bvh = BVHTree.FromPolygons(rv, rf)

    # 生の変位。対象外の頂点は 0 に固定する。これが平滑化の境界条件になり、
    # 正中（X=0）と尻尾の継ぎ目で変位が 0 へ収束するので折れ目ができない。
    zero = Vector((0.0, 0.0, 0.0))
    disp = [zero.copy() for _ in range(n)]
    target, raw_max = [], 0.0
    for i in range(n):
        p = V[i]
        if i not in skin or p.x <= 0.0 or p.y >= tail_y:
            continue
        w = smoothstep(tail_y, tail_y - SYM_TAIL_FADE, p.y)
        if w <= 0.0:
            continue
        loc, _, _, _ = bvh.find_nearest(p)
        if loc is None:
            continue
        disp[i] = (loc - p) * w
        target.append(i)
        raw_max = max(raw_max, disp[i].length)

    nbr = [[] for _ in range(n)]
    for e in mesh.data.edges:
        a, b = e.vertices
        nbr[a].append(b)
        nbr[b].append(a)
    for _ in range(SYM_SMOOTH_ITERS):
        nxt = [d.copy() for d in disp]
        for i in target:
            if not nbr[i]:
                continue
            avg = zero.copy()
            for j in nbr[i]:
                avg += disp[j]
            nxt[i] = disp[i].lerp(avg / len(nbr[i]), SYM_SMOOTH_LAMBDA)
        disp = nxt

    for i in target:
        mesh.data.vertices[i].co = V[i] + disp[i]
    mesh.data.update()

    # 左前足が前へ出る分だけ最下点が変わりうるので接地を取り直す
    gz = min(v.co.z for v in mesh.data.vertices)
    mesh.data.transform(Matrix.Translation(Vector((0.0, 0.0, -gz))))
    mesh.data.update()

    # 面積ゼロの面はボーンヒートを殺す。素材の時点で 3 個あり、ここで増えていないことを見る。
    degen = sum(1 for p in mesh.data.polygons if p.area < 1e-10)
    return {"skin_verts": len(skin), "mirror_faces": len(rf), "moved": len(target),
            "raw_max_move_mm": round(raw_max * 1000, 2),
            "smoothed_max_move_mm": round(max((disp[i].length for i in target), default=0) * 1000, 2),
            "degenerate_faces": degen, "reground_mm": round(gz * 1000, 3)}


def shape_head(mesh: bpy.types.Object) -> dict:
    """頭を koha の写真に寄せる: マズルを伸ばし、目の高さに毛の膨らみを立てる。

    Blender 座標系（-Y=前, +Z=上）。f = -y（前方向）, h = z（高さ）。

    マズル: 素材（マンチカン）は鼻先が目より 0.0157m しか前に出ていない。
      参照 input/raw_photos/face2/1648713873399_frame_001965.jpg, 1639815778356.jpeg
      では横顔のマズルがはっきり前に出て、しかも先が尖らず鈍い。前へ引き、細めすぎない。

    横幅: HEAD_WIDTH_PROFILE 参照。頭頂（EAR_BASE_Z）より上は耳の板なので、
      倍率を掛けると耳まで薄くなる。付け根の位置で決まる平行移動に切り替える。
      付け根ちょうどでは |x| = ear_x なので、倍率と平行移動は連続につながる。
    """
    xs = sorted(abs(v.co.x) for v in mesh.data.vertices
                if -v.co.y > 0.120 and abs(v.co.z - EAR_BASE_Z) < 0.006)
    ear_x = xs[len(xs) // 2] if xs else 0.032
    s_top = piecewise_linear(EAR_BASE_Z, HEAD_WIDTH_PROFILE)

    for v in mesh.data.vertices:
        f = -v.co.y
        h = v.co.z
        head_t = smoothstep(0.120, 0.152, f)   # 首→頭
        if head_t <= 0.0:
            continue

        # --- 横幅プロファイル（高さの関数） ---
        if h <= EAR_BASE_Z:
            s = piecewise_linear(max(h, 0.168), HEAD_WIDTH_PROFILE)
            v.co.x *= 1.0 + (s - 1.0) * head_t
        else:
            v.co.x -= math.copysign((1.0 - s_top) * ear_x * head_t, v.co.x)

        # --- マズルを前へ ---
        t = smoothstep(0.150, 0.185, f) * smoothstep(0.212, 0.198, h)
        if t > 0.0:
            v.co.y -= MUZZLE_EXTEND * t
            v.co.x *= 1.0 - MUZZLE_NARROW * t

    # --- 耳: 幅を広げ、外へ開く ---
    # 横幅プロファイルが耳の板を正中へ 6mm ほど寄せてしまうので、その分も含めて開き直す。
    # 付け根の広げは EAR_SPREAD_FADE の帯で頭頂へなじませる（段差を作ると裂ける）。
    ear_cx = {}
    for sgn in (1.0, -1.0):
        exs = [v.co.x for v in mesh.data.vertices
               if -v.co.y > 0.120 and v.co.z > EAR_BASE_Z and v.co.x * sgn > 0.0]
        ear_cx[sgn] = sum(exs) / max(len(exs), 1)
    for v in mesh.data.vertices:
        if -v.co.y <= 0.120 or v.co.z <= EAR_BASE_Z - EAR_SPREAD_FADE:
            continue
        sgn = 1.0 if v.co.x >= 0.0 else -1.0
        t = min(max((v.co.z - EAR_BASE_Z) / (EAR_TOP_Z - EAR_BASE_Z), 0.0), 1.0)
        w = smoothstep(EAR_BASE_Z - EAR_SPREAD_FADE, EAR_BASE_Z, v.co.z)
        # 幅: 耳ごとの X 重心まわりに広げる。**EAR_BASE_Z より上（=板）だけ**に掛ける。
        # なじませ帯 (w) に掛けると頭皮の中央の頂点が |x-重心| に比例して横に引かれ、
        # 頭頂が ~10mm 歪む（remap の実測で発覚）。
        w_plate = smoothstep(EAR_BASE_Z, EAR_BASE_Z + 0.004, v.co.z)
        v.co.x += (v.co.x - ear_cx[sgn]) * (EAR_WIDEN - 1.0) * w_plate
        v.co.x += math.copysign((EAR_SPREAD_BASE
                                 + (EAR_SPREAD_TIP - EAR_SPREAD_BASE) * t) * w, v.co.x)
        if v.co.z > EAR_BASE_Z:
            v.co.z = EAR_BASE_Z + (v.co.z - EAR_BASE_Z) * EAR_TALL

    # --- 耳の先端を1点へ収束（V 割れの解消。顔検討2.png で指摘）---
    # 板は前後2枚のカードで、先端が数 mm 開いており正面から V に見える。
    # 上部 (EAR_WELD_FROM〜) を先端重心へ smoothstep で引き寄せて尖りを1点にする。
    for sgn in (1.0, -1.0):
        evs = [v for v in mesh.data.vertices
               if -v.co.y > 0.120 and v.co.z > EAR_BASE_Z and v.co.x * sgn > 0.0]
        z_top = max(v.co.z for v in evs)
        tips = [v for v in evs if v.co.z > z_top - 0.005]
        tcx = sum(v.co.x for v in tips) / len(tips)
        tcy = sum(v.co.y for v in tips) / len(tips)
        z0 = EAR_BASE_Z + (z_top - EAR_BASE_Z) * EAR_WELD_FROM
        for v in evs:
            wt = smoothstep(z0, z_top, v.co.z) * EAR_TIP_WELD
            if wt > 0.0:
                v.co.x += (tcx - v.co.x) * wt
                v.co.y += (tcy - v.co.y) * wt

    # --- 眉庇（おでこ）を前へ: 目が彫り深く見えるように（顔検討2.png）---
    for v in mesh.data.vertices:
        w = (bump(BROW_H[0], BROW_H[1], v.co.z)
             * smoothstep(0.140, 0.165, -v.co.y)
             * smoothstep(0.055, 0.030, abs(v.co.x)))
        if w > 0.0:
            v.co.y -= BROW_OUT * w

    # --- 喉を引っ込め、その毛のボリュームを胸へ下ろす ---
    for v in mesh.data.vertices:
        wf = smoothstep(RUFF_FRONT[0], RUFF_FRONT[1], -v.co.y)
        if wf <= 0.0:
            continue
        wt = bump(THROAT_Z[0], THROAT_Z[1], v.co.z)
        wr = bump(RUFF_Z[0], RUFF_Z[1], v.co.z)
        v.co.y += (THROAT_TUCK * wt - RUFF_OUT * wr) * wf     # +y は後ろ
        v.co.x *= 1.0 + RUFF_WIDE * wr * wf

    # --- 頭を大きく（首の付け根を支点に） ---
    pivot = Vector((0.0, -HEAD_PIVOT_F, HEAD_PIVOT_Z))
    for v in mesh.data.vertices:
        w = (smoothstep(0.120, 0.152, -v.co.y)
             * smoothstep(HEAD_SCALE_Z[0], HEAD_SCALE_Z[1], v.co.z))
        if w <= 0.0:
            continue
        v.co = pivot + (v.co - pivot) * (1.0 + (HEAD_SCALE - 1.0) * w)

    mesh.data.update()
    top = max(v.co.z for v in mesh.data.vertices)
    nose = max(-v.co.y for v in mesh.data.vertices)
    return {"muzzle_extend": MUZZLE_EXTEND, "muzzle_narrow": MUZZLE_NARROW,
            "ear_base_x": ear_x, "width_profile": HEAD_WIDTH_PROFILE,
            "ear_tall": EAR_TALL, "throat_tuck": THROAT_TUCK, "ruff_out": RUFF_OUT,
            "head_scale": HEAD_SCALE,
            "top_z": round(top, 4), "nose_fore": round(nose, 4)}


def center_head_midline(mesh: bpy.types.Object) -> dict:
    """頭の正中線（鼻筋）を X=0 に戻す。

    fore のスライスごとに表面の中心 (minX+maxX)/2 を測り、その分だけ X を戻す。
    純粋な X の平行移動場なので面が折れることはない。首へ向けて滑らかに 0 へ落とす。
    """
    V = [v.co.copy() for v in mesh.data.vertices]
    f_lo = HEAD_CENTER_FADE[0]
    f_hi = max(-v.y for v in V)
    step = (f_hi - f_lo) / HEAD_CENTER_SLICES

    table = []
    for i in range(HEAD_CENTER_SLICES):
        a = f_lo + step * i
        xs = [v.x for v in V if a <= -v.y < a + step]
        if len(xs) < 8:
            continue
        table.append([a + step * 0.5, (min(xs) + max(xs)) / 2.0])

    # 3点移動平均で滑らかにする（スライスごとの中心はノイズを含む）
    smooth = []
    for i, (f, c) in enumerate(table):
        lo, hi = max(0, i - 1), min(len(table), i + 2)
        smooth.append((f, sum(t[1] for t in table[lo:hi]) / (hi - lo)))

    for v in mesh.data.vertices:
        f = -v.co.y
        w = smoothstep(HEAD_CENTER_FADE[0], HEAD_CENTER_FADE[1], f)
        if w <= 0.0:
            continue
        v.co.x -= piecewise_linear(f, smooth) * w
    mesh.data.update()

    nose_f = max(-v.co.y for v in mesh.data.vertices)
    after = [v.co.x for v in mesh.data.vertices if -v.co.y > nose_f - 0.006]
    return {"offset_mm": [(round(f, 3), round(c * 1000, 2)) for f, c in smooth],
            "nose_x_after_mm": round(sum(after) / len(after) * 1000, 2)}


# 耳は左右で同じ UV 島を共有している（罠⑪。実測: 対応点の UV 距離 中央値 0.0104、
# 両耳の面の UV 重心が同じセルに集まる）。そのままでは「右の耳の後ろは茶色単色、
# 左は上が茶色で下が黒」（配色.pdf p9）を作れない。**+X の耳の UV 島を空き領域へ逃がす。**
# UV 占有率は 56.9% しかなく、空きは十分にある。
EAR_UV_Z = 0.252          # これより上を耳の板とみなす（shape_head の前の座標）
EAR_UV_OFFSET = (-0.015137, -0.318604)   # 4096px の整数倍。素材の絵もこの分だけ複製する


def separate_ear_uvs(mesh: bpy.types.Object) -> dict:
    """+X の耳の UV 島を空き領域へ平行移動し、左右の耳を別々に塗れるようにする。

    平行移動なので、素材テクスチャ側も同じ矩形をコピーすれば絵（毛・耳の内側のピンク）は
    そのまま保たれる。コピーは p3_paint_texture.py が行う（EAR_UV_OFFSET を共有）。
    """
    me = mesh.data
    uvl = me.uv_layers.active.data

    moved_loops, src_uv = 0, []
    for poly in me.polygons:
        c = sum((me.vertices[i].co for i in poly.vertices), Vector()) / len(poly.vertices)
        if -c.y <= 0.120 or c.z <= EAR_UV_Z or c.x <= 0.0:
            continue
        for li in poly.loop_indices:
            src_uv.append(tuple(uvl[li].uv))
            uvl[li].uv[0] += EAR_UV_OFFSET[0]
            uvl[li].uv[1] += EAR_UV_OFFSET[1]
            moved_loops += 1

    if not moved_loops:
        raise RuntimeError("+X の耳の面が見つからない。EAR_UV_Z を確認すること。")

    # 移動先が本当に空いているか確かめる。重なっていたら他の部位の絵を壊す。
    dst = [(u + EAR_UV_OFFSET[0], v + EAR_UV_OFFSET[1]) for u, v in src_uv]
    du0, du1 = min(u for u, _ in dst), max(u for u, _ in dst)
    dv0, dv1 = min(v for _, v in dst), max(v for _, v in dst)
    clash = 0
    for poly in me.polygons:
        c = sum((me.vertices[i].co for i in poly.vertices), Vector()) / len(poly.vertices)
        if -c.y > 0.120 and c.z > EAR_UV_Z and c.x > 0.0:
            continue          # 動かした耳自身
        for li in poly.loop_indices:
            u, v = uvl[li].uv
            if du0 <= u <= du1 and dv0 <= v <= dv1:
                clash += 1
    if clash:
        raise RuntimeError(f"耳の UV 移動先が空いていない（{clash} ループが重なる）。"
                           f"EAR_UV_OFFSET を選び直すこと。")

    return {"moved_loops": moved_loops, "offset": EAR_UV_OFFSET,
            "dst_bbox": [round(du0, 4), round(dv0, 4), round(du1, 4), round(dv1, 4)]}


def paw_clusters(mesh: bpy.types.Object) -> dict:
    """接地付近の頂点から、4本の脚の足先クラスタ（X,Y中心）を測る。"""
    vs = [v.co.copy() for v in mesh.data.vertices]
    ground = min(v.z for v in vs)
    low = [v for v in vs if v.z < ground + 0.030]
    mid_y = (min(v.y for v in low) + max(v.y for v in low)) / 2.0
    out = {"ground": ground}
    for key, sel in (("front_l", [v for v in low if v.y < mid_y and v.x < 0]),
                     ("front_r", [v for v in low if v.y < mid_y and v.x > 0]),
                     ("hind_l", [v for v in low if v.y >= mid_y and v.x < 0]),
                     ("hind_r", [v for v in low if v.y >= mid_y and v.x > 0])):
        out[key] = Vector((sum(v.x for v in sel) / len(sel),
                           sum(v.y for v in sel) / len(sel),
                           ground))
    # 左右で X の絶対値・Y を平均して完全対称にする（メッシュの微小な非対称を持ち込まない）
    for a, b in (("front_l", "front_r"), ("hind_l", "hind_r")):
        ax = (abs(out[a].x) + abs(out[b].x)) / 2.0
        ay = (out[a].y + out[b].y) / 2.0
        out[a] = Vector((-ax, ay, ground))
        out[b] = Vector((+ax, ay, ground))
    return out


def place_leg_chains(arm: bpy.types.Object, mesh: bpy.types.Object) -> dict:
    """脚チェーンを、各足先の真上に垂直な柱として左右対称に置き直す。

    なぜ必要か: ヒョウのレストポーズは「歩幅を開いたストーキング姿勢」で、
    左前脚が腹の下に畳まれ、左後脚は尻尾の付け根まで後退している
    （実測: bip01_l_hand.y=-0.046 / bip01_r_hand.y=-0.152、bip01_l_foot.y=+0.215）。
    B-6 の区分線形ワープはこの歩幅を保存してしまうため、立ち姿勢のメッシュの中に
    「畳まれた脚の骨」が残る。ボーンヒートはその骨に腹の頂点を割り当て、
    歩行アニメで腹が片側だけ吸い上がって胴がくびれる。
    辺は裂けないので qa_skin_stretch では検出できない（qa_belly_bind.py を追加した理由）。

    さらに脚の付け根が正中線に 1.7〜2.3cm 寄っていた（足先 |X|≈0.040 / 付け根 |X|≈0.018）。
    付け根を足先の真上へ出すことで、腹の頂点は脊椎・骨盤側に割り当てられる。
    """
    amw = arm.matrix_world.copy()
    amw_inv = amw.inverted()
    paw = paw_clusters(mesh)
    ground = paw["ground"]

    # チェーン定義: (ボーン列, 足先キー, 付け根の高さ係数, 足先ボーン)
    # 高さ係数は接地から背の何割か。ヒョウ由来の元の高さ（0.112〜0.121）に合わせる。
    top = max(v.co.z for v in mesh.data.vertices)
    chains = [
        (["bip01_l_upperarm", "bip01_l_forearm", "bip01_l_hand"], "front_r", 0.45, "bip01_l_hand"),
        (["bip01_r_upperarm", "bip01_r_forearm", "bip01_r_hand"], "front_l", 0.45, "bip01_r_hand"),
        (["bip01_l_thigh", "bip01_l_calf", "bip01_l_horselink", "bip01_l_foot"], "hind_r", 0.42,
         "bip01_l_foot"),
        (["bip01_r_thigh", "bip01_r_calf", "bip01_r_horselink", "bip01_r_foot"], "hind_l", 0.42,
         "bip01_r_foot"),
    ]
    # 注意: このリグは bip01_l_* が +X 側にある（実測。名前と符号が逆）。

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arm.data.edit_bones
    moved = 0

    for names, paw_key, z_frac, paw_bone in chains:
        target = paw[paw_key]
        root_z = ground + (top - ground) * z_frac
        root = Vector((target.x * ROOT_X_FRAC, target.y, root_z))
        foot = Vector((target.x, target.y, ground + 0.010))

        lengths = [(amw @ ebs[n].tail - amw @ ebs[n].head).length for n in names]
        total = sum(lengths)
        span = (foot - root)

        old_paw_head = amw @ ebs[paw_bone].head.copy()
        acc = 0.0
        for n, L in zip(names, lengths):
            eb = ebs[n]
            eb.use_connect = False
            h = root + span * (acc / total)
            acc += L
            t = root + span * (acc / total)
            if n == paw_bone:
                # 足先ボーンは前方（-Y）へ水平に寝かせる
                t = Vector((h.x, h.y - L, ground + 0.006))
            eb.head = amw_inv @ h
            eb.tail = amw_inv @ t
            moved += 1

        # 指・つま先は足先ボーンに剛体で追従させる（ウェイトは乗らないが位置は揃える）
        shift = (amw @ ebs[paw_bone].head) - old_paw_head
        side = "l" if "_l_" in paw_bone else "r"
        pref = f"bip01_{side}_finger" if "hand" in paw_bone else f"bip01_{side}_toe"
        for eb in ebs:
            if eb.name.startswith(pref):
                eb.use_connect = False
                eb.head = amw_inv @ ((amw @ eb.head) + shift)
                eb.tail = amw_inv @ ((amw @ eb.tail) + shift)
                moved += 1

        # 鎖骨は脊椎から肩へ橋渡し
        if "upperarm" in names[0]:
            cl = ebs[f"bip01_{'l' if '_l_' in names[0] else 'r'}_clavicle"]
            cl.use_connect = False
            cl.head = amw_inv @ Vector((target.x * 0.25, target.y, root_z + 0.015))
            cl.tail = amw_inv @ root
            moved += 1

    bpy.ops.object.mode_set(mode="OBJECT")
    return {"moved_bones": moved, "ground": round(ground, 4),
            "paws": {k: [round(c, 4) for c in v] for k, v in paw.items() if k != "ground"}}


def add_belly_bones(arm: bpy.types.Object, mesh: bpy.types.Object) -> dict:
    """腹の中にデフォーム専用ボーンを追加し、脊椎に剛体追従させる。

    なぜ必要か: この猫は短足で腹が地面すれすれまで垂れており、腹の真下を脚の骨が通る。
    一方ヒョウ由来の脊椎は背の 82% の高さ（背中の表面直下）にある。距離で見ると
    腹の頂点は必ず脚の骨に負ける。脚チェーンを足先の真上へ直した後でも
    腹の 58% が脚ボーン支配のままだった（qa_belly_bind.py で実測）。

    ウェイトを手で書くのではなく、**腹の中にボーンを置いてボーンヒートに正しく解かせる。**
    アニメーションはこれらのボーンを触らない（b6b の RETARGET_BONES に無い）ので、
    親の脊椎・骨盤と一緒に剛体で動く。
    """
    vs = [v.co.copy() for v in mesh.data.vertices]

    def belly_z(y0: float, y1: float) -> float:
        """その Y 帯の腹面の高さ。2パーセンタイルだと胸元の毛の裾を拾って低く出るので 10。"""
        sel = sorted(v.co.z for v in mesh.data.vertices
                     if y0 <= v.co.y < y1 and abs(v.co.x) < 0.025)
        return sel[len(sel) // 10] if len(sel) > 30 else 0.05

    # 腹の面からわずかに内側（+2.2cm）にボーンを通す。
    # 前端は胸（前脚の間）まで伸ばす。ここを空けると bip01_r_forearm が胸を掴む。
    segs = [
        ("koha_belly_front", "bip01_spine1", -0.118, -0.030),
        ("koha_belly_mid", "bip01_spine", -0.030, 0.030),
        ("koha_belly_rear", "bip01_pelvis", 0.030, 0.095),
    ]
    amw = arm.matrix_world.copy()
    amw_inv = amw.inverted()

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arm.data.edit_bones
    added = []
    for name, parent, y0, y1 in segs:
        z = belly_z(y0, y1) + 0.022
        eb = ebs.new(name)
        eb.head = amw_inv @ Vector((0.0, y0, z))
        eb.tail = amw_inv @ Vector((0.0, y1, z))
        eb.parent = ebs[parent]
        eb.use_connect = False
        eb.use_deform = True
        added.append({"name": name, "parent": parent, "z": round(z, 4)})
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"added": added}


def fit_bones(arm: bpy.types.Object, mesh: bpy.types.Object, lm: dict) -> dict:
    """B-6 の区分線形ワープ。尻尾だけカールせずメッシュの尻尾軸に沿わせる。"""
    amw = arm.matrix_world.copy()
    amw_inv = amw.inverted()

    def bw(name: str, attr: str = "head") -> Vector:
        b = arm.data.bones[name]
        return amw @ (b.head_local if attr == "head" else b.tail_local)

    src = {
        "nose_y": bw("bone004", "tail").y,
        "front_paw_y": (bw("bip01_l_hand").y + bw("bip01_r_hand").y) / 2.0,
        "hind_paw_y": (bw("bip01_l_foot").y + bw("bip01_r_foot").y) / 2.0,
        "tail_root_y": bw("bone016").y,
        "spine_top_z": max(bw("bip01_spine").z, bw("bip01_spine2").z),
        "head_center": bw("bip01_head"),
        "half_width": abs(bw("bip01_l_hand").x) * 3.0,
    }
    y_map = [
        (src["nose_y"], lm["nose_y"]),
        (src["front_paw_y"], lm["front_paw_y"]),
        (src["hind_paw_y"], lm["hind_paw_y"]),
        (src["tail_root_y"], lm["tail_root_y"]),
    ]
    z_scale = (lm["back_top_z"] * 0.82) / src["spine_top_z"]
    x_scale = min(2.5, (lm["half_width"] * 0.7) / max(src["half_width"], 1e-6))

    hip_z = lm["back_top_z"] * 0.42
    sho_z = lm["back_top_z"] * 0.45
    zf_back = hip_z / max(bw("bip01_l_thigh").z, 1e-6)
    zf_front = sho_z / max(bw("bip01_l_upperarm").z, 1e-6)
    leg_zf = {n: (zf_front if "front" in c else zf_back)
              for c, names in LEG_CHAINS.items() for n in names}
    # B-6 は horselink(足首) と hand/foot/指/つま先を無視していた。脚チェーン全体を同じ
    # Z 係数に載せないと、足首から先だけ別の高さにワープされて脚が折れる。
    for s in ("l", "r"):
        for p in ("clavicle", "hand", "horselink", "foot"):
            leg_zf[f"bip01_{s}_{p}"] = zf_front if p in ("clavicle", "hand") else zf_back
        for pref, zf in (("finger", zf_front), ("toe", zf_back)):
            for b in arm.data.bones:
                if b.name.startswith(f"bip01_{s}_{pref}"):
                    leg_zf[b.name] = zf

    head_names, neck_names, tail_names = set(HEAD_BONES), set(NECK_BONES), set(TAIL_BONES)

    def warp(p: Vector, name: str = "") -> Vector:
        return Vector((p.x * x_scale,
                       piecewise_linear(p.y, y_map),
                       p.z * leg_zf.get(name, z_scale)))

    head_offset = (lm["head_center"] + Vector((0.0, 0.0, lm["back_top_z"] * 0.02))) - warp(src["head_center"])

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for eb in arm.data.edit_bones:
        if eb.name in tail_names:
            continue
        for attr in ("head", "tail"):
            q = warp(amw @ getattr(eb, attr), eb.name)
            if eb.name in head_names:
                q += head_offset
            elif eb.name in neck_names:
                q += head_offset * 0.45
            setattr(eb, attr, amw_inv @ q)

    curve = tail_axis_points(mesh, lm, len(TAIL_BONES) + 1)
    for i, name in enumerate(TAIL_BONES):
        eb = arm.data.edit_bones[name]
        eb.head = amw_inv @ curve[i]
        eb.tail = amw_inv @ curve[i + 1]
    bpy.ops.object.mode_set(mode="OBJECT")

    return {"z_scale": round(z_scale, 4), "x_scale": round(x_scale, 4),
            "zf_front": round(zf_front, 4), "zf_back": round(zf_back, 4),
            "tail_bones_straightened": len(TAIL_BONES),
            "leg_zf_bones": len(leg_zf)}


# ---------------------------------------------------------------- bind

def bind_standard(mesh: bpy.types.Object, arm: bpy.types.Object) -> dict:
    """主外皮に Automatic Weights → 実メッシュへ Data Transfer。自作ウェイトは一切書かない。"""
    keep = largest_component_verts(mesh)
    total = len(mesh.data.vertices)

    disabled = []
    for name in NO_DEFORM_BONES:
        if name in arm.data.bones:
            arm.data.bones[name].use_deform = False
            disabled.append(name)

    # --- プロキシ（主外皮のみ）を作る ---
    proxy = mesh.copy()
    proxy.data = mesh.data.copy()
    proxy.name = proxy.data.name = PROXY_NAME
    bpy.context.scene.collection.objects.link(proxy)

    bm = bmesh.new()
    bm.from_mesh(proxy.data)
    bm.verts.ensure_lookup_table()
    drop = [v for v in bm.verts if v.index not in keep]
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    bm.to_mesh(proxy.data)
    bm.free()
    proxy.data.update()

    # --- Automatic Weights（ボーンヒート） ---
    bpy.ops.object.select_all(action="DESELECT")
    proxy.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    heat_groups = len(proxy.vertex_groups)

    # --- 実メッシュへウェイト転写 ---
    activate(mesh)
    dt = mesh.modifiers.new("WeightTransfer", "DATA_TRANSFER")
    dt.object = proxy
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "POLYINTERP_NEAREST"
    dt.layers_vgroup_select_src = "ALL"
    dt.layers_vgroup_select_dst = "NAME"
    bpy.ops.object.datalayout_transfer(modifier=dt.name)
    bpy.ops.object.modifier_apply(modifier=dt.name)

    # --- 後始末 ---
    bpy.data.objects.remove(proxy, do_unlink=True)

    mesh.parent = arm
    mesh.matrix_parent_inverse = arm.matrix_world.inverted()
    am = mesh.modifiers.new("Armature", "ARMATURE")
    am.object = arm

    activate(mesh)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)

    # ウェイト平滑化。ボーン境界の急峻さが肘・肩・股関節の裂けを生む（初回計測で確認）。
    # Blender 標準の vertex_group_smooth は編集モードで選択頂点に対して働く。
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.object.vertex_group_smooth(group_select_mode="ALL",
                                       factor=SMOOTH_FACTOR, repeat=SMOOTH_REPEAT)
    bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.vertex_group_limit_total(limit=WEIGHT_LIMIT)
    bpy.ops.object.vertex_group_normalize_all(lock_active=False)

    used = {g.group for v in mesh.data.vertices for g in v.groups if g.weight > 1e-6}
    unweighted = sum(1 for v in mesh.data.vertices
                     if not any(g.weight > 1e-6 for g in v.groups))
    return {
        "method": "Automatic Weights (bone heat) on main shell + Data Transfer + smooth + limit",
        "total_verts": total,
        "main_shell_verts": len(keep),
        "transferred_verts": total - len(keep),
        "deform_disabled_bones": len(disabled),
        "vertex_groups_from_heat": heat_groups,
        "vertex_groups_final": len(mesh.vertex_groups),
        "bones_carrying_weight": len(used),
        "unweighted_verts": unweighted,
        "smooth": {"factor": SMOOTH_FACTOR, "repeat": SMOOTH_REPEAT},
        "weight_limit": WEIGHT_LIMIT,
    }


# ---------------------------------------------------------------- main

def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.skeleton)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")

    print("[P1-A] importing mesh ...")
    mesh, mstats = import_and_prepare_mesh(a.mesh)
    print(f"[P1-A] verts {mstats['before']} -> merge {mstats['after_merge']} -> join {mstats['joined']}")

    scale = normalize_mesh(mesh)

    # 左右対称化は **骨フィットより前**。素材メッシュは左半身が細く左前足が後ろにあり、
    # そのままだと骨が非対称なメッシュに合わされてしまう。
    # 歩幅の均し（足先の平均は動かさない）→ ボリュームの鏡像化、の順。
    print("[P1-A] equalizing stride (paws -> midpoint of L/R) ...")
    stride = equalize_stride(mesh)
    print(f"[P1-A] stride: {stride}")

    print("[P1-A] symmetrizing body (left half <- mirror of right half) ...")
    sym = symmetrize_body(mesh)
    print(f"[P1-A] symmetry: {sym}")

    # 対称化は正中線を動かさないので、曲がったマズルは残る。ここで鼻筋を X=0 に戻す。
    print("[P1-A] centering head midline (nose -> X=0) ...")
    hc = center_head_midline(mesh)
    print(f"[P1-A] head center: nose_x_after={hc['nose_x_after_mm']}mm")

    # 耳の UV を左右で分離する（shape_head より前。耳の板は z>0.252 で拾える）。
    print("[P1-A] separating ear UV islands (+X ear -> free space) ...")
    ear_uv = separate_ear_uvs(mesh)
    print(f"[P1-A] ear uv: {ear_uv}")

    lm = measure_landmarks(mesh)
    print(f"[P1-A] scale={scale:.4f} nose_y={lm['nose_y']:.3f} tail_root_y={lm['tail_root_y']:.3f} "
          f"back_top_z={lm['back_top_z']:.3f}")

    print("[P1-A] fitting bones (tail left straight; curl is P2) ...")
    fit = fit_bones(arm, mesh, lm)
    print(f"[P1-A] fit: {fit}")

    # 頭の整形は骨フィットの **後**。normalize_mesh は体長を「鼻先→尻尾根元」で
    # 定義するので、先にマズルを伸ばすと胴が縮み、全身の骨が動いてしまう。
    # 実際それだけで Jump の破綻辺が 0.489% → 0.537% とゲートを割った。
    # 頭の整形は見た目だけの話であり、体のバインドに影響してはならない。
    print("[P1-A] shaping head (muzzle + width profile) ...")
    hs = shape_head(mesh)
    print(f"[P1-A] head: {hs}")

    print("[P1-A] re-placing leg chains (symmetric, vertical, stride removed) ...")
    legs = place_leg_chains(arm, mesh)
    print(f"[P1-A] legs: {legs}")

    print("[P1-A] adding belly deform bones ...")
    belly = add_belly_bones(arm, mesh)
    print(f"[P1-A] belly: {belly}")

    if LEOPARD_MESH in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[LEOPARD_MESH], do_unlink=True)

    print("[P1-A] binding with standard modifiers ...")
    skin = bind_standard(mesh, arm)
    print(f"[P1-A] bind: {skin}")

    out_blend = Path(a.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    out_glb = Path(a.output_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(out_glb), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {out_glb}")

    rep = Path(a.report)
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps({
        "task": "P1-A: rebind koha9 mesh with standard Blender modifiers only",
        "inputs": {"skeleton": a.skeleton, "mesh": a.mesh},
        "outputs": {"blend": str(out_blend), "glb": str(out_glb)},
        "mesh": mstats,
        "mesh_scale": scale,
        "stride": stride,
        "symmetry": sym,
        "head_center": hc,
        "ear_uv": ear_uv,
        "head_shape": hs,
        "bone_fit": fit,
        "leg_chains": legs,
        "belly_bones": belly,
        "skinning": skin,
        "actions": [x.name for x in bpy.data.actions],
        "note": "アニメーションはこの後 b6b_retarget_animations_blender.py でリターゲットする。",
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {rep}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
