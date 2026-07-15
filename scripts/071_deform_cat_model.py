from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return
    except ImportError:
        pass

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"
    load_env_file(env_path)

    blender_path = os.environ.get("BLENDER_PATH")
    if not blender_path:
        print("ERROR: BLENDER_PATH is not set in .env")
        return 1

    input_blend = repo_root / "output" / "rigged" / "cat_master_base.blend"
    if not input_blend.exists():
        print(f"ERROR: Input blend file does not exist: {input_blend}")
        return 1

    output_blend = repo_root / "output" / "rigged" / "cat_deformed.blend"
    output_glb = repo_root / "output" / "clean_3d" / "cat_deformed.glb"
    output_fbx = repo_root / "output" / "clean_3d" / "cat_deformed.fbx"
    report = repo_root / "output" / "reports" / "task71_cat_deformed.json"
    
    deform_script = repo_root / "blender" / "cat_master_deform.py"

    cmd = [
        blender_path,
        "-b",
        "-P",
        str(deform_script),
        "--",
        "--input",
        str(input_blend),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--report",
        str(report)
    ]

    print("Running Blender to deform cat model (short legs, round head, fluffy shell)...")
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )
    
    print(completed.stdout)
    if completed.stderr:
        print("Blender stderr:")
        print(completed.stderr)

    if completed.returncode == 0 and output_blend.exists() and output_glb.exists():
        print(f"\nSUCCESS: Deformed cat model created.")
        print(f"- Blend: {output_blend}")
        print(f"- GLB: {output_glb}")
        print(f"- FBX: {output_fbx}")
        
        # 1. 構造の検証
        inspect_glb_script = repo_root / "scripts" / "056_inspect_glb.py"
        if inspect_glb_script.exists():
            print("\nVerifying deformed GLB structure:")
            subprocess.run([
                sys.executable,
                str(inspect_glb_script),
                str(output_glb)
            ])
            
        # 2. Godotシーンへのコピー（Staging）
        godot_dir = repo_root / "godot" / "Godot3dcat"
        if godot_dir.exists():
            staged_glb = godot_dir / "cat_deformed.glb"
            import shutil
            shutil.copy2(output_glb, staged_glb)
            print(f"\nStaged deformed GLB to Godot project: {staged_glb}")
            
            # MainAppearance.tscn を更新して、新しい cat_deformed.glb を参照するようにする
            # MainAppearance.tscn の中にある GLB の参照パスを置換
            update_godot_scene_reference(godot_dir / "MainAppearance.tscn", "cat_deformed.glb")
            
        return 0
    else:
        print(f"\nFAILED: Blender process returned exit code {completed.returncode}")
        return 1

def update_godot_scene_reference(scene_path: Path, new_glb_name: str) -> None:
    if not scene_path.exists():
        print(f"Godot scene file not found: {scene_path}")
        return
        
    content = scene_path.read_text(encoding="utf-8")
    
    # [ext_resource type="PackedScene" uid="uid://..." path="res://cat_photo_camera_projection_bake_pass.glb" id="1_xxx"]
    # のような記述を探して、path="res://cat_deformed.glb" に書き換える。
    # 既存の GLB ファイル名（何であれ）を検出して置換する
    import re
    # res://*.glb というパターンを res://cat_deformed.glb に置き換える
    new_content, count = re.subn(
        r'path="res://[^"]+\.glb"',
        f'path="res://{new_glb_name}"',
        content
    )
    
    if count > 0:
        scene_path.write_text(new_content, encoding="utf-8")
        print(f"Updated Godot scene resource reference to: res://{new_glb_name} (replaced {count} instances)")
    else:
        # もし見つからなかった場合は、置換がうまくいかなかった
        print("Warning: Could not find resource path pattern in Godot scene to update.")

if __name__ == "__main__":
    sys.exit(main())
