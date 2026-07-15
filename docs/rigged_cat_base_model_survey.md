# Task 3D: リグ付き猫ベースモデル経路調査

## 目的

最終成果物を「静的な猫っぽい3Dメッシュ」ではなく、歩く、ジャンプ/飛ぶ、寝るなどの基本動作ができるリグ付き猫モデルにするため、現実的なベースモデル経路を調査する。

## 結論

Task 3D の推奨経路は次の2段階。

1. **短期MVP検証:** CC0 の既存アニメーション付き四足動物モデルで、Blender -> GLB/FBX -> Godot のアニメーション再生パイプラインを先に通す。
2. **猫らしさの反映:** Task 3F 以降で、写真、マスク、Hunyuan3D生成メッシュを参照として、リグ付きベースモデルの見た目、体型、マテリアルを猫に寄せる。

理由:

- 画像生成メッシュは高密度で、直接リグを入れて自然に動かすには不向き。
- 無料・商用利用可・猫専用・リグ付き・複数アニメーション付きの条件を同時に満たす候補は少ない。
- まずはリグ、アニメーション、エンジン再生の成立を確認する方が、プロジェクト全体のリスクを早く下げられる。

## 候補比較

### 候補A: Quaternius Ultimate Animated Animal Pack

- 種別: 既存アニメーション付き四足動物モデルパック。
- ライセンス: CC0。
- 形式: FBX / OBJ / Blend / glTF。
- アニメーション: あり。公式ページでは12種類の動物と、各モデルに12以上のアニメーションがあると説明されている。
- 対象動物: bull, fox, horse, donkey, wolf, cow, deer, stag, llama, alpaca, husky, shiba inu, doge 系。
- 猫専用か: いいえ。
- Blender適性: 高い。BlendとFBX/glTFがあるため取り込みやすい。
- Godot適性: 高い。glTF があり、Godot は3D scene importで glTF 2.0 を扱える。
- Unity / Unreal適性: 中から高。FBX と glTF があるため検証対象にできる。
- 良い点:
  - CC0でライセンスリスクが低い。
  - アニメーション付き四足モデルとして、MVPの可動パイプライン検証に向いている。
  - Blender / Godot / Unity / Unreal の形式検証に使いやすい。
- 懸念点:
  - 猫そのものではない。
  - sleep/lie-down が含まれるかは未確認。
  - 見た目を猫に寄せるには Task 3F 以降の編集が必要。
- 判断: **Task 3E の第一候補。**

### 候補B: Quaternius Farm Animal Pack

- 種別: 既存アニメーション付き動物モデルパック。
- ライセンス: CC0。
- 形式: FBX / OBJ / Blend。
- アニメーション: あり。
- 対象動物: 7種類のfarm animals。公式ページでは各動物に個別アニメーションがあると説明されている。
- 猫専用か: いいえ。
- 良い点:
  - CC0。
  - Blend / FBX があり、Blenderとゲームエンジン検証に使いやすい。
- 懸念点:
  - 猫ではない。
  - glTFが公式形式に含まれていないため、BlenderからGLBを再出力する必要がある。
- 判断: **代替候補。Ultimate Animated Animal Pack の方を優先。**

### 候補C: 猫専用の無料リグ付きモデルを個別に探す

- 種別: Sketchfab、OpenGameArt、個人配布などの個別モデル。
- ライセンス: モデルごとに異なる。
- 形式: モデルごとに異なる。
- 良い点:
  - 猫らしい外観に近い可能性がある。
  - 既に猫として作られていれば Task 3F の外観調整が軽くなる。
- 懸念点:
  - ライセンス確認が重い。
  - 再配布、商用利用、改変、ゲーム利用の条件がモデルごとに異なる。
  - リグ品質、アニメーション有無、Blender互換性が不安定。
- 判断: **Task 3E の第一候補にはしない。Task 3F/将来改善で追加調査。**

### 候補D: SMAL / 3D Menagerie 系の研究用動物モデル

- 種別: 研究用の動物形状・姿勢モデル。
- ライセンス: 実装・データごとに確認が必要。
- 良い点:
  - cats, dogs, horses などを含む動物形状・姿勢の研究として有用。
  - 画像から動物形状や姿勢を推定する方向性の参考になる。
- 懸念点:
  - ゲームエンジン向けのリグ付きアニメーションアセットとして直接使うものではない。
  - セットアップとライセンス確認が重い。
  - MVPの短期実装には不向き。
- 判断: **研究参考。MVPのベースモデル経路からは外す。**

### 候補E: 自作の簡易リグ付き猫ベースモデル

- 種別: Blenderでローカル作成する簡易猫モデル。
- ライセンス: 自作ならプロジェクト管理しやすい。
- 良い点:
  - ライセンス制約を最小化できる。
  - 必要なボーン構造とアニメーションを最初から設計できる。
- 懸念点:
  - モデリング、リギング、ウェイト、アニメーションの作業量が大きい。
  - 自然な見た目や動きには時間がかかる。
- 判断: **既存CC0モデル経路が失敗した場合のフォールバック。**

## 推奨するTask 3E方針

Task 3E では、まず **Quaternius Ultimate Animated Animal Pack** を使って、以下を検証する。

1. パックを取得する。
2. Blenderで `.blend` または `.fbx` / `.gltf` を開く。
3. 四足動物モデルのArmature、mesh、animation clipsを確認する。
4. walk と jump 系アニメーションを確認する。
5. sleep/lie-down がなければ、仮のlie-downアニメーションをBlenderで作る方針にする。
6. GLB/FBXとして出力する。
7. GodotでAnimationPlayerまたはAnimationTreeから再生確認する。

猫専用ではない点は許容する。Task 3E の目的は、まず「可動モデルの技術パイプラインが成立するか」を確認すること。

## Task 3F への引き渡し

Task 3F では、以下を計画する。

- 写真から毛色、模様、体型の特徴を拾う。
- Hunyuan3D生成メッシュを形状参考として横に置く。
- リグ付きベースモデルを破壊しない範囲でプロポーションやマテリアルを編集する。
- 必要に応じてテクスチャ投影、手動ペイント、マテリアル調整を検討する。

## Task 3G への引き渡し

Task 3G では、最低限以下のアニメーションを用意または確認する。

- idle / stand
- walk
- jump または飛ぶような上下移動
- sleep または lie-down

高品質な自然動作は後続改善とし、まずはGodotで再生できることを優先する。

## 参照元

- Quaternius FAQ: https://quaternius.com/faq.html
- Quaternius Ultimate Animated Animal Pack: https://quaternius.com/packs/ultimateanimatedanimals.html
- Quaternius Farm Animal Pack: https://quaternius.com/packs/farmanimal.html
- Blender glTF 2.0 documentation: https://docs.blender.org/manual/en/4.3/addons/import_export/scene_gltf2.html
- Godot Importing 3D scenes: https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/index.html
- 3D Menagerie paper: https://arxiv.org/abs/1611.07700

