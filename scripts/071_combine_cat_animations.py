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

    input_cat_dir = repo_root / "input" / "cat"
    fbx_dir = input_cat_dir / "uploads_files_1903704_FBX" / "fbx"
    
    if not fbx_dir.exists():
        print(f"ERROR: fbx directory does not exist: {fbx_dir}")
        return 1

    # アニメーションファイルのマッピングを定義
    # 複数のパス候補を設定し、存在するものを採用する
    candidates = {
        "Idle": [
            fbx_dir / "4_FashionCat" / "modnica_anim.fbx",
            fbx_dir / "modnica_anim.fbx",
            input_cat_dir / "uploads_files_1903704_FBX" / "Model" / "Modn_cat.fbx"
        ],
        "Walk": [
            fbx_dir / "3_HomeCat" / "houseCat_anim.fbx",
            fbx_dir / "houseCat_anim.fbx",
            input_cat_dir / "uploads_files_1903704_FBX" / "Model" / "House_cat.fbx"
        ],
        "Sleep": [
            fbx_dir / "1_FatCat" / "LazyCat_anim.fbx",
            fbx_dir / "LazyCat_anim.fbx",
            input_cat_dir / "uploads_files_1903704_FBX" / "Model" / "Lazy_cat.fbx"
        ],
        "Run": [
            fbx_dir / "2_ShustriyCat" / "Shustruj_animation.fbx",
            fbx_dir / "Shustruj_anim.fbx",
            input_cat_dir / "uploads_files_1903704_FBX" / "Model" / "Nimble_cat.fbx"
        ]
    }

    fbx_files = {}
    for label, paths in candidates.items():
        found = False
        for path in paths:
            if path.exists():
                fbx_files[label] = path
                found = True
                break
        if not found:
            print(f"ERROR: Could not find FBX file for action '{label}'")
            return 1

    print("Target files mapped:")
    for label, path in fbx_files.items():
        print(f"- {label}: {path.relative_to(repo_root)}")

    output_blend = repo_root / "output" / "rigged" / "cat_master_base.blend"
    
    inspect_script = repo_root / "blender" / "combine_cat_animations.py"
    
    # 引数を構築
    cmd_args = [str(output_blend)]
    for label, filepath in fbx_files.items():
        cmd_args.append(f"{label}={filepath}")
        
    cmd = [
        blender_path,
        "-b",
        "-P",
        str(inspect_script),
        "--"
    ] + cmd_args
    
    print("\nRunning Blender to combine animations...")
    completed = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False
    )
    
    print(completed.stdout)
    if completed.stderr:
        print("Blender stderr output:")
        print(completed.stderr)
        
    if completed.returncode == 0 and output_blend.exists():
        print(f"\nSUCCESS: Created combined master Blend file: {output_blend}")
        
        # 検証用にGLBとしても一時書き出しをテストする
        # (動作確認のため)
        test_export(blender_path, repo_root, output_blend)
        return 0
    else:
        print(f"\nFAILED: Blender process returned code {completed.returncode}")
        return 1

def test_export(blender_path: str, repo_root: Path, blend_path: Path):
    # 簡単なテストエクスポートスクリプトを実行してGLBが出せるかチェック
    export_py = """
import bpy
import os
import sys

bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index("--") + 1])
out_glb = sys.argv[sys.argv.index("--") + 2]

# テストエクスポート (Draco圧縮は無効化)
bpy.ops.export_scene.gltf(
    filepath=out_glb,
    export_format='GLB',
    export_animations=True,
    export_rest_position_armature=True,
    export_draco_mesh_compression_enable=False
)
print("TEST_EXPORT_SUCCESS")
"""
    temp_script = repo_root / "output" / "reports" / "temp_test_export.py"
    temp_script.parent.mkdir(parents=True, exist_ok=True)
    temp_script.write_text(export_py, encoding="utf-8")
    
    out_glb = repo_root / "output" / "rigged" / "cat_master_base_test.glb"
    
    subprocess.run([
        blender_path,
        "-b",
        "-P",
        str(temp_script),
        "--",
        str(blend_path),
        str(out_glb)
    ], capture_output=True)
    
    if temp_script.exists():
        temp_script.unlink()
        
    if out_glb.exists():
        print(f"Test export succeeded: {out_glb}")
        # GLB検証スクリプトがあれば走らせる
        inspect_glb_script = repo_root / "scripts" / "056_inspect_glb.py"
        if inspect_glb_script.exists():
            print("\nVerifying exported GLB structure:")
            subprocess.run([
                sys.executable,
                str(inspect_glb_script),
                str(out_glb)
            ])
    else:
        print("Test export to GLB failed.")

if __name__ == "__main__":
    sys.exit(main())
