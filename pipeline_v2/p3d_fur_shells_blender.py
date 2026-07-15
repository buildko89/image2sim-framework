"""P3-10: 胸の出っ張りを抑え、胴体に多層毛シェルを生成する（prompt5.md 対応）。

1. 胸のタック: 胸の頂点（実測で Zmax≈0.212、顎と同じだけ前へ出ている）を最大 8mm
   後ろへ引っ込める。滑らかな falloff で肩・顎には触れない。
2. 毛シェル: 体メッシュを3層複製し、頂点法線方向（腹・胸は下向きバイアス付き）へ
   部位別の量だけ膨らませ、`p3_koha9_fur_shell.png`（RGB=basecolor, A=毛筋）を
   alpha cutoff 違い（外層ほど高い=まばら）で貼る。複製なのでウェイトは体と同一 →
   アニメも体と一緒に動く。

座標系の注意: 設計座標は glTF 系（Y上/Z前）。Blender ワールドへは b=(gx,−gz,gy)。
罠: シェルをアーマチュアへ親子付けしない（0.0009 スケールで潰れる。P3-9 で実測）。

  blender --background --python pipeline_v2/p3d_fur_shells_blender.py -- \
    --input output_v2/base/p3_koha9.blend --fur output_v2/textures/p3_koha9_fur_shell.png \
    --output-blend output_v2/base/p3_koha9.blend --output-glb output_v2/base/p3_koha9.glb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

BODY_MAT = "Koha9Body"
# (層の伸び率 t, alpha cutoff)。外層ほど毛がまばらになる。
# cutoff は p3_make_fur_alpha.CUTOFFS と揃える。
# **最内層は cutoff=None = 完全不透明の「第二の皮膚」。** 房の隙間から反対側や
# 腹の中心の面（別の色）が覗くと、白/黒のゴミに見える（赤テクスチャ実験で確定）。
# 不透明の内層があれば、隙間の背景は常に「その場所と同じ色」になる。
# 不透明層は毛長の 70% まで上げる。55% でも腹の輪郭に隙間の筋が残った（実機で指摘）。
# 芯は不透明・外側 30% だけ房のフリンジにする。
LAYERS = [(0.70, None), (0.82, 0.32), (0.91, 0.52), (1.00, 0.70)]
MIN_FUR = 0.0015   # これ未満の毛長の面はシェルから削除（顔・耳・尻尾芯。
#                    不透明内層が目を低解像度テクスチャで覆うのを防ぐ + Zファイト回避）

# 胸のタック（glTF系）。8mm→13mm でも「あまりにも出っ張りすぎ」と指摘 → 18mm。
TUCK_MAX = 0.018
TUCK_Y0, TUCK_YSIG = 0.095, 0.062     # Y の山（ここが最も引っ込む）
TUCK_Z_ON = (0.13, 0.18)              # Z がこの範囲で 0→1
TUCK_X_OFF = (0.035, 0.065)           # |X| がこの範囲で 1→0（肩は触らない）


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--fur", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def fur_amount(g: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """頂点ごとの毛の長さ[m]と下向きバイアス係数。g は glTF 系 (N,3)。"""
    x, y, z = g[:, 0], g[:, 1], g[:, 2]
    # 基本は短く密（2.5mm）。長いままだと背中の黒斑の上に外層の点が浮いて
    # 「黒いゴミ」に見える（prompt6.md で指摘）。長くするのは腹・胸・腰だけ。
    amt = np.full(len(g), 0.0025)
    grav = np.full(len(g), 0.15)

    # 腹のスカート（赤丸）: もっと長く・密に（prompt6.md）。下向きに垂らす。
    # Z の窓は腹ボーンと脚ボーンのウェイト境界（belly_front Z≈0.07 / belly_rear Z≈-0.10）
    # より内側で絞る。境界上に長い毛を置くと (M_a-M_b)·d でレスト辺が伸ばされ、
    # Jump の qa_skin_stretch が 0.54% に超過する（実測）。
    belly = smoothstep(0.105, 0.055, y) * smoothstep(-0.105, -0.070, z) * smoothstep(0.065, 0.025, z)
    amt = amt + belly * 0.0175                        # 最大 20mm
    # 下向きバイアスが強いと、白い脇腹の頂点がラスト斑の上まで垂れて
    # 「白い毛だけ色が違う」ように見える（実機で指摘）。腹の法線はもともと下向きなので
    # バイアスは弱くてもスカートは垂れる。
    grav = np.where(belly > 0.3, 0.45, grav)

    # 胸〜首（青丸）: ほどよくモフモフ（形はタックで抑える）。毛の分も見かけの
    # 膨らみになるので控えめに（8.5mm → 6mm）。|X| は胸の中央だけ
    # （肩・上腕の上に乗せると upperarm⇔胴の境界で qa_skin_stretch を割る。実測）
    chest = smoothstep(0.10, 0.145, z) * smoothstep(0.175, 0.13, y) * smoothstep(0.035, 0.06, y) \
        * smoothstep(0.058, 0.038, np.abs(x))
    amt = np.maximum(amt, 0.0025 + chest * 0.0035)    # 最大 6mm
    grav = np.where(chest > 0.3, 0.40, grav)

    # 腰まわりも実物はふわっとしている
    rump = smoothstep(-0.075, -0.115, z) * smoothstep(0.045, 0.075, y) * smoothstep(0.185, 0.15, y)
    amt = np.maximum(amt, 0.0025 + rump * 0.005)

    # 抑える所: 顔・耳・足先・尻尾の芯
    amt = amt * (1.0 - 0.85 * smoothstep(0.10, 0.145, z) * smoothstep(0.16, 0.19, y))   # 顔
    amt = np.where(y > 0.250, 0.0, amt)                                                  # 耳
    amt = amt * smoothstep(0.008, 0.035, y)                                              # 足先
    # 尻尾の芯（カールしたプルーム本体）はシェル無し
    tail_core = (z < -0.135) & (y > 0.16)
    amt = np.where(tail_core, 0.0, amt)                                                  # 尻尾
    # 尾根元の裏（bone016 支配の帯 y 0.125〜0.16）は丸ごと消すと素通しになる（実機で
    # 指摘）ので、短い毛 2mm で面を残して塞ぐ。長い毛はウェイト境界の増幅で
    # qa_skin_stretch を割るため置けない（Jump で実測）。
    junction = (z < -0.132) & (y > 0.125) & (y <= 0.16)
    amt = np.where(junction, 0.002, amt)

    # 腹⇔脚のウェイト境界の細い帯（前足の付け根 z≈0.07 / 後足の付け根 z≈-0.10、
    # どちらも脚の間で外からほぼ見えない）は毛を消す。体側でも元々破綻ギリギリの
    # 場所で、シェルを重ねると qa_skin_stretch の Jump が 0.82% まで割れる（実測）。
    # 毛長が MIN_FUR を切ると面ごと削除され、シェルがこの帯を複製しなくなる。
    # 前側の帯は脇の下（bip01_l_upperarm⇔胴、z≈0.05 y≈0.078）まで広げる。
    # 不透明層を外へ寄せたら（LAYERS 0.55〜）ここでも割れた（実測）。
    bf = smoothstep(0.105, 0.085, y) * smoothstep(0.030, 0.045, z) * smoothstep(0.100, 0.088, z)
    # 前脚上部の外側（bip01_*_upperarm 支配、rest≈[±0.05, 0.08, 0.118]）も Jump で割れる。
    # 2.5mm の薄い層なので消しても見た目への影響は小さい
    arm = (np.abs(x) > 0.033) & (z > 0.085) & (z < 0.140) & (y < 0.105)
    amt = np.where(arm, 0.0, amt)
    br = smoothstep(0.10, 0.075, y) * smoothstep(-0.078, -0.088, z) * smoothstep(-0.122, -0.112, z)
    amt = amt * (1.0 - 0.97 * np.maximum(bf, br))
    return amt, grav


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)

    body = next(o for o in bpy.data.objects if o.type == "MESH"
                and o.data.materials and o.data.materials[0].name == BODY_MAT
                and "FurShell" not in o.name)
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    if any("FurShell" in o.name for o in bpy.data.objects):
        raise SystemExit("FurShell は既に存在する（二重生成を防ぐため中断）")

    M = np.array(body.matrix_world)                    # 4x4
    M3, Minv3 = M[:3, :3], np.linalg.inv(M[:3, :3])
    nv = len(body.data.vertices)
    co = np.empty(nv * 3)
    body.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    nrm = np.empty(nv * 3)
    body.data.vertices.foreach_get("normal", nrm)
    nrm = nrm.reshape(-1, 3)

    w = co @ M3.T + M[:3, 3]                           # Blender ワールド
    g = np.stack([w[:, 0], w[:, 2], -w[:, 1]], axis=1)  # glTF 系 (x, y=up, z=fwd)
    nw = nrm @ np.linalg.inv(M3).T                     # 法線は逆転置で変換
    nw /= np.linalg.norm(nw, axis=1, keepdims=True) + 1e-12
    ng = np.stack([nw[:, 0], nw[:, 2], -nw[:, 1]], axis=1)

    # ---- 1. 胸のタック ----
    fy = np.exp(-((g[:, 1] - TUCK_Y0) / TUCK_YSIG) ** 2)
    fz = smoothstep(*TUCK_Z_ON, g[:, 2])
    fx = 1.0 - smoothstep(*TUCK_X_OFF, np.abs(g[:, 0]))
    tuck = TUCK_MAX * fy * fz * fx
    g_t = g.copy()
    g_t[:, 2] -= tuck
    print(f"[P3d] 胸のタック: 対象 {(tuck > 0.001).sum()} 頂点, 最大 {tuck.max()*1000:.1f} mm")

    def to_blender_co(gpts):
        wb = np.stack([gpts[:, 0], -gpts[:, 2], gpts[:, 1]], axis=1)
        return (wb - M[:3, 3]) @ Minv3.T

    body.data.vertices.foreach_set("co", to_blender_co(g_t).ravel())
    body.data.update()

    # ---- 2. 毛シェル ----
    img = bpy.data.images.load(str(Path(a.fur).resolve()), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    img.pack()

    amt, grav = fur_amount(g_t)
    dirs = ng + np.stack([np.zeros(nv), -grav, np.zeros(nv)], axis=1)
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True) + 1e-12

    # 変位ベクトル場を隣接でスムージングする。量や向きが急変する所（腹の縁・凹面）で
    # 隣接頂点の変位先が重なり、レスト辺がほぼ潰れて qa_skin_stretch の比率が爆発する
    # （Jump 0.529% FAIL, max x43.75 を実測）。場を均せば潰れ辺が消える。
    ne = len(body.data.edges)
    ev = np.empty(ne * 2, dtype=np.int64)
    body.data.edges.foreach_get("vertices", ev)
    e0, e1 = ev[0::2], ev[1::2]
    deg = np.zeros(nv)
    np.add.at(deg, e0, 1.0)
    np.add.at(deg, e1, 1.0)

    # 体のウェイトを読む（境界検出とシェル用スムージングの両方で使う）
    ngroups = len(body.vertex_groups)
    W = np.zeros((nv, ngroups), np.float32)
    for v in body.data.vertices:
        for ge in v.groups:
            W[v.index, ge.group] = ge.weight

    # ウェイトが不連続な場所（腹⇔脚・脇・付け根などの境界）の毛は自動で短くする。
    # 境界では隣接頂点のボーン行列差が毛長のぶん増幅され、qa_skin_stretch を割る
    # （手作業の帯では脇腹の belly_rear 境界などが漏れた。実測）。境界は皮膚の
    # 折り目なので短毛になるのは見た目にも自然。
    dW = 0.5 * np.abs(W[e0] - W[e1]).sum(1)
    gw = np.zeros(nv)
    np.maximum.at(gw, e0, dW)
    np.maximum.at(gw, e1, dW)
    print(f"[P3d] gw 百分位 50/90/99/max: "
          f"{np.percentile(gw,50):.3f}/{np.percentile(gw,90):.3f}/"
          f"{np.percentile(gw,99):.3f}/{gw.max():.3f}")
    # この体はウェイト自体は滑らか（差は小さい）が骨の回転が大きいので、
    # しきい値は低めに取る（0.45〜だと 0 頂点で効かなかった。実測）
    cap = 1.0 - 0.85 * smoothstep(0.08, 0.26, gw)
    amt = amt * cap
    print(f"[P3d] ウェイト境界で毛を短縮: {int((cap < 0.9).sum())} 頂点")

    disp = dirs * amt[:, None]
    for _ in range(4):
        acc = np.zeros_like(disp)
        np.add.at(acc, e0, disp[e1])
        np.add.at(acc, e1, disp[e0])
        disp = 0.5 * disp + 0.5 * acc / np.maximum(deg, 1.0)[:, None]

    # 毛の無い面（顔・耳・尻尾芯・足先）はシェルから削除する
    amt_max = np.maximum(amt, 0.0)
    del_polys = [p.index for p in body.data.polygons
                 if max(amt_max[v] for v in p.vertices) < MIN_FUR]
    print(f"[P3d] シェルから削除する面: {len(del_polys)} / {len(body.data.polygons)}")

    # シェル用にウェイトを隣接でスムージングする（体本体は触らない）。
    # 毛が「平均化された体表」に追従するのは見た目にも自然。上位4本に絞って正規化する
    # （glTF は JOINTS_0 の4本まで）。W は境界検出のときに読み込み済み。
    for _ in range(8):
        acc = np.zeros_like(W)
        np.add.at(acc, e0, W[e1])
        np.add.at(acc, e1, W[e0])
        W = 0.5 * W + 0.5 * acc / np.maximum(deg, 1.0)[:, None]
    top4 = np.argsort(W, axis=1)[:, -4:]
    Ws = np.zeros_like(W)
    rows = np.arange(nv)[:, None]
    Ws[rows, top4] = W[rows, top4]
    Ws /= np.maximum(Ws.sum(1, keepdims=True), 1e-9)

    made = []
    for li, (t, cutoff) in enumerate(LAYERS, 1):
        sh = body.copy()
        sh.data = body.data.copy()
        sh.name = sh.data.name = f"FurShell{li}"
        bpy.context.scene.collection.objects.link(sh)

        sh.data.vertices.foreach_set("co", to_blender_co(g_t + disp * t).ravel())
        sh.data.update()

        # スムージング済みウェイトを書き込む（上位4本、正規化済み）
        for gi, vg in enumerate(sh.vertex_groups):
            col = Ws[:, gi]
            nz = np.flatnonzero(col > 1e-4)
            vg.remove(list(range(nv)))
            for i in nz:
                vg.add([int(i)], float(col[i]), "REPLACE")

        # 毛の無い面を削除（元の頂点番号を属性に残して、法線の対応を取る）
        bm = bmesh.new()
        bm.from_mesh(sh.data)
        lay = bm.verts.layers.int.new("orig_idx")
        bm.verts.ensure_lookup_table()
        for i, v in enumerate(bm.verts):
            v[lay] = i
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in del_polys], context="FACES")
        bm.to_mesh(sh.data)
        bm.free()
        orig = np.array([a.value for a in sh.data.attributes["orig_idx"].data], dtype=int)

        # 法線は変位後の形から再計算させず、**体の頂点法線をそのまま使う**。
        # 再計算させると房が下の体表と違う向きで照らされ、上側は黒・下側は白の
        # 「色が乗っていない」見た目になる（実機で指摘された）。体と同じ法線なら
        # 房の明るさが真下の毛と一致して馴染む。
        sh.data.normals_split_custom_set_from_vertices(nrm[orig].tolist())

        mat = bpy.data.materials.new(f"FurShell{li}")
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = img
        mat.node_tree.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        bsdf.inputs["Roughness"].default_value = 1.0
        if "Specular IOR Level" in bsdf.inputs:      # 白いテカりを消す
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
        # 裏面は描かない（doubleSided だと反対側の房の裏面が透けて見え、法線が
        # 反転して上側では黒いゴミ・下側では白いゴミに見える。実機で指摘された）
        mat.use_backface_culling = True
        if cutoff is not None:
            # Blender 5.0 の glTF エクスポーターは blend_method を見ず、ノードグラフから
            # alphaMode を決める（search_node_tree.detect_alpha_clip）。テクスチャの Alpha を
            # Math:GREATER_THAN(cutoff) 経由で BSDF Alpha につなぐと MASK + alphaCutoff で出る。
            clip = mat.node_tree.nodes.new("ShaderNodeMath")
            clip.operation = "GREATER_THAN"
            clip.inputs[1].default_value = cutoff
            mat.node_tree.links.new(tex.outputs["Alpha"], clip.inputs[0])
            mat.node_tree.links.new(clip.outputs["Value"], bsdf.inputs["Alpha"])
            mat.blend_method = "CLIP"      # ビューポート表示用（エクスポートには効かない）
            mat.alpha_threshold = cutoff
        # cutoff=None（最内層）はアルファを繋がない = OPAQUE の第二の皮膚
        sh.data.materials.clear()
        sh.data.materials.append(mat)
        made.append(sh.name)
        print(f"  {sh.name}: 伸び {t:.2f} / cutoff {cutoff} / faces {len(sh.data.polygons)}")

    print(f"[P3d] shells: {made} 各 {nv} verts (体と同じウェイト)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
