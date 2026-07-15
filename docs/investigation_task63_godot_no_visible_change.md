# Task 6.3 Godotで差分が見えない問題の調査

## 実施日

2026-06-30

## 現象

Godotで `cat_tripo_reference_visual_pass.glb` を確認しても、前回の `cat_fluffy_shortleg_pass.glb` との差分が見えない。

## 調査結果

GLBファイル自体は別物だった。

- `output/clean_3d/cat_fluffy_shortleg_pass.glb`
- `output/clean_3d/cat_tripo_reference_visual_pass.glb`

`Get-FileHash` でhashが異なることを確認した。

Godot側にも新GLBは配置され、importファイルも存在していた。

- `godot/Godot3dcat/cat_tripo_reference_visual_pass.glb`
- `godot/Godot3dcat/cat_tripo_reference_visual_pass.glb.import`

ただし、`MainAppearance.tscn` に2つの問題があった。

1. `force_cat_materials = true`
   - `play_animation.gd` がGLB内のmaterialを無視し、固定色の `StandardMaterial3D` でsurface overrideしていた。
   - 固定色は旧モデル寄りの色で、Task 6.3のmaterial color変更がGodot上で見えなくなっていた。

2. ext_resourceのUIDが旧GLBのまま
   - pathは `res://cat_tripo_reference_visual_pass.glb` に変わっていたが、uidは旧 `cat_fluffy_shortleg_pass.glb` の `uid://cbn8v0pqx6plo` のままだった。
   - 新GLBのimport UIDは `uid://ct283i73stah7`。

## 修正

`godot/Godot3dcat/MainAppearance.tscn` を修正した。

- `uid://cbn8v0pqx6plo` から `uid://ct283i73stah7` へ変更。
- `force_cat_materials = true` から `force_cat_materials = false` へ変更。

修正後:

```text
[ext_resource type="PackedScene" uid="uid://ct283i73stah7" path="res://cat_tripo_reference_visual_pass.glb" id="1_cat"]
force_cat_materials = false
```

## 補足

Task 6.3の変更は、GLB内のmaterial colorとpolygon material assignmentを使っている。Godot側でsurface overrideを有効にすると、その差分は見えない。

今後、GLBの見た目を確認するときは、`force_cat_materials` を原則 `false` にする。

`force_cat_materials` は、GLB import materialが壊れた場合の緊急確認用としてのみ使う。

## 追加調査: 新旧GLBの見た目差分

Godot設定修正後も差が見えない可能性が高かったため、Blender preview画像同士でピクセル差分を確認した。

比較対象:

- 旧: `output/reports/cat_fluffy_shortleg_side_preview.png`
- 新: `output/reports/task63_cat_tripo_reference_side_preview.png`

結果:

```text
mean_rgb_diff: [0.8758, 1.2760, 1.9072]
rms_rgb_diff: [7.3075, 8.3598, 12.5097]
bbox: (206, 40, 483, 173)
```

平均差分はRGBで約1から2/255程度だった。これは目視ではほぼ分からない。

増幅差分画像:

- `output/reports/task63_vs_fluffy_side_diff_x12.png`

## 追加結論

Task 6.3はGLBとしては変化しているが、見た目の変化量が小さすぎる。Godotで変化がないように見えるのは自然。

つまり、現在の「フラットマテリアル色の微調整 + ポリゴン単位の柄変更 + fur shell微調整」では、Tripo参照の質感差を可動モデルへ十分に反映できない。

この方式で実画像やTripo v2.5参照に大きく近づけるのは難しい。次に進むなら、以下のどちらかに切り替える必要がある。

1. 差が明確に見えるほど大胆な手動風スタイル調整を行う。
   - 色・柄を大きく変える。
   - ただし、低ポリゴン/フラットマテリアルらしさは残る。

2. 本命としてtexture系の処理に進む。
   - UV / texture bake / projection / AI retexture のいずれか。
   - Tripoの毛流れや白毛の陰影を取り込むにはこちらが必要。

現時点では、Task 6.3の方針は「安全だが効果が薄い」と判断する。
