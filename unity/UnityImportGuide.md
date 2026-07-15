# Unity Import Guide

## 目的

Task 6では、Godotで確認済みの `cat_shape_pass` アセットをUnityに読み込み、表示、スケール、接地、アニメーション再生を確認する。

## 対象アセット

優先確認:

- `output/unity/cat_shape_pass.glb`
- `output/unity/cat_shape_pass.fbx`

Unityプロジェクトへ直接コピーする場合:

- `unity/CatImportCheck/Assets/Image2Sim/cat_shape_pass.glb`
- `unity/CatImportCheck/Assets/Image2Sim/cat_shape_pass.fbx`

## 準備

アセットをUnity確認用ディレクトリへ配置する:

```powershell
python scripts/06_unity_import_check.py --overwrite
```

既存Unityプロジェクト `unity/CatImportCheck` がある場合は、`Assets/Image2Sim/` へもコピーできる:

```powershell
python scripts/06_unity_import_check.py --copy-to-project --overwrite
```

## Unityでの確認手順

1. Unity HubまたはUnity Editorで任意の3Dプロジェクトを開く。
2. `cat_shape_pass.glb` または `cat_shape_pass.fbx` を `Assets/Image2Sim/` へ配置する。
3. UnityのProjectビューでインポートが完了するのを待つ。
4. インポートされたモデルをSceneへドラッグする。
5. 表示、スケール、向き、床面との接地を確認する。
6. Animation/Animator関連のimport欄で `Idle`、`Walk`、`Jump_ToIdle` が見えるか確認する。
7. 簡易Animator ControllerまたはAnimationプレビューで `Idle`、`Walk`、`Jump_ToIdle` を再生する。

## 判定

Pass:

- モデルがUnity Scene上に表示される。
- スケールが極端に崩れていない。
- 接地点が大きく床から外れていない。
- skinned meshとして破綻なく表示される。
- `Idle`、`Walk`、`Jump_ToIdle` を確認できる。
- 再生時に色、メッシュ、骨が大きく破綻しない。

Needs Fix:

- UnityがGLB/FBXを読み込めない。
- アニメーション一覧が空になる。
- skinned meshが崩れる。
- スケール、向き、接地が大きく崩れる。
- Godotでは問題なかった色や形状がUnityで大きく変わる。

## 注意

UnityのGLB対応はプロジェクト設定やパッケージ状態に依存する。GLBが扱いにくい場合はFBXを優先して確認する。

FBXはBlender exportで `-Z Forward` / `Y Up` を使っている。
