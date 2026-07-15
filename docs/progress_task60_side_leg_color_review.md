# Task 6.0: 横向き足まわり補正と色改善方針

## 実施日

2026-06-30

## 依頼内容

1. `input/raw_photos/横.png` と `input/raw_photos/横1.png` を参照し、`cat_fluffy_shortleg_pass.glb` の横から見た足の違和感を実画像へ近づける。
2. `input/selected_photos/`、`input/raw_photos/` の実画像と比べて、全体色をどう近づけるべきか検討する。
3. 対応内容をMarkdownファイルで出力する。

補足: リポジトリ上では `横1.png` は見つからず、代わりに `input/raw_photos/横2.png` が存在したため、今回は `横.png` と `横2.png` を横向き参照として扱った。

## 横向き画像から見た特徴

- 実猫は長毛で、腹下の毛が低く垂れている。脚そのものが極端に短いだけでなく、上部の脚が毛でかなり隠れて見える。
- 前足は白く、細い棒ではなく、毛で少し太く丸く見える。
- 後足は尻尾・腰まわりの長毛と黒/茶の柄に埋もれ、足首の形がはっきり出すぎない。
- 横から見ると胸毛と首まわりのボリュームが大きく、前脚の上部を隠している。
- 尻尾はかなり太い plume tail で、現行リグの細い尻尾よりも毛量が強い。

## 実施した調整

対象スクリプト:

- `blender/cat_fluffy_shortleg_pass.py`

再生成した主な出力:

- `output/rigged/cat_fluffy_shortleg_pass.blend`
- `output/clean_3d/cat_fluffy_shortleg_pass.glb`
- `output/clean_3d/cat_fluffy_shortleg_pass.fbx`
- `output/godot/cat_fluffy_shortleg_pass.glb`
- `godot/Godot3dcat/cat_fluffy_shortleg_pass.glb`

追加した確認用スクリプト:

- `blender/render_glb_preview.py`

追加した確認用プレビュー:

- `output/reports/cat_fluffy_shortleg_side_preview.png`

具体的な変更:

- 脚圧縮を維持しつつ、足先が潰れすぎないよう脚の圧縮係数を `0.35` に調整した。
- 胴体、肩、胸、上脚をさらに少し下げて広げ、横から見たとき腹下と胸毛で脚上部が隠れるようにした。
- 下脚と足先を少し横・前後方向に広げ、実画像の丸い毛足に寄せた。
- `PhotoCat_Fur_Shell` 側も、胴体、胸、肩、上脚、下脚の膨らませ方を強め、脚だけが棒状に出る印象を減らした。
- フラットマテリアルの色を実画像寄りに微調整した。
  - 白毛: 少し明るく、クリーム寄りに変更。
  - 茶毛: 既存よりオレンジ寄りに変更。
  - 黒毛: 完全な黒ではなく、暗い茶黒寄りに変更。
  - 影色: 既存よりやや落ち着いたクリーム影に変更。

## 検証結果

`output/clean_3d/cat_fluffy_shortleg_pass.glb` のGLB検査結果:

- animation数: 12
- skin数: 1
- mesh数: 2
  - main mesh
  - fur shell mesh
- material数: 4
- base color texture: なし
- `Idle`、`Walk`、`Jump_ToIdle` は利用可能。
- sleep / lie-down 専用clipは従来どおり存在せず、`Eating` または `Idle_2_HeadLow` が暫定fallback。

レポート:

- `output/reports/task59_cat_fluffy_shortleg_pass.json`
- `output/reports/task59_cat_fluffy_shortleg_glb_inspection.json`
- `output/reports/task59_cat_fluffy_shortleg_animation_validation.json`

## 現行Frameworkで近づけられる範囲

今回の調整で、横から見たときの「脚が棒状に長く見える」印象は、腹下・胸毛・足先シルエットの方向から少し改善できた。

ただし、現行モデルは以下の制約が大きい。

- 元のリグ付きベースが低ポリゴンの四足動物モデルで、実猫の骨格・毛束とは形状差がある。
- `PhotoCat_Fur_Shell` は本物の毛ではなく、外側に複製メッシュを膨らませる近似表現。
- 色はGLB内のフラットなマテリアル色だけで、写真由来のテクスチャがない。
- 柄の境界もポリゴン単位の割り当てなので、実画像の細かい毛流れ、白毛の陰影、茶黒の混ざりは再現できない。

そのため、現行Frameworkだけで「実物にかなり近い色・毛流れ」まで持っていくのは難しい。短期的には形状・マテリアル色・大まかな柄配置の改善が限界。

## 色を実画像へ近づけるための推奨方針

### 短期: 現行Framework内でできること

1. マテリアル色を今回のように写真寄りへ調整する。
2. 横・正面・背面の写真を見ながら、黒/茶/白のポリゴン割り当て領域を手作業に近いルールで追加調整する。
3. Godotで見る照明条件を固定し、BlenderとGodotで色が変わりすぎないようにする。

この方針は軽く、アニメーション付きGLBを壊しにくい。一方で、写真らしさの上限は低い。

### 中期: BlenderでUV展開と手描き/投影テクスチャ

最も堅実な改善策は、現在のリグ付きメッシュにUVを用意し、実画像を見ながら2Kまたは4Kのbase color textureを作ること。

候補:

- Blender Texture Paintで白、茶、黒の境界を手作業で描く。
- 実画像を参照平面として置き、側面・正面・背面から投影してテクスチャ下地を作る。
- Krita / Photoshop / Substance PainterでUV画像を編集する。
- 完成したbase color textureをGLBへ埋め込む。

この方法なら、現行のアニメーションリグを維持したまま、色と柄の実物感をかなり上げられる。

### 長期: 別の3D生成/テクスチャ生成を併用

現行Frameworkだけでは難しい場合の選択肢:

- Hunyuan3Dなどのtexture生成付き経路を再検討し、実画像からより写真寄りの静的テクスチャモデルを作る。
- Tripo / Meshyなどのmulti-image対応サービスで、実猫に近いtextured assetを生成し、形状・色の参照として使う。
- 生成された静的モデルをそのまま使うのではなく、現在のリグ付きモデルへ色・柄・形状の参考として転写する。
- 必要なら、Blender上でリトポロジーまたは手動モデリングを行い、低ポリゴンベースの限界を超える。

MVPとしては、現在のリグ付きGLBを維持しつつ、BlenderでUV/テクスチャ作成へ進むのが最も安全。クラウド生成モデルは、最終アニメーション対象ではなく「見た目の参考」または「テクスチャ転写元」として使うのがよい。

## 次にやるなら

1. `cat_fluffy_shortleg_pass.glb` をGodotで確認し、横から見た前足・後足・腹下の印象を再レビューする。
2. 問題が足元に残る場合は、次は骨格ではなく下脚・足先・胸毛シェルの局所補正をさらに行う。
3. 色の本格改善に進む場合は、マテリアル色調整ではなくUV texture作成タスクに切り替える。
