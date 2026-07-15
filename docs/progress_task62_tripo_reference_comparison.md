# Task 6.2: Tripo v2.5参照比較と採用方針

## 実施日

2026-06-30

## 目的

Tripo v2.5でdownloadできたtexture付きGLBを、現行の可動モデル `cat_fluffy_shortleg_pass.glb` と実画像に並べて比較し、次の見た目改善passで何を採用するか決める。

このTaskでは、Tripo GLBを最終可動モデルに置き換えない。あくまで、既存リグ付きモデルの改善に使える参照情報を抽出する。

## 比較対象

実画像:

- `input/raw_photos/横.png`
- `input/selected_photos/reference_front_face_1763363798733.jpg`

現行可動モデル:

- `output/clean_3d/cat_fluffy_shortleg_pass.glb`

Tripo v2.5参照:

- `output/raw_3d/cloud_manual/tripo/calico_cat_v25/calico_cat_v25.glb`

確認画像:

- `output/reports/task62_tripo_reference_comparison_sheet.jpg`
- `output/reports/cat_fluffy_shortleg_side_preview.png`
- `output/reports/cat_fluffy_shortleg_front_preview.png`
- `output/reports/task61_tripo_v25_side_preview.png`
- `output/reports/task61_tripo_v25_front_preview.png`

## GLB性質の確認

Tripo v2.5 GLB:

- generator: `Tripo`
- mesh数: 1
- material数: 1
- base color texture: あり
- skin数: 0
- animation数: 0

結論:

- texture付き静的参照として使う。
- 直接の最終可動モデル、Godotアニメーション対象、リグ付き置換モデルとしては使わない。

## 比較結果

### 現行可動モデルの強み

- 12 animationとskinを維持している。
- Godot確認済みの可動モデルとして使える。
- 低ポリゴンで軽く、ゲームエンジン側で扱いやすい。
- 足の短さ、腹下シルエット、ふさふさshellは最低限成立している。

### 現行可動モデルの弱み

- フラットマテリアル中心で、実画像の毛流れや陰影がない。
- 三毛柄の境界がポリゴン単位で硬い。
- 白毛の細かいクリーム影、胸毛、腹毛の流れが表現できていない。
- 顔の丸さや長毛の密度は実猫より弱い。

### Tripo v2.5参照の強み

- base color textureを持ち、毛流れ・縦筋・白毛の陰影が見える。
- 長毛猫としての見た目情報が現行可動モデルより多い。
- 白、茶、黒の三毛らしさがフラットマテリアルより自然。
- 胸毛、腹毛、胴体側面の毛束感が参考になる。
- 正面のふっくらした胸・顔まわりのボリュームは、実画像との方向性が近い。

### Tripo v2.5参照の弱み

- 尻尾が実画像よりかなり誇張され、形状参照としては危険。
- 口、顔、目周りに生成AI特有の崩れがある。
- 前脚、後脚、足先はそのまま採用できる精度ではない。
- skin / animationがなく、既存の可動パイプラインには直接乗らない。
- 実猫固有の柄位置とは一致しない。特に顔・背中・尻尾の柄は参考止まり。

## 採用する要素

次の要素は、次の可動モデル改善passで参照する価値がある。

1. 白毛の色味と陰影
   - 完全な白ではなく、クリーム、薄い灰色、毛束影を混ぜる。

2. 茶毛の彩度
   - 現行より少し暖かいオレンジ茶を使う。
   - ただしTripoほど濃くしすぎない。

3. 黒毛の扱い
   - 真っ黒ではなく、茶黒・灰黒寄りの暗色にする。

4. 胸毛と腹毛の毛流れ
   - 縦方向の筋、胸から下へ落ちる毛束感を参考にする。

5. 胴体側面の長毛ボリューム
   - 実画像に近いのは、脚そのものより腹下の毛が脚を隠す方向。

6. 正面のふっくら感
   - 顔・胸・首まわりは、現行可動モデルより少し丸く見せたい。

## 採用しない要素

次の要素は採用しない。

1. Tripoの尻尾形状
   - 実画像より過剰に広がり、別の造形になっている。

2. Tripoの顔・口まわり
   - 生成崩れがあり、そのまま参考にすると不自然になる。

3. Tripoの脚形状
   - 可動モデルへ直接転写できない。

4. Tripo meshそのもの
   - skin / animationなし。最終モデルへの置換対象ではない。

5. Tripoの柄位置を完全コピーすること
   - 実猫固有の柄とは違うため、色味と毛流れだけを抽出する。

## 次の実装方針

次は `cat_tripo_reference_visual_pass` を作るのがよい。

目的:

- Tripo v2.5のtexture情報を見ながら、既存可動モデルの見た目を一段改善する。
- ただし、アニメーション・skin・Godot互換性を壊さない。

安全な初回実装範囲:

1. material colorの再調整
   - 白毛を明るくしすぎず、クリーム影を増やす。
   - 茶毛を実画像とTripoの中間へ寄せる。
   - 黒毛を少し茶黒寄りにする。

2. polygon material assignmentの改善
   - 背中と胴体側面の茶/黒patchを実画像寄りに再配置する。
   - 顔中央は白を残し、左右の三毛capを少し調整する。

3. fur shellの局所強化
   - 胸毛、腹毛、胴体側面の下方向ボリュームを増やす。
   - 脚を伸ばすのではなく、腹毛で脚が隠れる方向にする。

4. Tripoを参照オブジェクトとしてBlend内に残す
   - GLB/FBX exportからは除外する。
   - 手動確認や今後の自動比較に使えるようにする。

今回は見送ること:

- 自動texture transfer。
- UV展開と本格texture bake。
- Tripo meshへのリギング。
- Hunyuan3D texture生成。

## Hunyuan3Dの扱い

現時点では、Hunyuan3Dはまだ使わない。

理由:

- Tripo v2.5から、textureと毛流れの参照情報は得られた。
- まず取得済みのTripo情報を既存可動モデルへ反映する方が効率的。
- Hunyuan3D texture生成は、セットアップ負荷とVRAM負荷が高い可能性がある。

Hunyuan3Dを再開する条件:

- Tripo参照を使った改善後も、実画像との差が大きい。
- 現行モデルのtexture表現をさらに上げる必要がある。
- Cloud/Web UI無料枠で追加downloadできる手段がなくなった。

## 次タスク案

Task 6.3: Tripo Reference Visual Pass

出力予定:

- `blender/cat_tripo_reference_visual_pass.py`
- `scripts/063_cat_tripo_reference_visual_pass.py`
- `output/rigged/cat_tripo_reference_visual_pass.blend`
- `output/clean_3d/cat_tripo_reference_visual_pass.glb`
- `output/clean_3d/cat_tripo_reference_visual_pass.fbx`
- `output/reports/task63_cat_tripo_reference_visual_pass.json`
- `output/reports/task63_cat_tripo_reference_visual_glb_inspection.json`
- `output/reports/task63_cat_tripo_reference_side_preview.png`
- `output/reports/task63_cat_tripo_reference_front_preview.png`
