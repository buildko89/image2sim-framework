"""B-6: Koha9 Mesh Transplant (Blender CLI script)

方針転換（A案）: ヒョウメッシュを変形して猫に寄せるのをやめ、理想の見た目である
koha9_cat メッシュ（= png/koha1-4.png の実体）を Leopard アーマチュア
（98ボーン・8アニメーション）にスキニングして載せ替える。

処理の流れ:
  1. cat_koha9.blend（B-4: 変形済みスケルトン）を開く
  2. koha9_cat.glb をインポートし、シェイプキー310個を除去、
     トランスフォームを焼き込み、2メッシュ（本体+尻尾プルーム）を結合、
     体長（鼻先→尻尾根元）を TARGET_BODY_LENGTH に正規化、接地を Z=0 に
  3. メッシュからランドマーク（前後の足の位置・背の高さ・頭の中心・尻尾根元）を計測し、
     ボーンのレスト位置を区分線形ワープでメッシュ内部へフィット
  4. 尻尾: メッシュを上方へカール変形（png/koha 参照の巻き尻尾）し、
     尻尾ボーン (bone016-020) を同じカール曲線に沿って再配置
  5. ヒョウメッシュを削除し、koha9 メッシュをボーンヒート自動ウェイトでバインド
  6. blend + GLB（8アニメーション同梱）を出力

使用方法:
  blender --background --python pipeline_v2/b6_koha9_mesh_transplant_blender.py -- \
    --skeleton output_v2/base/cat_koha9.blend \
    --mesh input/cat2/koha9_cat.glb \
    --output-blend output_v2/base/cat_koha.blend \
    --output-glb output_v2/base/cat_koha.glb \
    --report output_v2/reports/b6_koha9_mesh_transplant.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

LEOPARD_MESH = "Leopard_Hybrid"
NEW_MESH_NAME = "Koha9"

TARGET_BODY_LENGTH = 0.35   # 鼻先→尻尾根元 (m)
TAIL_CURL_DEG = 155.0       # 尻尾カールの累積角（png/koha: 背の上まで巻き上げ）
TAIL_CURL_START = 0.12      # カール開始位置（尻尾根元からの正規化距離）
TAIL_LENGTH_SCALE = 0.90    # 尻尾をわずかに短縮（ユーザー要望: 長すぎる）

HEAD_BONES = ["bip01_head"] + [f"bone{i:03d}" for i in range(1, 16)] + ["s_fxtop", "s_fxtop_0"]
NECK_BONES = ["bip01_neck", "bip01_neck1"]
TAIL_BONES = [f"bone{i:03d}" for i in range(16, 21)]

# ウェイト割り当ての設計（領域ゲート方式）:
#   - 胴体・頭: 脊椎チェーンに沿った Y 方向ガウシアンカーネル。
#     3D距離だと太い腹の頂点が脚ボーンに吸われるため、体軸方向のみで配分する。
#   - 脚: 各脚チェーンへの距離ゲート付きで、チェーン内は 1/d² 配分、胴体と滑らかにブレンド。
#   - 尻尾: 「カール前に尻尾領域だった頂点」だけを尻尾ボーンに割り当てる。
#     （カール後の尻尾は背中の直上を通るため、単純距離だと背中が尻尾に吸われて爆発する）
#   - 耳・指・顎などの細部ボーンは使わない（頭/手足に剛体追従）。
BODY_CHAIN = ["bip01_head", "bip01_neck1", "bip01_neck", "bip01_spine2",
              "bip01_spine1", "bip01_spine", "bip01_pelvis"]
# 短足には2関節（付け根+膝）で十分。下腿・足先ボーンまで使うと、ヒョウ用の
# 大きな足首回転で足先メッシュが裂ける（ぬいぐるみ的な脚にするのが正解）。
LEG_CHAINS = {
    "l_front": ["bip01_l_upperarm", "bip01_l_forearm"],
    "r_front": ["bip01_r_upperarm", "bip01_r_forearm"],
    "l_back": ["bip01_l_thigh", "bip01_l_calf"],
    "r_back": ["bip01_r_thigh", "bip01_r_calf"],
}
WEIGHT_BONES = BODY_CHAIN + [b for chain in LEG_CHAINS.values() for b in chain] + TAIL_BONES
LEG_GATE_FAR = 0.075   # 脚チェーンからこの距離までは胴体とブレンド (m)
LEG_GATE_NEAR = 0.045  # この距離以内は脚チェーンのウェイトのみ (m)。脚表面(半径~0.04)を確実に含める
SMOOTH_ITERATIONS = 3  # ラプラシアン平滑化の回数


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transplant koha9 mesh onto leopard armature.")
    parser.add_argument("--skeleton", required=True)
    parser.add_argument("--mesh", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--report", required=True)
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


# ---------------------------------------------------------------- mesh prep

def import_and_prepare_mesh(glb_path: str) -> bpy.types.Object:
    """koha9 GLB を取り込み、単一メッシュ・ワールド座標焼き込み・Z=0接地にする。"""
    before = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    imported = [o for o in bpy.context.scene.objects if o not in before]
    meshes = [o for o in imported if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("No mesh in koha9 GLB")

    for obj in meshes:
        # シェイプキー除去（モーフアニメ310個はスキニングと干渉するため捨てる）
        if obj.data.shape_keys:
            obj.shape_key_clear()
        # ワールド座標を頂点に焼き込み、親エンプティから切り離す
        mw = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.data.transform(mw)
        obj.data.update()

    empties = [o for o in imported if o.type == "EMPTY"]

    # 結合（本体 + 尻尾プルーム）
    bpy.ops.object.select_all(action="DESELECT")
    main = max(meshes, key=lambda o: len(o.data.vertices))
    for obj in meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = main
    bpy.ops.object.join()
    mesh = bpy.context.view_layer.objects.active
    mesh.name = NEW_MESH_NAME
    mesh.data.name = NEW_MESH_NAME

    # 使われなくなった親エンプティを削除（join で無効化されるためメッシュとは別に収集済み）
    for obj in empties:
        bpy.data.objects.remove(obj, do_unlink=True)

    # アニメーション（モーフ用アクション）も除去
    for action in list(bpy.data.actions):
        if action.name.startswith("Object_"):
            bpy.data.actions.remove(action)
    return mesh


def measure_landmarks(mesh: bpy.types.Object) -> dict:
    """メッシュ形状からボーンフィット用のランドマークを計測する（座標系: -Y=前, +Z=上）"""
    vs = [v.co.copy() for v in mesh.data.vertices]
    min_y = min(v.y for v in vs)
    max_y = max(v.y for v in vs)
    min_z = min(v.z for v in vs)

    # Yスライスごとの断面積で「尻尾の根元」（断面が急に細くなる位置）を探す
    bins = 60
    span = (max_y - min_y) / bins
    slice_area = []
    for i in range(bins):
        y0 = min_y + i * span
        sel = [v for v in vs if y0 <= v.y < y0 + span]
        if len(sel) < 5:
            slice_area.append(0.0)
            continue
        dx = max(v.x for v in sel) - min(v.x for v in sel)
        dz = max(v.z for v in sel) - min(v.z for v in sel)
        slice_area.append(dx * dz)
    peak = max(slice_area)
    # 後方（+Y）に向かって、断面がピークの30%を下回った最初のスライス = 尻尾根元
    peak_idx = slice_area.index(peak)
    tail_root_y = max_y - 0.25 * (max_y - min_y)  # フォールバック
    for i in range(peak_idx, bins):
        if slice_area[i] < peak * 0.30:
            tail_root_y = min_y + i * span
            break

    body = [v for v in vs if v.y < tail_root_y]
    tail = [v for v in vs if v.y >= tail_root_y]

    # 足クラスタ: 接地付近（下から4cm相当 = 全高の12%）の頂点を前後に分ける
    body_max_z = max(v.z for v in body)
    low_cut = min_z + (body_max_z - min_z) * 0.12
    low = [v for v in body if v.z < low_cut]
    mid_y = (min(v.y for v in low) + max(v.y for v in low)) / 2.0
    front_paws = [v for v in low if v.y < mid_y]
    hind_paws = [v for v in low if v.y >= mid_y]

    # 頭領域: 前方25%
    head_cut = min_y + (tail_root_y - min_y) * 0.28
    head = [v for v in body if v.y < head_cut]

    tail_root_center = Vector((
        sum(v.x for v in tail) / len(tail) if tail else 0.0,
        tail_root_y,
        sum(v.z for v in vs if abs(v.y - tail_root_y) < span * 2) / max(1, len([v for v in vs if abs(v.y - tail_root_y) < span * 2])),
    ))

    return {
        "nose_y": min_y,
        "rear_y": max_y,
        "tail_root_y": tail_root_y,
        "tail_root_center": tail_root_center,
        "tail_tip_y": max_y,
        "ground_z": min_z,
        "back_top_z": body_max_z,
        "front_paw_y": sum(v.y for v in front_paws) / max(1, len(front_paws)),
        "hind_paw_y": sum(v.y for v in hind_paws) / max(1, len(hind_paws)),
        "head_center": Vector((
            sum(v.x for v in head) / max(1, len(head)),
            sum(v.y for v in head) / max(1, len(head)),
            sum(v.z for v in head) / max(1, len(head)),
        )),
        "half_width": max(abs(v.x) for v in body),
    }


def normalize_mesh(mesh: bpy.types.Object) -> float:
    """体長（鼻先→尻尾根元）を TARGET_BODY_LENGTH に、接地を Z=0、左右中心を X=0 にする。"""
    lm = measure_landmarks(mesh)
    body_len = lm["tail_root_y"] - lm["nose_y"]
    scale = TARGET_BODY_LENGTH / body_len
    mesh.data.transform(Matrix.Diagonal((scale, scale, scale, 1.0)))
    mesh.data.update()
    lm2 = measure_landmarks(mesh)
    offset = Vector((0.0, 0.0, -lm2["ground_z"]))
    mesh.data.transform(Matrix.Translation(offset))
    mesh.data.update()
    return scale


# ---------------------------------------------------------------- bone fit

def piecewise_linear(x: float, points: list[tuple[float, float]]) -> float:
    """制御点 (src, dst) の区分線形写像。端の外側は端区間の傾きで外挿する。"""
    pts = sorted(points)
    if x <= pts[0][0]:
        (x0, y0), (x1, y1) = pts[0], pts[1]
    elif x >= pts[-1][0]:
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
    else:
        for i in range(len(pts) - 1):
            if pts[i][0] <= x <= pts[i + 1][0]:
                (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                break
    if abs(x1 - x0) < 1e-9:
        return y0
    t = (x - x0) / (x1 - x0)
    return y0 + t * (y1 - y0)


def fit_bones(arm: bpy.types.Object, lm: dict) -> dict:
    """レストボーンを koha9 メッシュのランドマークへワープ。尻尾ボーンはカール曲線に沿わせる。"""
    amw = arm.matrix_world.copy()
    amw_inv = amw.inverted()

    def bone_world(name: str, attr: str = "head") -> Vector:
        b = arm.data.bones[name]
        return amw @ (b.head_local if attr == "head" else b.tail_local)

    # ソース（現スケルトン）ランドマーク
    src = {
        "nose_y": bone_world("bone004", "tail").y,
        "front_paw_y": (bone_world("bip01_l_hand").y + bone_world("bip01_r_hand").y) / 2.0,
        "hind_paw_y": (bone_world("bip01_l_foot").y + bone_world("bip01_r_foot").y) / 2.0,
        "tail_root_y": bone_world("bone016").y,
        "spine_top_z": max(bone_world("bip01_spine").z, bone_world("bip01_spine2").z),
        "head_center": bone_world("bip01_head"),
        "half_width": abs(bone_world("bip01_l_hand").x) * 3.0,  # 体幅の代理（脚の外側程度）
    }

    y_map_points = [
        (src["nose_y"], lm["nose_y"]),
        (src["front_paw_y"], lm["front_paw_y"]),
        (src["hind_paw_y"], lm["hind_paw_y"]),
        (src["tail_root_y"], lm["tail_root_y"]),
    ]
    # Z: 接地固定で背の高さ比スケール（メッシュの背にはたっぷり毛があるので 0.82 掛けで骨を内側に）
    z_scale = (lm["back_top_z"] * 0.82) / src["spine_top_z"]
    x_scale = min(2.5, (lm["half_width"] * 0.7) / max(src["half_width"], 1e-6))

    # 脚チェーンは別の Z 係数で「メッシュの脚ボリューム内」に収める。
    # 一律 z_scale だと股関節が背中の表面近くまで上がり、背中の頂点が脚ゲートに
    # 入って裂ける（B-6 v1 の失敗）。股関節はおよそ腹の高さ（背高の42%）に置く。
    hip_target_z = lm["back_top_z"] * 0.42
    shoulder_target_z = lm["back_top_z"] * 0.45
    zf_back = hip_target_z / max(bone_world("bip01_l_thigh").z, 1e-6)
    zf_front = shoulder_target_z / max(bone_world("bip01_l_upperarm").z, 1e-6)
    leg_zf = {}
    for chain, names in LEG_CHAINS.items():
        for n in names:
            leg_zf[n] = zf_front if "front" in chain else zf_back

    head_names = set(HEAD_BONES)
    neck_names = set(NECK_BONES)
    tail_names = set(TAIL_BONES)

    def warp(p: Vector, bone_name: str = "") -> Vector:
        zf = leg_zf.get(bone_name, z_scale)
        return Vector((p.x * x_scale, piecewise_linear(p.y, y_map_points), p.z * zf))

    # 頭クラスタの平行移動量（ワープ後の bip01_head を頭の実測中心へ。毛の分やや前下げ）
    head_target = lm["head_center"] + Vector((0.0, 0.0, lm["back_top_z"] * 0.02))
    head_offset = head_target - warp(src["head_center"])

    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    moved = {"warped": 0, "head": 0, "neck": 0, "tail": 0}
    for eb in arm.data.edit_bones:
        if eb.name in tail_names:
            continue  # 尻尾は後段でカール曲線に沿わせる
        for attr in ("head", "tail"):
            p = amw @ getattr(eb, attr)
            q = warp(p, eb.name)
            if eb.name in head_names:
                q += head_offset
            elif eb.name in neck_names:
                q += head_offset * 0.45
            setattr(eb, attr, amw_inv @ q)
        if eb.name in head_names:
            moved["head"] += 1
        elif eb.name in neck_names:
            moved["neck"] += 1
        else:
            moved["warped"] += 1

    # --- 尻尾ボーン: カール後の曲線に沿って等間隔配置 ---
    curve = tail_curve_points(lm, samples=len(TAIL_BONES) + 1)
    for i, name in enumerate(TAIL_BONES):
        eb = arm.data.edit_bones[name]
        eb.head = amw_inv @ curve[i]
        eb.tail = amw_inv @ curve[i + 1]
        moved["tail"] += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    return {"moved": moved, "z_scale": z_scale, "x_scale": x_scale,
            "zf_front": zf_front, "zf_back": zf_back,
            "hip_target_z": hip_target_z,
            "y_map": [[round(a, 4), round(b, 4)] for a, b in y_map_points]}


# ---------------------------------------------------------------- tail curl

def tail_curl_transform(lm: dict):
    """尻尾カールの写像を返す: 元の直線尻尾上の位置 → カール後のワールド座標。

    根元から距離 t (0-1) の点を、根元ピボット回りに累積角 θ(t) で上方へ曲げる。
    アーク積分で滑らかなカールにする。
    """
    root = lm["tail_root_center"].copy()
    tip_y = lm["tail_tip_y"]
    tail_len = (tip_y - root.y) * TAIL_LENGTH_SCALE
    curl_total = math.radians(TAIL_CURL_DEG)

    steps = 64

    def theta(t: float) -> float:
        if t <= TAIL_CURL_START:
            return 0.0
        u = (t - TAIL_CURL_START) / (1.0 - TAIL_CURL_START)
        return curl_total * u

    # 中心線をアーク積分で構築（+Y 方向スタート → 上向きにカール）
    centers = [root.copy()]
    dirs = []
    for i in range(steps):
        t = (i + 0.5) / steps
        a = theta(t)
        d = Vector((0.0, math.cos(a), math.sin(a)))
        dirs.append(d)
        centers.append(centers[-1] + d * (tail_len / steps))

    def transform(p: Vector) -> Vector:
        t = (p.y - root.y) / max(tip_y - root.y, 1e-9)
        t = max(0.0, min(1.0, t))
        idx = min(int(t * steps), steps - 1)
        c = centers[idx].lerp(centers[idx + 1], t * steps - idx)
        d = dirs[idx]
        # 断面内オフセット（元: x横, z上下）をカール後の座標系に載せ替え
        off_x = p.x - root.x
        off_z = p.z - root.z
        up = Vector((0.0, -d.z, d.y))  # d と直交する断面上方向
        return c + Vector((off_x, 0.0, 0.0)) + up * off_z

    return transform, centers


def tail_curve_points(lm: dict, samples: int) -> list[Vector]:
    """カール後の尻尾中心線を samples 個の等間隔点で返す（ボーン配置用）"""
    _, centers = tail_curl_transform(lm)
    n = len(centers) - 1
    return [centers[round(i * n / (samples - 1))] for i in range(samples)]


def curl_tail_mesh(mesh: bpy.types.Object, lm: dict) -> int:
    transform, _ = tail_curl_transform(lm)
    root_y = lm["tail_root_y"]
    count = 0
    for v in mesh.data.vertices:
        if v.co.y >= root_y:
            v.co = transform(v.co)
            count += 1
    mesh.data.update()
    return count


# ---------------------------------------------------------------- skinning

def _point_segment_dist(p: Vector, a: Vector, b: Vector) -> float:
    ab = b - a
    denom = ab.length_squared
    if denom < 1e-12:
        return (p - a).length
    t = max(0.0, min(1.0, (p - a).dot(ab) / denom))
    return (p - (a + ab * t)).length


def _chain_weights(p: Vector, segments: list[tuple[str, Vector, Vector]], top_k: int = 2) -> dict[str, float]:
    dists = sorted(((_point_segment_dist(p, a, b), name) for name, a, b in segments))[:top_k]
    raw = {name: 1.0 / (d * d + 1e-6) for d, name in dists}
    total = sum(raw.values())
    return {name: w / total for name, w in raw.items()}


def bind_mesh(mesh: bpy.types.Object, arm: bpy.types.Object, tail_verts: set[int]) -> dict:
    """領域ゲート付きウェイト割り当てでバインドする。

    ボーンヒート (ARMATURE_AUTO) は毛房などの非連結パーツが多い koha9 メッシュでは
    全滅し、単純な3D距離配分は「背中→尻尾」「腹→脚」の誤割り当てで爆発するため、
    領域ごとに使うボーンを制限する（モジュールdocstringとWEIGHT_BONES付近のコメント参照）。
    """
    disabled = []
    weight_set = set(WEIGHT_BONES)
    for bone in arm.data.bones:
        if bone.name not in weight_set and bone.use_deform:
            bone.use_deform = False
            disabled.append(bone.name)

    amw = arm.matrix_world.copy()

    def seg(name: str) -> tuple[str, Vector, Vector]:
        b = arm.data.bones[name]
        return (name, amw @ b.head_local, amw @ b.tail_local)

    tail_segs = [seg(n) for n in TAIL_BONES]
    leg_segs = {chain: [seg(n) for n in names] for chain, names in LEG_CHAINS.items()}
    # 胴体カーネル: 各脊椎ボーンの中点 Y をノードに、Y 距離ガウシアンで配分
    body_nodes = []
    for n in BODY_CHAIN:
        _, a, b = seg(n)
        body_nodes.append((n, (a.y + b.y) / 2.0))
    spans = [abs(body_nodes[i][1] - body_nodes[i + 1][1]) for i in range(len(body_nodes) - 1)]
    sigma = 1.2 * (sum(spans) / len(spans))

    def body_weights(p: Vector) -> dict[str, float]:
        raw = {}
        for name, yc in body_nodes:
            d = (p.y - yc) / sigma
            raw[name] = math.exp(-d * d)
        top = sorted(raw.items(), key=lambda kv: -kv[1])[:3]
        total = sum(w for _, w in top)
        return {name: w / total for name, w in top}

    mw = mesh.matrix_world.copy()
    weights: list[dict[str, float]] = [None] * len(mesh.data.vertices)
    pelvis_y = next(yc for n, yc in body_nodes if n == "bip01_pelvis")
    tail_base_y = tail_segs[0][1].y

    for v in mesh.data.vertices:
        p = mw @ v.co
        if v.index in tail_verts:
            w = _chain_weights(p, tail_segs, top_k=2)
            # 根元は骨盤へブレンドして胴とつなぐ
            base_t = max(0.0, min(1.0, (p.y - tail_base_y) / 0.05)) if p.y < tail_base_y + 0.05 else 1.0
            if base_t < 1.0:
                blend = 0.5 * (1.0 - base_t)
                w = {k: val * (1.0 - blend) for k, val in w.items()}
                w["bip01_pelvis"] = w.get("bip01_pelvis", 0.0) + blend
            weights[v.index] = w
            continue

        wb = body_weights(p)
        best_chain, best_d = None, 1e9
        for chain, segs in leg_segs.items():
            d = min(_point_segment_dist(p, a, b) for _, a, b in segs)
            if d < best_d:
                best_chain, best_d = chain, d
        if best_d < LEG_GATE_FAR:
            lam = (LEG_GATE_FAR - best_d) / (LEG_GATE_FAR - LEG_GATE_NEAR)
            lam = max(0.0, min(1.0, lam))
            lam = lam * lam * (3.0 - 2.0 * lam)  # smoothstep
            # 高さ制限: 股関節より上の頂点（背中・脇腹）には脚ウェイトを与えない
            hip_z = max(max(a.z, b.z) for _, a, b in leg_segs[best_chain])
            h_fade = max(0.0, min(1.0, (hip_z * 1.15 - p.z) / (hip_z * 0.25)))
            lam *= h_fade * h_fade * (3.0 - 2.0 * h_fade)
            wl = _chain_weights(p, leg_segs[best_chain], top_k=2)
            w = {k: val * (1.0 - lam) for k, val in wb.items()}
            for k, val in wl.items():
                w[k] = w.get(k, 0.0) + val * lam
            weights[v.index] = w
        else:
            weights[v.index] = wb

    # ラプラシアン平滑化（隣接頂点とのウェイト平均）で領域境界を滑らかに
    adjacency: list[list[int]] = [[] for _ in range(len(mesh.data.vertices))]
    for e in mesh.data.edges:
        i, j = e.vertices
        adjacency[i].append(j)
        adjacency[j].append(i)
    for _ in range(SMOOTH_ITERATIONS):
        new_weights: list[dict[str, float]] = [None] * len(weights)
        for i, w in enumerate(weights):
            if not adjacency[i]:
                new_weights[i] = w
                continue
            acc: dict[str, float] = {k: val * 0.5 for k, val in w.items()}
            share = 0.5 / len(adjacency[i])
            for j in adjacency[i]:
                for k, val in weights[j].items():
                    acc[k] = acc.get(k, 0.0) + val * share
            # 上位4本に制限して正規化（ゲームエンジンの4影響制限に合わせる）
            top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
            total = sum(val for _, val in top)
            new_weights[i] = {k: val / total for k, val in top}
        weights = new_weights

    # 小さな連結成分（毛房シェル）は成分内でウェイトを均一化して剛体化する。
    # 毛房は本体と非連結なためエッジ経由の平滑化が効かず、房の中で頂点ごとに
    # ウェイトが割れると板状に裂けて見える。
    parent = list(range(len(weights)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in mesh.data.edges:
        i, j = e.vertices
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
    components: dict[int, list[int]] = {}
    for i in range(len(weights)):
        components.setdefault(find(i), []).append(i)
    main_component = max(components.values(), key=len)
    # 本体表面の KD-tree（毛房の直下の表面ウェイトを引くため）
    from mathutils import kdtree
    kd = kdtree.KDTree(len(main_component))
    for i in main_component:
        kd.insert(mesh.data.vertices[i].co, i)
    kd.balance()

    rigidified = 0
    for members in components.values():
        if members is main_component:
            continue
        # 房の各頂点直下の本体ウェイトを平均 → 房全体に均一適用。
        # 房自身の位置ベース重みではなく本体表面の重みを使うことで、
        # 下の毛皮と完全に一体で動く（房が別方向に動いて板状に見える問題の根治）。
        acc: dict[str, float] = {}
        samples = members if len(members) <= 20 else members[:: max(1, len(members) // 20)]
        for i in samples:
            _, main_idx, _ = kd.find(mesh.data.vertices[i].co)
            for k, val in weights[main_idx].items():
                acc[k] = acc.get(k, 0.0) + val
        top = sorted(acc.items(), key=lambda kv: -kv[1])[:4]
        total = sum(val for _, val in top)
        mean_w = {k: val / total for k, val in top}
        for i in members:
            weights[i] = mean_w
        rigidified += 1

    groups = {name: mesh.vertex_groups.new(name=name) for name in WEIGHT_BONES}
    for i, w in enumerate(weights):
        for name, val in w.items():
            if val > 0.005:
                groups[name].add([i], val, "REPLACE")

    bpy.ops.object.select_all(action="DESELECT")
    mesh.select_set(True)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.parent_set(type="ARMATURE_NAME")

    orphan = sum(1 for v in mesh.data.vertices if not v.groups)
    return {"disabled_deform_bones": disabled, "orphan_vertices": orphan,
            "vertex_groups": len(mesh.vertex_groups), "method": "region_gated",
            "tail_vertices": len(tail_verts), "smooth_iterations": SMOOTH_ITERATIONS,
            "rigidified_components": rigidified, "total_components": len(components)}


# ---------------------------------------------------------------- main

def main() -> int:
    args = parse_args()
    bpy.ops.wm.open_mainfile(filepath=args.skeleton)

    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")

    print("[B-6] importing koha9 mesh ...")
    mesh = import_and_prepare_mesh(args.mesh)
    scale = normalize_mesh(mesh)
    lm = measure_landmarks(mesh)
    print(f"[B-6] mesh scale={scale:.4f} landmarks: nose_y={lm['nose_y']:.3f} "
          f"front_paw_y={lm['front_paw_y']:.3f} hind_paw_y={lm['hind_paw_y']:.3f} "
          f"tail_root_y={lm['tail_root_y']:.3f} back_top_z={lm['back_top_z']:.3f}")

    # カール前に尻尾領域の頂点を記録（ウェイト割り当てのゲートに使う。
    # カール後は尻尾が背中の直上を通るため、位置からは判定できなくなる）
    tail_verts = {v.index for v in mesh.data.vertices if v.co.y >= lm["tail_root_y"]}

    print("[B-6] curling tail mesh ...")
    curled = curl_tail_mesh(mesh, lm)
    print(f"[B-6] curled {curled} tail vertices")

    print("[B-6] fitting bones ...")
    fit_report = fit_bones(arm, lm)
    print(f"[B-6] fit: {fit_report}")

    # ヒョウメッシュ削除 → スキニング
    if LEOPARD_MESH in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects[LEOPARD_MESH], do_unlink=True)
    skin_report = bind_mesh(mesh, arm, tail_verts)
    print(f"[B-6] skinning: {skin_report}")

    out_blend = Path(args.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    out_glb = Path(args.output_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format="GLB",
        use_selection=True,
        export_animation_mode="ACTIONS",
    )
    print(f"  Exported: {out_glb}")

    report = {
        "task": "B-6: Koha9 Mesh Transplant",
        "reference_images": ["png/koha1.png", "png/koha3.png"],
        "inputs": {"skeleton": args.skeleton, "mesh": args.mesh},
        "outputs": {"blend": str(out_blend), "glb": str(out_glb)},
        "mesh_scale": scale,
        "landmarks": {k: (list(v) if isinstance(v, Vector) else v) for k, v in lm.items()},
        "tail": {"curl_deg": TAIL_CURL_DEG, "curl_start": TAIL_CURL_START,
                 "length_scale": TAIL_LENGTH_SCALE, "curled_vertices": curled},
        "bone_fit": fit_report,
        "skinning": skin_report,
        "actions": [a.name for a in bpy.data.actions],
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
