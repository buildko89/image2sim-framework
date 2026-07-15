# 見た目基準画像選定 進捗

## 実施日

2026-06-22

## 目的

`input/raw_photos/` と `input/raw_photos/video_frames/` から、Task 3F以降で猫の見た目基準に使える画像を選ぶ。

## 実施内容

1. `input/raw_photos/` と `input/raw_photos/video_frames/` の132枚を対象にした。
2. コンタクトシートを作成して全体を確認した。
3. 体型、顔、背面、尻尾、動作補助の観点で候補を絞った。
4. 原寸で主要候補を確認した。
5. 8枚を `input/selected_photos/` に用途付きの名前でコピーした。
6. 選定理由を `docs/reference_image_selection.md` に記録した。

## 選定した画像

- `input/selected_photos/reference_side_right_body_1698975320501.jpg`
- `input/selected_photos/reference_side_standing_pattern_1713434749448.jpg`
- `input/selected_photos/reference_back_top_tail_1755598074234.jpg`
- `input/selected_photos/reference_front_face_1763363798733.jpg`
- `input/selected_photos/reference_low_side_body_1752021930652_frame_000000.jpg`
- `input/selected_photos/reference_low_side_tail_motion_1752021930652_frame_000330.jpg`
- `input/selected_photos/reference_back_top_motion_1762988855408_frame_000630.jpg`
- `input/selected_photos/reference_front_low_1778499579924_frame_000945.jpg`

## 判断

主基準は静止画にする。

- 体型・胴体模様: `reference_side_right_body_1698975320501.jpg`
- 顔: `reference_front_face_1763363798733.jpg`
- 背面・尻尾: `reference_back_top_tail_1755598074234.jpg`

動画フレームは、低い目線、動作、補助角度の確認に使う。

## 次にやること

選定済み画像に対してTask 2背景除去を再実行し、切り抜き品質を確認する。

その後、Blenderでリグ付きベースモデル、選定画像、Hunyuan3D生成メッシュを同じ作業シーンに配置する。
