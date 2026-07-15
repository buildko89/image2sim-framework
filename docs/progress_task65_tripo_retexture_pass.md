# Task 6.5: Tripo Texture Retexture Pass

## 目的

Tripo v2.5でダウンロードできたGLBのテクスチャを利用し、既存のアニメーション付き猫モデルに対して、projection / bake / retexture 系の可能性を確認する。

今回は短時間で検証できる範囲として、完全なメッシュ間プロジェクションではなく、Tripo GLBに埋め込まれているbase color textureを抽出し、それを既存リグ付き猫モデルの材質別テクスチャに変換してGLBへ焼き込む方式を試した。

## 実施内容

- Tripo v2.5 GLBから埋め込みbase color textureを抽出した。
- 抽出したTripo textureを元に、既存猫モデル用の4種類の材質テクスチャを生成した。
- 既存のアニメーション付き猫メッシュにUVを追加し、各材質へbase color textureを接続した。
- GLB / FBX / Blendを再出力した。
- Godot確認用GLBを配置し、`MainAppearance.tscn`の参照先を今回のGLBへ切り替えた。

## 追加・更新ファイル

- `scripts/065_cat_tripo_retexture_pass.py`
- `output/textures/task65_cat_tripo_retexture/tripo_base_color.jpg`
- `output/textures/task65_cat_tripo_retexture/white_fur.png`
- `output/textures/task65_cat_tripo_retexture/warm_calico_fur.png`
- `output/textures/task65_cat_tripo_retexture/dark_calico_fur.png`
- `output/textures/task65_cat_tripo_retexture/cream_shadow_fur.png`
- `output/rigged/cat_tripo_retexture_pass.blend`
- `output/clean_3d/cat_tripo_retexture_pass.glb`
- `output/clean_3d/cat_tripo_retexture_pass.fbx`
- `output/godot/cat_tripo_retexture_pass.glb`
- `godot/Godot3dcat/cat_tripo_retexture_pass.glb`
- `godot/Godot3dcat/MainAppearance.tscn`

## 検証結果

- GLB inspection:
  - material: 4
  - mesh: 2
  - skin: 1
  - animation: 12
  - 4材質すべてで`has_base_color_texture = true`
  - 各mesh primitiveに`TEXCOORD_0`あり
- Animation validation:
  - animations: 12
  - available motions: 3
  - fallback motions: 1
  - missing motions: 0
- Task 6.4とのside preview差分:
  - mean RGB diff: `[1.92, 1.80, 1.52]`
  - RMS RGB diff: `[10.90, 9.89, 9.08]`
  - 以前の「ほぼ変化なし」よりは明確に変化している

## プレビュー

- `output/reports/task65_cat_tripo_retexture_side_preview.png`
- `output/reports/task65_cat_tripo_retexture_front_preview.png`

## 評価

今回の方式では、Godotで見えるレベルのテクスチャ差分は作れた。ただし、自然な猫の毛並みとしてはまだ弱い。

主な理由は、Tripoのtexture atlasをそのまま既存メッシュへ正確に投影しているわけではなく、抽出した色・明暗・模様情報を既存モデルの材質単位に再利用しているため。色の濃淡や三毛柄の方向性は出るが、実画像に対する毛並み位置、顔周り、脚、背中、尻尾の模様位置までは合わない。

## 結論

このTask 6.5は「retexture / bake の入口」としては有効。GLBに実テクスチャを入れる経路、Godot表示、アニメーション維持は確認できた。

一方で、自然さを上げるには次のどちらかが必要。

1. 既存リグ付きメッシュへ、実画像またはTripoレンダー画像をカメラ投影して焼く。
2. Tripoまたは別AIで生成した高品質メッシュを、既存アニメーションリグに近づける方向へ進める。

現時点では、短期の次手は1の「参照写真ベースのカメラ投影bake」を試すのが妥当。Tripo textureは使えるが、今回のようなatlas再利用だけでは自然さに限界がある。
