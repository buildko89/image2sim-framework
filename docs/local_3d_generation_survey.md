# ローカル / 無料 Image-to-3D 調査

## 目的

無料・ローカル・OSSを優先して、画像から3D候補モデルを作る方法を調査する。

この調査では、有料APIやクラウドクレジット制の3D生成サービスはMVP候補から外す。目的は、`selected/masked images` からローカル実行で3D候補を生成し、Blenderで取り込み、整形、正規化、エクスポートできる最初の試作ルートを決めること。

## 調査結果サマリー

| 候補 | 初回試作との相性 | 主な理由 |
| --- | --- | --- |
| TripoSR | 高い | MIT license、単一画像からの流れが単純、標準設定のVRAM目安が約6GB、最初の動作確認に向いている。 |
| InstantMesh | 中 | Apache-2.0、OBJ出力とテクスチャマップ出力の選択肢があるが、TripoSRよりセットアップとGPUメモリ面のリスクが高い。 |
| Hunyuan3D | 中 | 形状とテクスチャ品質は有望。Windows対応、GLB出力、Blender addon/API server経路があるが、ライセンスとVRAM制約に注意が必要。 |
| Blender Addon / Wrapper | 中 | Blender連携には有効だが、最初はCLIやローカルPythonで生成方式を検証してから使うのが安全。 |

## 候補

### TripoSR

- 種別: 単一画像から3D形状を復元するfeed-forward型の3D再構成モデル。
- ライセンス: MIT。
- 入力: 単一画像。スクリプトには複数画像パスも渡せるが、基本は単一画像ごとの再構成。
- 出力: 出力ディレクトリに3D meshを保存する。`--bake-texture` によりテクスチャ焼き込みも指定可能。
- 良い点:
  - 公式リポジトリが比較的小さく、導入経路が分かりやすい。
  - MIT licenseでMVP用途のリスクが低い。
  - 単一画像から試せるため、Task 3Bの初回試作に向いている。
  - 公式READMEでは、単一画像の標準設定で約6GB VRAMとされており、RTX 4060 8GBで現実的に試せる可能性が高い。
  - 高品質モデルを試す前の最初のパイプライン確認に向いている。
- 懸念点:
  - 最新のHunyuan3D系と比べると、形状やテクスチャ品質は弱い可能性がある。
  - 猫・動物の骨格や自然な形状は、Blenderでの後処理やベースモデル転写が必要になる可能性がある。
  - Windows上のCUDA、PyTorch、`torchmcubes` 周りでセットアップが詰まる可能性がある。
- Windows / RTX 4060適性: 初回候補として良い。RTX 4060 8GBで標準設定を試す価値がある。ただしCUDA/PyTorch環境の確認が必要。
- Blender連携: 生成meshをBlenderへ取り込み、原点、スケール、向きを正規化し、GLB/FBXへ出力する。テクスチャ焼き込み結果は別途確認する。
- メモ:
  - Task 3Bの第一候補。
  - 可能なら `input/masks/` の切り抜き画像を使う。
  - OBJ/meshのBlender取り込みと、テクスチャ焼き込みの扱いやすさを確認する。

### InstantMesh

- 種別: 単一画像からmeshを生成する、sparse-view reconstruction / LRM系の手法。
- ライセンス: Apache-2.0。
- 入力: 単一画像。内部で `rembg` を使える。すでに背景除去済み画像がある場合は `--no_rembg` が使える。
- 出力: 標準ではvertex color付きの `.obj` mesh。`--export_texmap` でテクスチャマップ出力も可能。
- 良い点:
  - Apache-2.0で比較的扱いやすい。
  - 公式のコマンドライン経路がある。
  - 背景除去済み画像と相性がよい可能性がある。
  - OBJ出力はBlenderに取り込みやすい。
  - テクスチャマップ出力の選択肢がある。
- 懸念点:
  - TripoSRよりパイプラインが複雑。
  - 公式READMEにメモリ節約のためのmulti-GPU Gradio挙動が書かれており、GPUメモリ負荷が高い可能性がある。
  - テクスチャマップ出力は時間がかかる可能性がある。
  - WindowsセットアップのリスクはTripoSRより高そう。
- Windows / RTX 4060適性: 可能性はあるが第一候補ではない。TripoSRで品質が不足した場合に試す。
- Blender連携: OBJをBlenderへ取り込み、vertex colorやmaterial状態を確認し、正規化してGLB/FBX出力する。
- メモ:
  - TripoSRの品質が不足した場合の候補。
  - Blender連携を優先するなら、NeRF系よりmesh出力経路を優先する。

### Hunyuan3D

