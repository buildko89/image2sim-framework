"""P3-1: 塗り替えたテクスチャをモデルに適用して GLB を出す。

素材の2枚（本体 RGB / 毛シェル RGBA）は RGB が完全に同一なので、同じ絵を割り当てる。
毛シェル側だけアルファ付きの PNG を使う（毛カードの切り抜きが消えると板になる）。

  blender --background --python pipeline_v2/p3_apply_texture_blender.py -- \
    --input output_v2/base/p2_koha.blend \
    --rgb output_v2/textures/p3_koha_basecolor.png \
    --rgba output_v2/textures/p3_koha_basecolor_alpha.png \
    --output-blend output_v2/base/p3_koha.blend \
    --output-glb output_v2/base/p3_koha.glb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy

MAT_BODY = "Koha9Body"
MAT_FUR = "Koha9Tail"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--rgb", required=True)
    p.add_argument("--rgba", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def swap(mat: bpy.types.Material, path: str) -> int:
    n = 0
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB"
    for node in mat.node_tree.nodes:
        if node.type == "TEX_IMAGE":
            old = node.image.name if node.image else "(none)"
            node.image = img
            print(f"  [{mat.name}] {old} -> {Path(path).name}")
            n += 1
    return n


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)

    swapped = 0
    for name, path in ((MAT_BODY, a.rgb), (MAT_FUR, a.rgba)):
        mat = bpy.data.materials.get(name)
        if mat is None:
            raise SystemExit(f"material not found: {name} "
                             f"(有るのは {[m.name for m in bpy.data.materials]})")
        swapped += swap(mat, str(Path(path).resolve()))
    print(f"[P3] swapped {swapped} image nodes")

    # GLB に埋め込むため画像をパックする
    for img in bpy.data.images:
        if img.source == "FILE" and not img.packed_file:
            img.pack()

    out_blend = Path(a.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    out_glb = Path(a.output_glb)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(out_glb), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {out_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
