from __future__ import annotations

import os
import subprocess
import sys
import shutil
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

    input_blend = repo_root / "output" / "rigged" / "cat_final.blend"
    if not input_blend.exists():
        print(f"ERROR: Input blend file does not exist: {input_blend}")
        return 1

    output_blend = repo_root / "output" / "rigged" / "cat_final.blend"
    output_glb = repo_root / "output" / "clean_3d" / "cat_final.glb"
    output_fbx = repo_root / "output" / "clean_3d" / "cat_final.fbx"
    
    scale_script = repo_root / "blender" / "scale_cat_model.py"

    cmd = [
        blender_path,
        "-b",
        "-P",
        str(scale_script),
        "--",
        "--input",
        str(input_blend),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx)
    ]

    print("Running Blender to scale the cat model to realistic dimensions...")
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

    if completed.returncode == 0 and output_glb.exists():
        print("\nSUCCESS: Model scaled successfully.")
        
        # Godotへコピー（Staging）
        godot_dir = repo_root / "godot" / "Godot3dcat"
        if godot_dir.exists():
            staged_glb = godot_dir / "cat_deformed.glb"
            shutil.copy2(output_glb, staged_glb)
            print(f"Staged scaled GLB to Godot project: {staged_glb}")
            
            # キャッシュ削除
            godot_cache = godot_dir / ".godot"
            if godot_cache.exists():
                shutil.rmtree(godot_cache)
                print("Cleared Godot project cache folder.")
                
        return 0
    else:
        print(f"\nFAILED: Blender process returned exit code {completed.returncode}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
