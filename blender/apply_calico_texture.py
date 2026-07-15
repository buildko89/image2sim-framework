import bpy
import os
import sys
import math
import argparse

def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Create calico texture via Blender Vertex Color and CPU Cycles Baking.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--output-fbx", required=True)
    parser.add_argument("--output-tex", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(argv)

def get_calico_color(x, y, z):
    # 三毛猫の配色カラー定義 (RGB 0.0 - 1.0)
    base_white = (0.95, 0.94, 0.91)
    orange_brown = (0.68, 0.32, 0.08)
    dark_black = (0.09, 0.07, 0.06)
    
    # 3D空間のブチの球体定義 (center_x, center_y, center_z, radius, color)
    # モデルのサイズに合わせたスケール感に調整
    spots = [
        # 右肩付近の茶ブチ
        (0.08, 0.12, 0.18, 0.11, orange_brown),
        # 左脇腹付近の黒ブチ
        (-0.09, -0.06, 0.14, 0.12, dark_black),
        # 右腰付近の黒ブチ
        (0.09, -0.22, 0.16, 0.11, dark_black),
        # 左臀部付近の茶ブチ
        (-0.07, -0.32, 0.13, 0.12, orange_brown),
    ]
    
    # 1. 顔の塗り分け (Yが前方向、Y > 0.16付近)
    if y > 0.16:
        # 鼻筋は白
        if abs(x) < 0.022:
            return base_white
        # 右耳・右頬は茶色
        elif x > 0:
            return orange_brown
        # 左耳・左頬は黒色
        else:
            return dark_black
            
    # 2. 尻尾の縞模様 (Yが後ろ方向、Y < -0.38付近)
    if y < -0.38:
        # Y座標の位置に応じて縞々にする
        stripe = int(y * 18) % 2
        return orange_brown if stripe == 0 else dark_black

    # 3. 体のスポット判定
    closest_color = base_white
    min_dist_ratio = 1.0
    
    for sx, sy, sz, radius, color in spots:
        dist = math.sqrt((x - sx)**2 + (y - sy)**2 + (z - sz)**2)
        ratio = dist / radius
        if ratio < min_dist_ratio:
            min_dist_ratio = ratio
            closest_color = color
            
    if min_dist_ratio < 1.0:
        # 滑らかな境界ブレンド (Smoothstep)
        t = 3 * (min_dist_ratio ** 2) - 2 * (min_dist_ratio ** 3)
        r = base_white[0] * t + closest_color[0] * (1 - t)
        g = base_white[1] * t + closest_color[1] * (1 - t)
        b = base_white[2] * t + closest_color[2] * (1 - t)
        return (r, g, b)
        
    return base_white

def main():
    args = parse_args()
    
    print(f"Loading animated blend: {args.input}")
    bpy.ops.wm.open_mainfile(filepath=args.input)
    
    # 対象のメッシュオブジェクトを取得
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not meshes:
        print("ERROR: No mesh objects found in scene.")
        sys.exit(1)
        
    print(f"Found meshes for texturing: {[m.name for m in meshes]}")
    
    # 1. ベースメッシュのみに Smart UV Project を実行して綺麗にUV展開する
    # (Fur_ShellオブジェクトはベースメッシュのUV座標を完全に共有する必要があるため、絶対にUVを再展開してはならない)
    for mesh in meshes:
        if "Fur_Shell" in mesh.name:
            print(f"Skipping Smart UV Project for Fur Shell: {mesh.name}")
            continue
        bpy.context.view_layer.objects.active = mesh
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        # 重なりのない綺麗なUV展開
        bpy.ops.uv.smart_project(angle_limit=66.0, island_margin=0.015)
        bpy.ops.object.mode_set(mode='OBJECT')
        print(f"Smart UV projected: {mesh.name}")
        
    # 2. 頂点カラーを計算してペイント
    for mesh in meshes:
        # 既存のColor Attributeをクリーンアップ
        while mesh.data.color_attributes:
            mesh.data.color_attributes.remove(mesh.data.color_attributes[0])
            
        # POINTドメイン（頂点単位）でカラーアトリビュートを作成
        color_attr = mesh.data.color_attributes.new(
            name="Color",
            type='FLOAT_COLOR',
            domain='POINT'
        )
        
        # 頂点ごとに色を適用
        # ワールド行列を適用してグローバル（またはポーズ済み）座標での塗り分けを行う
        # これによりメッシュの初期位置に準拠した綺麗なブチになる
        matrix_world = mesh.matrix_world
        for i, vertex in enumerate(mesh.data.vertices):
            # グローバル座標に変換
            global_co = matrix_world @ vertex.co
            # 三毛猫カラーを取得
            r, g, b = get_calico_color(global_co.x, global_co.y, global_co.z)
            # アルファ値は1.0 (Fur_Shellオブジェクトの場合は後でマテリアルで透過制御)
            color_attr.data[i].color = (r, g, b, 1.0)
            
        print(f"Applied vertex colors to: {mesh.name}")

    # 3. ベイク用の一時マテリアルを設定
    # 2048x2048 のベイクターゲットテクスチャを作成
    img_name = "Cat_Calico_Albedo"
    img = bpy.data.images.get(img_name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(img_name, width=2048, height=2048, alpha=True)
    img.filepath_raw = args.output_tex
    img.file_format = 'PNG'
    
    # ベイク用の一時マテリアルを作成
    bake_mat = bpy.data.materials.new("Bake_Material")
    bake_mat.use_nodes = True
    nodes = bake_mat.node_tree.nodes
    links = bake_mat.node_tree.links
    
    # ノードクリーンアップ
    nodes.clear()
    
    # ノード配置
    node_out = nodes.new("ShaderNodeOutputMaterial")
    node_emit = nodes.new("ShaderNodeEmission")
    node_color_attr = nodes.new("ShaderNodeAttribute")
    node_color_attr.attribute_name = "Color"
    
    # ベイク対象の画像テクスチャノード（これがActiveである必要がある）
    node_tex = nodes.new("ShaderNodeTexImage")
    node_tex.image = img
    # Activeにしてベイク先にする
    nodes.active = node_tex
    
    # リンク接続
    links.new(node_color_attr.outputs["Color"], node_emit.inputs["Color"])
    links.new(node_emit.outputs["Emission"], node_out.inputs["Surface"])
    
    # 全メッシュに一時的にこのマテリアルを割り当てる
    orig_materials = {}
    for mesh in meshes:
        orig_materials[mesh.name] = [slot.material for slot in mesh.material_slots]
        # マテリアルスロットをクリアして一時マテリアルをアサイン
        mesh.data.materials.clear()
        mesh.data.materials.append(bake_mat)
        
    # 4. Cyclesを用いたEMITベイクを実行（GPU不要、CPUで超高速動作）
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.cycles.device = 'CPU'
    # 高速化のためサンプル数を1にする
    bpy.context.scene.cycles.samples = 1
    bpy.context.scene.cycles.bake_type = 'EMIT'
    
    print("\nBaking albedo texture (Cycles CPU)...")
    # すべてのメッシュを選択状態にしてベイク
    bpy.ops.object.select_all(action='DESELECT')
    for mesh in meshes:
        mesh.select_set(True)
        
    bpy.ops.object.bake(type='EMIT', save_mode='INTERNAL')
    
    # ベイク画像を保存
    os.makedirs(os.path.dirname(args.output_tex), exist_ok=True)
    img.save_render(filepath=args.output_tex)
    print(f"Baked texture saved to: {args.output_tex}")
    
    # 5. 完成マテリアルの作成とアサイン
    final_mat = bpy.data.materials.new("Cat_Material")
    final_mat.use_nodes = True
    f_nodes = final_mat.node_tree.nodes
    f_links = final_mat.node_tree.links
    
    f_nodes.clear()
    f_out = f_nodes.new("ShaderNodeOutputMaterial")
    f_bsdf = f_nodes.new("ShaderNodeBsdfPrincipled")
    f_tex = f_nodes.new("ShaderNodeTexImage")
    # 新しくベイクされたテクスチャをロード
    bpy.ops.image.open(filepath=args.output_tex)
    loaded_img = bpy.data.images.get(os.path.basename(args.output_tex))
    if loaded_img:
        f_tex.image = loaded_img
        loaded_img.pack()
    
    f_links.new(f_tex.outputs["Color"], f_bsdf.inputs["Base Color"])
    f_links.new(f_bsdf.outputs["BSDF"], f_out.inputs["Surface"])
    
    # 毛並みシェル用の透過マテリアルの作成
    shell_mat = bpy.data.materials.new("Cat_Shell_Material")
    shell_mat.use_nodes = True
    shell_mat.blend_method = 'BLEND'  # 透過対応
    s_nodes = shell_mat.node_tree.nodes
    s_links = shell_mat.node_tree.links
    
    s_nodes.clear()
    s_out = s_nodes.new("ShaderNodeOutputMaterial")
    s_bsdf = s_nodes.new("ShaderNodeBsdfPrincipled")
    s_tex = s_nodes.new("ShaderNodeTexImage")
    if loaded_img:
        s_tex.image = loaded_img
        
    # 半透明設定 (Alpha = 0.35)
    s_bsdf.inputs["Alpha"].default_value = 0.35
    s_bsdf.inputs["Roughness"].default_value = 0.95 # 光沢を抑える
    
    s_links.new(s_tex.outputs["Color"], s_bsdf.inputs["Base Color"])
    s_links.new(s_bsdf.outputs["BSDF"], s_out.inputs["Surface"])
    
    # マテリアルの再アサイン
    for mesh in meshes:
        mesh.data.materials.clear()
        if "Fur_Shell" in mesh.name:
            mesh.data.materials.append(shell_mat)
        else:
            mesh.data.materials.append(final_mat)
            
    # 一時マテリアルとアトリビュートを削除（クリーンアップ）
    bpy.data.materials.remove(bake_mat)
    
    # 保存
    os.makedirs(os.path.dirname(args.output_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.output_blend)
    print(f"\nSaved customized Blend file with baked texture: {args.output_blend}")
    
    # GLBエクスポート (Draco圧縮は無効化)
    bpy.ops.export_scene.gltf(
        filepath=args.output_glb,
        export_format='GLB',
        export_animations=True,
        export_rest_position_armature=True,
        export_draco_mesh_compression_enable=False
    )
    print(f"Exported GLB: {args.output_glb}")
    
    # FBXエクスポート
    bpy.ops.export_scene.fbx(
        filepath=args.output_fbx,
        bake_anim=True,
        add_leaf_bones=False
    )
    print(f"Exported FBX: {args.output_fbx}")
    
    # レポート作成
    report_data = {
        "success": True,
        "texture_baked": args.output_tex,
        "meshes_textured": [m.name for m in meshes]
    }
    with open(args.report, "w", encoding="utf-8") as f:
        import json
        json.dump(report_data, f, indent=4, ensure_ascii=False)
    print("Report written.")

if __name__ == "__main__":
    main()
