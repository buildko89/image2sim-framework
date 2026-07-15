# 追加基準画像の背景除去 進捗

## 実施日

2026-06-22

## 目的

Task 3F以降で使う見た目基準画像に対して背景除去を実行し、Blender参照配置や形状・模様確認に使いやすい切り抜きを作成する。

## 入力

- `input/selected_photos/`

今回追加した基準画像:

- `reference_side_right_body_1698975320501.jpg`
- `reference_side_standing_pattern_1713434749448.jpg`
- `reference_back_top_tail_1755598074234.jpg`
- `reference_front_face_1763363798733.jpg`
- `reference_low_side_body_1752021930652_frame_000000.jpg`
- `reference_low_side_tail_motion_1752021930652_frame_000330.jpg`
- `reference_back_top_motion_1762988855408_frame_000630.jpg`
- `reference_front_low_1778499579924_frame_000945.jpg`

## 実行コマンド

```powershell
python scripts/02_remove_backgrounds.py
```

## 実行結果

- 入力画像数: 12
- 処理成功: 12
- 失敗: 0
- 警告: 0

## 出力

- `input/masks/`
- `input/masks_review/`
- `output/reports/background_removal.json`
- `output/reports/background_removal.csv`
- `output/reports/reference_masks_review_sheet.jpg`

## 確認結果

- 横向き主基準 `reference_side_right_body_1698975320501` は、体型・胴体模様確認に十分使える。
- 正面主基準 `reference_front_face_1763363798733` は、顔・胸毛確認に使える。
- 背面主基準 `reference_back_top_tail_1755598074234` は、背中模様と尻尾確認に使える。
- 動画フレーム由来の画像は、低い目線や動作中の補助参照として使う。

## 判断

追加基準画像の背景除去は完了。次はリグ付きモデル、切り抜き参照画像、Hunyuan3D静的メッシュをBlenderで並べる作業、またはアニメーション確認へ進める。
