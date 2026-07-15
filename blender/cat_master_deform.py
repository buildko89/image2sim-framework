import bpy
import os
import sys
import argparse
import json

def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Deform cat model toward short legs and fluffy shape.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--output-fbx", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(argv)

def group_index(mesh, name):
    group = mesh.vertex_groups.get(name)
    return group.index if group else None

def vertex_weight(vertex, index):
    if index is None:
        return 0.0
    for group in vertex.groups:
        if group.group == index:
            return group.weight
    return 0.0

def max_weight(vertex, indices):
    return max((vertex_weight(vertex, index) for index in indices), default=0.0)

def main():
    args = parse_args()
    
    print(f"Loading master base blend: {args.input}")
    bpy.ops.wm.open_mainfile(filepath=args.input)
    
    # 全てのメッシュオブジェクトを処理対象にする
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    
    # 頂点グループ名の定義
    leg_names = [
        "CatGirl2:frontHip_R", "CatGirl2:frontKnee_R", "CatGirl2:frontAnkle_R", "CatGirl2:frontBall_R",
        "CatGirl2:frontHip_L", "CatGirl2:frontKnee_L", "CatGirl2:frontAnkle_L", "CatGirl2:frontBall_L",
        "CatGirl2:backHip_R", "CatGirl2:backKnee_R", "CatGirl2:backAnkle_R", "CatGirl2:backBall_R",
        "CatGirl2:backHip_L", "CatGirl2:backKnee_L", "CatGirl2:backAnkle_L", "CatGirl2:backBall_L"
    ]
    body_names = [
        "CatGirl2:BackA_M", "CatGirl2:BackB_M", "CatGirl2:Chest_M", "CatGirl2:Root_M",
        "CatGirl2:Rump_R", "CatGirl2:Rump_L", "CatGirl2:Scapula_R", "CatGirl2:Scapula_L"
    ]
    neck_names = ["CatGirl2:Neck_M", "CatGirl2:NeckPart1_M", "CatGirl2:NeckPart2_M"]
    head_names = ["CatGirl2:Head_M", "CatGirl2:Jaw_M", "CatGirl2:JawEnd_M", "CatGirl2:Hair_M"]
    tail_names = [f"CatGirl2:Tail{i}_M" for i in range(7)]
    
    report_data = {
        "meshes_processed": [],
        "deformations": {}
    }
    
    # 共通のZ軸滑らか圧縮関数
    def deform_z(z_val, f_z, leg_h, leg_s):
        h = z_val - f_z
        if h < 0.0:
            return z_val
        if h < leg_h:
            # 接地から脚の付け根に向かって滑らかにブレンド
            t = 1.0 - (h / leg_h)
            t = 3 * (t ** 2) - 2 * (t ** 3) # smoothstep
            compressed_h = h * leg_s
            return f_z + h * (1.0 - t) + compressed_h * t
        else:
            # 胴体部分は一律で下げる
            offset_z = leg_h * (1.0 - leg_s)
            return z_val - offset_z

    # 代表的なメッシュからZ座標の範囲と接地高を自動判定
    global_foot_z = 0.0
    global_max_z = 1.0
    if meshes:
        global_foot_z = min((vertex.co.z for vertex in meshes[0].data.vertices), default=0.0)
        global_max_z = max((vertex.co.z for vertex in meshes[0].data.vertices), default=1.0)
    
    global_height = global_max_z - global_foot_z
    print(f"Detected model height: {global_height} (Min Z: {global_foot_z}, Max Z: {global_max_z})")
    
    # 脚の付け根の高さをモデル全高の 52% とする
    leg_height = global_height * 0.52
    leg_scale = 0.50
    print(f"Set leg_height to: {leg_height} and leg_scale to: {leg_scale}")

    for mesh in meshes:
        print(f"\nDeforming mesh: {mesh.name}")
        
        leg_indices = [group_index(mesh, name) for name in leg_names]
        body_indices = [group_index(mesh, name) for name in body_names]
        neck_indices = [group_index(mesh, name) for name in neck_names]
        head_indices = [group_index(mesh, name) for name in head_names]
        tail_indices = [group_index(mesh, name) for name in tail_names]
        
        counts = {"legs": 0, "body": 0, "neck": 0, "head": 0, "tail": 0}
        
        # 頂点変形ループ
        for vertex in mesh.data.vertices:
            co = vertex.co
            original_z = co.z
            
            # 1. 四肢の滑らかなZ軸圧縮 (トポロジー破壊を防ぐため幾何学的に適用)
            co.z = deform_z(original_z, global_foot_z, leg_height, leg_scale)
            
            # 接地からの高さを基準にしたブレンド係数
            h = original_z - global_foot_z
            t_leg = 0.0
            if h < leg_height:
                t_leg = 1.0 - (h / leg_height)
                t_leg = 3 * (t_leg ** 2) - 2 * (t_leg ** 3)
            
            # 足のボリューム感（太さ）をX, Y軸方向に少し太くする
            co.x *= 1.0 + 0.15 * t_leg
            co.y *= 1.0 + 0.15 * t_leg
            if t_leg > 0.01:
                counts["legs"] += 1
                
            # 2. 胴体を横に広げる（胴長短足ふくよか感）
            body_w = max_weight(vertex, body_indices)
            if body_w > 0.01:
                co.x *= 1.0 + 0.25 * body_w  # 体幅のボリュームを大きく追加
                co.y *= 1.0 + 0.05 * body_w
                counts["body"] += 1
                
            # 3. 首を少し太く
            neck_w = max_weight(vertex, neck_indices)
            if neck_w > 0.01:
                co.x *= 1.0 + 0.15 * neck_w
                counts["neck"] += 1
                
            # 4. 頭の丸顔化とマズル平坦化
            head_w = max_weight(vertex, head_indices)
            if head_w > 0.01:
                co.x *= 1.0 + 0.12 * head_w  # 頬のふっくら感
                co.z *= 1.0 + 0.04 * head_w
                # モデルの口元をつぶして丸みを出す
                if co.y > 0.0:
                    co.y *= 1.0 - 0.08 * head_w
                else:
                    co.y *= 1.0 + 0.08 * head_w
                counts["head"] += 1
                
            # 5. 尻尾を太く
            tail_w = max_weight(vertex, tail_indices)
            if tail_w > 0.01:
                vertex.co += vertex.normal * 0.045 * tail_w
                counts["tail"] += 1
                
        mesh.data.update()
        report_data["meshes_processed"].append(mesh.name)
        report_data["deformations"][mesh.name] = counts
        print(f"-> Deformed vertex counts: {counts}")

    # === アーマチュアのボーンも全く同じZ軸圧縮で変形し、リグ位置をスキンウェイトに一致させる ===
    arm = bpy.data.objects.get("Cat_Armature")
    if not arm:
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                arm = obj
                break
    if arm:
        print("\nDeforming armature bones...")
        # 編集モードに入る
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode='EDIT')
        
        # すべてのエディットボーンのZ座標を幾何学的に縮小
        for bone in arm.data.edit_bones:
            bone.head.z = deform_z(bone.head.z, global_foot_z, leg_height, leg_scale)
            bone.tail.z = deform_z(bone.tail.z, global_foot_z, leg_height, leg_scale)
            
        bpy.ops.object.mode_set(mode='OBJECT')
        print("Armature bones deformed successfully.")

        
    # 皮毛シェル (Fur Shell) の作成と追加
    # メッシュをコピーして法線方向に少しふくらませる
    for mesh in meshes:
        if "Fur_Shell" in mesh.name or "eye" in mesh.name.lower():
            print(f"Skipping Fur Shell creation for: {mesh.name}")
            continue
            
        print(f"\nCreating Fur Shell for: {mesh.name}")
        shell = mesh.copy()
        shell.data = mesh.data.copy()
        shell.name = f"{mesh.name}_Fur_Shell"
        shell.data.name = f"{mesh.data.name}_Fur_Shell"
        
        # シーンへのリンク
        bpy.context.collection.objects.link(shell)
        
        # 安全な親子関係の設定（親の逆行列を直接コピーして、モディファイアの重複や二重スケーリングを完璧に防止）
        shell.parent = mesh.parent
        shell.matrix_parent_inverse = mesh.matrix_parent_inverse.copy()
        
        # シェルからシェイプキーを完全に削除（アニメーション評価時の頂点爆発を防止）
        if shell.data.shape_keys:
            shell.shape_key_clear()
            
        # トランスフォームの適用（位置・回転・スケールを完全に固定し、ズレを防止）
        bpy.ops.object.select_all(action='DESELECT')
        shell.select_set(True)
        bpy.context.view_layer.objects.active = shell
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
        
        body_indices = [group_index(shell, name) for name in body_names]
        tail_indices = [group_index(shell, name) for name in tail_names]
        head_indices = [group_index(shell, name) for name in head_names]
        neck_indices = [group_index(shell, name) for name in neck_names]
        
        for vertex in shell.data.vertices:
            body_w = max_weight(vertex, body_indices)
            tail_w = max_weight(vertex, tail_indices)
            head_w = max_weight(vertex, head_indices)
            neck_w = max_weight(vertex, neck_indices)
            
            # シェルの法線方向への押し出し幅設定（部位によって変える）
            influence = max(body_w, tail_w * 1.3, head_w * 0.4, neck_w * 0.8)
            if influence > 0.01:
                # 頂点を法線方向に押し出して長毛のボリュームを作る
                vertex.co += vertex.normal * 0.038 * influence
                
        shell.data.update()
        print(f"-> Fur Shell created: {shell.name}")
        
    # 保存
    os.makedirs(os.path.dirname(args.output_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.output_blend)
    print(f"\nSaved customized Blend file: {args.output_blend}")
    
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
    
    # レポート保存
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    main()
