from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import bpy
from mathutils import Matrix


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ドローンBlendのObject階層とローター回転分離を検証します。")
    parser.add_argument("blend")
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def matrix_delta(left: Matrix, right: Matrix) -> float:
    return max(
        abs(float(left[row][column]) - float(right[row][column]))
        for row in range(4)
        for column in range(4)
    )


def main() -> int:
    args = parse_args()
    blend_path = Path(args.blend).resolve()
    bpy.ops.wm.open_mainfile(filepath=str(blend_path), load_ui=False)
    duplicate_collections = sorted(
        collection.name
        for collection in bpy.data.collections
        if collection.name.rsplit(".", 1)[-1].isdigit()
    )
    if duplicate_collections:
        raise AssertionError(f"重複suffix付きCollectionがあります: {duplicate_collections}")

    groove_errors = {
        obj.name: obj.parent.name if obj.parent else None
        for obj in bpy.data.objects
        if "__groove_" in obj.name
        and (obj.parent is None or obj.parent.name != obj.name.split("__groove_", 1)[0])
    }
    if groove_errors:
        raise AssertionError(f"groove parentが不正です: {groove_errors}")

    if "wing_root" in bpy.data.objects:
        wing_root = bpy.data.objects["wing_root"]
        wing_children = {child.name for child in wing_root.children}
        expected_wing_children = {
            obj.name
            for obj in bpy.data.objects
            if obj.name == "main_wing" or obj.name.startswith("wing_bracket_")
        }
        if wing_children != expected_wing_children:
            raise AssertionError(
                f"wing_root childrenが不正です: expected={sorted(expected_wing_children)}, actual={sorted(wing_children)}"
            )

    rotor_results: dict[str, dict[str, Any]] = {}
    spin_objects = sorted(
        (obj for obj in bpy.data.objects if obj.name.startswith("rotor_") and obj.name.endswith("_spin")),
        key=lambda item: item.name,
    )
    if not spin_objects:
        raise AssertionError("rotor_*_spinがありません。")
    for spin in spin_objects:
        rotor_id = spin.name[len("rotor_") : -len("_spin")]
        assembly = spin.parent
        if assembly is None or assembly.name != f"rotor_{rotor_id}":
            raise AssertionError(f"{spin.name}のassembly parentが不正です。")
        fixed_objects = [child for child in assembly.children if child != spin]
        spinning_objects = list(spin.children)
        expected_spinning = {f"rotor_{rotor_id}_blades", f"rotor_{rotor_id}_hub"}
        if {obj.name for obj in spinning_objects} != expected_spinning:
            raise AssertionError(f"{spin.name}の回転部品が不正です。")
        axis = bpy.data.objects.get(f"motor_{rotor_id}_axis")
        if axis is None or (axis.matrix_world.translation - spin.matrix_world.translation).length > 1e-9:
            raise AssertionError(f"{spin.name}とmotor axisの原点が一致しません。")

        fixed_before = {obj.name: obj.matrix_world.copy() for obj in fixed_objects}
        spinning_before = {obj.name: obj.matrix_world.copy() for obj in spinning_objects}
        spin.rotation_euler.z += math.radians(17.0)
        bpy.context.view_layer.update()
        fixed_delta = max(
            (matrix_delta(fixed_before[obj.name], obj.matrix_world) for obj in fixed_objects),
            default=0.0,
        )
        spinning_delta = min(
            (matrix_delta(spinning_before[obj.name], obj.matrix_world) for obj in spinning_objects),
            default=0.0,
        )
        if fixed_delta > 1e-9:
            raise AssertionError(f"{spin.name}の回転で固定部品が動きました: {fixed_delta}")
        if spinning_delta <= 1e-6:
            raise AssertionError(f"{spin.name}の回転部品が動いていません: {spinning_delta}")
        rotor_results[rotor_id] = {
            "fixed_objects": sorted(obj.name for obj in fixed_objects),
            "spinning_objects": sorted(obj.name for obj in spinning_objects),
            "fixed_matrix_delta": fixed_delta,
            "minimum_spinning_matrix_delta": spinning_delta,
        }

    print(f"HIERARCHY_QA=PASS model={blend_path.name} rotors={len(rotor_results)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
