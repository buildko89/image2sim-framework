# Task 3A 進捗報告: Free/Local Image-to-3D Survey and Workflow Redesign

- 作成日: 2026-06-22
- 状態: 完了
- 方針: 無料・ローカル・OSS優先の半自動3D生成へ再整理

## 実施内容

- MVP方針を「有料API前提」ではなく「無料・ローカル・OSS優先」に再定義した。
- Blender工程を「完全手動モデリング」ではなく、自動生成候補の import / cleanup / normalize / export を担う工程として再定義した。
- Task 3をTask 3A〜3Dに分割した。
- Godot / Unity / Unreal を対象エンジンとして再確認した。
- 最初の表示確認候補をGodotにした。
- Tripo / Meshy / paid Blender AI plugins / cloud credit based 3D generation APIs を Optional / Deferred / Experimental に移した。
- `docs/local_3d_generation_survey.md` を追加し、TripoSR / InstantMesh / Hunyuan3D / Blender addon・wrapper候補の調査テンプレートを作成した。
- `config/pipeline.yaml` を `generation.mode: local_first` に更新した。
- 公式リポジトリと技術レポートを確認し、Task 3Bの初回候補をTripoSRに決めた。
- Hunyuan3D-2mini shape-only と InstantMesh をフォールバック候補にした。
- `docs/local_3d_generation_survey.md` を日本語で整理し直した。

## 新しいTask構成

### Task 3A: Free/Local Image-to-3D Survey

無料・ローカル・OSSのimage-to-3D候補を調査し、最初に試作する方式を決める。

### Task 3B: Local Image-to-3D Prototype

Task 3Aで選んだ方式を使い、selected/masked imagesからOBJ/GLB/PLYを出力する。

### Task 3C: Blender Import and Normalize

ローカル生成された3D候補をBlenderへ取り込み、スケール、原点、向きなどを正規化してGLB/FBXへ出力する。

### Task 3D: Base Cat Model Transfer Route

画像または生成アセットの外観・テクスチャを、クリーンな既存rigged cat base modelへ転写する経路を調査する。

## 今回やっていないこと

- 有料API呼び出し
- Tripo/Meshy API実装
- 実際の3D生成
- Blenderでの本格モデリング
- Godot/Unity/Unreal取り込み実装

## 次のTask

Task 3B: Local Image-to-3D Prototype

TripoSRを最初のローカル生成候補として、selected/masked imagesからOBJ/GLB/PLY系の3D候補出力を試す。
