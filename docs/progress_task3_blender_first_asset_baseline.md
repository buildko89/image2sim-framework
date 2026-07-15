# Task 3 進捗報告: Blender-first Asset Baseline

- 作成日: 2026-06-22
- 状態: 完了
- 方針: 無料・ローカル優先、Blender-first、有料3D生成APIは不使用

## 実装内容

- `scripts/03_blender_reference_scene.py` を追加した。
- `blender/create_reference_scene.py` を追加した。
- selected/masked images を収集し、Blender参照シーン作成の入力にできるようにした。
- `--dry-run` でBlenderを起動せずに計画確認できるようにした。
- `BLENDER_PATH` が設定されている場合、Windows `blender.exe` を background mode で起動できるようにした。
- 参照画像を textured planes または image empties として配置できるようにした。
- `.blend` 出力を標準出力にした。
- `--export-glb` 指定時にGLBプレビューも出力できるようにした。
- Tripo / Meshy / paid AI API はTask 3の実行経路から外した。

## 主要成果物

- `scripts/03_blender_reference_scene.py`
- `blender/create_reference_scene.py`
- `output/raw_3d/cat_reference_scene.blend`
- `output/raw_3d/cat_reference_scene.glb`
- `output/reports/blender_reference_scene_plan.json`
- `output/reports/blender_reference_scene.json`

## 実行方法

Dry-run:

```powershell
python scripts/03_blender_reference_scene.py --config config/pipeline.yaml --dry-run
```

`.blend` 作成:

```powershell
python scripts/03_blender_reference_scene.py --config config/pipeline.yaml
```

GLBも出力:

```powershell
python scripts/03_blender_reference_scene.py --config config/pipeline.yaml --export-glb
```

image emptiesとして配置:

```powershell
python scripts/03_blender_reference_scene.py --config config/pipeline.yaml --reference-mode empties
```

## 検証結果

- Python構文チェック: 成功
- dry-run実行: 成功
- 実Blender出力: 未実行

## 未実行理由

現在の `input/selected_photos/` と `input/masks/` には実画像がなく、`.gitkeep` のみ存在するため、実際の `.blend` / `.glb` 生成は行っていない。

## 次のTask

Task 4: Blender Cleanup and Export

Blenderで作成・編集したモデルをゲームエンジン向けに正規化し、GLB/FBXとして出力する工程へ進む。
