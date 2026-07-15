# Task 6.1: Meshy / Tripo 無料枠優先のAI 3D生成検証計画

## 実施日

2026-06-30

## 背景

`cat_fluffy_shortleg_pass.glb` は、現行の低ポリゴン・フラットマテリアル・既存リグ維持の範囲では短期改善の上限に近い。

今後、Blender手作業に強く依存すると、このFrameworkを作っている目的から外れる。そのため、次の段階ではAI 3D生成サービスを使い、写真に近いテクスチャ・毛流れ・柄・形状を得られるか検証する。

ユーザー方針:

- Meshy と Tripo を無料枠で使える範囲で優先検証する。
- Meshy / Tripo で十分な成果が得られない場合の最後の手立てとして Hunyuan3D を残す。
- Blenderは手作業モデリング用途ではなく、自動import、normalize、preview、inspection、exportの実行環境として扱う。

## Phase 0確認結果

2026-06-30時点で、ユーザー確認により Tripo と Meshy は無料版だけではAPI利用できない見込み。

Meshy公式API pricingでも、生成APIは事前にAPI usageを購入して使う方式と説明されている。そのため、当初想定していた「無料枠でAPIを1回ずつ試す」計画は、そのままでは実行しない。

この結果を受けて、次の優先順位へ切り替える。

1. Meshy / Tripo のWeb UI無料枠で生成とGLB/FBX/OBJ downloadができるか確認する。
2. Web UI生成物を手動downloadし、Framework側でimport / normalize / preview / compareする。
3. Web UIでも十分に試せない場合は、Hunyuan3Dを最後の手立てとして再開する。
4. API利用は、無料で使えることが確認できた場合、またはユーザーが有料credit利用を明示的に許可した場合だけ再検討する。

追加確認:

- Meshy: Web UIの生成結果は良さそうだが、downloadが有料のため今回の無料枠検証対象から外す。
- Tripo: v3.1はdownloadが有料の見込み。v2.5ではGLB downloadが可能だったため、v2.5出力をFramework側の手動Cloud assetとして受け入れた。
- 受け入れ元: `input/cloud_manual/tripo/calico cat 3d model.glb`
- Framework処理用コピー: `output/raw_3d/cloud_manual/tripo/calico_cat_v25/calico_cat_v25.glb`

## 基本方針

1. 既存の `cat_fluffy_shortleg_pass.glb` は、当面の可動モデルとして固定する。
2. Meshy / Tripo の出力は、最初は最終可動モデルではなく「高品質な静的参照アセット」として扱う。
3. 生成結果が良ければ、以下のどれに使えるか判断する。
   - テクスチャ・毛色・柄の参照
   - 形状シルエットの参照
   - 既存リグ付きモデルの改善方針
   - 将来的なリグ転写または再リギング候補
4. 実API送信は必ずopt-inにする。
5. 無料枠・残credit・1回あたりcredit消費を確認するまで、実送信はしない。
6. 有料creditを自動消費する処理は実装しない。
7. 無料版でAPIが使えない場合は、API実装ではなく「Web UI生成物の受け入れ・比較」をFramework側の主作業にする。

## 参照した公式情報

### Meshy

- API pricingはcredit制。公式pricingでは、生成APIは事前にAPI usageを購入して使う形と説明されている。
- Image to 3D / Multi Image to 3D は、モデル種別とtexture有無によりcredit消費が異なる。
- Multi Image to 3D は、1から4枚の画像入力、texture生成、PBR、4K base color texture、texture prompt、target format `glb`、multi-view thumbnailなどに対応している。
- 画像入力は公開URLまたはbase64 data URIで渡せる。

参照:

- https://docs.meshy.ai/en/api/pricing
- https://docs.meshy.ai/en/api/multi-image-to-3d

### Tripo

- 既存リポジトリには `scripts/03_tripo_image_to_3d.py` があり、dry-run、upload、task creation、polling、raw response保存、download準備の実装がある。
- Tripoは現在このFramework上で最小工数で再検証できるprovider。
- 無料枠、残credit、利用可能task種別はアカウント状態に依存する可能性があるため、実送信前にTripo dashboard / docsで確認する。

