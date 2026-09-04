import bpy
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, r"D:\source\repos\3DModelDevPJ\image2sim-framework")
sys.path.insert(0, r"D:\source\repos\3DModelDevPJ\image2sim-framework\blender\drone_model")

from build_drone import load_config, verify_drone_model

def run_custom_qa():
    config_path = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\resolved_config.json"
    if not os.path.exists(config_path):
        config_path = r"D:\source\repos\3DModelDevPJ\image2sim-framework\config\codrone_model.yaml"
        
    config = load_config(config_path)
    
    custom_blend = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend"
    bpy.ops.wm.open_mainfile(filepath=custom_blend)
    
    root = bpy.data.objects.get("drone_root")
    qa_report = verify_drone_model(root, config)
    print("QA REPORT FOR CUSTOM MODEL:")
    print(json.dumps(qa_report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    import os
    run_custom_qa()
