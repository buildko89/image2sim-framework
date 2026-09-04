import json

d = json.load(open('output/custom_params_dump.json', encoding='utf-8'))
keys = [
    'body_core', 'body_canopy_cap', 'front_eye_fl', 'front_eye_fr',
    'front_ir_sensor_l_housing', 'front_ir_sensor_r_housing',
    'tail_light_panel', 'battery_pack', 'battery_codrone_label_plate',
    'guard_side_left', 'guard_side_right',
    'guard_fl_strut_01', 'guard_fl_strut_02',
    'bottom_optical_flow_sensor', 'bottom_ir_height_sensor'
]

print("=== KEY CUSTOM PARAMETERS ===")
for k in keys:
    if k in d:
        item = d[k]
        print(f"\n[{k}]")
        print(f"  world_center: {item['world_center_mm']}")
        print(f"  world_size:   {item['world_size_mm']}")
        print(f"  local_loc:    {item['local_loc_mm']}")
        print(f"  local_rot:    {item['local_rot_deg']}")
        print(f"  materials:    {item['materials']}")
