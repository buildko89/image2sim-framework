"""腹が脚ボーンに吸われていないかを検査する（qa_skin_stretch では検出できない破綻）。

背景: P3-1 のレビューで「右側面で腹が消える」と指摘された。原因は、ヒョウのレストポーズが
歩幅を開いたストーキング姿勢で、畳まれた前脚の骨が腹の下に入り込んでおり、
ボーンヒートが腹の頂点を脚ボーンに割り当てていたこと。腹は脚と一緒に「まとまって」動くので
**辺は裂けない**。qa_skin_stretch.py は全8アニメ PASS のまま見逃した。

**この指標は体型依存であり、普遍的なゲートではない。**
腹が地面すれすれまで垂れ、腹の真下を短い脚の骨が通る koha の体型に対してのみ意味を持つ。
脚が長く腹が高いヒョウ（cat_base）は腹の 58% が脚ボーンに割り当てられているが、
脚が長いぶん腹が振り回されないので視覚的な破綻は起きない。cat_base はこの閾値では
FAIL するが、それは欠陥ではない。**koha の体型のモデルにだけ適用すること。**

    python pipeline_v2/qa_belly_bind.py --glb output_v2/base/p3_koha.glb
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_skin_stretch as q  # noqa: E402

LEG_KEYS = ("upperarm", "forearm", "hand", "finger", "thigh", "calf", "horselink", "foot", "toe")

# 「腹」の範囲は体半幅に対する相対値で取る。絶対値 0.03m にすると、半幅 0.038m しかない
# ヒョウ（cat_base）では内腿まで含んでしまい、基準線が FAIL する。
BELLY_X_FRAC = 0.45    # 正中線から半幅のこの割合までを「腹」とみなす
BELLY_NORMAL_Y = -0.4  # 法線Yがこれ以下 = 腹側

# 閾値の校正（実測値、体半幅に対する相対サンプル）:
#   cat_base.glb   （ヒョウ・脚が長い） 58.4%  ← 体型が違うので FAIL するが欠陥ではない
#   cat_koha9.glb（B-4）             66.8%
#   cat_koha.glb   （B-6）              98.7%  ← 破綻
#   p3_koha 修正前                      99.7%  ← 破綻（右側面で腹が消える）
#   p3_koha 修正後（脚再配置＋腹ボーン） 38.7%  ← 健全
#
# **判定は「脚ボーンへ流れるウェイト総量」で行う。**
# 「左右どちらの脚に偏っているか」も試したが判別しなかった（cat_base 0.58 / 破綻モデル 0.80 /
#  修正後 0.38）。腹の左頂点が左脚のウェイトを持つのは自然だからである。
# 左右差(mm)も修正前後で 28.8 → 25.9 しか動かず判別力が無いので、参考値として出すだけにする
# （Jump はヒョウ自身が左右非対称な踏み切りをするため、そもそも差が出る）。
FAIL_LEG_WEIGHT = 0.50     # 腹のウェイトの半分超が脚に流れていたら FAIL
WARN_ASYMMETRY = 0.020     # 左右差の参考警告 (m)
SAMPLES = 12


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()

    gltf, blob = q.load_glb(Path(a.glb))
    nodes = gltf["nodes"]
    parent = {c: i for i, nd in enumerate(nodes) for c in nd.get("children", [])}
    skin = gltf["skins"][0]
    joints = skin["joints"]
    jnames = [nodes[j].get("name", "") for j in joints]
    is_leg = np.array([any(k in n for k in LEG_KEYS) for n in jnames])
    ibm = np.transpose(q.read_accessor(gltf, blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4),
                       (0, 2, 1))

    V, N, J, W = [], [], [], []
    for nd in nodes:
        if "mesh" not in nd or "skin" not in nd:
            continue
        # 髭（P3-9）と毛シェル（P3-10、体の複製）は腹の検査対象ではない上、
        # 髭の X 幅 ±0.09 は体半幅の 99 百分位を押し広げ、シェルの垂れたスカートは
        # 腹の頂点選択を変えて基準線(40.2%)を 46.0% までずらす（実測）。除外して
        # 「体メッシュそのもののバインド」だけを従来の基準線と比較できるようにする。
        name = nd.get("name", "")
        if "Whiskers" in name or "FurShell" in name or "TailFill" in name:
            continue
        for pr in gltf["meshes"][nd["mesh"]]["primitives"]:
            V.append(q.read_accessor(gltf, blob, pr["attributes"]["POSITION"]).astype(float))
            N.append(q.read_accessor(gltf, blob, pr["attributes"]["NORMAL"]).astype(float))
            J.append(q.read_accessor(gltf, blob, pr["attributes"]["JOINTS_0"]).astype(int))
            W.append(q.read_accessor(gltf, blob, pr["attributes"]["WEIGHTS_0"]).astype(float))
    V, N, J, W = np.vstack(V), np.vstack(N), np.vstack(J), np.vstack(W)

    # ---- 1. 静的: 腹の支配ボーン ----
    half_width = float(np.percentile(np.abs(V[:, 0]), 99))
    belly_x = half_width * BELLY_X_FRAC
    body_len = float(V[:, 2].max() - V[:, 2].min())
    torso_z = (V[:, 2] > -0.25 * body_len) & (V[:, 2] < 0.25 * body_len)  # 尻尾・頭を除いた胴
    belly = (np.abs(V[:, 0]) < belly_x) & (N[:, 1] < BELLY_NORMAL_Y) & torso_z
    print(f"体半幅 {half_width:.4f} m → 腹の範囲 |X| < {belly_x:.4f} m")
    dom = J[np.arange(len(J)), np.argmax(W, axis=1)]
    leg_frac = float(is_leg[dom][belly].mean()) if belly.sum() else 0.0
    # 脚ボーンへ流れているウェイトの総量でも見る
    leg_w = float((W * is_leg[J]).sum(1)[belly].mean()) if belly.sum() else 0.0

    print(f"腹の頂点 {int(belly.sum())} 個（法線Y<{BELLY_NORMAL_Y}, 胴）")
    print(f"  支配ボーンが脚: {leg_frac:.2%}   （参考）")
    print(f"  脚ボーンへのウェイト総量: {leg_w:.2%}   ← 判定に使う（閾値 {FAIL_LEG_WEIGHT:.0%}）")
    if belly.sum():
        bad = np.flatnonzero(belly)[is_leg[dom][belly]]
        if len(bad):
            from collections import Counter
            print("  腹を掴んでいる脚ボーン:",
                  dict(Counter(jnames[d] for d in dom[bad]).most_common(5)))

    # ---- 2. 動的: 左右の腹底の食い違い ----
    rest_local = [q.node_local(nd) for nd in nodes]

    def globals_at(lm):
        out = {}

        def rec(i):
            if i in out:
                return out[i]
            m = lm[i]
            if i in parent:
                m = rec(parent[i]) @ m
            out[i] = m
            return m
        for i in range(len(nodes)):
            rec(i)
        return out

    def skinned(g):
        pal = np.stack([g[j] @ ibm[k] for k, j in enumerate(joints)])
        acc = np.zeros((len(V), 3))
        for c in range(J.shape[1]):
            w = W[:, c][:, None]
            M = pal[J[:, c]]
            acc += w * (np.einsum("nij,nj->ni", M[:, :3, :3], V) + M[:, :3, 3])
        return acc

    # 追跡するのは「レストで定義した腹の頂点集合」そのもの。
    # Z スライスの帯（|X|∈[0.012,0.045]）で測ると足先（|X|≈0.035〜0.040）が混ざり、
    # 歩行で当然に出る左右差を破綻と誤判定する（最初の実装の誤り）。
    bl = belly & (V[:, 0] < -0.25 * belly_x)
    br = belly & (V[:, 0] > 0.25 * belly_x)
    if bl.sum() < 10 or br.sum() < 10:
        print("腹の頂点が足りず、左右差は測れない")
        return 0

    def lr_gap(P):
        return float(P[bl][:, 1].mean() - P[br][:, 1].mean())

    rest_gap = lr_gap(skinned(globals_at(rest_local)))
    print(f"\n腹の頂点 左{int(bl.sum())} / 右{int(br.sum())}")
    print(f"レスト姿勢の左右の腹底差（基準値）: {rest_gap*1000:+.1f} mm")

    anims = []
    worst = 0.0
    for anim in gltf.get("animations", []):
        chans = {}
        for ch in anim["channels"]:
            t = ch["target"]
            if "node" not in t:
                continue
            s = anim["samplers"][ch["sampler"]]
            chans.setdefault(t["node"], {})[t["path"]] = (
                q.read_accessor(gltf, blob, s["input"]).ravel(),
                q.read_accessor(gltf, blob, s["output"]))
        tmax = max((tt[-1] for c in chans.values() for tt, _ in c.values()), default=0.0)
        peak = 0.0
        for si in range(SAMPLES):
            t = tmax * si / max(SAMPLES - 1, 1)
            lm = list(rest_local)
            for ni, paths in chans.items():
                nd = nodes[ni]
                tr = np.array(nd.get("translation", [0, 0, 0]), float)
                ro = np.array(nd.get("rotation", [0, 0, 0, 1]), float)
                sc = np.array(nd.get("scale", [1, 1, 1]), float)
                if "translation" in paths:
                    tr = q.sample_channel(*paths["translation"], t, False)
                if "rotation" in paths:
                    ro = q.sample_channel(*paths["rotation"], t, True)
                if "scale" in paths:
                    sc = q.sample_channel(*paths["scale"], t, False)
                lm[ni] = q.trs_matrix(tr, ro, sc)
            peak = max(peak, abs(lr_gap(skinned(globals_at(lm))) - rest_gap))
        worst = max(worst, peak)
        anims.append({"animation": anim["name"], "max_lr_gap_mm": round(peak * 1000, 1),
                      "note": "warn" if peak > WARN_ASYMMETRY else "ok"})
        flag = "!" if peak > WARN_ASYMMETRY else " "   # cp932 コンソールなので記号は ASCII
        print(f"  {flag} {anim['name']:22} 腹の左右の高さのズレ 最大 {peak*1000:5.1f} mm（参考）")

    verdict = "FAIL" if leg_w > FAIL_LEG_WEIGHT else "PASS"
    print(f"\nOVERALL: {verdict}  (腹のウェイトの {leg_w:.1%} が脚ボーンへ / "
          f"左右差 最大 {worst*1000:.1f} mm)")

    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({
            "glb": a.glb,
            "belly_verts": int(belly.sum()),
            "belly_dominated_by_leg_bones": round(leg_frac, 4),
            "belly_weight_to_leg_bones": round(leg_w, 4),
            "rest_lr_gap_mm": round(rest_gap * 1000, 1),
            "animations": anims,
            "thresholds": {"leg_weight_fail": FAIL_LEG_WEIGHT, "lr_gap_warn_m": WARN_ASYMMETRY},
            "verdict": verdict,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
