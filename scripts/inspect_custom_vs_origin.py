import bpy
import json
import math
from pathlib import Path

def analyze_blend(blend_path: Path) -> dict:
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    results = {}
    
    for obj in bpy.data.objects:
        # Calculate world bounding box and center
        if obj.type == 'MESH':
            verts_world = [obj.matrix_world @ v.co for v in obj.data.vertices]
            if verts_world:
                min_x = min(v.x for v in verts_world)
                max_x = max(v.x for v in verts_world)
                min_y = min(v.y for v in verts_world)
                max_y = max(v.y for v in verts_world)
                min_z = min(v.z for v in verts_world)
                max_z = max(v.z for v in verts_world)
            else:
                min_x = max_x = min_y = max_y = min_z = max_z = 0.0
        else:
            w_pos = obj.matrix_world.translation
            min_x = max_x = w_pos.x
            min_y = max_y = w_pos.y
            min_z = max_z = w_pos.z

        loc = obj.location
        rot = obj.rotation_euler
        w_loc = obj.matrix_world.translation

        results[obj.name] = {
            "type": obj.type,
            "parent": obj.parent.name if obj.parent else None,
            "part_type": obj.get("part_type"),
            "local_location_mm": [round(loc.x * 1000.0, 3), round(loc.y * 1000.0, 3), round(loc.z * 1000.0, 3)],
            "local_rotation_deg": [round(math.degrees(rot.x), 3), round(math.degrees(rot.y), 3), round(math.degrees(rot.z), 3)],
            "world_location_mm": [round(w_loc.x * 1000.0, 3), round(w_loc.y * 1000.0, 3), round(w_loc.z * 1000.0, 3)],
            "world_bbox_mm": {
                "min": [round(min_x * 1000.0, 3), round(min_y * 1000.0, 3), round(min_z * 1000.0, 3)],
                "max": [round(max_x * 1000.0, 3), round(max_y * 1000.0, 3), round(max_z * 1000.0, 3)],
                "center": [
                    round((min_x + max_x) / 2.0 * 1000.0, 3),
                    round((min_y + max_y) / 2.0 * 1000.0, 3),
                    round((min_z + max_z) / 2.0 * 1000.0, 3),
                ],
                "size": [
                    round((max_x - min_x) * 1000.0, 3),
                    round((max_y - min_y) * 1000.0, 3),
                    round((max_z - min_z) * 1000.0, 3),
                ],
            }
        }
    return results

def main():
    origin_path = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_origin\codrone.blend")
    custom_path = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric_custom\codrone.blend")
    
    print("--- Analyzing ORIGIN ---")
    origin_data = analyze_blend(origin_path)
    
    print("--- Analyzing CUSTOM ---")
    custom_data = analyze_blend(custom_path)
    
    diff_report = {}
    all_keys = sorted(set(origin_data.keys()) | set(custom_data.keys()))
    
    for key in all_keys:
        orig = origin_data.get(key)
        cust = custom_data.get(key)
        if orig and cust:
            diff_report[key] = {
                "status": "MODIFIED" if orig != cust else "UNCHANGED",
                "origin_world_loc": orig["world_location_mm"],
                "custom_world_loc": cust["world_location_mm"],
                "origin_world_size": orig["world_bbox_mm"]["size"],
                "custom_world_size": cust["world_bbox_mm"]["size"],
                "origin_world_center": orig["world_bbox_mm"]["center"],
                "custom_world_center": cust["world_bbox_mm"]["center"],
                "origin_local_loc": orig["local_location_mm"],
                "custom_local_loc": cust["local_location_mm"],
                "origin_rot_deg": orig["local_rotation_deg"],
                "custom_rot_deg": cust["local_rotation_deg"],
                "origin_parent": orig["parent"],
                "custom_parent": cust["parent"],
            }
        elif orig:
            diff_report[key] = {"status": "ONLY_IN_ORIGIN", "origin": orig}
        else:
            diff_report[key] = {"status": "ONLY_IN_CUSTOM", "custom": cust}
            
    output_path = Path(r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\blend_diff_report.json")
    output_path.write_text(json.dumps(diff_report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Diff report saved to {output_path}")

if __name__ == "__main__":
    main()
