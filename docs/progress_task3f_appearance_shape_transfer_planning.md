# Task 3F: 外観・形状転写計画 進捗

## 実施日

2026-06-22

## 目的

Task 3Eで準備したリグ付き四足動物ベースを、猫らしい見た目と体型へ近づけるための計画を作成する。

## 実施内容

1. 現在の入力データを確認した。
2. 選択済み写真とマスクの用途を整理した。
3. Hunyuan3D生成メッシュの位置づけを「参照用」に明確化した。
4. Task 3Eのリグ付きFoxベースを、可動モデルの土台として扱う方針を整理した。
5. 毛色、模様、体型、耳、顔、尻尾、アニメーション保持の優先度を決めた。
6. MVPでやることと、後回しにすることを分けた。
7. 次の実装Taskで使う想定ワークフローを定義した。

## 成果物

- `docs/appearance_shape_transfer_plan.md`
- `docs/progress_task3f_appearance_shape_transfer_planning.md`

## 現在使える入力

- `input/selected_photos/front_P_20260326_195241.jpg`
- `input/selected_photos/front_P_20260326_195242.jpg`
- `input/selected_photos/front_right_1780404696258.jpg`
- `input/selected_photos/side_right_1773200710029.jpg`
- `input/masks/*_cutout.png`
- `output/clean_3d/cat_clean.glb`
- `output/rigged/cat_base_rigged.blend`
- `output/rigged/cat_base_rigged.glb`
- `output/rigged/cat_base_rigged.fbx`

## 決定した方針

- 最終可動モデルの土台は、Task 3Eで作成したリグ付きFoxベースを使う。
- Hunyuan3D生成メッシュは直接動かす対象ではなく、体型やシルエットの参考にする。
- 実画像とマスクは、毛色、模様、耳、顔、尻尾、体型の判断に使う。
- まずはBlender上で参照画像と静的メッシュを並べ、低リスクなマテリアル調整と軽いプロポーション調整から始める。
- Armature、weight、animation clipを壊さないことを最優先にする。

## MVPで優先すること

- 猫として認識できる見た目に近づける。
- リグとアニメーションを保持する。
- Godotで表示・再生確認できるGLBへつなげる。
- 写真そっくりではなく、動く猫モデルとして成立させる。

## MVPでやらないこと

- 有料APIによる外観転写。
- Hunyuan3D高密度メッシュへの直接リギング。
- 写真からの完全自動テクスチャ投影。
- 高品質な毛並み再現。
- 自然で完成度の高いsleep / lie-downアニメーション制作。

## 次のTask

Task 3G: Basic Cat Animation Set

ただし、Task 3Gへ進む前に、画像ファイルについて次を相談する。

- どの画像を見た目の基準にするか。
- 横向き、正面、斜めのどれを優先するか。
- 毛色や模様をどの程度再現したいか。
- 追加で背面または斜め後ろの全身画像が必要か。

## 判断

Task 3Fは完了とする。

次の実装では、`output/rigged/cat_base_rigged.blend` をベースに、参照画像と `output/clean_3d/cat_clean.glb` をBlenderシーンへ配置し、見た目調整用の作業ファイルを作るのが妥当。
