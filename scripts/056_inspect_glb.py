from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect GLB materials, meshes, skins, and animation target paths.")
    parser.add_argument("input", help="Input GLB path.")
    parser.add_argument("--report", help="Optional JSON report path.")
    return parser.parse_args()


def read_glb_json(glb_path: Path) -> dict[str, Any]:
    data = glb_path.read_bytes()
    if len(data) < 20:
        raise ValueError(f"GLB is too small: {glb_path}")
    magic, version, _length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError(f"Unsupported GLB header: {glb_path}")
    chunk_length, chunk_type = struct.unpack_from("<II", data, 12)
    if chunk_type != 0x4E4F534A:
        raise ValueError(f"First GLB chunk is not JSON: {glb_path}")
    return json.loads(data[20 : 20 + chunk_length].decode("utf-8"))


def summarize(gltf: dict[str, Any]) -> dict[str, Any]:
    materials = []
    for index, material in enumerate(gltf.get("materials", [])):
        pbr = material.get("pbrMetallicRoughness", {})
        materials.append(
            {
                "index": index,
                "name": material.get("name"),
                "base_color_factor": pbr.get("baseColorFactor"),
                "has_base_color_texture": "baseColorTexture" in pbr,
            }
        )

    meshes = []
    for index, mesh in enumerate(gltf.get("meshes", [])):
        primitives = []
        for primitive in mesh.get("primitives", []):
            primitives.append(
                {
                    "material": primitive.get("material"),
                    "attributes": sorted((primitive.get("attributes") or {}).keys()),
                    "targets_count": len(primitive.get("targets", [])),
                }
            )
        meshes.append({"index": index, "name": mesh.get("name"), "primitive_count": len(primitives), "primitives": primitives})

    animations = []
    for index, animation in enumerate(gltf.get("animations", [])):
        samplers = animation.get("samplers", [])
        channels = animation.get("channels", [])
        target_paths = sorted({(channel.get("target") or {}).get("path") for channel in channels})
        animations.append(
            {
                "index": index,
                "name": animation.get("name"),
                "sampler_count": len(samplers),
                "channel_count": len(channels),
                "target_paths": target_paths,
            }
        )

    return {
        "asset": gltf.get("asset", {}),
        "material_count": len(materials),
        "mesh_count": len(meshes),
        "skin_count": len(gltf.get("skins", [])),
        "animation_count": len(animations),
        "materials": materials,
        "meshes": meshes,
        "animations": animations,
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    summary = summarize(read_glb_json(input_path))
    text = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
