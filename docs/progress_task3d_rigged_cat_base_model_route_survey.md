# Task 3D 進捗: Rigged Cat Base Model Route Survey

## 実行日

2026-06-22

## 目的

リグ付き・アニメーション可能な猫モデルを作るため、最初に使うべきベースモデル経路を調査する。

## 結果

Task 3D は完了。

詳細は以下に記録した。

- `docs/rigged_cat_base_model_survey.md`

## 調査した候補

- Quaternius Ultimate Animated Animal Pack
- Quaternius Farm Animal Pack
- 猫専用の無料リグ付き個別モデル探索
- SMAL / 3D Menagerie 系の研究用動物モデル
- Blenderでの簡易リグ付き猫モデル自作

## 推奨

Task 3E では、まず **Quaternius Ultimate Animated Animal Pack** を使う。

理由:

- CC0でライセンスリスクが低い。
- FBX / OBJ / Blend / glTF がある。
- 既にアニメーション付き。
- Blender、Godot、Unity、Unreal の可動モデルパイプライン検証に向いている。

ただし、猫専用モデルではない。そのため、Task 3Eでは「可動パイプライン検証」を優先し、猫らしさは Task 3F で寄せる。

## 注意点

- Task 3B/3C の Hunyuan3D 生成メッシュは、最終可動モデルではなく参照モデルとして扱う。
- 生成メッシュの直接リギングはMVPでは行わない。
- sleep / lie-down が既存アニメーションにない場合は、Blenderで簡易アニメーションを追加する方針にする。

## 次のTask

Task 3E: Rigged Cat Base Model Preparation

実施内容:

- Quaternius Ultimate Animated Animal Pack を取得する。
- Blenderでリグ、メッシュ、アニメーションを確認する。
- GLB/FBX出力できるか確認する。
- Godotで再生確認へ進める素材を作る。

