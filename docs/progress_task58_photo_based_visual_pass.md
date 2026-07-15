# Task 5.8: Photo-Based Godot Visual Improvement Pass 進捗

## 実施日

2026-06-29

## 目的

`raw_photos` / `selected_photos` の実猫とGodot上のモデル差分が大きいため、アニメーション追加より先に見た目を改善する。

## 参照した特徴

代表写真から、対象猫は次の特徴として扱う。

- 長毛の三毛猫。
- 体は白が多い。
- 頭頂部、耳まわり、背中、腰に黒と茶のパッチがある。
- 顔は丸く、マズルは短い。
- 胴体はふわっと太い。
- 尻尾は短くするより、長くふさふさした縞っぽい尾。

参照画像:

- `input/selected_photos/reference_side_right_body_1698975320501.jpg`
- `input/selected_photos/reference_front_face_1763363798733.jpg`
- `input/selected_photos/reference_back_top_tail_1755598074234.jpg`
- `input/selected_photos/reference_side_standing_pattern_1713434749448.jpg`

## 実施内容

1. `output/rigged/cat_shape_pass.blend` を入力にした写真ベースのvisual passを追加した。
2. 体をやや幅広く、低くして長毛猫らしいボリュームへ寄せた。
3. 頭をさらに丸め、マズルの長さを弱めた。
4. 耳を少し低く、狐っぽい尖りを弱めた。
5. 参照猫に合わせ、尻尾は短縮ではなく長くふさふさした方向へ戻した。
6. マテリアルを白ベース三毛柄へ再割り当てした。
7. `MainAppearance.tscn` を `cat_visual_pass.glb` 参照へ切り替えた。
8. Godot側の強制マテリアル色も写真ベースの白、茶、黒、クリームへ更新した。

## 追加したファイル

- `blender/cat_visual_pass.py`
- `scripts/058_cat_visual_pass.py`
- `docs/progress_task58_photo_based_visual_pass.md`

## 出力

- `output/rigged/cat_visual_pass.blend`
- `output/clean_3d/cat_visual_pass.glb`
- `output/clean_3d/cat_visual_pass.fbx`
- `output/godot/cat_visual_pass.glb`
- `godot/Godot3dcat/cat_visual_pass.glb`
- `output/reports/task58_cat_visual_pass.json`
- `output/reports/task58_cat_visual_pass_plan.json`
- `output/reports/task58_cat_visual_animation_validation.json`
- `output/reports/task58_cat_visual_glb_inspection.json`

## 検証結果

`output/clean_3d/cat_visual_pass.glb`:

- animation数: 12
- skin数: 1
- mesh数: 1
- `Idle`: available
- `Walk`: available
- `Jump_ToIdle`: available
- sleep / lie-down: true clipなし。従来どおり `Eating` が仮fallback。

Godot:

- `D:/Godot_v4.6-stable_mono_win64/Godot_v4.6-stable_mono_win64.exe --headless --path godot/Godot3dcat --quit`
- 終了コード: 0

## 次の確認

Godot Editorで `MainAppearance.tscn` を再生し、以下を確認する。

- 白ベース三毛猫として以前より近づいたか。
- 尻尾が参照写真のふさふさした尾に近づいたか。
- 顔が丸く、狐っぽい長い鼻先が弱まったか。
- `1` `2` `3` `4` / `Space` / `R` のレビュー操作が引き続き使えるか。
- `Walk` と `Jump_ToIdle` でメッシュが破綻しないか。

## 判断

自動生成と構造検証は完了。

Godot上の目視確認待ち。
