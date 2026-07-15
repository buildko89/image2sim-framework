"""B-3 v2: Generate Calico Texture (Blender CLI script)

cat_base.blend を開き、パレット (config/cat_color_palette.yaml) の色で
三毛柄シェーダを構築し、UV Channel0 に EMIT ベイクして Diffuse を生成する。

v2 の柄設計（参照: png/koha1-4.png = koha9_cat 理想レンダー）:
  - 体: 白優勢。大きめ・少数・ソフト輪郭のオレンジ斑（中心は orange_deep）
  - 背骨頂部: 小さな黒斑
  - 尻尾: tail_tan / tail_brown の縞ミックス（白斑なし）
    → 頂点グループ bone016-020 から頂点カラーマスクを生成して分離
  - 頭部: 暗色キャップ（bip01_head + bone001-015、上側のみ）、マズルは白
  - 耳 (bone005/007/014/015): 暗色

使用方法:
  blender --background output_v2/base/cat_base.blend \
    --python pipeline_v2/b3_generate_calico_texture_blender.py -- \
    --palette config/cat_color_palette.yaml \
    --output-texture output_v2/textures/cat_calico_diffuse.png \
    --output-blend output_v2/base/cat_calico.blend \
    --output-glb output_v2/base/cat_calico.glb \
    --report output_v2/reports/b3_generate_calico_texture.json \
    --resolution 2048
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

MESH_NAME = "Leopard_Hybrid"
UV_LAYER = "Channel0"
MASK_ATTR = "CalicoMask"

TAIL_GROUPS = [f"bone{i:03d}" for i in range(16, 21)]
HEAD_GROUPS = ["bip01_head"] + [f"bone{i:03d}" for i in range(1, 16)]
EAR_GROUPS = ["bone005", "bone007", "bone014", "bone015"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bake calico texture onto base cat model (v2).")
    parser.add_argument("--palette", required=True)
    parser.add_argument("--output-texture", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--resolution", type=int, default=2048)
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []
    return parser.parse_args(argv)


def load_palette(path: str) -> dict[str, tuple[float, float, float]]:
    """YAML からパレットを読む（PyYAML が Blender に無い場合に備えた最小パーサ）"""
    try:
        import yaml
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        return {c["name"]: tuple(c["rgb"]) for c in data["palette"]}
    except ModuleNotFoundError:
        colors: dict[str, tuple[float, float, float]] = {}
        name = None
        rgb: list[float] = []
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("- name:"):
                if name and len(rgb) == 3:
                    colors[name] = tuple(rgb)
                name = s.split(":", 1)[1].strip()
                rgb = []
            elif s.startswith("- ") and name is not None and len(rgb) < 3:
                try:
                    rgb.append(float(s[2:]))
                except ValueError:
                    pass
            elif s.startswith("usage:") and name and len(rgb) == 3:
                colors[name] = tuple(rgb)
        if name and len(rgb) == 3:
            colors[name] = tuple(rgb)
        return colors


def srgb_to_linear(c: float) -> float:
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def lin(rgb: tuple[float, float, float]) -> tuple[float, float, float, float]:
    """sRGB(0-1) → リニア + アルファ。ノードの色入力はリニア前提。"""
    return (srgb_to_linear(rgb[0]), srgb_to_linear(rgb[1]), srgb_to_linear(rgb[2]), 1.0)


def build_mask_attribute(obj: bpy.types.Object) -> dict:
    """頂点グループから R=尻尾, G=頭, B=耳 の頂点カラーマスクを作る"""
    me = obj.data
    group_index = {g.name: g.index for g in obj.vertex_groups}

    def weight_sum(v, names) -> float:
        idx = {group_index[n] for n in names if n in group_index}
        return min(1.0, sum(g.weight for g in v.groups if g.group in idx))

    attr = me.color_attributes.get(MASK_ATTR)
    if attr is None:
        attr = me.color_attributes.new(name=MASK_ATTR, type="FLOAT_COLOR", domain="POINT")

    counts = {"tail": 0, "head": 0, "ear": 0}
    for v in me.vertices:
        r = weight_sum(v, TAIL_GROUPS)
        g = weight_sum(v, HEAD_GROUPS)
        b = weight_sum(v, EAR_GROUPS)
        attr.data[v.index].color = (r, g, b, 1.0)
        counts["tail"] += r > 0.5
        counts["head"] += g > 0.5
        counts["ear"] += b > 0.5
    print(f"  Mask verts: tail={counts['tail']} head={counts['head']} ear={counts['ear']}")
    if not all(counts.values()):
        raise RuntimeError(f"mask generation failed: {counts}")
    return counts


def build_bake_material(palette: dict, bake_image: bpy.types.Image) -> bpy.types.Material:
    mat = bpy.data.materials.new("CalicoBake")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    def node(type_: str, x: float, y: float, **props):
        n = nt.nodes.new(type_)
        n.location = (x, y)
        for k, v in props.items():
            setattr(n, k, v)
        return n

    link = nt.links.new

    def soft_threshold(value_out, center: float, width: float, x: float, y: float):
        """smoothstep でソフトな閾値マスクを作る"""
        m = node("ShaderNodeMapRange", x, y)
        m.interpolation_type = "SMOOTHSTEP"
        m.inputs["From Min"].default_value = center - width
        m.inputs["From Max"].default_value = center + width
        link(value_out, m.inputs["Value"])
        return m.outputs["Result"]

    def mix_rgba(x: float, y: float, blend="MIX"):
        m = node("ShaderNodeMix", x, y, data_type="RGBA")
        m.blend_type = blend
        return m

    coord = node("ShaderNodeTexCoord", -1600, 0)
    sep = node("ShaderNodeSeparateXYZ", -1400, 0)
    link(coord.outputs["Generated"], sep.inputs["Vector"])

    # 頂点カラーマスク (R=尻尾, G=頭, B=耳)
    attr = node("ShaderNodeAttribute", -1600, 400, attribute_name=MASK_ATTR)
    mask = node("ShaderNodeSeparateColor", -1400, 400)
    link(attr.outputs["Color"], mask.inputs["Color"])

    # === 体の柄 ===
    # 高さマスク: 下半身は白。境界はノイズで揺らす
    edge_noise = node("ShaderNodeTexNoise", -1400, 200)
    edge_noise.inputs["Scale"].default_value = 4.0
    link(coord.outputs["Generated"], edge_noise.inputs["Vector"])
    height_base = node("ShaderNodeMath", -1200, 250, operation="MULTIPLY_ADD")
    height_base.inputs[1].default_value = 0.12
    height_base.inputs[2].default_value = -0.06
    link(edge_noise.outputs["Fac"], height_base.inputs[0])
    height_shift = node("ShaderNodeMath", -1050, 250, operation="ADD")
    link(sep.outputs["Z"], height_shift.inputs[0])
    link(height_base.outputs["Value"], height_shift.inputs[1])
    height_mask = soft_threshold(height_shift.outputs["Value"], 0.45, 0.06, -900, 250)

    # オレンジ斑: 少数・大きめ・ソフト輪郭
    patch1 = node("ShaderNodeTexNoise", -1200, -200)
    patch1.inputs["Scale"].default_value = 1.6
    patch1.inputs["Detail"].default_value = 2.0
    patch1.inputs["Roughness"].default_value = 0.5
    link(coord.outputs["Generated"], patch1.inputs["Vector"])
    orange_soft = soft_threshold(patch1.outputs["Fac"], 0.545, 0.03, -900, -200)
    orange_mask = node("ShaderNodeMath", -700, -100, operation="MULTIPLY")
    link(height_mask, orange_mask.inputs[0])
    link(orange_soft, orange_mask.inputs[1])

    # 斑の中心を濃く (orange_deep)
    deep_soft = soft_threshold(patch1.outputs["Fac"], 0.615, 0.04, -900, -350)
    deep_mask = node("ShaderNodeMath", -700, -300, operation="MULTIPLY")
    link(height_mask, deep_mask.inputs[0])
    link(deep_soft, deep_mask.inputs[1])

    # 背骨頂部の小さな黒斑
    spine_noise = node("ShaderNodeTexNoise", -1200, -550)
    spine_noise.inputs["Scale"].default_value = 2.6
    spine_noise.inputs["Detail"].default_value = 2.0
    spine_noise.noise_dimensions = "4D"
    spine_noise.inputs["W"].default_value = 11.7
    link(coord.outputs["Generated"], spine_noise.inputs["Vector"])
    spine_soft = soft_threshold(spine_noise.outputs["Fac"], 0.68, 0.03, -900, -550)
    spine_top = soft_threshold(sep.outputs["Z"], 0.72, 0.06, -900, -700)
    spine_mask3 = node("ShaderNodeMath", -700, -550, operation="MULTIPLY")
    link(spine_soft, spine_mask3.inputs[0])
    link(spine_top, spine_mask3.inputs[1])

    # 白 → オレンジ → 濃オレンジ → 黒斑
    mix_orange = mix_rgba(-450, 0)
    mix_orange.inputs[6].default_value = lin(palette["white"])
    mix_orange.inputs[7].default_value = lin(palette["orange"])
    link(orange_mask.outputs["Value"], mix_orange.inputs["Factor"])

    mix_deep = mix_rgba(-300, 0)
    mix_deep.inputs[7].default_value = lin(palette["orange_deep"])
    link(mix_orange.outputs[2], mix_deep.inputs[6])
    link(deep_mask.outputs["Value"], mix_deep.inputs["Factor"])

    mix_spine = mix_rgba(-150, 0)
    mix_spine.inputs[7].default_value = lin(palette["black"])
    link(mix_deep.outputs[2], mix_spine.inputs[6])
    link(spine_mask3.outputs["Value"], mix_spine.inputs["Factor"])

    # === 尻尾: tan/brown の縞ミックス ===
    tail_noise = node("ShaderNodeTexNoise", -450, -700)
    tail_noise.inputs["Scale"].default_value = 7.0
    tail_noise.inputs["Detail"].default_value = 4.0
    link(coord.outputs["Generated"], tail_noise.inputs["Vector"])
    tail_fac = soft_threshold(tail_noise.outputs["Fac"], 0.5, 0.12, -250, -700)
    tail_color = mix_rgba(-100, -600)
    tail_color.inputs[6].default_value = lin(palette["tail_tan"])
    tail_color.inputs[7].default_value = lin(palette["tail_brown"])
    link(tail_fac, tail_color.inputs["Factor"])

    mix_tail = mix_rgba(50, 0)
    link(mix_spine.outputs[2], mix_tail.inputs[6])
    link(tail_color.outputs[2], mix_tail.inputs[7])
    link(mask.outputs["Red"], mix_tail.inputs["Factor"])

    # === 頭部キャップ: 上側のみ暗色+オレンジ混じり、マズルは白のまま ===
    cap_height = soft_threshold(sep.outputs["Z"], 0.86, 0.03, -250, 500)
    cap_mask = node("ShaderNodeMath", -100, 450, operation="MULTIPLY")
    link(mask.outputs["Green"], cap_mask.inputs[0])
    link(cap_height, cap_mask.inputs[1])

    cap_noise = node("ShaderNodeTexNoise", -250, 650)
    cap_noise.inputs["Scale"].default_value = 6.0
    link(coord.outputs["Generated"], cap_noise.inputs["Vector"])
    cap_fac = soft_threshold(cap_noise.outputs["Fac"], 0.55, 0.05, -100, 650)
    cap_color = mix_rgba(50, 550)
    cap_color.inputs[6].default_value = lin(palette["black"])
    cap_color.inputs[7].default_value = lin(palette["orange_deep"])
    link(cap_fac, cap_color.inputs["Factor"])

    mix_cap = mix_rgba(200, 0)
    link(mix_tail.outputs[2], mix_cap.inputs[6])
    link(cap_color.outputs[2], mix_cap.inputs[7])
    link(cap_mask.outputs["Value"], mix_cap.inputs["Factor"])

    # === 耳: 暗色 ===
    mix_ear = mix_rgba(350, 0)
    mix_ear.inputs[7].default_value = lin(palette["black"])
    link(mix_cap.outputs[2], mix_ear.inputs[6])
    link(mask.outputs["Blue"], mix_ear.inputs["Factor"])

    # === 毛の微細な明度ゆらぎ ===
    fur_noise = node("ShaderNodeTexNoise", 350, -400)
    fur_noise.inputs["Scale"].default_value = 60.0
    fur_noise.inputs["Detail"].default_value = 6.0
    link(coord.outputs["Generated"], fur_noise.inputs["Vector"])
    fur_range = node("ShaderNodeMapRange", 500, -400)
    fur_range.inputs["To Min"].default_value = 0.93
    fur_range.inputs["To Max"].default_value = 1.04
    link(fur_noise.outputs["Fac"], fur_range.inputs["Value"])
    gray = node("ShaderNodeCombineColor", 500, -200)
    link(fur_range.outputs["Result"], gray.inputs["Red"])
    link(fur_range.outputs["Result"], gray.inputs["Green"])
    link(fur_range.outputs["Result"], gray.inputs["Blue"])
    fur_mult = mix_rgba(650, 0, blend="MULTIPLY")
    fur_mult.inputs["Factor"].default_value = 1.0
    link(mix_ear.outputs[2], fur_mult.inputs[6])
    link(gray.outputs["Color"], fur_mult.inputs[7])

    # === Emission → 出力（EMIT ベイク用） ===
    emit = node("ShaderNodeEmission", 850, 0)
    link(fur_mult.outputs[2], emit.inputs["Color"])
    out = node("ShaderNodeOutputMaterial", 1050, 0)
    link(emit.outputs["Emission"], out.inputs["Surface"])

    # ベイク先イメージノード（アクティブにしておく）
    tgt = node("ShaderNodeTexImage", 850, -300)
    tgt.image = bake_image
    for n in nt.nodes:
        n.select = False
    tgt.select = True
    nt.nodes.active = tgt

    return mat


def main() -> int:
    args = parse_args()
    palette = load_palette(args.palette)
    print(f"Palette: { {k: [round(v,3) for v in rgb] for k, rgb in palette.items()} }")
    required = {"white", "orange", "orange_deep", "black", "tail_tan", "tail_brown"}
    missing = required - palette.keys()
    if missing:
        print(f"ERROR: palette missing colors: {missing}")
        return 1

    obj = bpy.data.objects.get(MESH_NAME)
    if obj is None:
        print(f"ERROR: mesh '{MESH_NAME}' not found")
        return 1

    uv = obj.data.uv_layers.get(UV_LAYER)
    if uv is None:
        print(f"ERROR: UV layer '{UV_LAYER}' not found")
        return 1
    obj.data.uv_layers.active = uv
    uv.active_render = True

    print(f"\n[Step 0] Building vertex-group masks (tail/head/ear) ...")
    mask_counts = build_mask_attribute(obj)

    res = args.resolution
    bake_image = bpy.data.images.new("cat_calico_diffuse", width=res, height=res, alpha=False)
    bake_image.colorspace_settings.name = "sRGB"

    original_mat = obj.material_slots[0].material
    bake_mat = build_bake_material(palette, bake_image)
    obj.material_slots[0].material = bake_mat

    print(f"\n[Step 1] Baking calico pattern to {res}x{res} ...")
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="EMIT", margin=8)
    print("  Bake done")

    tex_path = Path(args.output_texture)
    tex_path.parent.mkdir(parents=True, exist_ok=True)
    bake_image.filepath_raw = str(tex_path)
    bake_image.file_format = "PNG"
    bake_image.save()
    print(f"  Saved texture: {tex_path}")

    print(f"\n[Step 2] Rewiring original material ...")
    obj.material_slots[0].material = original_mat
    nt = original_mat.node_tree
    principled = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for l in list(nt.links):
        if l.to_node == principled and l.to_socket.name == "Emission Color":
            nt.links.remove(l)
    if "Emission Strength" in principled.inputs:
        principled.inputs["Emission Strength"].default_value = 0.0
    for l in nt.links:
        if l.to_node == principled and l.to_socket.name == "Base Color":
            if l.from_node.type == "TEX_IMAGE":
                l.from_node.image = bake_image
    bake_image.pack()
    bpy.data.materials.remove(bake_mat)

    print(f"\n[Step 3] Saving blend + exporting GLB ...")
    out_blend = Path(args.output_blend)
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"  Saved: {out_blend}")

    out_glb = Path(args.output_glb)
    out_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(
        filepath=str(out_glb),
        export_format="GLB",
        use_selection=True,
        export_animation_mode="ACTIONS",
    )
    print(f"  Exported: {out_glb}")

    report = {
        "task": "B-3 v2: Generate Calico Texture",
        "reference_images": ["png/koha1.png", "png/koha2.png", "png/koha3.png", "png/koha4.png"],
        "palette": {k: list(v) for k, v in palette.items()},
        "resolution": res,
        "mask_vertex_counts": {k: int(v) for k, v in mask_counts.items()},
        "outputs": {
            "texture": str(tex_path),
            "blend": str(out_blend),
            "glb": str(out_glb),
        },
        "notes": "v2: vertex-group masks for tail (bone016-020), head cap (bip01_head+bone001-015, upper only), ears. Soft-edged sparse orange patches, small spine black patch, tan/brown mixed tail.",
    }
    rp = Path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n  Report: {rp}")
    print("\nDone!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
