from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime

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

def find_3d_files(target_dir: Path) -> list[Path]:
    extensions = {".fbx", ".blend", ".glb", ".gltf", ".stl"}
    found_files = []
    # 再帰的に探索
    for path in target_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            # zip や rar の展開前ファイルはスキップ
            if "_FbxBlender.zip" in path.parts or "_FbxUnity.zip" in path.parts:
                continue
            # uploads_files_1903704_FBX などのフォルダの中身を優先
            found_files.append(path)
    return found_files

def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    env_path = repo_root / ".env"
    load_env_file(env_path)

    blender_path = os.environ.get("BLENDER_PATH")
    if not blender_path:
        print("ERROR: BLENDER_PATH is not set in .env")
        return 1

    input_cat_dir = repo_root / "input" / "cat"
    if not input_cat_dir.exists():
        print(f"ERROR: input/cat directory does not exist: {input_cat_dir}")
        return 1

    # 3Dアセットファイルを探索
    asset_files = find_3d_files(input_cat_dir)
    if not asset_files:
        print("No 3D files found in input/cat.")
        return 0

    print(f"Found {len(asset_files)} asset files to inspect:")
    for f in asset_files:
        print(f"- {f.relative_to(repo_root)}")

    output_dir = repo_root / "output" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    inspect_script = repo_root / "blender" / "inspect_cat_asset.py"
    
    results = []
    
    for asset_file in asset_files:
        rel_path = asset_file.relative_to(repo_root)
        print(f"\nInspecting: {rel_path}")
        
        # テンポラリ出力ファイル
        temp_json = output_dir / f"temp_inspect_{asset_file.stem}.json"
        if temp_json.exists():
            temp_json.unlink()
            
        cmd = [
            blender_path,
            "-b",
            "-P",
            str(inspect_script),
            "--",
            str(asset_file),
            str(temp_json)
        ]
        
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )
            
            if temp_json.exists():
                with open(temp_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
                temp_json.unlink()
                print(f"-> SUCCESS: meshes={data['meshes_count']}, armatures={data['armatures_count']}, actions={data['actions_count']}")
            else:
                print(f"-> FAILED (No report output)")
                print("Blender output:")
                print(completed.stdout)
                print(completed.stderr)
                results.append({
                    "filename": asset_file.name,
                    "filepath": str(asset_file),
                    "error": "Failed to generate inspection report from Blender",
                    "blender_stdout": completed.stdout,
                    "blender_stderr": completed.stderr
                })
        except subprocess.TimeoutExpired:
            print("-> TIMEOUT (60 seconds expired)")
            results.append({
                "filename": asset_file.name,
                "filepath": str(asset_file),
                "error": "Blender process timed out"
            })
        except Exception as e:
            print(f"-> ERROR: {str(e)}")
            results.append({
                "filename": asset_file.name,
                "filepath": str(asset_file),
                "error": str(e)
            })

    # 結果をJSONでマージ保存
    report_json_path = output_dir / "cat_assets_inspection_report.json"
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"\nSaved combined report to: {report_json_path}")

    # Markdownサマリーの作成
    summary_md_path = output_dir / "cat_assets_inspection_summary.md"
    create_markdown_summary(results, summary_md_path, repo_root)
    print(f"Saved Markdown summary to: {summary_md_path}")

    return 0

def create_markdown_summary(results: list, output_path: Path, repo_root: Path) -> None:
    lines = []
    lines.append("# input/cat 提供アセット調査サマリー (Task 70)")
    lines.append(f"\n調査実施日: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("\n`input/cat` 内にユーザーより提供された3Dモデルファイルを Blender 5.0 を用いて解析した結果です。")
    lines.append("\n## アセット一覧比較")
    lines.append("\n| ファイル名 | 拡張子 | メッシュ数 | ボーン数 | アニメーション数 | 備考 |")
    lines.append("|---|---|---|---|---|---|")
    
    for r in results:
        fname = r.get("filename", "Unknown")
        filepath = r.get("filepath", "")
        # 相対パスを取得
        try:
            rel_path = Path(filepath).relative_to(repo_root).as_posix()
            link = f"[{fname}](file:///{filepath.replace(os.sep, '/')})"
        except ValueError:
            link = fname
            
        ext = Path(filepath).suffix if filepath else "N/A"
        
        if "error" in r:
            lines.append(f"| {link} | {ext} | N/A | N/A | N/A | ❌ エラー: {r['error']} |")
        else:
            meshes_cnt = r.get("meshes_count", 0)
            armatures_cnt = r.get("armatures_count", 0)
            actions_cnt = r.get("actions_count", 0)
            
            # ボーン数
            bones_str = "0"
            if armatures_cnt > 0:
                bones_str = ", ".join([f"{a['name']}({a['bones_count']} bones)" for a in r.get("armatures", [])])
                
            note = ""
            if armatures_cnt > 0 and actions_cnt > 0:
                note = "✨ リグ・アニメーション付き"
            elif armatures_cnt > 0:
                note = "🦴 リグ付き（アニメなし）"
            elif meshes_cnt > 0:
                note = "📦 静的メッシュ"
                
            lines.append(f"| {link} | {ext} | {meshes_cnt} | {bones_str} | {actions_cnt} | {note} |")

    lines.append("\n## 詳細情報")
    
    for r in results:
        if "error" in r:
            continue
        fname = r.get("filename", "Unknown")
        lines.append(f"\n### {fname}")
        lines.append(f"- **パス**: `{r.get('filepath')}`")
        
        # メッシュ情報
        lines.append("- **メッシュ構成**:")
        for mesh in r.get("meshes", []):
            lines.append(f"  - `{mesh['name']}`: 頂点数 {mesh['vertices_count']}, ポリゴン数 {mesh['polygons_count']}")
            if mesh.get("materials"):
                lines.append(f"    - マテリアル: {', '.join(mesh['materials'])}")
                
        # アニメーション情報
        actions = r.get("actions", [])
        if actions:
            lines.append(f"- **アニメーション数**: {len(actions)}")
            lines.append("  - アクション名:")
            for act in actions:
                lines.append(f"    - `{act}`")
        else:
            lines.append("- **アニメーション**: なし")
            
    output_path.write_text("\n".join(lines), encoding="utf-8")

if __name__ == "__main__":
    sys.exit(main())
