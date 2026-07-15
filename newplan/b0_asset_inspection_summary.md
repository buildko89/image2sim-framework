# B-0 モデル棚卸し結果レポート

> **実行日:** 2026-07-08  
> **検査数:** 30 モデルファイル  
> **結果:** [b0_asset_inspection.json](file:///D:/source/repos/3DModelDevPJ/image2sim-framework/output_v2/reports/b0_asset_inspection.json)

---

## ランキング上位モデル

| 順位 | モデル | リグ | アニメーション | 頂点数 | ポリゴン | ボーン数 | テクスチャ |
|------|--------|------|-------------|--------|---------|---------|----------|
| 1 | **White+Tiger.blend** | ✅ (120ボーン) | 23 アクション | 89,747 | 165,865 | 120+38 | あり |
| 2 | **Leopard_Hybrid_A1.Fbx** | ✅ (98ボーン) | 8 アクション | 22,848 | 20,820 | 98 | Diffuse+Normal+Opacity |
| 3 | LazyCat_anim.fbx | ✅ (54ボーン) | 1 アクション | 777 | 834 | 54 | 未確認 |
| 4 | houseCat_anim.fbx | ✅ (54ボーン) | 1 アクション | 869 | 924 | 54 | 未確認 |
| 5 | modnica_anim.fbx | ✅ (54ボーン) | 1 アクション | 911 | 982 | 54 | 未確認 |
| - | **koha9_cat (scene.gltf)** | ❌ なし | 1 (MorphTarget) | 9,282 | - | 0 | ✅ 2枚 |

---

## 推奨ベースモデル: Leopard_Hybrid_A1.Fbx

> [!IMPORTANT]
> White+Tiger.blend はスコア最高ですが、**トラ** であり寸法が巨大（209m x 114m）です。
> Route B のベースとしては **Leopard_Hybrid_A1.Fbx** を推奨します。

### 推奨理由

| 項目 | Leopard_Hybrid_A1.Fbx | White+Tiger.blend |
|------|----------------------|-------------------|
| 動物種 | ヒョウ（猫科、体型が猫に近い） | トラ（巨大、猫からは遠い） |
| メッシュ密度 | 22,848 頂点（ゲーム向き） | 89,747 頂点（重すぎる可能性） |
| モデルサイズ | 0.84m x 4.46m x 1.78m（現実的） | 45m x 209m x 115m（**巨大**） |
| アニメーション | **Idle1, Idle2, Walk, Run, Jump, Atk1, Atk2, Walkback** | Attack, Run（名前が曖昧） |
| リグ | 98 ボーン（四足動物用、整理済み） | 120+38 ボーン（2アーマチュア、複雑） |
| テクスチャ | **Diffuse + Normal + Opacity** (PBR対応) | あり |
| ファイルサイズ | 71 MB | 156 MB |
| 形式 | FBX (Blender版) | .blend |

### Leopard_Hybrid のアニメーション一覧

| アニメーション | フレーム数 | 用途 |
|-------------|----------|------|
| Idle1 | 151 | 待機1 |
| Idle2 | 451 | 待機2（長め） |
| Walk | 81 | 歩行 |
| Walkback | 81 | 後退 |
| Run | 31 | 走行 |
| Jump | 581 | ジャンプ |
| Atk1 | 91 | 攻撃1 |
| Atk2 | 101 | 攻撃2 |

### 代替候補

低ポリ猫モデル群 (LazyCat, houseCat, modnica_anim 等) も使えますが:
- 頂点数 700〜900 で非常にローポリ
- アニメーション1つのみ
- テクスチャが不明確

---

## 次のステップ

ベースモデルの選定を確認後、以下を実行します:

1. **B-1:** 選定モデルの Blender 準備（スケール正規化、不要オブジェクト削除）
2. **B-2:** カラーパレット確認
3. **B-3:** テクスチャ生成・適用

> [!NOTE]
> Leopard_Hybrid_A1 はヒョウの模様テクスチャが付いています。Route B ではこのテクスチャを**三毛猫パターン**に置き換えます。
> 体型は猫科なので、スケールを小さくすれば猫として十分通用します。

  ## B-0 モデル棚卸し完了  30ファイルを検査した結果をレポートにまとめました
  
  ### 主な発見
  • koha9_cat はリグ（骨格）なし — MorphTargetアニメーションのみ。骨格ベースのアニメーションには不向き                                                            • White+Tiger.blend はスコア最高ですが、トラであり寸法が巨大（209m）で扱いにくい
  • Leopard_Hybrid_A1.Fbx が Route B のベースモデルとして最適と判断：• 猫科（ヒョウ）で体型が猫に近い
  • 8つのアニメーション (Idle, Walk, Run, Jump, Attack等)
  • 98ボーン の整理されたリグ
  • PBRテクスチャ付き (Diffuse + Normal + Opacity)
  • ゲーム向きの 22,848 頂点
  
  ### 確認事項
  Leopard_Hybrid_A1.Fbx をベースモデルとして進めてよいでしょうか？ それとも別のモデル（低ポリ猫シリーズ等）の方がご希望に近いでしょうか？                                      
────────────────────────────────────────────────────────────
> Leopard_Hybrid_A1.Fbxをベースで問題ないです。ただ、最終的なモデルは、koha9_catが理想です。
The user confirms:
  了解しました！方針を整理します
  • ベースのリグ・アニメーション: Leopard_Hybrid_A1.Fbx（98ボーン、8アニメーション）
  • 目標の外見・体型: koha9_cat（短足・丸顔・もふもふ）
  • テクスチャ: 写真由来の三毛猫パターン
  B-1（ベースモデル準備）を進めます。Leopard をインポート → スケール正規化 → 猫サイズに調整 → GLBでテスト出力するスクリプトを作ります。                                        
● Create(D:/source/repos/3DModelDevPJ/image2sim-framework/pipeline_v2/b1_prepare_base_model_blender.py)
● Create(D:/source/repos/3DModelDevPJ/image2sim-framework/pipeline_v2/b1_prepare_base_model.py) (ctrl+o to expand)

モデル参考の情報
D:\source\repos\3DModelDevPJ\image2sim-framework\input\cat2
D:\source\repos\3DModelDevPJ\image2sim-framework\input\cat

元の画像D:\source\repos\3DModelDevPJ\image2sim-framework\input\raw_photos足りなければ、E:\workから使える画像をチョイスする。