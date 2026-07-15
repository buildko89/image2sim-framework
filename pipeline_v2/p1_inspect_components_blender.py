"""P1 前提調査 その2: 重複頂点を除いた後の連結成分を分類する。

狙い: 「主外皮（Automatic Weights を通す対象）」と「浮いたパーツ（ウェイト転送で処理する対象）」に
分けられるかを確認する。分けられるなら、B-6 の自作ウェイト（Union-Find + 剛体化）は不要。

  blender --background --python pipeline_v2/p1_inspect_components_blender.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

REPO = Path(r"D:/source/repos/3DModelDevPJ/image2sim-framework")
MESH_GLB = REPO / "input/cat2/koha9_cat.glb"
REPORT = REPO / "output_v2/reports/p1_components.json"


def components(bm):
    seen, comps = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, verts = [v], []
        seen.add(v.index)
        while stack:
            cur = stack.pop()
            verts.append(cur)
            for e in cur.link_edges:
                o = e.other_vert(cur)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        comps.append(verts)
    comps.sort(key=len, reverse=True)
    return comps


def comp_stats(verts) -> dict:
    faces, edges = set(), set()
    for v in verts:
        faces.update(f.index for f in v.link_faces)
        edges.update(e for e in v.link_edges)
    boundary = sum(1 for e in edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in edges if len(e.link_faces) > 2)
    co = [v.co for v in verts]
    lo = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    hi = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    ctr = (lo + hi) / 2
    return {
        "verts": len(verts),
        "faces": len(faces),
        "boundary_edges": boundary,
        "nonmanifold_edges": nonman,
        "closed": boundary == 0 and nonman == 0,
        "center": [round(v, 4) for v in ctr],
        "size": [round(v, 4) for v in (hi - lo)],
    }


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(MESH_GLB))

    out = {}
    for obj in [o for o in bpy.context.scene.objects if o.type == "MESH"]:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()

        comps = components(bm)
        stats = [comp_stats(c) for c in comps]
        out[obj.name] = {
            "verts_after_merge": len(bm.verts),
            "n_components": len(comps),
            "largest": stats[0],
            "others_total_verts": sum(s["verts"] for s in stats[1:]),
            "others": stats[1:],
        }
        bm.free()

        s = out[obj.name]
        print(f"\n[{obj.name}] merge後 {s['verts_after_merge']}頂点 / 成分 {s['n_components']}個")
        L = s["largest"]
        print(f"  最大成分: {L['verts']}頂点 {L['faces']}面  境界辺={L['boundary_edges']} "
              f"非多様体={L['nonmanifold_edges']}  閉じている={L['closed']}")
        print(f"            size={L['size']} center={L['center']}")
        print(f"  残り {s['n_components']-1} 成分 / 計 {s['others_total_verts']}頂点")
        for i, o in enumerate(s["others"][:12]):
            print(f"    #{i+1:2} verts={o['verts']:4} size={o['size']} center={o['center']} "
                  f"closed={o['closed']}")
        if s["n_components"] > 13:
            print(f"    ... 他 {s['n_components']-13} 成分")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nreport -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
