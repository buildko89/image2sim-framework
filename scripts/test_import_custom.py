import bpy
import os
from pathlib import Path

def test_import():
    custom_blend = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend"
    
    # Create new clean mainfile
    bpy.ops.wm.read_factory_settings(use_empty=True)
    
    with bpy.data.libraries.load(custom_blend, link=False) as (data_from, data_to):
        data_to.objects = data_from.objects
        
    for obj in data_to.objects:
        if obj is not None:
            bpy.context.scene.collection.objects.link(obj)
            
    print(f"Imported {len(data_to.objects)} objects successfully!")
    out_blend = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\test_import_custom.blend"
    bpy.ops.wm.save_as_mainfile(filepath=out_blend)
    print(f"Saved test file to {out_blend}")

if __name__ == "__main__":
    test_import()