- 種別: 画像またはテキストから3D形状・テクスチャを生成するシステム。Hunyuan3D-2には、shape generation、texture generation、Gradio app、local API server、Blender addon経路がある。
- ライセンス: Tencent Hunyuan 3D community license。標準的なMIT/Apache系OSSライセンスではない。地域制限や利用制限があるため、配布や商用利用前に確認が必要。
- 入力: 画像またはテキスト。画像から形状生成に対応。multi-view経路もある。
- 出力: Python APIでは `trimesh` objectを返し、GLB/OBJなどへ保存できる。local API server例では `test2.glb` を出力している。
- 良い点:
  - 調査候補の中では、形状とテクスチャ品質の期待値が高い。
  - 公式README上でWindows、macOS、Linux対応が示されている。
  - shape-onlyは約6GB VRAM、shape+textureは合計約16GB VRAMと記載されている。
  - Hunyuan3D-2mini、turbo、low-vram系の選択肢がある。
  - local API serverとBlender addonがあり、本プロジェクトのBlender中心方針と相性がよい。
- 懸念点:
  - ライセンスがMIT/Apacheより制約的。
  - shape+textureはRTX 4060 8GBでは厳しい可能性が高い。
  - セットアップがTripoSRより重い。
  - バリエーションが多く、最初の選定が複雑。
- Windows / RTX 4060適性: shape-onlyまたはmini/low-vram経路なら可能性あり。フルのshape+textureは8GB VRAMでは厳しい想定。
- Blender連携: 有望。local API server + Blender addonを後で評価するか、PythonでGLB/OBJ保存して既存のBlender cleanup/exportへ渡す。
- メモ:
  - TripoSRの次に評価する候補。
  - すぐにテクスチャ品質が必要な場合は、`Hunyuan3D-2mini` のshape-onlyから試し、texture generationは分けて検証する。

### Blender Addon / Wrapper Options

- 種別: Blender内からローカルimage-to-3Dモデルを呼び出すaddon、またはワークフローwrapper。
- ライセンス: 使用するモデルやaddonによる。
- 入力: 画像パス、local API server endpoint、または生成済みmesh path。
- 出力: Blender scene object、GLB/FBX、またはOBJ/GLB/PLYなどの中間ファイル。
- 良い点:
  - 「ローカル生成候補をBlenderへ取り込んで整形する」という本プロジェクトの方向性に合う。
  - Hunyuan3Dは公式にlocal API server + Blender addon経路がある。
  - ComfyUI wrapperなども試作・比較には使える可能性がある。
  - Blenderを中心にしつつ、完全手動モデリング依存を避けられる。
- 懸念点:
  - wrapperごとに品質や安定性が異なる。
  - addonが内部処理を隠すため、失敗時の切り分けが難しい。
  - ライセンスは内部で使うモデルに依存する。
  - Blender Python環境と機械学習用Python環境が衝突しやすい。
- Windows / RTX 4060適性: 生成処理をBlender外のPython環境で動かし、Blenderは取り込み・整形に集中させる構成が望ましい。
- Blender連携: 高い。ただし最初からaddon経由にせず、まずCLIまたはlocal Pythonで生成方式を検証する。
- メモ:
  - 初回試作はaddonから始めない。
  - まずCLI/local Python生成を確認し、その後Blender自動化に包む。

## 評価基準

- 無料・ローカルで使えるか
- ライセンス
- セットアップ難易度
- GPU / VRAM要件
- 出力形式
- テクスチャ対応
- Blender取り込み手順
- Godot / Unity / Unreal互換性
- 猫・動物への適性

## 初期推奨

Task 3Bでは **TripoSRを最初に試す**。

理由:

- ローカル単一画像の流れが最も単純。
- MIT licenseでMVPのリスクが低い。
- 公式README上の標準VRAM目安が約6GBで、RTX 4060 8GBに比較的合う。
- `selected/masked image -> local 3D candidate -> Blender import/cleanup/export -> Godot check` の流れを最短で確認できる。

フォールバック候補:

- TripoSRの猫・動物出力が不十分な場合は、**Hunyuan3D-2mini shape-only** を次に評価する。
- permissive licenseを重視し、TripoSRの品質が足りない場合は、Hunyuan3Dより先に **InstantMesh** を評価する。

## Task 3B 試作案

1. Task 1.5とTask 2を実データで実行し、selected/masked input imagesを準備する。
2. TripoSR用の隔離されたローカル環境を作る。
3. `input/masks/` の切り抜き画像1枚でTripoSRを実行する。
4. raw outputを `output/raw_3d/local/triposr/` に保存する。
5. 実行時間、VRAM挙動、セットアップ問題、出力形式、Blender取り込み結果を記録する。
6. Task 3CまたはTask 4のBlender import/cleanup/exportへ渡して正規化する。

## 参照元

- TripoSR official repository: https://github.com/VAST-AI-Research/TripoSR
- TripoSR technical report: https://arxiv.org/abs/2403.02151
- InstantMesh official repository: https://github.com/TencentARC/InstantMesh
- InstantMesh technical report: https://arxiv.org/abs/2404.07191
- Hunyuan3D-2 official repository: https://github.com/Tencent-Hunyuan/Hunyuan3D-2
- Hunyuan3D 2.0 technical report: https://arxiv.org/abs/2501.12202