参照:

- https://platform.tripo3d.ai/docs/introduction
- `scripts/03_tripo_image_to_3d.py`

## Provider優先順位

### 第1候補: Tripo

理由:

- 既存スクリプトがある。
- dry-run前提の安全設計がすでにある。
- まず1枚画像から、現在のAPI接続・出力品質・credit消費感を最小工数で確認できる。

期待する成果:

- texture付きGLBが取得できるか。
- 実猫の三毛柄・長毛感が、現行モデルよりどれくらい近づくか。
- 生成結果をBlenderで正規化し、横/正面プレビュー比較に使えるか。

### 第2候補: Meshy

理由:

- Multi Image to 3D があり、1から4枚の写真を使える。
- texture生成、PBR、4K base color、target format `glb`、thumbnail出力があり、今回の「色・毛流れ・柄」の課題に合う。
- data URI入力に対応しているため、ローカル写真を外部公開URL化せずに送れる可能性がある。

注意:

- 公式pricing上はcredit制で、無料API枠が常に使えるとは限らない。
- 実送信前にMeshy dashboardで残creditと消費creditを確認する。
- 無料creditが確認できない場合は、Meshyはdry-runまでに止める。

### 最後の手立て: Hunyuan3D

理由:

- すでにローカルでshape-only生成の実績がある。
- Cloud providerが使えない、credit不足、出力品質不足、API制約が強い場合のfallbackとして残す。
- ただしtexture生成はVRAM・実行時間・セットアップ負荷が高い可能性があるため、最初から切らない。

## 実行フェーズ

### Phase 0: 無料枠とAPIキー確認

目的:

- 実API送信できる状態かを確認する。
- paid実行を避ける。

実施内容:

- `.env` に `TRIPO_API_KEY` と `MESHY_API_KEY` を設定できるか確認する。
- Tripo dashboardで残credit、無料枠期限、1生成あたりの消費creditを確認する。
- Meshy dashboardで残credit、無料枠有無、Multi Image to 3D with texture の消費creditを確認する。
- 確認結果を `output/reports/task61_provider_credit_check.json` に記録する。

完了条件:

- credit残高が不明なproviderは実送信対象から外す。
- 無料枠内で何回まで送るかを明記する。
- 初期上限は `1 provider 1 generation` とする。

現在の判定:

- Tripo: 無料版だけではAPI利用不可の見込み。API送信タスクは保留。
- Meshy: 無料版だけではAPI利用不可の見込み。公式pricing上もAPI生成は事前購入型。API送信タスクは保留。
- Meshy Web UI: downloadが有料のため今回対象外。
- Tripo Web UI: v3.1 downloadは有料の見込み。v2.5 GLB downloadは成功。
- 次の作業はTripo v2.5 GLBのBlender比較と、必要に応じたHunyuan3D fallback判断。

### Phase 0B: Web UI無料枠の確認

目的:

- APIを使わずに、Tripo / Meshy のWeb UIで無料生成とasset downloadができるか確認する。

確認項目:

- 無料版で Image to 3D または Multi Image to 3D が実行できるか。
- 生成結果を GLB / FBX / OBJ のいずれかでdownloadできるか。
- texture付きassetをdownloadできるか。
- 商用/個人利用、保持期限、download回数などの制約があるか。
- 生成結果をこのFrameworkの `output/raw_3d/cloud_manual/<provider>/` に置けるか。

手動download時の保存先:

```text
output/raw_3d/cloud_manual/tripo/<date_or_asset_name>/
output/raw_3d/cloud_manual/meshy/<date_or_asset_name>/
```

完了条件:

- どちらか一方でもtexture付き3D assetをdownloadできれば、Phase 4のBlender自動比較へ進む。
- どちらもdownload不可なら、Cloud provider無料枠の検証を停止し、Hunyuan3D fallbackへ進む。

