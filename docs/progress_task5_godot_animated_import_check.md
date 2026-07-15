# Task 5: Godot Animated Import Check 進捗

## 実施日

2026-06-22

## 目的

Task 4で出力したアニメーション付きGLBをGodot向けに配置し、Godotで表示・アニメーション再生確認を行える状態にする。

## 実施内容

1. Godot実行コマンドがPATH上にあるか確認した。
2. Godot本体はPATH上では見つからなかったため、自動起動確認は行わなかった。
3. Task 4出力の `output/clean_3d/cat_rigged_clean.glb` をGodot確認用ディレクトリへコピーした。
4. コピー後のGLBにanimation、skin、meshが残っていることを確認した。
5. Godot向け手順書をアニメーション付きGLB前提に更新した。
6. ユーザーがGodot上でモデル表示を目視確認した。

## 実行コマンド

```powershell
python scripts/05_godot_import_check.py --input output/clean_3d/cat_rigged_clean.glb --output-dir output/godot --overwrite
```

## 出力

- `output/godot/cat_rigged_clean.glb`
- `output/reports/godot_import_check.json`
- `godot/GodotImportGuide.md`

## GLB確認結果

- animation数: 12
- skin数: 1
- mesh数: 1

含まれるアニメーション:

- Attack
- Death
- Eating
- Gallop
- Gallop_Jump
- Idle
- Idle_2
- Idle_2_HeadLow
- Idle_HitReact1
- Idle_HitReact2
- Jump_ToIdle
- Walk

## Godotで確認する項目

- `cat_rigged_clean.glb` をGodot 4系プロジェクトに配置できる。
- シーンにインスタンス化して表示できる。
- スケールが極端に大きすぎない、または小さすぎない。
- 接地位置が大きく崩れていない。
- AnimationPlayerまたはインポートされたアニメーション一覧にクリップが表示される。
- `Idle`、`Walk`、`Jump_ToIdle` を再生できる。

## 判断

Task 5は、Godot向け配置、GLB構造確認、ユーザー目視表示確認として完了とする。

ユーザーがGodot上で「きつねが出てきた」ことを確認済み。これは現時点では想定通りで、現在の可動ベースモデルがQuaternius Foxであるため。

ただし、`Idle`、`Walk`、`Jump_ToIdle` の再生確認は未完了。

## 次のTask

Task 5.5: Cat Appearance Pass on Fox Rig
