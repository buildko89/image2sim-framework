"""P1 前提調査: koha9_cat.glb の各メッシュが Automatic Weights を通せる状態か測る。

ボーンヒート（Automatic Weights）が落ちる条件は主に3つ:
  1. 非多様体（穴・境界辺・3面以上が共有する辺）
  2. 連結成分が複数（浮いたパーツ）
  3. 重複頂点

B-6 は「毛房の非連結パーツで全滅」したと記録されているが、実際に何がどれだけあるのかは
測られていない。まずそこを確認する。

  blender --background --python pipeline_v2/p1_inspect_mesh_blender.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy

REPO = Path(r"D:/source/repos/3DModelDevPJ/image2sim-framework")
MESH_GLB = REPO / "input/cat2/koha9_cat.glb"
REPORT = REPO / "output_v2/reports/p1_mesh_inspection.json"


def connected_components(bm: bmesh.types.BMesh) -> list[int]:
    seen = set()
    sizes = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, comp = [v], 0
        seen.add(v.index)
        while stack:
            cur = stack.pop()
            comp += 1
            for e in cur.link_edges:
                o = e.other_vert(cur)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)
        sizes.append(comp)
    return sorted(sizes, reverse=True)


def analyse(obj: bpy.types.Object) -> dict:
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()

    boundary = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonmanifold_e = sum(1 for e in bm.edges if len(e.link_faces) > 2)
    wire = sum(1 for e in bm.edges if len(e.link_faces) == 0)
    comps = connected_components(bm)

    # 重複頂点（0.0001m 以内）
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    dup = before - len(bm.verts)

    out = {
        "object": obj.name,
        "verts": before,
        "faces": len(obj.data.polygons),
        "shape_keys": len(obj.data.shape_keys.key_blocks) if obj.data.shape_keys else 0,
        "materials": [m.name for m in obj.data.materials],
        "boundary_edges": boundary,
        "nonmanifold_edges_3plus": nonmanifold_e,
        "wire_edges": wire,
        "duplicate_verts_at_1e-4": dup,
        "connected_components": len(comps),
        "component_sizes_top10": comps[:10],
        "verts_outside_largest_component": before - comps[0] if comps else 0,
    }
    bm.free()
    return out


def main() -> int:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(MESH_GLB))

    results = [analyse(o) for o in bpy.context.scene.objects if o.type == "MESH"]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n" + "=" * 78)
    for r in results:
        print(f"\n[{r['object']}]  verts={r['verts']} faces={r['faces']} "
              f"shape_keys={r['shape_keys']} materials={r['materials']}")
        print(f"  連結成分            : {r['connected_components']}  "
              f"(最大={r['component_sizes_top10'][0] if r['component_sizes_top10'] else 0}, "
              f"それ以外={r['verts_outside_largest_component']}頂点)")
        print(f"  上位10成分のサイズ  : {r['component_sizes_top10']}")
        print(f"  境界辺(穴)          : {r['boundary_edges']}")
        print(f"  非多様体辺(3面以上) : {r['nonmanifold_edges_3plus']}")
        print(f"  ワイヤ辺            : {r['wire_edges']}")
        print(f"  重複頂点(1e-4)      : {r['duplicate_verts_at_1e-4']}")
        ok = (r["connected_components"] == 1 and r["boundary_edges"] == 0
              and r["nonmanifold_edges_3plus"] == 0)
        print(f"  => Automatic Weights: {'そのまま通る見込み' if ok else '前処理が必要'}")
    print("\n" + "=" * 78)
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
