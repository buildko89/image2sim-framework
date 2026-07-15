# 動画からの候補画像抽出

## 目的

猫は静止してくれないため、写真だけでは正面、横、斜め、背面の良い参照画像を揃えにくい。そこで `input/raw_photos/Movies/` に置いた動画から候補フレームを抽出し、通常の画像入力として使えるようにする。

## 入力

- `input/raw_photos/Movies/*.mp4`
- `input/raw_photos/Movies/*.mov`
- `input/raw_photos/Movies/*.m4v`

## 出力

- `input/raw_photos/video_frames/*.jpg`
- `output/reports/video_frame_extraction.json`
- `output/reports/video_frame_extraction.csv`

抽出された画像は `input/raw_photos/` 配下にあるため、通常の Task 1 画像インベントリ、Task 1.5 画像選択、Task 2 背景除去の流れに載せられる。

## 実行例

```powershell
python scripts/012_extract_video_frames.py
```

より多く候補を出す場合:

```powershell
python scripts/012_extract_video_frames.py --interval-seconds 0.5 --max-frames-per-video 24
```

実行中は動画ごとに進捗が表示される。途中で止めた場合でも、処理済み動画分の部分レポートが `output/reports/video_frame_extraction.json` と `.csv` に保存される。

ブレが強いフレームを減らしたい場合:

```powershell
python scripts/012_extract_video_frames.py --min-sharpness 80
```

## 方針

- 動画全フレームは保存しない。
- 一定間隔で候補フレームを抜く。
- OpenCVのLaplacian varianceで簡易シャープネスを計算する。
- しきい値以上のフレームだけを保存する。
- 最終判断は人間がレビューする。

## 注意点

- シャープネス値は絶対的な品質評価ではない。
- 暗い動画や背景が細かい動画では、良いフレームでも低く出ることがある。
- 良い画像が少ない場合は、`--min-sharpness` を下げるか、`--interval-seconds` を短くする。
- `KeyboardInterrupt` が出た場合は、ユーザー操作などで処理が中断された状態。再実行すればよい。
- 抽出後は `input/raw_photos/video_frames/` を確認し、使いたい画像を Task 1.5 で選ぶ。

## Task 3F以降での使い方

外観・形状転写では、次のようなフレームが特に有効。

- 真横の全身
- 正面の全身
- 斜め前の全身
- 斜め後ろまたは背面
- 尻尾が見えているもの
- 体が大きくブレていないもの

解像度が高くなくても、輪郭、毛色、模様、尻尾の長さ、体型の参考には使える。
