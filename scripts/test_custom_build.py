import bpy
import json
import math
from pathlib import Path

def test_custom_import_pipeline():
    custom_blend = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend")
    if not custom_blend.exists():
        print(f"Error: {custom_blend} not found")
        return
        
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    # Create main root and collections
    main_coll = bpy.context.scene.collection
    root = bpy.data.objects.new("drone_root", None)
    root.empty_display_size = 0.01
    main_coll.objects.link(root)
    
    # Load objects from custom blend
    with bpy.data.libraries.load(str(custom_blend), link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
        
    loaded_root = None
    for obj in data_to.objects:
        if obj is None:
            continue
        if obj.name == "drone_root":
            loaded_root = obj
            continue
        main_coll.objects.link(obj)
        
    if loaded_root is not None:
        # Copy metadata from loaded root to new root
        for k, v in loaded_root.items():
            root[k] = v
        bpy.data.objects.remove(loaded_root)
        
    # Re-parent top-level objects to root
    for obj in bpy.data.objects:
        if obj != root and obj.parent is None:
            obj.parent = root
            
    out_blend = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric\codrone.blend")
    out_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))
    print(f"Successfully replicated custom model into {out_blend}!")

if __name__ == "__main__":
    test_custom_import_pipeline()
