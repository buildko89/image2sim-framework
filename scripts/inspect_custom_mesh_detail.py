import bpy
import json
import math
from pathlib import Path

def inspect_mesh_details():
    custom_path = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend"
    bpy.ops.wm.open_mainfile(filepath=custom_path)
    
    details = {}
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
            
        verts_world = [list(obj.matrix_world @ v.co) for v in obj.data.vertices]
        min_x = min(v[0] for v in verts_world)
        max_x = max(v[0] for v in verts_world)
        min_y = min(v[1] for v in verts_world)
        max_y = max(v[1] for v in verts_world)
        min_z = min(v[2] for v in verts_world)
        max_z = max(v[2] for v in verts_world)
        
        details[obj.name] = {
            "matrix_world": [list(row) for row in obj.matrix_world],
            "location_mm": [round(obj.location.x * 1000.0, 3), round(obj.location.y * 1000.0, 3), round(obj.location.z * 1000.0, 3)],
            "rotation_euler_deg": [round(math.degrees(obj.rotation_euler.x), 3), round(math.degrees(obj.rotation_euler.y), 3), round(math.degrees(obj.rotation_euler.z), 3)],
            "rotation_quaternion": [round(v, 4) for v in obj.rotation_quaternion] if hasattr(obj, "rotation_quaternion") else None,
            "scale": [round(obj.scale.x, 4), round(obj.scale.y, 4), round(obj.scale.z, 4)],
            "bbox_world_mm": {
                "min": [round(min_x * 1000.0, 3), round(min_y * 1000.0, 3), round(min_z * 1000.0, 3)],
                "max": [round(max_x * 1000.0, 3), round(max_y * 1000.0, 3), round(max_z * 1000.0, 3)],
                "center": [
                    round((min_x + max_x) / 2.0 * 1000.0, 3),
                    round((min_y + max_y) / 2.0 * 1000.0, 3),
                    round((min_z + max_z) / 2.0 * 1000.0, 3),
                ]
            },
            "vertex_count": len(obj.data.vertices),
            "sample_verts_world_mm": [[round(v[0]*1000.0, 3), round(v[1]*1000.0, 3), round(v[2]*1000.0, 3)] for v in verts_world[:10]],
            "materials": [m.name for m in obj.data.materials] if hasattr(obj.data, "materials") else [],
        }
        
    out_file = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\custom_mesh_details.json")
    out_file.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Mesh details dumped to {out_file}")

if __name__ == "__main__":
    inspect_mesh_details()
