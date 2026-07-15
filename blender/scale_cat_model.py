import bpy
import os
import sys
import argparse

def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Scale the cat model to realistic size (approx 15x larger).")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--output-fbx", required=True)
    return parser.parse_args(argv)

def main():
    args = parse_args()
    
    print(f"Loading blend: {args.input}")
    bpy.ops.wm.open_mainfile(filepath=args.input)
    
    # オブジェクト選択モード
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    
    arm = bpy.data.objects.get("Cat_Armature")
    if not arm:
        # 代替名で検索
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                arm = obj
                break
                
    if not arm:
        print("ERROR: Armature not found.")
        sys.exit(1)
        
    print(f"Using armature: {arm.name}")
    
    # すべてのメッシュとアーマチュアを選択
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    
    arm.select_set(True)
    for mesh in meshes:
        mesh.select_set(True)
        
    # アクティブオブジェクトを設定
    bpy.context.view_layer.objects.active = arm
    
    # すでに最初の結合段階で15倍スケール適用済みのため、ここでは1.0倍（拡大なし）とする
    scale_factor = 1.0
    print(f"Scaling objects by factor {scale_factor}...")
    
    # 親であるアーマチュアのスケールを変更すると、子は自動的に連動するが、
    # Apply Scaleを確実に行うために明示的に適用する
    arm.scale *= scale_factor
    
    # トランスフォームの個別適用 (Apply Scale)
    # 親子同時適用の二重評価による崩壊を完全に防ぐため、1つずつ個別に適用する
    for obj in [arm] + meshes:
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    print("Scale applied individually and successfully.")
    
    # 寸法の再確認
    for mesh in meshes:
        print(f"Mesh {mesh.name} dimensions after scale: {mesh.dimensions}")
        
    # 保存
    os.makedirs(os.path.dirname(args.output_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.output_blend)
    print(f"Saved scaled Blend: {args.output_blend}")
    
    # GLBエクスポート (テクスチャ埋め込みを維持, Draco圧縮は無効化)
    bpy.ops.export_scene.gltf(
        filepath=args.output_glb,
        export_format='GLB',
        export_animations=True,
        export_rest_position_armature=True,
        export_draco_mesh_compression_enable=False
    )
    print(f"Exported scaled GLB: {args.output_glb}")
    
    # FBXエクスポート
    bpy.ops.export_scene.fbx(
        filepath=args.output_fbx,
        bake_anim=True,
        add_leaf_bones=False
    )
    print(f"Exported scaled FBX: {args.output_fbx}")

if __name__ == "__main__":
    main()
