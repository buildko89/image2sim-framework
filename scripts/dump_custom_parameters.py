import bpy
import json
import math
from pathlib import Path

def dump_custom_params():
    custom_path = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend"
    bpy.ops.wm.open_mainfile(filepath=custom_path)
    
    data = {}
    for obj in bpy.data.objects:
        w_loc = obj.matrix_world.translation
        loc = obj.location
        rot = obj.rotation_euler
        scale = obj.scale
        
        mats = [m.name for m in obj.data.materials] if (obj.type == 'MESH' and hasattr(obj.data, 'materials')) else []
        
        if obj.type == 'MESH':
            verts_world = [obj.matrix_world @ v.co for v in obj.data.vertices]
            min_x = min(v.x for v in verts_world)
            max_x = max(v.x for v in verts_world)
            min_y = min(v.y for v in verts_world)
            max_y = max(v.y for v in verts_world)
            min_z = min(v.z for v in verts_world)
            max_z = max(v.z for v in verts_world)
        else:
            min_x = max_x = w_loc.x
            min_y = max_y = w_loc.y
            min_z = max_z = w_loc.z
            
        data[obj.name] = {
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "part_type": obj.get("part_type"),
            "materials": mats,
            "local_loc_mm": [round(loc.x * 1000.0, 3), round(loc.y * 1000.0, 3), round(loc.z * 1000.0, 3)],
            "local_rot_deg": [round(math.degrees(rot.x), 3), round(math.degrees(rot.y), 3), round(math.degrees(rot.z), 3)],
            "scale": [round(scale.x, 4), round(scale.y, 4), round(scale.z, 4)],
            "world_loc_mm": [round(w_loc.x * 1000.0, 3), round(w_loc.y * 1000.0, 3), round(w_loc.z * 1000.0, 3)],
            "world_center_mm": [round((min_x + max_x) / 2.0 * 1000.0, 3), round((min_y + max_y) / 2.0 * 1000.0, 3), round((min_z + max_z) / 2.0 * 1000.0, 3)],
            "world_size_mm": [round((max_x - min_x) * 1000.0, 3), round((max_y - min_y) * 1000.0, 3), round((max_z - min_z) * 1000.0, 3)],
            "world_min_max_mm": {
                "x": [round(min_x * 1000.0, 3), round(max_x * 1000.0, 3)],
                "y": [round(min_y * 1000.0, 3), round(max_y * 1000.0, 3)],
                "z": [round(min_z * 1000.0, 3), round(max_z * 1000.0, 3)],
            }
        }
        
    out_file = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\custom_params_dump.json")
    out_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Dumped parameters to {out_file}")

if __name__ == "__main__":
    dump_custom_params()
