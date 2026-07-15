"""P3-15: 尻尾のプルームの透けを構造的に塞ぐ。

プルームは 78 枚のアルファ抜きカード。カードの間が素通しで、後ろから見ると
先端半分が透ける（実機で指摘、1440px で確認）。対処は3段:

1. **不透明の芯**: プルームを中心線へ 45% に縮めた複製を不透明マテリアルで内側に置く。
   体の毛シェルで効いた「第二の皮膚」と同じ原理 — カードの隙間の背景が常に尻尾の色になる。
2. **カードの多重化**: 85% に縮めた複製を重ね、カードを互い違いにして隙間を減らす。
3. **カードを MASK 化**: 元の Koha9Tail は BLEND で、半透明で薄く見える上に
   Godot でソート消えする。Math:GREATER_THAN(0.25) で MASK にする。

縮小は「Y スライスごとの重心へ XZ だけ寄せる」。プルームはほぼ垂直（Y 0.18〜0.33）なので
中心線の近似として十分。複製はウェイトも複製されるのでアニメ追従はそのまま。

  blender --background --python pipeline_v2/p3e_tail_densify_blender.py -- \
    --input output_v2/base/p3_koha9.blend \
    --output-blend output_v2/base/p3_koha9.blend --output-glb output_v2/base/p3_koha9.glb
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np

TUFT_MAT = "Koha9Tail"
MASK_CUTOFF = 0.25
YBIN = 0.012   # 中心線推定の Y スライス幅 [m]（glTF系）


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def find_tuft_object():
    """毛束カードのオブジェクトを探す。体と同居している場合はカードだけの複製を作る。"""
    for ob in bpy.data.objects:
        if ob.type != "MESH" or "FurShell" in ob.name or "TailFill" in ob.name:
            continue
        mats = [m.name for m in ob.data.materials if m]
        if TUFT_MAT not in mats:
            continue
        if mats == [TUFT_MAT]:
            return ob, False
        return ob, True   # 体と同居（マテリアルで面を絞る必要あり）
    raise SystemExit(f"{TUFT_MAT} を持つオブジェクトが見つからない")


def isolate_tuft_copy(src, mixed: bool, name: str):
    """src の複製を作り、毛束カードの面だけ残す。"""
    ob = src.copy()
    ob.data = src.data.copy()
    ob.name = ob.data.name = name
    bpy.context.scene.collection.objects.link(ob)
    if mixed:
        mi = [i for i, m in enumerate(ob.data.materials) if m and m.name == TUFT_MAT][0]
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        drop = [f for f in bm.faces if f.material_index != mi]
        bmesh.ops.delete(bm, geom=drop, context="FACES")
        bm.to_mesh(ob.data)
        bm.free()
    return ob


def shrink_to_centerline(ob, M, scale: float):
    """Y スライスごとの重心へ XZ を scale 倍で寄せる（glTF系で計算）。"""
    nv = len(ob.data.vertices)
    co = np.empty(nv * 3)
    ob.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    M3, Minv3 = M[:3, :3], np.linalg.inv(M[:3, :3])
    w = co @ M3.T + M[:3, 3]
    g = np.stack([w[:, 0], w[:, 2], -w[:, 1]], axis=1)   # gltf (x, y=up, z=fwd)

    ybin = np.round(g[:, 1] / YBIN).astype(int)
    for b in np.unique(ybin):
        sel = ybin == b
        c = g[sel].mean(0)
        g[sel, 0] = c[0] + (g[sel, 0] - c[0]) * scale
        g[sel, 2] = c[2] + (g[sel, 2] - c[2]) * scale

    wb = np.stack([g[:, 0], -g[:, 2], g[:, 1]], axis=1)
    ob.data.vertices.foreach_set("co", ((wb - M[:3, 3]) @ Minv3.T).ravel())
    ob.data.update()


def main() -> int:
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.input)
    if any("TailFill" in o.name for o in bpy.data.objects):
        raise SystemExit("TailFill は既に存在する（二重生成を防ぐため中断）")

    src, mixed = find_tuft_object()
    M = np.array(src.matrix_world)
    print(f"[P3e] 毛束: {src.name} (体と同居: {mixed})")

    # 1. 元の毛束カードを MASK 化（BLEND はソート消え + 半透明で薄い）
    mat = bpy.data.materials[TUFT_MAT]
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    tex = next(n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE")
    for lk in list(mat.node_tree.links):
        if lk.to_node == bsdf and lk.to_socket.name == "Alpha":
            mat.node_tree.links.remove(lk)
    clip = mat.node_tree.nodes.new("ShaderNodeMath")
    clip.operation = "GREATER_THAN"
    clip.inputs[1].default_value = MASK_CUTOFF
    mat.node_tree.links.new(tex.outputs["Alpha"], clip.inputs[0])
    mat.node_tree.links.new(clip.outputs["Value"], bsdf.inputs["Alpha"])
    print(f"[P3e] {TUFT_MAT} -> MASK cutoff {MASK_CUTOFF}")

    # 2. 不透明の芯（45% に縮小、アルファ無し）
    core = isolate_tuft_copy(src, mixed, "TailFillCore")
    shrink_to_centerline(core, M, 0.45)
    cmat = bpy.data.materials.new("TailFillCore")
    cmat.use_nodes = True
    cb = cmat.node_tree.nodes["Principled BSDF"]
    ct = cmat.node_tree.nodes.new("ShaderNodeTexImage")
    ct.image = tex.image
    cmat.node_tree.links.new(ct.outputs["Color"], cb.inputs["Base Color"])
    cb.inputs["Roughness"].default_value = 1.0
    if "Specular IOR Level" in cb.inputs:
        cb.inputs["Specular IOR Level"].default_value = 0.0
    core.data.materials.clear()
    core.data.materials.append(cmat)
    print(f"[P3e] TailFillCore: {len(core.data.vertices)} verts (不透明・45%)")

    # 3. 互い違いのカード（85% に縮小、元と同じ MASK マテリアル）
    mid = isolate_tuft_copy(src, mixed, "TailFillMid")
    shrink_to_centerline(mid, M, 0.85)
    mid.data.materials.clear()
    mid.data.materials.append(mat)
    print(f"[P3e] TailFillMid: {len(mid.data.vertices)} verts (MASK・85%)")

    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
