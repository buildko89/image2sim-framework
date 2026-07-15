# Task 5 進捗報告: Godot Import Check

- 作成日: 2026-06-22
- 状態: 完了
- 方針: Task 4で出力したGLBをGodotで読み込み、シーン上に表示できることを確認する

## 実装内容

- `scripts/05_godot_import_check.py` を追加した。
- `godot/GodotImportGuide.md` を追加した。
- `config/pipeline.yaml` に `godot_import_check` 設定を追加した。
- `output/godot/` をGodot確認用の配置先として整備した。
- `--dry-run` でGLBコピー前の計画確認ができるようにした。
- Task 4のGLBが存在する場合、`output/godot/` へコピーできるようにした。
- GodotでのGLB配置、シーン作成、表示確認項目を文書化した。

## 主要成果物

- `scripts/05_godot_import_check.py`
- `godot/GodotImportGuide.md`
- `output/godot/cat_clean.glb`
- `output/reports/godot_import_check_plan.json`
- `output/reports/godot_import_check.json`

## 実行方法

Dry-run:

```powershell
python scripts/05_godot_import_check.py --config config/pipeline.yaml --dry-run
```

GLBをGodot確認用ディレクトリへコピー:

```powershell
python scripts/05_godot_import_check.py --config config/pipeline.yaml
```

## Godotでの確認項目

- GLBをGodotに読み込める。
- 3Dシーン上でモデルが表示される。
- 足元または接地点が床面に合っている。
- スケールが極端に崩れていない。
- 向きが確認しやすい。
- テクスチャやマテリアルが破綻していない。

## 検証結果

- Python構文チェック: 成功
- dry-run実行: 成功
- 実GLBコピー: 未実行
- Godot Editorでの目視確認: 未実行

## 未実行理由

現在はTask 4の実出力 `output/clean_3d/cat_clean.glb` がまだ存在しないため、実GLBコピーとGodot Editorでの表示確認は行っていない。

## 次のTask

Task 6: Unity Import Check

UnityでGLB/FBXを読み込み、表示できることを確認する手順と成果物を整備する。