現在の結果:

- Tripo v2.5でtexture付きGLB download成功。
- Meshyはdownload有料のため停止。
- Phase 4へ進む。

### Phase 1: 入力画像セットの固定

目的:

- Meshy / Tripo / Hunyuan3D の比較条件を揃える。

候補入力:

- 正面: `input/selected_photos/reference_front_face_1763363798733.jpg`
- 横: `input/raw_photos/横.png`
- 横2: `input/raw_photos/横2.png`
- 背中/尻尾: `input/selected_photos/reference_back_top_tail_1755598074234.jpg`
- 既存cutout: `input/masks/*_cutout.png`

実施内容:

- providerごとに使用する画像を決める。
- 背景あり写真とcutoutのどちらが向くかを分けて試す。
- 入力画像リストを `output/reports/task61_input_image_set.json` に保存する。

完了条件:

- Tripo用の1枚入力を決める。
- Meshy用の1から4枚入力を決める。
- 画像の向き、用途、期待効果を記録する。

### Phase 2: Tripo dry-run / 1回送信

目的:

- 既存Tripo連携を使い、無料枠内でtexture付き静的GLBを1つ得られるか確認する。
- Phase 0の結果により、無料版APIが使えない間はこのPhaseを保留する。

実施内容:

- まずdry-run:

```powershell
python scripts/03_tripo_image_to_3d.py --dry-run
```

- payload、入力画像、出力先、download設定、raw response保存先を確認する。
- credit残高が確認済みの場合だけ、ユーザー承認後に `--submit` を使う。

出力予定:

- `output/reports/raw_api_response_tripo_<task_id>.json`
- `output/raw_3d/cloud/tripo/<task_id>/`
- `output/reports/task61_tripo_generation.json`

評価:

- texture付きGLBが取得できたか。
- 実猫の白/茶/黒の配色が近いか。
- 横から見た体型・脚・尻尾の印象が近いか。
- Blenderでimportできるか。
- Godot/GLB用途の参照として使えるか。

中止条件:

- credit不足。
- APIキー未設定。
- 送信前に有料課金が必要。
- 出力形式がGLBで取得できない。

### Phase 3: Meshy dry-run / 1回送信

目的:

- Multi Image to 3Dで、複数写真からより良いtexture付きGLBを得られるか確認する。
- Phase 0の結果により、無料版APIが使えない間はこのPhaseを保留する。

実施内容:

- Meshy用スクリプトを追加する。
  - 例: `scripts/061_meshy_multi_image_to_3d.py`
- 最初はdry-runのみ。
- payloadには以下を基本設定として入れる。

```json
{
  "image_urls": ["data:image/jpeg;base64,..."],
  "ai_model": "latest",
  "should_texture": true,
  "enable_pbr": true,
  "hd_texture": false,
  "target_formats": ["glb"],
  "multi_view_thumbnails": true,
  "remove_lighting": true
}
```

初回は `hd_texture: false` にする。4K textureは魅力的だが、無料枠消費や処理時間が増える可能性があるため、最初は標準textureで品質を確認する。

出力予定:

- `output/reports/task61_meshy_multi_image_plan.json`
- `output/reports/raw_api_response_meshy_<task_id>.json`
- `output/raw_3d/cloud/meshy/<task_id>/model.glb`
- `output/raw_3d/cloud/meshy/<task_id>/preview_front.png`
- `output/raw_3d/cloud/meshy/<task_id>/preview_right.png`
- `output/raw_3d/cloud/meshy/<task_id>/preview_back.png`
- `output/raw_3d/cloud/meshy/<task_id>/preview_left.png`

評価:

- Tripoよりtextureが実猫に近いか。
- 複数写真が形状と柄の再現に効いているか。
- 毛流れや三毛の境界が現行モデルより良いか。
- GLBがBlenderで安定してimportできるか。
- 生成メッシュのポリゴン数・原点・スケールが扱いやすいか。

中止条件:

