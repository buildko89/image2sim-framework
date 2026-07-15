import bpy
import json
import sys
import os

def clear_scene():
    # 既存のオブジェクトをすべてクリア
    bpy.ops.wm.read_factory_settings(use_empty=True)

def inspect_file(filepath):
    clear_scene()
    ext = os.path.splitext(filepath)[1].lower()
    
    print(f"Loading {filepath} ...")
    if ext == '.blend':
        bpy.ops.wm.open_mainfile(filepath=filepath)
    elif ext == '.fbx':
        try:
            bpy.ops.import_scene.fbx(filepath=filepath)
        except AttributeError:
            # Blender 4.1/4.2+ では一部インポーターのAPIが変更されている可能性がある
            bpy.ops.import_scene.fbx(filepath=filepath)
    elif ext in ['.glb', '.gltf']:
        bpy.ops.import_scene.gltf(filepath=filepath)
    elif ext == '.stl':
        try:
            # Blender 4.0 以降の STL インポート
            bpy.ops.wm.stl_import(filepath=filepath)
        except AttributeError:
            # 旧バージョン対応のフォールバック
            bpy.ops.import_mesh.stl(filepath=filepath)
    else:
        print(f"Unsupported file type: {ext}")
        return None

    # 情報収集
    meshes = []
    armatures = []
    actions = []

    for obj in bpy.data.objects:
        if obj.type == 'MESH':
            mesh_info = {
                "name": obj.name,
                "vertices_count": len(obj.data.vertices),
                "polygons_count": len(obj.data.polygons),
                "materials": [slot.material.name for slot in obj.material_slots if slot.material]
            }
            meshes.append(mesh_info)
        elif obj.type == 'ARMATURE':
            armature_info = {
                "name": obj.name,
                "bones_count": len(obj.data.bones),
                "bone_names": [bone.name for bone in obj.data.bones][:50] # 多すぎる場合は一部省略して記録
            }
            armatures.append(armature_info)
            
    # アニメーション（アクション）の一覧
    for action in bpy.data.actions:
        actions.append(action.name)
        
    return {
        "filename": os.path.basename(filepath),
        "filepath": filepath,
        "meshes_count": len(meshes),
        "meshes": meshes,
        "armatures_count": len(armatures),
        "armatures": armatures,
        "actions_count": len(actions),
        "actions": actions
    }

if __name__ == "__main__":
    # 引数のパース
    # blender -b -P blender/inspect_cat_asset.py -- <input_path> <output_path>
    try:
        args = sys.argv[sys.argv.index("--") + 1:]
        input_path = args[0]
        output_path = args[1]
    except (ValueError, IndexError):
        print("Usage: blender -b -P inspect_cat_asset.py -- <input_path> <output_path>")
        sys.exit(1)
    
    try:
        info = inspect_file(input_path)
        if info:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, indent=4, ensure_ascii=False)
            print("INSPECT_SUCCESS")
        else:
            print("INSPECT_FAILED: Invalid or unsupported file")
            sys.exit(1)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"INSPECT_FAILED: {str(e)}")
        sys.exit(1)
