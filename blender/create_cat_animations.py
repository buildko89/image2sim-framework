import bpy
import os
import sys
import math
import argparse
from mathutils import Quaternion, Euler

def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    parser = argparse.ArgumentParser(description="Create custom cat animations (Punch, WakeUp/Threat).")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--output-glb", required=True)
    parser.add_argument("--output-fbx", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(argv)

def get_armature():
    arm = bpy.data.objects.get("Cat_Armature")
    if not arm:
        # 代替名での検索
        for obj in bpy.data.objects:
            if obj.type == 'ARMATURE':
                return obj
    return arm

def set_bone_rotation_deg(pose_bone, x, y, z):
    # Euler度数法からQuaternionへの安全な変換
    rad_x = math.radians(x)
    rad_y = math.radians(y)
    rad_z = math.radians(z)
    
    # 既存のレストポーズや初期角度を保ちつつ上書きするため、ボーンの初期回転モードに合わせる
    euler = Euler((rad_x, rad_y, rad_z), 'XYZ')
    
    if pose_bone.rotation_mode == 'QUATERNION':
        pose_bone.rotation_quaternion = euler.to_quaternion()
        pose_bone.keyframe_insert(data_path="rotation_quaternion")
    elif pose_bone.rotation_mode == 'AXIS_ANGLE':
        # 軸角モード（念のため）
        q = euler.to_quaternion()
        axis, angle = q.to_axis_angle()
        pose_bone.rotation_axis_angle = (angle, axis[0], axis[1], axis[2])
        pose_bone.keyframe_insert(data_path="rotation_axis_angle")
    else:
        pose_bone.rotation_euler = euler
        pose_bone.keyframe_insert(data_path="rotation_euler")

def copy_pose_at_frame(arm_obj, source_action_name, source_frame, target_frame):
    """他のアクションの特定フレームのポーズを現在のタイムラインの特定フレームにコピーする"""
    original_action = arm_obj.animation_data.action
    source_action = bpy.data.actions.get(source_action_name)
    
    if source_action:
        # 一時的にソースアクションを紐付けてポーズをロード
        arm_obj.animation_data.action = source_action
        bpy.context.scene.frame_set(source_frame)
        
        # ボーンのポーズを記憶
        bone_poses = {}
        for bone in arm_obj.pose.bones:
            bone_poses[bone.name] = {
                "loc": bone.location.copy(),
                "rot_q": bone.rotation_quaternion.copy(),
                "rot_e": bone.rotation_euler.copy(),
                "scale": bone.scale.copy()
            }
            
        # ターゲットアクションに戻す
        arm_obj.animation_data.action = original_action
        bpy.context.scene.frame_set(target_frame)
        
        # ポーズを適用してキーフレームを挿入
        for bone in arm_obj.pose.bones:
            if bone.name in bone_poses:
                p = bone_poses[bone.name]
                bone.location = p["loc"]
                bone.rotation_quaternion = p["rot_q"]
                bone.rotation_euler = p["rot_e"]
                bone.scale = p["scale"]
                
                # キーフレームの挿入
                if bone.rotation_mode == 'QUATERNION':
                    bone.keyframe_insert(data_path="rotation_quaternion")
                else:
                    bone.keyframe_insert(data_path="rotation_euler")
                bone.keyframe_insert(data_path="location")
                bone.keyframe_insert(data_path="scale")

def create_punch_animation(arm_obj):
    print("\nCreating Cat_Punch animation...")
    # 新しいアクションを作成
    action = bpy.data.actions.new(name="Cat_Punch")
    action.use_fake_user = True
    
    if not arm_obj.animation_data:
        arm_obj.animation_data_create()
    arm_obj.animation_data.action = action
    
    # 30フレームのアニメーション
    # 基本ポーズは Cat_Idle からコピー
    for f in [1, 5, 10, 14, 20, 30]:
        copy_pose_at_frame(arm_obj, "Cat_Idle", 1, f)
        
    # 右前足のボーン名
    hip_r = arm_obj.pose.bones.get("CatGirl2:frontHip_R")
    knee_r = arm_obj.pose.bones.get("CatGirl2:frontKnee_R")
    ankle_r = arm_obj.pose.bones.get("CatGirl2:frontAnkle_R")
    head = arm_obj.pose.bones.get("CatGirl2:Head_M")
    
    # --- フレーム 5: パンチのタメ (右前足を引く、肘を曲げる) ---
    bpy.context.scene.frame_set(5)
    if hip_r: set_bone_rotation_deg(hip_r, -25, -10, 15)
    if knee_r: set_bone_rotation_deg(knee_r, 45, 0, 0)
    if head: set_bone_rotation_deg(head, 0, 5, -10) # 頭を少し傾ける
    
    # --- フレーム 10: 振り上げ (右前足を前上方に持ち上げる、肘を曲げる) ---
    bpy.context.scene.frame_set(10)
    if hip_r: set_bone_rotation_deg(hip_r, 65, 15, -10)
    if knee_r: set_bone_rotation_deg(knee_r, 85, 0, 0)
    if head: set_bone_rotation_deg(head, 5, 10, -15)
    
    # --- フレーム 14: インパクト (勢いよく前に振り下ろして伸ばす) ---
    bpy.context.scene.frame_set(14)
    if hip_r: set_bone_rotation_deg(hip_r, -45, -20, 25)
    if knee_r: set_bone_rotation_deg(knee_r, 10, 0, 0) # 伸ばす
    if ankle_r: set_bone_rotation_deg(ankle_r, -30, 0, 0)
    if head: set_bone_rotation_deg(head, -10, -5, 10) # パンチと同時に少し頭を下げる
    
    # --- フレーム 20: 戻り始める (足を引く) ---
    bpy.context.scene.frame_set(20)
    if hip_r: set_bone_rotation_deg(hip_r, 10, 10, -10)
    if knee_r: set_bone_rotation_deg(knee_r, 35, 0, 0)
    if head: set_bone_rotation_deg(head, 0, 0, 0)
    
    print("Cat_Punch animation created.")

def create_wakeup_animation(arm_obj):
    print("\nCreating Cat_WakeUp animation...")
    # 新しいアクションを作成
    action = bpy.data.actions.new(name="Cat_WakeUp")
    action.use_fake_user = True
    
    arm_obj.animation_data.action = action
    
    # 60フレームのアニメーション
    # 初期フレームは Cat_Sleep (睡眠状態) からロード
    # 最終フレームは Cat_Idle (立ち待機) へ遷移
    for f in range(1, 15):
        # 1〜15フレームは睡眠状態をキープ
        copy_pose_at_frame(arm_obj, "Cat_Sleep", 1, f)
        
    for f in range(45, 61):
        # 45〜60フレームは立ち待機状態
        copy_pose_at_frame(arm_obj, "Cat_Idle", 1, f)
        
    head = arm_obj.pose.bones.get("CatGirl2:Head_M")
    neck = arm_obj.pose.bones.get("CatGirl2:Neck_M")
    back_a = arm_obj.pose.bones.get("CatGirl2:BackA_M")
    back_b = arm_obj.pose.bones.get("CatGirl2:BackB_M")
    root = arm_obj.pose.bones.get("CatGirl2:Root_M")
    
    # --- フレーム 20: 頭と首を少し持ち上げる (ドローンに気づいて顔を上げる) ---
    # 中間ポーズを作るため、15フレームから徐々に変化
    bpy.context.scene.frame_set(20)
    if head: set_bone_rotation_deg(head, 35, 0, 0) # 顔を上げる
    if neck: set_bone_rotation_deg(neck, 25, 0, 0)
    
    # --- フレーム 30: 上体を起こし始める (前足をつく) ---
    bpy.context.scene.frame_set(30)
    # 睡眠状態から立ち上がりへの中間をブレンド
    copy_pose_at_frame(arm_obj, "Cat_Idle", 1, 30)
    # 少し姿勢を低くして起き上がり途中感を出す
    if root:
        root.location.z -= 0.05
        root.keyframe_insert(data_path="location")
    if back_a: set_bone_rotation_deg(back_a, -15, 0, 0)
    if head: set_bone_rotation_deg(head, 15, 0, 0)
    
    # --- フレーム 40: 完全に立ち上がった直後の威嚇 ( Threat / 背中を丸める ) ---
    bpy.context.scene.frame_set(40)
    copy_pose_at_frame(arm_obj, "Cat_Idle", 1, 40)
    # 背中を丸める (猫の威嚇姿勢)
    if back_a: set_bone_rotation_deg(back_a, 25, 0, 0)
    if back_b: set_bone_rotation_deg(back_b, 15, 0, 0)
    if neck: set_bone_rotation_deg(neck, -15, 0, 0) # 首をすくめる
    if head: set_bone_rotation_deg(head, -10, 0, 0) # 顎を引いてにらむ
    if root:
        root.location.z += 0.02 # 少し背を高く見せる
        root.keyframe_insert(data_path="location")
        
    # --- フレーム 45: 威嚇キープ ---
    bpy.context.scene.frame_set(45)
    if back_a: set_bone_rotation_deg(back_a, 20, 0, 0)
    if back_b: set_bone_rotation_deg(back_b, 10, 0, 0)
    if neck: set_bone_rotation_deg(neck, -10, 0, 0)
    if head: set_bone_rotation_deg(head, -5, 0, 0)
    
    print("Cat_WakeUp animation created.")

def main():
    args = parse_args()
    
    print(f"Loading deformed blend: {args.input}")
    bpy.ops.wm.open_mainfile(filepath=args.input)
    
    arm_obj = get_armature()
    if not arm_obj:
        print("ERROR: Armature object not found.")
        sys.exit(1)
    print(f"Using armature: {arm_obj.name}")
    
    # アニメーション作成
    create_punch_animation(arm_obj)
    create_wakeup_animation(arm_obj)
    
    # デフォルトアクションを待機に戻す
    idle_act = bpy.data.actions.get("Cat_Idle")
    if idle_act:
        arm_obj.animation_data.action = idle_act
        
    # 保存
    os.makedirs(os.path.dirname(args.output_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.output_blend)
    print(f"\nSaved master animated Blend file: {args.output_blend}")
    
    # GLBエクスポート (Draco圧縮は無効化)
    # アニメーションをすべて含める
    bpy.ops.export_scene.gltf(
        filepath=args.output_glb,
        export_format='GLB',
        export_animations=True,
        export_rest_position_armature=True,
        export_draco_mesh_compression_enable=False
    )
    print(f"Exported GLB: {args.output_glb}")
    
    # FBXエクスポート
    bpy.ops.export_scene.fbx(
        filepath=args.output_fbx,
        bake_anim=True,
        add_leaf_bones=False
    )
    print(f"Exported FBX: {args.output_fbx}")
    
    # レポート作成
    actions = [a.name for a in bpy.data.actions if a.name.startswith("Cat_")]
    report_data = {
        "success": True,
        "actions_created": ["Cat_Punch", "Cat_WakeUp"],
        "total_actions_in_file": len(actions),
        "actions_list": actions,
        "output_glb": args.output_glb,
        "output_fbx": args.output_fbx
    }
    with open(args.report, "w", encoding="utf-8") as f:
        import json
        json.dump(report_data, f, indent=4, ensure_ascii=False)
    print("Report written.")

if __name__ == "__main__":
    main()
