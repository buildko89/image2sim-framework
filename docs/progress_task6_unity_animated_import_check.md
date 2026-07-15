# Task 6: Unity Animated Import Check 進捗

## 実施日

2026-06-29

## 目的

Godotで表示・アニメーション再生確認済みの `cat_shape_pass` アセットをUnityへ持ち込み、表示、スケール、接地、アニメーション再生を確認できる状態にする。

## 実施内容

1. Unity Editorの存在を確認した。
2. Unity確認用の配置スクリプトを追加した。
3. Unity import手順書を追加した。
4. `cat_shape_pass.glb` と `cat_shape_pass.fbx` を `output/unity/` へコピーした。
5. Python構文チェックを実施した。

## Unity Editor

- 検出済み:
  - `C:\Program Files\Unity\Hub\Editor\6000.3.10f1\Editor\Unity.exe`
- `unity` / `Unity` コマンドはPATH上にはない。

## 追加したファイル

- `scripts/06_unity_import_check.py`
- `unity/UnityImportGuide.md`
- `docs/progress_task6_unity_animated_import_check.md`

## 出力

- `output/unity/cat_shape_pass.glb`
- `output/unity/cat_shape_pass.fbx`
- `output/reports/unity_import_check_plan.json`
- `output/reports/unity_import_check.json`

## 実行コマンド

```powershell
python scripts/06_unity_import_check.py --dry-run
python -m compileall scripts blender
python scripts/06_unity_import_check.py --overwrite
```

## 次の確認

1. Unity HubまたはUnity Editorで3Dプロジェクトを開く。
2. `output/unity/cat_shape_pass.glb` または `output/unity/cat_shape_pass.fbx` を `Assets/Image2Sim/` へ配置する。
3. Sceneへドラッグして表示確認する。
4. `Idle`、`Walk`、`Jump_ToIdle` が見えるか確認する。
5. 再生時に色、メッシュ、骨が破綻しないか確認する。

## 判断

Task 6はUnity向けアセット配置と手順整備まで完了。

ユーザー判断により、Unity確認は一旦保留し、以後はGodotのみで進める。

Unity Editor上の目視import/playback確認は未実施。
