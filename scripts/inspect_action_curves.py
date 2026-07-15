import bpy
import sys

def main():
    bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
    
    print("\n=== Model Dimensions Inspection ===")
    for obj in bpy.context.scene.objects:
        if obj.type in ['ARMATURE', 'MESH']:
            print(f"Object: {obj.name}")
            print(f"  Type: {obj.type}")
            print(f"  Scale: {obj.scale}")
            print(f"  Dimensions: {obj.dimensions}")
            print(f"  Parent: {obj.parent.name if obj.parent else 'None'}")
            if obj.type == 'MESH':
                print(f"    Vertex count: {len(obj.data.vertices)}")
                # 最初の数個の頂点座標
                if len(obj.data.vertices) > 0:
                    print(f"    Sample vertex 0: {obj.data.vertices[0].co}")

if __name__ == "__main__":
    main()
