# Godot3dcat プロジェクト確認 進捗

## 実施日

2026-06-22

## 目的

ユーザーが作成した `godot/Godot3dcat` プロジェクトを確認し、Task 5のGodot表示確認状況と次の課題を整理する。

## 確認したプロジェクト

- `godot/Godot3dcat/project.godot`
- `godot/Godot3dcat/cat_rigged_clean.glb`
- `godot/Godot3dcat/cat_rigged_clean.glb.import`

## 確認結果

- Godotプロジェクトは存在する。
- `cat_rigged_clean.glb` がプロジェクト直下に配置されている。
- Godotのimportファイルが生成されている。
- import設定では `animation/import=true` になっている。
- GLB本体には12本のanimation、1つのskin、1つのmeshが含まれている。
- Godot 4.6実行ファイルは次の場所に存在した。
  - `D:/Godot_v4.6-stable_mono_win64/Godot_v4.6-stable_mono_win64.exe`

## ユーザー確認結果

ユーザー側でGodot表示確認を行い、「きつねが出てきた」と報告があった。

これは現時点では想定通り。Task 3E以降の可動モデル土台はQuaterniusのFoxであり、Task 5はまずリグ付き・アニメーション付きモデルがGodotに表示できるかを確認する工程だったため。

## 追加したファイル

- `godot/Godot3dcat/Main.tscn`
- `godot/Godot3dcat/play_animation.gd`
- `godot/Godot3dcat/validate_import.gd`

## 追加内容

### Main.tscn

`cat_rigged_clean.glb` をインスタンス化し、ライトとカメラを置いた確認用シーン。

### play_animation.gd

起動時にGLB内の `AnimationPlayer` を探し、`Idle` を再生する。`Idle` が見つからない場合は最初のアニメーションを再生する。

### validate_import.gd

headless確認用にGLBをロードし、AnimationPlayerとアニメーション一覧を取得するための検証スクリプト。

## CLI確認

通常exeでのheadlessプロジェクト起動:

```powershell
D:/Godot_v4.6-stable_mono_win64/Godot_v4.6-stable_mono_win64.exe --headless --path godot/Godot3dcat --quit
```

結果:

- 終了コード: 0

console版での `--script` 実行:

```powershell
D:/Godot_v4.6-stable_mono_win64/Godot_v4.6-stable_mono_win64_console.exe --headless --path godot/Godot3dcat --script godot/Godot3dcat/validate_import.gd
```

結果:

- Godot側がsignal 11でクラッシュ。
- このためCLIによるアニメーション一覧取得は未完了。
- Editor上での目視確認を優先する。

## 判断

GodotプロジェクトへのGLB配置と表示確認は成立している。

ただし、現在表示されるのはFoxベースモデルであり、猫らしい外観にはまだなっていない。これはGodot側の問題ではなく、Blender側で外観・形状転写をまだ実施していないため。

## 次の課題

1. Godot上で `Main.tscn` を開き、`Idle` が再生されるか確認する。
2. `Walk`、`Jump_ToIdle` の再生確認を行う。
3. Foxベースから猫らしい外観へ寄せるBlender作業を開始する。
4. 必要ならTask 3Fの計画から、外観調整実装Taskを追加する。

## 結論

Task 5の「Godotで表示できること」はユーザー確認により達成済み。

次に本質的に必要なのは、ゲームエンジン連携ではなく、Foxベースのリグ付きモデルを猫らしく見せるためのBlender外観調整である。

このため、次の作業として `Task 5.5: Cat Appearance Pass on Fox Rig` をbacklogへ追加する。
