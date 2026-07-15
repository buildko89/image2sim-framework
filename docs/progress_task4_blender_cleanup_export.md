# Task 4 進捗報告: Blender Cleanup and Export

- 作成日: 2026-06-22
- 状態: 完了
- 方針: Blenderで作成・編集したモデルをGodot / Unity / Unreal向けに正規化して出力する

## 実装内容

- `scripts/04_blender_cleanup_export.py` を追加した。
- `blender/cleanup_export.py` を追加した。
- `docs/game_engine_export_policy.md` を追加した。
- `.blend` / `.glb` / `.gltf` / `.fbx` / `.obj` を入力候補として扱えるようにした。
- `--dry-run` でBlenderを起動せずに計画確認できるようにした。
- メートル単位設定、X/Y原点寄せ、足元 `Z=0` 配置、目標高さへのスケール調整を実装した。
- `--remove-reference-objects` でTask 3の参照画像オブジェクトを削除できるようにした。
- `--apply-transforms` でスケール変換を適用できるようにした。
- GLBとFBXを出力できるようにした。
- Godot / Unity / Unreal向けのexport方針を文書化した。

## 主要成果物

- `scripts/04_blender_cleanup_export.py`
- `blender/cleanup_export.py`
- `docs/game_engine_export_policy.md`
- `output/clean_3d/cat_clean.glb`
- `output/clean_3d/cat_clean.fbx`
- `output/reports/blender_cleanup_export_plan.json`
- `output/reports/blender_cleanup_export.json`

## 実行方法

Dry-run:

```powershell
python scripts/04_blender_cleanup_export.py --config config/pipeline.yaml --dry-run
```

GLB/FBX出力:

```powershell
python scripts/04_blender_cleanup_export.py --config config/pipeline.yaml
```

参照画像オブジェクトを削除して出力:

```powershell
python scripts/04_blender_cleanup_export.py --config config/pipeline.yaml --remove-reference-objects
```

目標高さを指定:

```powershell
python scripts/04_blender_cleanup_export.py --config config/pipeline.yaml --target-height 1.2
```

## 検証結果

- Python構文チェック: 成功
- dry-run実行: 成功
- 実Blender出力: 未実行

## 未実行理由

現在はTask 3の実 `.blend` 出力がまだ存在せず、実画像と `BLENDER_PATH` を使ったBlender実行も未実施のため、実際のGLB/FBX生成は行っていない。

## 次のTask

Task 5: Godot Import Check

GLBをGodotに配置し、シーン上で表示できることを確認する手順と成果物を整備する。
