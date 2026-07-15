# Task 5.9: Short Legs and Fluffy Fur Silhouette Pass 進捗

## 実施日

2026-06-29

## 目的

写真ベースの見た目改善後、ユーザー確認で「写真に近くなったが、足が長すぎる」「毛のふさふさ感がもう少し欲しい」と分かったため、Godot確認向けに追加の局所改善を行う。

## 実施内容

1. `output/rigged/cat_visual_pass.blend` を入力にした短足・ふさふさpassを追加した。
2. 足先を床付近に残したまま、脚vertex groupを強めに縦方向圧縮した。
3. 胴体と肩まわりを少し下げ、幅を増やして、長毛で脚が隠れる印象を強めた。
4. ふさふさ感のため、同じarmatureに追従する外側の `PhotoCat_Fur_Shell` メッシュを追加した。
5. 初回版ではfur shellが白一色で本体の三毛色を覆ってしまったため、shell側も `cat_visual_pass` の三毛マテリアル割り当てを保持するよう修正した。
5. `MainAppearance.tscn` を `cat_fluffy_shortleg_pass.glb` 参照へ切り替えた。
6. Godot headless起動で読み込みを確認した。

## 追加したファイル

- `blender/cat_fluffy_shortleg_pass.py`
- `scripts/059_cat_fluffy_shortleg_pass.py`
- `docs/progress_task59_shortleg_fluffy_pass.md`

## 出力

- `output/rigged/cat_fluffy_shortleg_pass.blend`
- `output/clean_3d/cat_fluffy_shortleg_pass.glb`
- `output/clean_3d/cat_fluffy_shortleg_pass.fbx`
- `output/godot/cat_fluffy_shortleg_pass.glb`
- `godot/Godot3dcat/cat_fluffy_shortleg_pass.glb`
- `output/reports/task59_cat_fluffy_shortleg_pass.json`
- `output/reports/task59_cat_fluffy_shortleg_pass_plan.json`
- `output/reports/task59_cat_fluffy_shortleg_animation_validation.json`
- `output/reports/task59_cat_fluffy_shortleg_glb_inspection.json`

## 検証結果

`output/clean_3d/cat_fluffy_shortleg_pass.glb`:

- animation数: 12
- skin数: 1
- mesh数: 2
  - main mesh
  - fur shell mesh
- `Idle`: available
- `Walk`: available
- `Jump_ToIdle`: available
- sleep / lie-down: true clipなし。従来どおり `Eating` が仮fallback。

## 形状変更の実測

`output/reports/task59_cat_fluffy_shortleg_pass.json` より:

- 脚の圧縮係数: 0.33
- 脚vertex対象数: 1415
- body/shoulderを下げて、脚が長く見えにくい方向に調整。
- `PhotoCat_Fur_Shell` を追加し、外側シルエットを膨らませた。
- `PhotoCat_Fur_Shell` は白一色ではなく、main meshと同じ三毛マテリアル分割を保持する。

## 次の確認

Godot Editorで `MainAppearance.tscn` を再生し、以下を確認する。

- 足が以前より短く見えるか。
- ふさふさ感が増えたか。
- `Walk` で脚や外側シェルが破綻しないか。
- `Jump_ToIdle` でシェルが大きくずれないか。

## 注意点

ふさふさ感は実毛シミュレーションではなく、skinned meshの外側シェルでシルエットを膨らませるMVP向け表現。

Godotで二重メッシュ感が強すぎる場合は、シェル膨らませ量を下げる。
