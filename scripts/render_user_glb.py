import bpy
import math
from pathlib import Path

# Clear scene
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# Import GLB
glb_path = r"D:\source\repos\3DModelDevPJ\image2sim-framework\input\raw_photos\drone\quadrotor drone 3d model.glb"
bpy.ops.import_scene.gltf(filepath=glb_path)

# Calculate bounding box of imported model
all_mesh_objs = [o for o in bpy.data.objects if o.type == 'MESH']
min_x = min(min((o.matrix_world @ v.co).x for v in o.data.vertices) for o in all_mesh_objs)
max_x = max(max((o.matrix_world @ v.co).x for v in o.data.vertices) for o in all_mesh_objs)
min_y = min(min((o.matrix_world @ v.co).y for v in o.data.vertices) for o in all_mesh_objs)
max_y = max(max((o.matrix_world @ v.co).y for v in o.data.vertices) for o in all_mesh_objs)
min_z = min(min((o.matrix_world @ v.co).z for v in o.data.vertices) for o in all_mesh_objs)
max_z = max(max((o.matrix_world @ v.co).z for v in o.data.vertices) for o in all_mesh_objs)

cx = (min_x + max_x) / 2.0
cy = (min_y + max_y) / 2.0
cz = (min_z + max_z) / 2.0
span_x = max_x - min_x
span_y = max_y - min_y
span_z = max_z - min_z
max_span = max(span_x, span_y, span_z)

print(f"MODEL BOUNDS: X=[{min_x:.3f}, {max_x:.3f}], Y=[{min_y:.3f}, {max_y:.3f}], Z=[{min_z:.3f}, {max_z:.3f}]")
print(f"CENTER: ({cx:.3f}, {cy:.3f}, {cz:.3f}), MAX SPAN: {max_span:.3f}")

# Add lighting
light_data = bpy.data.lights.new(name="Sun", type='SUN')
light_data.energy = 4.0
light_obj = bpy.data.objects.new(name="Sun", object_data=light_data)
bpy.context.collection.objects.link(light_obj)
light_obj.rotation_euler = (math.radians(45), math.radians(30), math.radians(45))

# Camera setup
cam_data = bpy.data.cameras.new(name="Camera")
cam_obj = bpy.data.objects.new(name="Camera", object_data=cam_data)
bpy.context.collection.objects.link(cam_obj)
bpy.context.scene.camera = cam_obj

# Set camera to view model center
cam_obj.location = (cx + max_span * 1.5, cy - max_span * 1.5, cz + max_span * 1.2)
direction = (bpy.path.abspath("//") if False else None)
# Point camera to center
cam_obj.rotation_mode = 'XYZ'
cam_obj.rotation_euler = (math.radians(60), 0, math.radians(45))

bpy.context.scene.render.resolution_x = 800
bpy.context.scene.render.resolution_y = 800

out_path = r"D:\source\repos\3DModelDevPJ\image2sim-framework\output\codrone_parametric\user_glb_iso.png"
bpy.context.scene.render.filepath = out_path
bpy.ops.render.render(write_still=True)
print(f"Saved: {out_path}")
