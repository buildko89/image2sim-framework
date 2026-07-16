"""P4-4: レストから骨を回して新規ポーズ（お座り/香箱座り）のアクションを作る。

ポーズは JSON で与える（反復調整用）。世界軸回転を親→子の順に加算（頭は保持=罠㉓）。
四肢や胴の折り畳みは矢状面なので基本は world X 回転。左右対称は l/r 両方に同角度。
姿勢を作った後、全メッシュの最下点が床(Z=0)に来るようルート(bip01)を垂直移動して接地。
新規アクションに全ポーズ骨＋ルートをキーし、任意で呼吸の微動を足してループ化する。

JSON 例:
{
  "rotations": [["bip01_spine","X",40], ["bip01_l_thigh","X",-60], ...],
  "loop_frames": 120,
  "breathe_bones": ["bip01_spine1"], "breathe_deg": 2.0,
  "root_lift": "auto"
}

  blender --background --python pipeline_v2/p4_pose_action_blender.py -- \
    --input ... --output-blend ... --output-glb ... \
    --pose-json scratchpad/sit.json --action "Armature|Sit"
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

EXCLUDE = ("Whisker",)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output-blend", required=True)
    p.add_argument("--output-glb", required=True)
    p.add_argument("--pose-json", required=True)
    p.add_argument("--action", required=True)
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    return p.parse_args(argv)


def swing_inplace(pb, R) -> None:
    loc = pb.matrix.to_translation()
    rot = (R.to_3x3() @ pb.matrix.to_3x3()).to_4x4()
    pb.matrix = Matrix.Translation(loc) @ rot


def reset_pose(arm) -> None:
    if arm.animation_data:
        arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def meshes():
    return [o for o in bpy.context.scene.objects
            if o.type == "MESH" and not any(x in o.name for x in EXCLUDE)]


TAIL_BONES = {f"bone{i:03d}" for i in range(16, 21)}


def tail_vertex_mask(ob) -> set:
    """尻尾ボーンに 0.5 超のウェイトを持つ頂点 index（接地判定から除外する）。"""
    gidx = {vg.index for vg in ob.vertex_groups if vg.name in TAIL_BONES}
    if not gidx:
        return set()
    out = set()
    for v in ob.data.vertices:
        if sum(g.weight for g in v.groups if g.group in gidx) > 0.5:
            out.add(v.index)
    return out


def min_world_z(exclude_tail: bool = True) -> float:
    deps = bpy.context.evaluated_depsgraph_get()
    mn = 1e9
    for ob in meshes():
        skip = tail_vertex_mask(ob) if exclude_tail else set()
        ev = ob.evaluated_get(deps)
        me = ev.to_mesh()
        mw = ob.matrix_world
        for v in me.vertices:
            if v.index in skip:
                continue
            z = (mw @ v.co).z
            if z < mn:
                mn = z
        ev.to_mesh_clear()
    return mn


def lift_root(arm, dz_world: float) -> None:
    pb = arm.pose.bones["bip01"]
    delta = arm.matrix_world.to_3x3().inverted() @ Vector((0.0, 0.0, dz_world))
    m = pb.matrix.copy()
    m.translation = m.translation + delta
    pb.matrix = m
    bpy.context.view_layer.update()


def apply_rotation(arm, bone, axis, deg) -> None:
    swing_inplace(arm.pose.bones[bone], Matrix.Rotation(math.radians(deg), 4, axis))
    bpy.context.view_layer.update()


def main() -> int:
    a = parse_args()
    spec = json.loads(Path(a.pose_json).read_text(encoding="utf-8"))
    bpy.ops.wm.open_mainfile(filepath=a.input)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")

    reset_pose(arm)
    for bone, axis, deg in spec["rotations"]:
        apply_rotation(arm, bone, axis, float(deg))

    posed_bones = sorted({r[0] for r in spec["rotations"]})

    # 接地: 最下点が Z=0 になるようルートを持ち上げ/下げ
    if spec.get("root_lift", "auto") == "auto":
        mn = min_world_z(exclude_tail=True)
        lift_root(arm, -mn)
        print(f"[P4po] floor clamp(尻尾除外): body minZ {mn:+.4f} -> lift {-mn:+.4f}")
    elif spec.get("root_lift"):
        lift_root(arm, float(spec["root_lift"]))
    print(f"[P4po] posed bones: {posed_bones}  body minZ={min_world_z(True):+.4f}"
          f"  尻尾込み minZ={min_world_z(False):+.4f}（尻尾床は 0 付近が目標）")

    # 新規アクション（同名が既にあれば置換 = 正典を入力にしても Sit.001 が生えない）
    if not arm.animation_data:
        arm.animation_data_create()
    old = bpy.data.actions.get(a.action)
    if old is not None:
        bpy.data.actions.remove(old)
        print(f"[P4po] 既存アクション {a.action} を置換")
    act = bpy.data.actions.new(a.action)
    # 重要: fake user を立てないと、後続ツールが blend を開いた時に
    # 非アクティブの新規アクションが「未使用」として自動削除される
    # （実害: 2026-07-16 に Sit が消えて Godot で再生できなくなった）
    act.use_fake_user = True
    arm.animation_data.action = act
    try:
        slot = act.slots.new(id_type='OBJECT', name="pose")
        arm.animation_data.action_slot = slot
    except Exception as e:
        print("slot:", e)

    loop = int(spec.get("loop_frames", 120))
    breathe_bones = spec.get("breathe_bones", [])
    breathe_deg = float(spec.get("breathe_deg", 0.0))

    # ルート location と全ポーズ骨 rotation_quaternion をキー（frame1 と loop で同値=ループ）
    key_bones = posed_bones + ["bip01"]
    for f in (1, loop):
        for b in key_bones:
            arm.pose.bones[b].keyframe_insert("rotation_quaternion", frame=f)
        arm.pose.bones["bip01"].keyframe_insert("location", frame=f)

    # 呼吸: 中間フレームで胸を少し広げる（world X の微小回転を加算した値をキー）
    if breathe_bones and breathe_deg and loop > 4:
        mid = loop // 2
        base = {b: arm.pose.bones[b].rotation_quaternion.copy() for b in breathe_bones}
        for b in breathe_bones:
            swing_inplace(arm.pose.bones[b], Matrix.Rotation(math.radians(breathe_deg), 4, "X"))
        bpy.context.view_layer.update()
        for b in breathe_bones:
            arm.pose.bones[b].keyframe_insert("rotation_quaternion", frame=mid)
        for b in breathe_bones:  # 戻す（frame1/loop の値は既にキー済み）
            arm.pose.bones[b].rotation_quaternion = base[b]

    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(a.output_blend)))
    print(f"  Saved: {a.output_blend}")
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.export_scene.gltf(filepath=str(Path(a.output_glb)), export_format="GLB",
                              use_selection=True, export_animation_mode="ACTIONS")
    print(f"  Exported: {a.output_glb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
