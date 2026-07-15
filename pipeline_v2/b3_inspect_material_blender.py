"""B-3 事前調査: cat_base.blend のマテリアル・UV 構成をダンプする。"""
from __future__ import annotations

import json
import sys

import bpy

OUT = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv else "material_dump.json"

info: dict = {"objects": [], "materials": [], "images": []}

for obj in bpy.context.scene.objects:
    entry = {"name": obj.name, "type": obj.type, "parent": obj.parent.name if obj.parent else None}
    if obj.type == "MESH":
        entry["uv_layers"] = [l.name for l in obj.data.uv_layers]
        entry["materials"] = [s.material.name if s.material else None for s in obj.material_slots]
        entry["vertex_groups"] = len(obj.vertex_groups)
    info["objects"].append(entry)

for mat in bpy.data.materials:
    m = {"name": mat.name, "use_nodes": mat.use_nodes, "blend_method": mat.blend_method, "nodes": []}
    if mat.use_nodes:
        for node in mat.node_tree.nodes:
            n = {"type": node.type, "name": node.name}
            if node.type == "TEX_IMAGE" and node.image:
                n["image"] = node.image.name
                n["filepath"] = node.image.filepath
            if node.type == "BSDF_PRINCIPLED":
                n["inputs_linked"] = [i.name for i in node.inputs if i.is_linked]
            m["nodes"].append(n)
        m["links"] = [
            f"{l.from_node.name}.{l.from_socket.name} -> {l.to_node.name}.{l.to_socket.name}"
            for l in mat.node_tree.links
        ]
    info["materials"].append(m)

for img in bpy.data.images:
    info["images"].append({
        "name": img.name,
        "filepath": img.filepath,
        "size": list(img.size),
        "packed": img.packed_file is not None,
    })

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(info, f, indent=2, ensure_ascii=False)
print(f"dumped to {OUT}")
