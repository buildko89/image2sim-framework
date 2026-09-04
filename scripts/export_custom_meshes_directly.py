import bpy
import json
import math
from pathlib import Path

def extract_all_object_specs():
    custom_blend = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend"
    bpy.ops.wm.open_mainfile(filepath=custom_blend)
    
    specs = {}
    for obj in bpy.data.objects:
        w_mat = obj.matrix_world
        w_loc = w_mat.translation
        loc = obj.location
        rot = obj.rotation_euler
        scale = obj.scale
        
        mesh_info = {}
        if obj.type == 'MESH':
            verts_world = [list(w_mat @ v.co) for v in obj.data.vertices]
            verts_local = [list(v.co) for v in obj.data.vertices]
            
            min_xw = min(v[0] for v in verts_world)
            max_xw = max(v[0] for v in verts_world)
            min_yw = min(v[1] for v in verts_world)
            max_yw = max(v[1] for v in verts_world)
            min_zw = min(v[2] for v in verts_world)
            max_zw = max(v[2] for v in verts_world)
            
            min_xl = min(v[0] for v in verts_local)
            max_xl = max(v[0] for v in verts_local)
            min_yl = min(v[1] for v in verts_local)
            max_yl = max(v[1] for v in verts_local)
            min_zl = min(v[2] for v in verts_local)
            max_zl = max(v[2] for v in verts_local)
            
            mesh_info = {
                "vertex_count": len(obj.data.vertices),
                "polygon_count": len(obj.data.polygons),
                "world_size_mm": [round((max_xw - min_xw)*1000.0, 3), round((max_yw - min_yw)*1000.0, 3), round((max_zw - min_zw)*1000.0, 3)],
                "local_size_mm": [round((max_xl - min_xl)*1000.0, 3), round((max_yl - min_yl)*1000.0, 3), round((max_zl - min_zl)*1000.0, 3)],
                "world_center_mm": [round((min_xw + max_xw)/2.0*1000.0, 3), round((min_yw + max_yw)/2.0*1000.0, 3), round((min_zw + max_zw)/2.0*1000.0, 3)],
                "world_bbox_min_mm": [round(min_xw*1000.0, 3), round(min_yw*1000.0, 3), round(min_zw*1000.0, 3)],
                "world_bbox_max_mm": [round(max_xw*1000.0, 3), round(max_yw*1000.0, 3), round(max_zw*1000.0, 3)],
                "sample_verts_world_mm": [[round(v[0]*1000.0, 3), round(v[1]*1000.0, 3), round(v[2]*1000.0, 3)] for v in verts_world],
            }
            
        mats = [m.name for m in obj.data.materials] if (obj.type == 'MESH' and hasattr(obj.data, "materials")) else []
        
        specs[obj.name] = {
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "part_type": obj.get("part_type"),
            "materials": mats,
            "location_local_mm": [round(loc.x * 1000.0, 3), round(loc.y * 1000.0, 3), round(loc.z * 1000.0, 3)],
            "rotation_euler_deg": [round(math.degrees(rot.x), 3), round(math.degrees(rot.y), 3), round(math.degrees(rot.z), 3)],
            "scale": [round(scale.x, 4), round(scale.y, 4), round(scale.z, 4)],
            "location_world_mm": [round(w_loc.x * 1000.0, 3), round(w_loc.y * 1000.0, 3), round(w_loc.z * 1000.0, 3)],
            "mesh": mesh_info,
        }
        
    out_file = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\all_custom_specs.json")
    out_file.write_text(json.dumps(specs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"All object specs exported to {out_file}")

if __name__ == "__main__":
    extract_all_object_specs()
