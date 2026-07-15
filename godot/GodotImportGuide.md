# Godot Import Guide

## 目的

Task 5では、Task 4で出力したアニメーション付きGLBをGodotに読み込み、シーン上で表示できることと、基本アニメーションを再生できることを確認する。

## 前提

- Task 4で `output/clean_3d/cat_rigged_clean.glb` が作成されている。
- Godot 4系のプロジェクトをローカルで作成できる。
- 最初の確認では自動化よりも、表示、スケール、原点、向き、アニメーション再生の目視確認を優先する。

## Godot向けGLB配置手順

1. Task 5の準備スクリプトをdry-runする。

```powershell
python scripts/05_godot_import_check.py --input output/clean_3d/cat_rigged_clean.glb --dry-run
```

2. Task 4のGLBが存在する状態で、Godot確認用ディレクトリへコピーする。

```powershell
python scripts/05_godot_import_check.py --input output/clean_3d/cat_rigged_clean.glb --overwrite
```

3. `output/godot/cat_rigged_clean.glb` をGodotプロジェクトの `res://assets/` などに配置する。

4. Godot EditorでGLBを選択し、インポートが完了していることを確認する。

5. 新規3Dシーンを作成し、GLBをシーンへドラッグしてインスタンス化する。

6. 表示確認を行う。

確認項目:

- モデルがビューポートに表示される。
- 足元または接地点が床面に合っている。
- スケールが極端に大きすぎたり小さすぎたりしない。
- 向きが確認しやすい。
- テクスチャやマテリアルが破綻していない。
- `AnimationPlayer` またはインポートされたAnimation一覧にクリップが表示される。
- `Idle`、`Walk`、`Jump_ToIdle` のいずれかを再生できる。

## 推奨シーン設定

- `Node3D` をルートにする。
- `DirectionalLight3D` を追加する。
- `Camera3D` を追加し、モデル全体が見える位置に置く。
- 必要なら `MeshInstance3D` またはインスタンス化したGLBのTransformを一時的に調整して確認する。

## 判定

Pass:

- GLBをGodotに読み込める。
- シーン上でモデルが表示される。
- 原点、スケール、向きに重大な問題がない。
- `Idle`、`Walk`、`Jump_ToIdle` の基本アニメーションが再生できる。

Needs Fix:

- 読み込みに失敗する。
- モデルが表示されない。
- スケールが極端に崩れている。
- 足元原点または接地がTask 4方針と合っていない。
- アニメーション一覧が空になる。
- skin/armatureが壊れてアニメーション再生時にモデルが破綻する。

## 記録

Task 5スクリプトは以下を出力する。

```text
output/reports/godot_import_check_plan.json
output/reports/godot_import_check.json
output/godot/cat_rigged_clean.glb
```

Godot Editor上の目視結果は、必要に応じて `docs/progress_task5_godot_import_check.md` に追記する。
