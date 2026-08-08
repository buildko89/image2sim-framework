from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


COMPONENT_SIZES = {
    5120: 1,
    5121: 1,
    5122: 2,
    5123: 2,
    5125: 4,
    5126: 4,
}
TYPE_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="2つのGLBをインデックス順に依存せず意味比較します。")
    parser.add_argument("reference")
    parser.add_argument("candidate")
    parser.add_argument("--report")
    return parser.parse_args()


def read_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"GLBが小さすぎます: {path}")
    magic, version, declared_length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or declared_length != len(data):
        raise ValueError(f"GLBヘッダーが不正です: {path}")
    document: dict[str, Any] | None = None
    binary = b""
    offset = 12
    while offset < len(data):
        chunk_length, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8 : offset + 8 + chunk_length]
        if chunk_type == 0x4E4F534A:
            document = json.loads(chunk.decode("utf-8"))
        elif chunk_type == 0x004E4942:
            binary = chunk
        offset += 8 + chunk_length
    if document is None:
        raise ValueError(f"JSON chunkがありません: {path}")
    return document, binary


def accessor_signature(document: dict[str, Any], binary: bytes, index: int) -> dict[str, Any]:
    accessor = document["accessors"][index]
    if "sparse" in accessor:
        raise ValueError("sparse accessorは比較対象外です。")
    view = document["bufferViews"][accessor["bufferView"]]
    component_size = COMPONENT_SIZES[accessor["componentType"]]
    component_count = TYPE_COMPONENTS[accessor["type"]]
    element_size = component_size * component_count
    stride = int(view.get("byteStride", element_size))
    start = int(view.get("byteOffset", 0)) + int(accessor.get("byteOffset", 0))
    values = b"".join(
        binary[start + item * stride : start + item * stride + element_size]
        for item in range(int(accessor["count"]))
    )
    return {
        "component_type": accessor["componentType"],
        "type": accessor["type"],
        "count": accessor["count"],
        "normalized": bool(accessor.get("normalized", False)),
        "min": accessor.get("min"),
        "max": accessor.get("max"),
        "data_sha256": hashlib.sha256(values).hexdigest(),
    }


def named_items(items: list[dict[str, Any]], category: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        name = str(item.get("name", f"<{category}:{index}>"))
        if name in result:
            raise ValueError(f"{category}名が重複しています: {name}")
        result[name] = item
    return result


def contains_texture_reference(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            key.endswith("Texture") or contains_texture_reference(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(contains_texture_reference(item) for item in value)
    return False


def semantic_snapshot(path: Path) -> dict[str, Any]:
    document, binary = read_glb(path)
    materials = document.get("materials", [])
    meshes = document.get("meshes", [])
    nodes = document.get("nodes", [])

    material_names = [str(item.get("name", f"<material:{index}>")) for index, item in enumerate(materials)]
    mesh_names = [str(item.get("name", f"<mesh:{index}>")) for index, item in enumerate(meshes)]
    node_names = [str(item.get("name", f"<node:{index}>")) for index, item in enumerate(nodes)]
    named_items(materials, "material")
    named_items(meshes, "mesh")
    named_items(nodes, "node")

    mesh_snapshot: dict[str, Any] = {}
    for mesh_index, mesh in enumerate(meshes):
        primitives = []
        for primitive in mesh.get("primitives", []):
            material = materials[primitive["material"]] if "material" in primitive else None
            uses_texture = contains_texture_reference(material)
            primitives.append({
                "mode": primitive.get("mode", 4),
                "material": (
                    material_names[primitive["material"]]
                    if "material" in primitive
                    else None
                ),
                "indices": (
                    accessor_signature(document, binary, primitive["indices"])
                    if "indices" in primitive
                    else None
                ),
                "attributes": {
                    semantic: accessor_signature(document, binary, accessor_index)
                    for semantic, accessor_index in sorted(primitive.get("attributes", {}).items())
                    if not semantic.startswith("TEXCOORD_") or uses_texture
                },
                "targets": [
                    {
                        semantic: accessor_signature(document, binary, accessor_index)
                        for semantic, accessor_index in sorted(target.items())
                    }
                    for target in primitive.get("targets", [])
                ],
                "extras": primitive.get("extras"),
                "extensions": primitive.get("extensions"),
            })
        mesh_snapshot[mesh_names[mesh_index]] = {
            "primitives": primitives,
            "weights": mesh.get("weights"),
            "extras": mesh.get("extras"),
            "extensions": mesh.get("extensions"),
        }

    parents: dict[int, int] = {}
    for parent_index, node in enumerate(nodes):
        for child_index in node.get("children", []):
            parents[child_index] = parent_index
    node_snapshot = {
        node_names[index]: {
            "parent": node_names[parents[index]] if index in parents else None,
            "children": sorted(node_names[child] for child in node.get("children", [])),
            "mesh": mesh_names[node["mesh"]] if "mesh" in node else None,
            "matrix": node.get("matrix"),
            "translation": node.get("translation"),
            "rotation": node.get("rotation"),
            "scale": node.get("scale"),
            "weights": node.get("weights"),
            "extras": node.get("extras"),
            "extensions": node.get("extensions"),
        }
        for index, node in enumerate(nodes)
    }
    scene_snapshot = {
        str(scene.get("name", f"<scene:{index}>")): sorted(node_names[node] for node in scene.get("nodes", []))
        for index, scene in enumerate(document.get("scenes", []))
    }
    return {
        "scene_roots": scene_snapshot,
        "nodes": node_snapshot,
        "meshes": mesh_snapshot,
        "materials": named_items(materials, "material"),
        "animations": document.get("animations", []),
        "skins": document.get("skins", []),
    }


def category_diff(reference: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    reference_keys = set(reference)
    candidate_keys = set(candidate)
    return {
        "only_reference": sorted(reference_keys - candidate_keys),
        "only_candidate": sorted(candidate_keys - reference_keys),
        "changed": sorted(
            key
            for key in reference_keys & candidate_keys
            if reference[key] != candidate[key]
        ),
    }


def main() -> int:
    args = parse_args()
    reference = semantic_snapshot(Path(args.reference))
    candidate = semantic_snapshot(Path(args.candidate))
    categories = {
        name: category_diff(reference[name], candidate[name])
        if isinstance(reference[name], dict) and isinstance(candidate[name], dict)
        else {"changed": reference[name] != candidate[name]}
        for name in reference
    }
    equivalent = reference == candidate
    report = {"equivalent": equivalent, "categories": categories}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    print(text)
    return 0 if equivalent else 1


if __name__ == "__main__":
    raise SystemExit(main())
