# Task 3B 進捗: Local Image-to-3D Prototype

## 目的

Task 3A で選定した無料・ローカル・OSS優先の候補を使い、`input/masks/` の切り抜き画像から3D候補モデルを生成し、OBJ/GLB/PLY のいずれかを `output/raw_3d/` に出力する。

## 実行日

2026-06-22

## 入力候補

Task 2 で生成済みの切り抜き画像を使用候補にした。

- `input/masks/side_right_1773200710029_cutout.png`
- `input/masks/front_right_1780404696258_cutout.png`
- `input/masks/front_P_20260326_195242_cutout.png`
- `input/masks/front_P_20260326_195241_cutout.png`

最初の実行候補は、切り抜き品質と被写体サイズのバランスがよい `input/masks/side_right_1773200710029_cutout.png`。

## 採用候補

Task 3A の結果に従い、最初のプロトタイプ候補として TripoSR を使用した。

理由:

- 無料・ローカル実行候補
- MIT License
- 単一画像からの3D生成に対応
- OBJ/GLB 出力が想定できる
- Blender へ取り込みやすい
- RTX 4060 Laptop GPU の 8GB VRAM で検証対象にできる

## 実施内容

- `external/TripoSR` に TripoSR リポジトリを取得した。
- `.venv_triposr` を作成した。
- pip / setuptools / wheel を更新した。
- PyTorch CUDA wheel を導入した。
- PyTorch から CUDA GPU が見えることを確認した。
- TripoSR の依存関係インストールを実行した。

確認結果:

- Python: 3.12.10
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU
- PyTorch: 2.5.1+cu121
- `torch.cuda.is_available()`: `True`

## TripoSR 試行結果

TripoSR での3D生成は未完了。

TripoSR の依存関係 `torchmcubes` のビルドで停止した。原因は CUDA Toolkit / NVCC が見つからないこと。

確認結果:

- `nvcc` は PATH 上に存在しない。
- `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA` が存在しない。
- GPUドライバと PyTorch CUDA wheel は存在するが、CUDA拡張をビルドするための CUDA Toolkit が不足している。

## Hunyuan3D-2mini shape-only 試行結果

TripoSR に固執せず、Task 3A のフォールバック候補である Hunyuan3D-2mini shape-only を試した。

実施内容:

- `external/Hunyuan3D-2` に Hunyuan3D-2 リポジトリを取得した。
- `.venv_hunyuan3d` を作成した。
- PyTorch CUDA wheel を導入した。
- Hunyuan3D の `requirements.txt` を導入した。
- Hunyuan3D 本体を editable install した。
- `scripts/03b_hunyuan3d_shape_prototype.py` を追加した。
- `input/masks/side_right_1773200710029_cutout.png` を入力にして shape-only 生成を実行した。

確認結果:

- Python: 3.12.10
- GPU: NVIDIA GeForce RTX 4060 Laptop GPU
- PyTorch: 2.5.1+cu121
- `torch.cuda.is_available()`: `True`
- モデル: `tencent/Hunyuan3D-2mini`
- subfolder: `hunyuan3d-dit-v2-mini`
- mode: shape-only
- steps: 30
- octree resolution: 320
- 生成時間: 約42秒
- 初回モデルダウンロード込み総時間: 約270秒

## 出力

Hunyuan3D-2mini shape-only により GLB を生成した。

- `output/raw_3d/local/hunyuan3d/side_right_hunyuan3d_shape.glb`
- `output/reports/task3b_hunyuan3d_shape_prototype.json`

GLB 読み込み確認:

- loader: `trimesh`
- vertices: 208,506
- faces: 417,000
- bounds: `[[-0.9944694638252258, -0.4165964126586914, -0.5812422037124634], [0.994364321231842, 0.39439231157302856, 0.5777669548988342]]`

## 判断

Task 3B は Hunyuan3D-2mini shape-only 経路で完了。

TripoSR 経路は環境依存関係で Blocked のままだが、無料・ローカル・OSS優先の代替候補で GLB 出力まで到達できた。

これは入力画像の問題ではなく、TripoSR 側の Windows ローカル開発用 CUDA 環境不足の問題。

## 次のTaskへの引き渡し

Task 3C / Task 4 では、生成済みGLBを Blender に取り込み、以下を確認する。

- 向き
- スケール
- 原点
- 足元位置
- 不要部分
- Godot / Unity / Unreal 向けに使える GLB/FBX へ正規化できるか

## 推奨

次は Task 3C: Blender Import and Normalize を実行する。

有料API、Tripo API、Meshy API は使用しない。
