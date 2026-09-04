import json

data = json.load(open('output/all_custom_specs.json', encoding='utf-8'))

def inspect_group(title, keys):
    print(f"\n=================== {title} ===================")
    for k in keys:
        if k in data:
            item = data[k]
            mesh = item.get("mesh", {})
            print(f"\n[OBJECT: {k}]")
            print(f"  Parent:          {item['parent']}")
            print(f"  Local Location:  {item['location_local_mm']}")
            print(f"  Local Rotation:  {item['rotation_euler_deg']}")
            print(f"  World Center:    {mesh.get('world_center_mm')}")
            print(f"  World Size:      {mesh.get('world_size_mm')}")
            print(f"  World BBox Min:  {mesh.get('world_bbox_min_mm')}")
            print(f"  World BBox Max:  {mesh.get('world_bbox_max_mm')}")
            print(f"  Materials:       {item['materials']}")
            if "sample_verts_world_mm" in mesh and len(mesh["sample_verts_world_mm"]) > 0:
                print(f"  Vert Count:      {mesh['vertex_count']}")
                print(f"  Sample Verts:    {mesh['sample_verts_world_mm'][:6]}")

inspect_group("BODY & CANOPY", ["body_core", "body_canopy_cap", "battery_pack", "battery_codrone_label_plate"])
inspect_group("PROPELLER GUARDS", ["guard_side_left", "guard_side_right"])
inspect_group("MOTOR PODS & ROTORS", ["motor_fl", "motor_fl_housing", "motor_fl_red_cushion_ring", "rotor_fl_hub", "landing_leg_fl"])
inspect_group("FRONT EYES & SENSORS", ["front_eye_fl", "front_eye_fr", "front_ir_sensor_l_housing", "front_ir_sensor_l_lens", "front_ir_sensor_r_housing", "front_ir_sensor_r_lens"])
