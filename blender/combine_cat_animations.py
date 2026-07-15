import bpy
import os
import sys

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)

def cleanup_action_channels(armature_obj):
    armature_bones = set(armature_obj.data.bones.keys())
    print(f"\nCleaning up animation channels for armature: {armature_obj.name}")
    print(f"Master bone count: {len(armature_bones)}")
    
    for action in bpy.data.actions:
        # スロットとレイヤーをたどる (Blender 5.0 Layered Actions 対応)
        if len(action.slots) == 0:
            continue
            
        slot = action.slots[0]
        
        for layer in action.layers:
            for strip in layer.strips:
                try:
                    bag = strip.channelbag(slot=slot)
                except Exception as e:
                    continue
                    
                if not bag or not hasattr(bag, "fcurves") or not bag.fcurves:
                    continue
                    
                to_remove = []
                curves_list = list(bag.fcurves)
                
                for fcurve in curves_list:
                    data_path = fcurve.data_path
                    
                    if 'pose.bones["' in data_path:
                        start = data_path.find('["') + 2
                        end = data_path.find('"]')
                        bone_name = data_path[start:end]
                        
                        # 1. 存在しないボーンのチャンネルを削除
                        if bone_name not in armature_bones:
                            to_remove.append(fcurve)
                            continue
                            
                        # 2. ルート以外のボーンの位置移動 (Location) チャンネルを削除
                        if ".location" in data_path:
                            if "Root_M" not in bone_name and "Root" not in bone_name:
                                to_remove.append(fcurve)
                                
                if to_remove:
                    print(f"-> Removing {len(to_remove)} invalid/location channels from {action.name}")
                    for fcurve in to_remove:
                        try:
                            bag.fcurves.remove(fcurve)
                        except Exception as e:
                            pass

