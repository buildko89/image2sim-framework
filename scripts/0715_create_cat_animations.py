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

    input_blend = repo_root / "output" / "rigged" / "cat_deformed.blend"
    if not input_blend.exists():
        print(f"ERROR: Input blend file does not exist: {input_blend}")
        return 1

    output_blend = repo_root / "output" / "rigged" / "cat_animated.blend"
    output_glb = repo_root / "output" / "clean_3d" / "cat_animated.glb"
    output_fbx = repo_root / "output" / "clean_3d" / "cat_animated.fbx"
    report = repo_root / "output" / "reports" / "task715_cat_animated.json"
    
    anim_script = repo_root / "blender" / "create_cat_animations.py"

    cmd = [
        blender_path,
        "-b",
        "-P",
        str(anim_script),
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

    print("Running Blender to generate Punch and WakeUp/Threat animations...")
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
        print(f"\nSUCCESS: Custom cat animations generated.")
        print(f"- Blend: {output_blend}")
        print(f"- GLB: {output_glb}")
        print(f"- FBX: {output_fbx}")
        
        # 1. 構造の検証
        inspect_glb_script = repo_root / "scripts" / "056_inspect_glb.py"
        if inspect_glb_script.exists():
            print("\nVerifying animated GLB structure:")
            subprocess.run([
                sys.executable,
                str(inspect_glb_script),
                str(output_glb)
            ])
            
        # 2. Godotシーンへのコピー（Staging）
        # シーンファイルはすでに `cat_deformed.glb` を参照しているため、
        # 名前に `cat_deformed.glb` を使用して上書きコピーすることで、Godot側で追加されたアニメーションが即座に利用可能になります。
        godot_dir = repo_root / "godot" / "Godot3dcat"
        if godot_dir.exists():
            staged_glb = godot_dir / "cat_deformed.glb"
            import shutil
            shutil.copy2(output_glb, staged_glb)
            print(f"\nStaged animated GLB to Godot project: {staged_glb}")
            
            # また、コピー元として `cat_animated.glb` も格納しておく
            shutil.copy2(output_glb, godot_dir / "cat_animated.glb")
            
        return 0
    else:
        print(f"\nFAILED: Blender process returned exit code {completed.returncode}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
