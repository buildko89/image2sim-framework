# Task 6.6: Tripo Projection Bake Pass

## 目的

Tripo v2.5 GLBのテクスチャを、既存のアニメーション付き猫モデルへprojection / bakeする検証を行う。

Task 6.5ではTripo textureを抽出して材質別に再利用したが、厳密なメッシュ間投影ではなかった。今回はBlenderのselected-to-active bakeを使い、Tripo参照メッシュから既存リグ付きメッシュへ色を焼き込む方式を試した。

## 実施内容

- `output/rigged/cat_tripo_reference_visual_pass.blend`を入力にした。
- シーン内で横に置いていたTripo参照メッシュを、既存猫メッシュのバウンディングボックスへ一時的に整列した。
- 既存猫メッシュとfur shellに`ProjectionBakeUV`を作成した。
- Tripo参照メッシュをsource、既存猫メッシュをactive targetとしてDiffuse Color bakeを実行した。
- 焼き込んだtextureをGLBに入れて、アニメーション付きGLB / FBX / Blendを再出力した。
- Godot確認用にGLBをコピーし、`MainAppearance.tscn`の参照先をprojection bake版へ切り替えた。

## 追加ファイル

- `blender/cat_tripo_projection_bake_pass.py`
- `scripts/066_cat_tripo_projection_bake_pass.py`
- `output/textures/task66_cat_tripo_projection_bake/Fox_tripo_projection_bake.png`
- `output/textures/task66_cat_tripo_projection_bake/PhotoCat_Fur_Shell_tripo_projection_bake.png`
- `output/rigged/cat_tripo_projection_bake_pass.blend`
- `output/clean_3d/cat_tripo_projection_bake_pass.glb`
- `output/clean_3d/cat_tripo_projection_bake_pass.fbx`
- `output/godot/cat_tripo_projection_bake_pass.glb`
- `godot/Godot3dcat/cat_tripo_projection_bake_pass.glb`

## 検証結果

- GLB inspection:
  - material: 2
  - mesh: 2
  - skin: 1
  - animation: 12
  - 2材質とも`has_base_color_texture = true`
  - 各mesh primitiveに`TEXCOORD_0`あり
- Animation validation:
  - animations: 12
  - available motions: 3
  - fallback motions: 1
  - missing motions: 0
- Task 6.5とのside preview差分:
  - mean RGB diff: `[2.99, 2.77, 2.36]`
  - RMS RGB diff: `[16.76, 15.82, 14.23]`

## プレビュー

- `output/reports/task66_cat_tripo_projection_bake_side_preview.png`
- `output/reports/task66_cat_tripo_projection_bake_front_preview.png`

## 評価

projection bake自体は成功した。Tripo texture由来の模様が既存アニメーションモデルに焼き込まれ、Task 6.5よりも表面上の色変化は大きい。

ただし完成品質ではない。Tripoメッシュと既存猫メッシュは形状が一致していないため、単純なバウンディングボックス整列では顔、首、背中、脚の対応位置がずれる。結果として、顔周りが暗くなりすぎ、模様も自然な毛流れというより投影ムラに近い。

## 結論

今回の検証で、Framework上でも「Tripo textureをsourceにしたprojection bake」は実行可能だと確認できた。一方で、自然な見た目にするには、単純なselected-to-active bakeだけでは足りない。

次に改善するなら、以下の順が妥当。

1. Tripo meshと既存rig meshの位置合わせを手動ルールで改善する。
2. bake後のtextureに対して、黒つぶれ補正、明度補正、UV島のmargin拡張を入れる。
3. 実写真の横・正面画像からcamera projection bakeを試し、Tripo textureは補助情報として使う。

現時点でGodot確認対象は`godot/Godot3dcat/cat_tripo_projection_bake_pass.glb`。
