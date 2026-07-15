import bpy
import sys

def main():
    blend_file = sys.argv[-1]
    if not blend_file.endswith(".blend"):
        print("Please provide a .blend file as the last argument.")
        return
        
    bpy.ops.wm.open_mainfile(filepath=blend_file)
    
    print("\n=== Model Objects Inspection ===")
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH':
            print(f"Mesh: {obj.name}")
            print(f"  Scale: {obj.scale}")
            print(f"  Location: {obj.location}")
            print(f"  Dimensions: {obj.dimensions}")
            print(f"  Bounding Box Min/Max:")
            bbox = [obj.matrix_world @ mathutils.Vector(corner) for corner in obj.bound_box] if 'mathutils' in sys.modules else obj.bound_box
            # 簡易表示
            xs = [c[0] for c in obj.bound_box]
            ys = [c[1] for c in obj.bound_box]
            zs = [c[2] for c in obj.bound_box]
            print(f"    X: {min(xs):.4f} to {max(xs):.4f}")
            print(f"    Y: {min(ys):.4f} to {max(ys):.4f}")
            print(f"    Z: {min(zs):.4f} to {max(zs):.4f}")
            
        elif obj.type == 'ARMATURE':
            print(f"Armature: {obj.name}")
            print(f"  Scale: {obj.scale}")
            print(f"  Location: {obj.location}")

if __name__ == "__main__":
    main()