- 無料creditが確認できない。
- Multi Image to 3D with texture のcredit消費が無料枠を超える。
- APIがdata URI入力を受け付けない。
- GLBが取得できない。

### Phase 4: Blender自動比較

目的:

- Cloud生成GLBを、既存モデルと同じ条件で比較する。
- API生成物だけでなく、Web UIから手動downloadしたGLB/FBX/OBJも比較対象にする。

実施内容:

- Blenderで各GLBをimportする。
- scale、origin、floor contactをnormalizeする。
- 正面、横、背面、斜めのpreview画像を自動生成する。
- GLB内のmaterial、texture、mesh count、polygon count、animation有無をinspectする。

出力予定:

- `output/reports/task61_provider_comparison.md`
- `output/reports/task61_<provider>_glb_inspection.json`
- `output/reports/previews/task61_<provider>_front.png`
- `output/reports/previews/task61_<provider>_side.png`
- `output/reports/previews/task61_<provider>_back.png`

評価軸:

- 実猫らしさ。
- 横向きシルエット。
- 三毛柄の位置。
- 白毛の陰影。
- 長毛感。
- 尻尾の毛量。
- Blender/Godotに持ち込める安定性。
- 既存リグ付きモデルへ転用できる情報量。

### Phase 5: 採用判断

判断パターン:

1. Tripoが良い:
   - Tripo出力を形状/texture参照として採用。
   - Meshyは必要なら後続比較に回す。
2. Meshyが良い:
   - Meshy出力を形状/texture参照として採用。
   - 可能ならMeshyのRetexture / Rigging / Animationも別タスクで検討する。
3. 両方良い:
   - 既存リグ付きモデルは維持し、Tripo/Meshyの良い部分を比較参照にする。
4. 両方不十分:
   - Hunyuan3D texture生成または別ローカルAI texturingを最後の手立てとして検討する。
5. Cloud生成物が静的モデルとして非常に良い:
   - 既存リグ経路とは別に、静的展示用GLBとして保持する。
   - リグ転写は別タスクにする。

## 安全設計

- 実API送信は `--submit` または `--execute` が明示された場合のみ。
- デフォルトは必ずdry-run。
- `.env` のAPIキーはログに出さない。
- raw response内の署名付きURLはcommitしない。
- `output/raw_3d/cloud/` 配下はprovider別、task id別に保存する。
- 既存の `output/clean_3d/cat_fluffy_shortleg_pass.glb` は上書きしない。
- 無料枠を超える可能性がある処理は実行しない。
- 1回目の実送信は、各provider最大1回まで。

## 実装予定ファイル

追加候補:

- `scripts/061_check_cloud_provider_credits.py`
- `scripts/061_meshy_multi_image_to_3d.py`
- `blender/render_glb_preview.py` のprovider比較対応拡張
- `docs/plan_task61_meshy_tripo_free_tier_ai_generation.md`
- `output/reports/task61_provider_credit_check.json`
- `output/reports/task61_provider_comparison.md`

既存活用:

- `scripts/03_tripo_image_to_3d.py`
- `scripts/056_inspect_glb.py`
- `blender/render_glb_preview.py`
- `output/clean_3d/cat_fluffy_shortleg_pass.glb`

## 推奨する次の一手

Phase 0/0Bの結果、無料版API利用は難しい見込み。Meshyはdownload有料のため停止し、Tripo v2.5 GLBを手動Cloud assetとして受け入れた。次は Phase 4 のBlender自動比較を進める。

その後の優先順位は以下を推奨する。

1. Framework側: Tripo v2.5 GLBをimport / normalize / preview / inspectする。
2. Tripo v2.5 GLBを、`cat_fluffy_shortleg_pass.glb` の見た目参照として採用できるか判断する。
3. Hunyuan3D: Tripo v2.5の品質が不十分な場合だけ進める。

この順番なら、有料APIを使わず、Hunyuan3Dを最後の手立てとして温存しつつ、取得できたTripo v2.5 assetを最大限活用できる。
