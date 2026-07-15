import bpy
import os
import sys

def export_uv(blend_path, output_png):
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    
    # メッシュオブジェクトを見つける
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
    if not meshes:
        print("ERROR: No mesh found.")
        sys.exit(1)
        
    mesh_obj = meshes[0]
    print(f"Using mesh: {mesh_obj.name}")
    
    # 編集モードに入る
    bpy.context.view_layer.objects.active = mesh_obj
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    
    # UVレイアウトのエクスポート
    # Blender 4.x / 5.0 の UV レイアウトエクスポート
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    bpy.ops.uv.export_layout(filepath=output_png, size=(1024, 1024), opacity=0.25)
    print(f"UV layout exported to: {output_png}")

if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    blend_path = args[0]
    output_png = args[1]
    export_uv(blend_path, output_png)
