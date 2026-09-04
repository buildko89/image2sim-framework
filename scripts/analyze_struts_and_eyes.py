import json

details = json.load(open('output/custom_mesh_details.json', encoding='utf-8'))

print("=== STRUTS ANALYSIS (CUSTOM MODEL) ===")
strut_names = [k for k in details if "strut" in k]
for sname in sorted(strut_names):
    info = details[sname]
    bbox = info["bbox_world_mm"]
    min_v = bbox["min"]
    max_v = bbox["max"]
    center = bbox["center"]
    print(f"\n[{sname}]")
    print(f"  World center: {center}")
    print(f"  World X span: {min_v[0]} ~ {max_v[0]}")
    print(f"  World Y span: {min_v[1]} ~ {max_v[1]}")
    print(f"  World Z span: {min_v[2]} ~ {max_v[2]}")
    print(f"  Local loc:    {info['location_mm']}")
    print(f"  Local rot:    {info['rotation_euler_deg']}")
    print(f"  Sample verts: {info['sample_verts_world_mm'][:4]}")

print("\n=== FRONT EYES ANALYSIS (CUSTOM MODEL) ===")
for ename in ("front_eye_fl", "front_eye_fr"):
    if ename in details:
        info = details[ename]
        bbox = info["bbox_world_mm"]
        print(f"\n[{ename}]")
        print(f"  World center: {bbox['center']}")
        print(f"  World X span: {bbox['min'][0]} ~ {bbox['max'][0]}")
        print(f"  World Y span: {bbox['min'][1]} ~ {bbox['max'][1]}")
        print(f"  World Z span: {bbox['min'][2]} ~ {bbox['max'][2]}")
        print(f"  Local loc:    {info['location_mm']}")
        print(f"  Local rot:    {info['rotation_euler_deg']}")
        print(f"  Sample verts: {info['sample_verts_world_mm'][:4]}")