def combine_fbx_files(fbx_files, output_blend):
    clear_scene()
    
    master_armature = None
    master_mesh_objs = []
    
    # Walk (houseCat_anim) を最優先でインポートしてマスターにするためソート
    sorted_items = sorted(fbx_files.items(), key=lambda x: 0 if x[0] == "Walk" else 1)
    
    # 登録されたFBXファイルをループ処理
    for label, filepath in sorted_items:
        print(f"\nProcessing {label} from {filepath} ...")
        
        # 現在のアクションを記録
        existing_actions = set(bpy.data.actions.keys())
        
        # 選択オブジェクトをクリア
        bpy.ops.object.select_all(action='DESELECT')
        
        # インポート前の全オブジェクトを記録
        pre_import_objs = set(bpy.data.objects.keys())
        
        # FBXをインポート
        bpy.ops.import_scene.fbx(filepath=filepath)
        
        # 新しくインポートされたオブジェクトを特定
        post_import_objs = set(bpy.data.objects.keys())
        new_objs = [bpy.data.objects[name] for name in (post_import_objs - pre_import_objs)]
        
        # 新しいアクションを特定
        new_actions = set(bpy.data.actions.keys()) - existing_actions
        for act_name in new_actions:
            act = bpy.data.actions[act_name]
            new_name = f"Cat_{label}"
            act.name = new_name
            act.use_fake_user = True
            print(f"-> Renamed action '{act_name}' to '{new_name}' (Fake User = True)")
            
        current_armature = None
        current_meshes = []
        for obj in new_objs:
            if obj.type == 'ARMATURE':
                current_armature = obj
            elif obj.type == 'MESH':
                current_meshes.append(obj)
                
        if not master_armature and current_armature:
            # 最初のインポートしたアーマチュアとメッシュをマスターとする
            master_armature = current_armature
            master_armature.name = "Cat_Armature"
            
            # マスターのベース名から正式名へのマップを作成
            global master_bone_map
            master_bone_map = {}
            for bone in master_armature.data.bones:
                base_name = bone.name.split(":")[-1] if ":" in bone.name else bone.name
                master_bone_map[base_name] = bone.name
            print(f"-> Master bone map established with {len(master_bone_map)} bones.")
            
            # メッシュの親がこのアーマチュアならキープ
            for mesh_obj in current_meshes:
                mesh_obj.name = f"Cat_Mesh_{mesh_obj.name}"
                master_mesh_objs.append(mesh_obj)
            print(f"-> Set master armature: {master_armature.name}")
            print(f"-> Set master meshes: {[m.name for m in master_mesh_objs]}")
            
            # 選択解除
            bpy.ops.object.select_all(action='DESELECT')
        elif current_armature:
            # すでにマスターがある場合：インポートされた一時アーマチュアのボーン名をマスターのボーン名にマッピングリネームする
            # これにより、このFBXからインポートされたアクションのF-Curveパスが自動的に正しい名前に置換される
            print(f"-> Remapping bones for temporary armature: {current_armature.name}")
            for bone in current_armature.data.bones:
                old_bone_name = bone.name
                base_name = old_bone_name.split(":")[-1] if ":" in old_bone_name else old_bone_name
                if base_name in master_bone_map:
                    new_bone_name = master_bone_map[base_name]
                    if old_bone_name != new_bone_name:
                        bone.name = new_bone_name
            
            # クリーニング用の一時オブジェクト削除
            print(f"-> Cleaning up imported temporary objects for {label}...")
            bpy.ops.object.select_all(action='DESELECT')
            for obj in new_objs:
                obj.select_set(True)
            bpy.ops.object.delete()
            
    # 全てのアクションがマスターアーマチュアで再生可能か確認
    # (同一リグなので、アニメーションデータをリンクすれば動作する)
    if master_armature:
        if not master_armature.animation_data:
            master_armature.animation_data_create()
            
        # デフォルトのアクションをCat_Idle（もしあれば）にしておく
        idle_act = bpy.data.actions.get("Cat_Idle")
        if idle_act:
            master_armature.animation_data.action = idle_act
            print(f"\nSet default action to: Cat_Idle")
        else:
            # なければ最初に見つかったアクションを設定
            cat_actions = [a for a in bpy.data.actions if a.name.startswith("Cat_")]
            if cat_actions:
                master_armature.animation_data.action = cat_actions[0]
                print(f"\nSet default action to: {cat_actions[0].name}")
                
    # === スケールアップ（15倍）とトランスフォームの個別適用 ===
    if master_armature:
        print("\nScaling up master armature by 15x and applying transform individually...")
        bpy.context.view_layer.objects.active = master_armature
        bpy.ops.object.mode_set(mode='OBJECT')
        
        # マスターアーマチュアをスケールアップ
        master_armature.scale *= 15.0
        
        # 親子同時適用の二重評価による崩壊を防ぐため、1つずつ個別に適用する
        for obj in [master_armature] + master_mesh_objs:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
            
        bpy.ops.object.select_all(action='DESELECT')
        print("Master armature and meshes scaled up 15x individually and transforms applied.")
        
    # 不正なボーンチャンネルのクリーンアップはGodot側のランタイム処理に移譲したため、ここでは行わない
    pass
                
    # 保存
    os.makedirs(os.path.dirname(output_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=output_blend)
    print(f"\nSuccessfully saved combined model to: {output_blend}")

if __name__ == "__main__":
    # 引数のパース
    # blender -b -P blender/combine_cat_animations.py -- <output_blend> <label>=<filepath> <label>=<filepath> ...
    try:
        args = sys.argv[sys.argv.index("--") + 1:]
        output_blend = args[0]
        fbx_args = args[1:]
    except (ValueError, IndexError):
        print("Usage: blender -b -P combine_cat_animations.py -- <output_blend> <label1>=<path1> <label2>=<path2> ...")
        sys.exit(1)
        
    fbx_files = {}
    for arg in fbx_args:
        if "=" in arg:
            label, filepath = arg.split("=", 1)
            fbx_files[label] = filepath
            
    if not fbx_files:
        print("ERROR: No FBX files specified.")
        sys.exit(1)
        
    combine_fbx_files(fbx_files, output_blend)
