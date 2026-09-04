import json

data = json.load(open('output/blend_diff_report.json', encoding='utf-8'))
modified = {k: v for k, v in data.items() if v.get('status') == 'MODIFIED'}
only_custom = {k: v for k, v in data.items() if v.get('status') == 'ONLY_IN_CUSTOM'}
only_origin = {k: v for k, v in data.items() if v.get('status') == 'ONLY_IN_ORIGIN'}

print(f"Total objects: {len(data)}, Modified: {len(modified)}, Only Custom: {len(only_custom)}, Only Origin: {len(only_origin)}")
print("\n=================== MODIFIED OBJECTS ===================")
for k, v in modified.items():
    loc_diff = [v['custom_world_center'][i] - v['origin_world_center'][i] for i in range(3)]
    size_diff = [v['custom_world_size'][i] - v['origin_world_size'][i] for i in range(3)]
    rot_diff = [v['custom_rot_deg'][i] - v['origin_rot_deg'][i] for i in range(3)]
    
    is_loc_changed = any(abs(d) > 0.01 for d in loc_diff)
    is_size_changed = any(abs(d) > 0.01 for d in size_diff)
    is_rot_changed = any(abs(d) > 0.01 for d in rot_diff)
    
    if is_loc_changed or is_size_changed or is_rot_changed:
        print(f"\n[OBJECT: {k}]")
        print(f"  Parent: origin={v['origin_parent']} -> custom={v['custom_parent']}")
        if is_loc_changed:
            print(f"  Center (mm):  origin={v['origin_world_center']} -> custom={v['custom_world_center']} (diff: {[round(d,2) for d in loc_diff]})")
        if is_size_changed:
            print(f"  Size (mm):    origin={v['origin_world_size']} -> custom={v['custom_world_size']} (diff: {[round(d,2) for d in size_diff]})")
        if is_rot_changed:
            print(f"  Rotation (deg): origin={v['origin_rot_deg']} -> custom={v['custom_rot_deg']}")

if only_custom:
    print("\n=================== ONLY IN CUSTOM ===================")
    for k, v in only_custom.items():
        print(f"  + {k}: {v['custom']['world_location_mm']}")

if only_origin:
    print("\n=================== ONLY IN ORIGIN ===================")
    for k, v in only_origin.items():
        print(f"  - {k}: {v['origin']['world_location_mm']}")
