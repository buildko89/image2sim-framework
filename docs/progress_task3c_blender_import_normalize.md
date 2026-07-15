# Task 3C 進捗: Blender Import and Normalize

## 目的

Task 3B でローカル生成した3D候補モデルを Blender に取り込み、ゲームエンジン向けに使えるようにスケール、原点、足元位置を正規化し、GLB/FBXへ出力する。

## 実行日

2026-06-22

## 入力

- `output/raw_3d/local/hunyuan3d/side_right_hunyuan3d_shape.glb`

このGLBは Task 3B で Hunyuan3D-2mini shape-only により生成したもの。

## 実施内容

- Blender 5.0 をCLIで起動した。
- Hunyuan3D生成GLBをBlenderへ取り込んだ。
- メッシュのバウンディングボックスを計測した。
- 高さが 1.0 Blender meter になるようにスケールした。
- XY中心を原点へ移動した。
- 足元が Z=0 になるように移動した。
- GLB と FBX を出力した。
- 生成後のGLBを `trimesh` で読み込み確認した。

## 修正内容

Blender側スクリプト `blender/cleanup_export.py` の引数処理を修正した。

理由:

- Blender実行時は `--` 以降をPythonスクリプト引数として扱う必要がある。
- 既存実装ではBlender本体の引数も `argparse` が読んでしまい、`--input` 等が未指定扱いになっていた。

## 出力

Task 5 以降で使う標準出力:

- `output/clean_3d/cat_clean.glb`
- `output/clean_3d/cat_clean.fbx`

比較・履歴用出力:

- `output/clean_3d/cat_hunyuan3d_normalized.glb`
- `output/clean_3d/cat_hunyuan3d_normalized.fbx`

レポート:

- `output/reports/blender_cleanup_export.json`
- `output/reports/blender_cleanup_export_plan.json`

## 正規化結果

Blenderレポート上の結果:

- target height: 1.0
- mesh count: 1
- scale factor: 1.2330627666214935
- before size: `[1.9888337850570679, 1.1590092182159424, 0.81098872423172]`
- after size: `[2.4523568153381348, 1.429131031036377, 1.0]`
- after bbox min: `[-1.2261784076690674, -0.7145655155181885, 0.0]`
- after bbox max: `[1.2261784076690674, 0.7145655155181885, 1.0]`

GLB読み込み確認:

- loader: `trimesh`
- vertices: 1,249,392
- faces: 417,000
- bounds: `[[-1.2261784076690674, 0.0, -0.7145655155181885], [1.2261784076690674, 0.9999999701976776, 0.7145655155181885]]`

Blenderレポートでは Z=0 から Z=1.0 に正規化されている。`trimesh` 側では glTF/Blender 座標系の扱いにより軸の見え方が変わっているが、高さ方向の範囲は 1.0 として確認できる。

## 注意点

- 生成メッシュは高密度で、GLBが約35MBある。
- Godot / Unity / Unreal で扱う前に、必要に応じて Task 4 で軽量化・デシメーションを検討する。
- テクスチャ生成はまだ行っていないため、現時点では shape-only の表示確認が主目的。

## 判断

Task 3C は完了。

次は Task 4 で、ゲームエンジン向けの cleanup/export 方針として、軽量化や不要オブジェクト削除を追加検討する。
