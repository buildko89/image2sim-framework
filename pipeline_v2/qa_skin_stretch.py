"""スキニング破綻の自動検出（GLB を直接読む。Blender も Godot も不要）。

各アニメーションの各サンプル時刻でリニアブレンドスキニングを再現し、
メッシュの辺がレスト時に対してどれだけ伸縮したかを測る。
辺が極端に伸びる = 隣り合う頂点が別々のボーンに引き裂かれている、が検出できる。

使い方:
    python pipeline_v2/qa_skin_stretch.py --glb output_v2/base/cat_koha.glb
    python pipeline_v2/qa_skin_stretch.py --glb <path> --json output_v2/reports/qa_skin.json

判定: max_stretch > STRETCH_FAIL の辺が1本でもあれば FAIL。
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

import numpy as np

# 単純な「最大伸び率」は使えない。毛カードの極小な辺（cat_base は辺の18%が0.5mm未満）が
# 比を跳ね上げるため、無加工の元アセットですら最大 x14 を記録する。
# そこで「閾値を超えた辺が全体の何割か」で判定する。実測値:
#   cat_base (無加工ヒョウ)     0.05-0.14%  ← 正常なプロのスキニング
#   cat_koha9 (B-4)          0.04-0.19%  ← 正常。毛カードにわずかな破綻
#   cat_koha (B-6)              1.37-3.94%  ← 破綻。前脚が引き裂かれている
#
# P3-13 から毛シェル（FurShell*）は皮膚と別の閾値で判定する。シェルは体の複製を
# 法線方向へ膨らませたアルファ房で、ウェイト境界では房が体より先に開く。房の伸びは
# 皮膚の裂けと違い輪郭のほつれにしか見えない（Jump の 1440px キャプチャで確認）。
# 皮膚の閾値・判定は従来のまま（壊れた cat_koha B-6 は皮膚 1.37〜3.94% で今も FAIL する）。
STRETCH_FAIL = 3.0      # レスト長の何倍で「引き裂かれた辺」とみなすか
FAIL_FRACTION = 0.005   # 皮膚: 破綻した辺が 0.5% を超えたら FAIL
FUR_FAIL_FRACTION = 0.010   # 毛シェル: 1.0% を超えたら FAIL
SAMPLES = 12            # 1アニメあたりのサンプル数


# ---------- GLB パース ----------

def load_glb(path: Path):
    data = path.read_bytes()
    assert data[:4] == b"glTF", "not a GLB"
    off, chunks = 12, {}
    while off < len(data):
        clen, ctype = struct.unpack_from("<II", data, off)
        chunks[ctype] = data[off + 8: off + 8 + clen]
        off += 8 + clen + (-clen % 4)
    gltf = json.loads(chunks[0x4E4F534A])
    return gltf, chunks[0x004E4942]


COMP = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_accessor(gltf, bin_blob, index):
    acc = gltf["accessors"][index]
    n = NCOMP[acc["type"]]
    dtype = np.dtype(COMP[acc["componentType"]]).newbyteorder("<")
    bv = gltf["bufferViews"][acc["bufferView"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (dtype.itemsize * n)
    if stride == dtype.itemsize * n:
        buf = np.frombuffer(bin_blob, dtype=dtype, count=acc["count"] * n, offset=start)
        return buf.reshape(acc["count"], n)
    rows = [np.frombuffer(bin_blob, dtype=dtype, count=n, offset=start + i * stride)
            for i in range(acc["count"])]
    return np.stack(rows)


# ---------- TRS / 行列 ----------

def trs_matrix(t, r, s):
    x, y, z, w = r
    rot = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    m = np.eye(4)
    m[:3, :3] = rot * np.asarray(s)
    m[:3, 3] = t
    return m


def node_local(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape(4, 4).T
    return trs_matrix(node.get("translation", [0, 0, 0]),
                      node.get("rotation", [0, 0, 0, 1]),
                      node.get("scale", [1, 1, 1]))


def slerp(a, b, u):
    d = float(np.dot(a, b))
    if d < 0:
        b, d = -b, -d
    if d > 0.9995:
        return a + u * (b - a)
    th = np.arccos(np.clip(d, -1, 1))
    return (np.sin((1 - u) * th) * a + np.sin(u * th) * b) / np.sin(th)


def sample_channel(times, values, t, is_quat):
    if t <= times[0]:
        return values[0]
    if t >= times[-1]:
        return values[-1]
    i = int(np.searchsorted(times, t)) - 1
    u = (t - times[i]) / (times[i + 1] - times[i])
    if is_quat:
        return slerp(values[i], values[i + 1], u)
    return values[i] * (1 - u) + values[i + 1] * u


# ---------- 本体 ----------

def analyse(glb_path: Path):
    gltf, blob = load_glb(glb_path)
    nodes = gltf["nodes"]
    parent = {}
    for i, nd in enumerate(nodes):
        for c in nd.get("children", []):
            parent[c] = i

    skin = gltf["skins"][0]
    joints = skin["joints"]
    ibm = read_accessor(gltf, blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4)
    ibm = np.transpose(ibm, (0, 2, 1))  # column-major -> row-major
    jslot = {n: k for k, n in enumerate(joints)}

    # メッシュ（スキン付きノードのメッシュを全部集める）
    verts, edges, jnt, wgt = [], [], [], []
    fur_flags = []   # 頂点ごと: FurShell 由来か
    base = 0
    for nd in nodes:
        if "mesh" not in nd or "skin" not in nd:
            continue
        is_fur = ("FurShell" in nd.get("name", "")) or ("TailFill" in nd.get("name", ""))
        for prim in gltf["meshes"][nd["mesh"]]["primitives"]:
            p = read_accessor(gltf, blob, prim["attributes"]["POSITION"]).astype(float)
            j = read_accessor(gltf, blob, prim["attributes"]["JOINTS_0"]).astype(int)
            w = read_accessor(gltf, blob, prim["attributes"]["WEIGHTS_0"]).astype(float)
            idx = read_accessor(gltf, blob, prim["indices"]).ravel().astype(int)
            tri = idx.reshape(-1, 3) + base
            e = np.vstack([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
            verts.append(p); jnt.append(j); wgt.append(w); edges.append(e)
            fur_flags.append(np.full(len(p), is_fur))
            base += len(p)
    verts = np.vstack(verts); jnt = np.vstack(jnt); wgt = np.vstack(wgt)
    edges = np.unique(np.sort(np.vstack(edges), axis=1), axis=0)
    vert_fur = np.concatenate(fur_flags)
    edge_fur = vert_fur[edges[:, 0]]   # 辺はメッシュをまたがないので片端で判定できる
    n_skin, n_fur = int((~edge_fur).sum()), int(edge_fur.sum())

    def globals_at(local_mats):
        out = {}

        def resolve(i):
            if i in out:
                return out[i]
            m = local_mats[i]
            if i in parent:
                m = resolve(parent[i]) @ m
            out[i] = m
            return m
        for i in range(len(nodes)):
            resolve(i)
        return out

    rest_local = [node_local(nd) for nd in nodes]
    rest_g = globals_at(rest_local)

    def skinned(gmats):
        pal = np.stack([gmats[j] @ ibm[k] for k, j in enumerate(joints)])
        acc = np.zeros((len(verts), 3))
        for c in range(jnt.shape[1]):
            w = wgt[:, c][:, None]
            if not np.any(w):
                continue
            M = pal[jnt[:, c]]
            acc += w * (np.einsum("nij,nj->ni", M[:, :3, :3], verts) + M[:, :3, 3])
        return acc

    rest_pos = skinned(rest_g)
    rest_len = np.linalg.norm(rest_pos[edges[:, 0]] - rest_pos[edges[:, 1]], axis=1)
    live = rest_len > 1e-7

    results = []
    for anim in gltf.get("animations", []):
        samplers = anim["samplers"]
        chans = {}
        for ch in anim["channels"]:
            tgt = ch["target"]
            if "node" not in tgt:
                continue
            s = samplers[ch["sampler"]]
            times = read_accessor(gltf, blob, s["input"]).ravel()
            vals = read_accessor(gltf, blob, s["output"])
            chans.setdefault(tgt["node"], {})[tgt["path"]] = (times, vals)
        tmax = max((t[-1] for c in chans.values() for t, _ in c.values()), default=0.0)

        worst = 0.0
        worst_t = 0.0
        bad_edges = set()
        for si in range(SAMPLES):
            t = tmax * si / max(SAMPLES - 1, 1)
            lm = list(rest_local)
            for ni, paths in chans.items():
                nd = nodes[ni]
                tr = np.array(nd.get("translation", [0, 0, 0]), float)
                ro = np.array(nd.get("rotation", [0, 0, 0, 1]), float)
                sc = np.array(nd.get("scale", [1, 1, 1]), float)
                if "translation" in paths:
                    tr = sample_channel(*paths["translation"], t, False)
                if "rotation" in paths:
                    ro = sample_channel(*paths["rotation"], t, True)
                if "scale" in paths:
                    sc = sample_channel(*paths["scale"], t, False)
                lm[ni] = trs_matrix(tr, ro, sc)
            pos = skinned(globals_at(lm))
            ln = np.linalg.norm(pos[edges[:, 0]] - pos[edges[:, 1]], axis=1)
            ratio = np.where(live, ln / np.where(live, rest_len, 1), 1.0)
            m = float(ratio.max())
            if m > worst:
                worst, worst_t = m, float(t)
            bad_edges.update(np.flatnonzero(ratio > STRETCH_FAIL).tolist())

        bad = np.array(sorted(bad_edges), dtype=int)
        bad_fur = edge_fur[bad] if len(bad) else np.zeros(0, bool)
        skin_frac = float((~bad_fur).sum()) / max(n_skin, 1)
        fur_frac = float(bad_fur.sum()) / max(n_fur, 1)
        verdict = "FAIL" if (skin_frac > FAIL_FRACTION or fur_frac > FUR_FAIL_FRACTION) else "PASS"
        results.append({
            "animation": anim.get("name", "?"),
            "max_stretch": round(worst, 2),
            "at_time": round(worst_t, 3),
            "torn_edges": len(bad_edges),
            "torn_fraction": round(len(bad_edges) / len(edges), 5),
            "skin_torn_fraction": round(skin_frac, 5),
            "fur_torn_fraction": round(fur_frac, 5),
            "verdict": verdict,
        })
    return {
        "glb": str(glb_path),
        "vertices": int(len(verts)),
        "edges": int(len(edges)),
        "skin_edges": n_skin,
        "fur_edges": n_fur,
        "stretch_threshold": STRETCH_FAIL,
        "fail_fraction": FAIL_FRACTION,
        "fur_fail_fraction": FUR_FAIL_FRACTION,
        "animations": results,
        "verdict": "FAIL" if any(r["verdict"] == "FAIL" for r in results) else "PASS",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--json")
    a = ap.parse_args()

    rep = analyse(Path(a.glb))
    print(f"{rep['glb']}  verts={rep['vertices']} edges={rep['edges']} "
          f"(skin {rep['skin_edges']} / fur {rep['fur_edges']})  torn if stretch>x{rep['stretch_threshold']}, "
          f"fail if skin>{rep['fail_fraction']:.1%} or fur>{rep['fur_fail_fraction']:.1%}")
    for r in rep["animations"]:
        print(f"  {r['verdict']:4}  {r['animation']:22} skin={r['skin_torn_fraction']:7.3%}"
              f"  fur={r['fur_torn_fraction']:7.3%}  ({r['torn_edges']:4} edges)"
              f"  max_stretch=x{r['max_stretch']}")
    print(f"OVERALL: {rep['verdict']}")
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps(rep, indent=2), encoding="utf-8")
    return 0 if rep["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
