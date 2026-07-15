# 方針更新: リグ付きアニメーション可能な猫モデル

## 実行日

2026-06-22

## 背景

Task 3B / Task 3C により、無料・ローカル優先で画像から静的な猫らしい3Dメッシュを生成し、Blenderで正規化するところまでは確認できた。

ただし、最終ゴールとして必要なのは単なる静的3Dモデルではなく、歩く、ジャンプ/飛ぶ、寝るなどの動作ができる猫モデルである。

## 新しい方針

- 画像から生成したメッシュは、最終可動モデルではなく参照・形状候補として扱う。
- 最終成果物は、リグ付き猫ベースモデルを使った可動モデルにする。
- Blenderを中心に、リグ、ウェイト、アニメーション、GLB/FBX出力を扱う。
- Godot / Unity / Unreal では静的表示ではなくアニメーション再生まで確認する。
- 完全自動リギングや高品質な自然動作は後続改善とし、MVPではリグ付きベースモデル経路を優先する。

## 更新した文書

- `README.md`
- `docs/backlog.md`
- `docs/decisions.md`
- `docs/workflow.md`

## 追加したDecision

- `DEC-20260622-RIGGED-CAT-ANIMATION`

## 新しい主要Task

- Task 3D: Rigged Cat Base Model Route Survey
- Task 3E: Rigged Cat Base Model Preparation
- Task 3F: Appearance / Shape Transfer Planning
- Task 3G: Basic Cat Animation Set
- Task 4: Blender Rig Cleanup and Animation Export
- Task 5: Godot Animated Import Check
- Task 6: Unity Animated Import Check
- Task 7: Unreal Animated Import Check

## 次の推奨Task

Task 3D: Rigged Cat Base Model Route Survey

リグ付き猫ベースモデルの候補、ライセンス、Blender取り込み、アニメーション対応、GLB/FBX出力、Godot再生確認の可否を調査する。
