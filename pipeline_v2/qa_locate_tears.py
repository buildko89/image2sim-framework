"""破綻した辺がどこにあるかを特定する。qa_skin_stretch が FAIL したときの次の一手。

裂けた辺の頂点について、支配ボーン・レスト座標・所属プリミティブを集計する。

    python pipeline_v2/qa_locate_tears.py --glb output_v2/base/p1a_koha.glb
    python pipeline_v2/qa_locate_tears.py --glb <path> --anim Armature__Jump
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qa_skin_stretch as q  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--anim", help="部分一致。省略時は全アニメを合算")
    a = ap.parse_args()

    gltf, blob = q.load_glb(Path(a.glb))
    nodes = gltf["nodes"]
    parent = {c: i for i, nd in enumerate(nodes) for c in nd.get("children", [])}
    skin = gltf["skins"][0]
    joints = skin["joints"]
    jnames = [nodes[j].get("name", f"joint{k}") for k, j in enumerate(joints)]
    ibm = np.transpose(q.read_accessor(gltf, blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4),
                       (0, 2, 1))

    verts, edges, jnt, wgt, prim_of = [], [], [], [], []
    base = 0
    for nd in nodes:
        if "mesh" not in nd or "skin" not in nd:
            continue
        for pi, prim in enumerate(gltf["meshes"][nd["mesh"]]["primitives"]):
            p = q.read_accessor(gltf, blob, prim["attributes"]["POSITION"]).astype(float)
            j = q.read_accessor(gltf, blob, prim["attributes"]["JOINTS_0"]).astype(int)
            w = q.read_accessor(gltf, blob, prim["attributes"]["WEIGHTS_0"]).astype(float)
            idx = q.read_accessor(gltf, blob, prim["indices"]).ravel().astype(int)
            tri = idx.reshape(-1, 3) + base
            edges.append(np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]))
            verts.append(p); jnt.append(j); wgt.append(w)
            mat = gltf["materials"][prim["material"]]["name"] if "material" in prim else f"prim{pi}"
            prim_of += [mat] * len(p)
            base += len(p)
    verts = np.vstack(verts); jnt = np.vstack(jnt); wgt = np.vstack(wgt)
    edges = np.unique(np.sort(np.vstack(edges), axis=1), axis=0)
    prim_of = np.array(prim_of)

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
        acc = np.zeros((len(verts), 3))
        for c in range(jnt.shape[1]):
            w = wgt[:, c][:, None]
            M = pal[jnt[:, c]]
            acc += w * (np.einsum("nij,nj->ni", M[:, :3, :3], verts) + M[:, :3, 3])
        return acc

    rest_g = globals_at(rest_local)
    rest_pos = skinned(rest_g)
    rest_len = np.linalg.norm(rest_pos[edges[:, 0]] - rest_pos[edges[:, 1]], axis=1)
    live = rest_len > 1e-7

    torn_verts = Counter()
    torn_edge_set = set()
    for anim in gltf.get("animations", []):
        if a.anim and a.anim not in anim["name"].replace("|", "__"):
            continue
        samplers = anim["samplers"]
        chans = {}
        for ch in anim["channels"]:
            t = ch["target"]
            if "node" not in t:
                continue
            s = samplers[ch["sampler"]]
            chans.setdefault(t["node"], {})[t["path"]] = (
                q.read_accessor(gltf, blob, s["input"]).ravel(),
                q.read_accessor(gltf, blob, s["output"]))
        tmax = max((tt[-1] for c in chans.values() for tt, _ in c.values()), default=0.0)

        for si in range(q.SAMPLES):
            t = tmax * si / max(q.SAMPLES - 1, 1)
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
            pos = skinned(globals_at(lm))
            ln = np.linalg.norm(pos[edges[:, 0]] - pos[edges[:, 1]], axis=1)
            ratio = np.where(live, ln / np.where(live, rest_len, 1), 1.0)
            for ei in np.flatnonzero(ratio > q.STRETCH_FAIL):
                torn_edge_set.add(int(ei))
                torn_verts[int(edges[ei, 0])] += 1
                torn_verts[int(edges[ei, 1])] += 1

    if not torn_verts:
        print("裂けた辺なし。")
        return 0

    vs = np.array(sorted(torn_verts))
    print(f"裂けた辺 {len(torn_edge_set)} / {len(edges)}  関与頂点 {len(vs)}\n")

    print("プリミティブ（マテリアル）別:")
    for name, n in Counter(prim_of[vs]).most_common():
        tot = int((prim_of == name).sum())
        print(f"  {name:16} {n:5} / {tot:5} 頂点 ({n/tot:.2%})")

    print("\n支配ボーン別（ウェイト最大のボーン）:")
    dom = jnt[vs, np.argmax(wgt[vs], axis=1)]
    for j, n in Counter(dom.tolist()).most_common(12):
        print(f"  {jnames[j]:24} {n:5} 頂点")

    # glTF は Y-up・-Z 前方。この猫は +Z 側に頭、-Z 側に尻尾が来る。
    print("\nレスト座標の範囲（glTF系 X=左右 Y=上下 Z=前後）:")
    p = rest_pos[vs]
    for i, ax in enumerate(("X 左右", "Y 上下", "Z 前後")):
        print(f"  {ax}: {p[:,i].min():+.3f} .. {p[:,i].max():+.3f}   (全体 "
              f"{rest_pos[:,i].min():+.3f} .. {rest_pos[:,i].max():+.3f})")

    print("\n最も多く裂けた頂点 上位10:")
    for vi, c in torn_verts.most_common(10):
        k = int(np.argmax(wgt[vi]))
        print(f"  v{vi:5} x{c:3}回  {prim_of[vi]:16} 支配={jnames[jnt[vi, k]]:22} "
              f"w={wgt[vi, k]:.2f}  rest={np.round(rest_pos[vi], 3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
