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

    input_blend = repo_root / "output" / "rigged" / "cat_animated.blend"
    if not input_blend.exists():
        print(f"ERROR: Input blend file does not exist: {input_blend}")
        return 1

    output_blend = repo_root / "output" / "rigged" / "cat_final.blend"
    output_glb = repo_root / "output" / "clean_3d" / "cat_final.glb"
    output_fbx = repo_root / "output" / "clean_3d" / "cat_final.fbx"
    output_tex = repo_root / "output" / "textures" / "cat_calico_diffuse.png"
    report = repo_root / "output" / "reports" / "task72_cat_final.json"
    
    tex_script = repo_root / "blender" / "apply_calico_texture.py"

    cmd = [
        blender_path,
        "-b",
        "-P",
        str(tex_script),
        "--",
        "--input",
        str(input_blend),
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--output-fbx",
        str(output_fbx),
        "--output-tex",
        str(output_tex),
        "--report",
        str(report)
    ]

    print("Running Blender to generate calico texture and bake it...")
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
        print(f"\nSUCCESS: Calico texture baked and applied.")
        print(f"- Blend: {output_blend}")
        print(f"- GLB: {output_glb}")
        print(f"- FBX: {output_fbx}")
        print(f"- Texture: {output_tex}")
        
        # 1. 構造の検証
        inspect_glb_script = repo_root / "scripts" / "056_inspect_glb.py"
        if inspect_glb_script.exists():
            print("\nVerifying final GLB structure:")
            subprocess.run([
                sys.executable,
                str(inspect_glb_script),
                str(output_glb)
            ])
            
        # 2. Godotシーンへのコピー（Staging）
        godot_dir = repo_root / "godot" / "Godot3dcat"
        if godot_dir.exists():
            # Godotプロジェクトでは従来通り `cat_deformed.glb` を使っているので、
            # 完成した `cat_final.glb` を `cat_deformed.glb` に上書きコピーして即時反映させる
            staged_glb = godot_dir / "cat_deformed.glb"
            staged_tex = godot_dir / "cat_calico_diffuse.png"
            
            import shutil
            shutil.copy2(output_glb, staged_glb)
            shutil.copy2(output_tex, staged_tex)
            shutil.copy2(output_glb, godot_dir / "cat_final.glb")
            
            print(f"\nStaged final GLB and texture to Godot project:")
            print(f"- Staged GLB: {staged_glb}")
            print(f"- Staged Texture: {staged_tex}")
            
        return 0
    else:
        print(f"\nFAILED: Blender process returned exit code {completed.returncode}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
