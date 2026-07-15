# Task 6.3: Tripo Reference Visual Pass 進捗

## 実施日

2026-06-30

## 目的

Tripo v2.5のtexture付き静的GLBを参照し、既存の可動モデル `cat_fluffy_shortleg_pass.glb` の見た目を安全に一段改善する。

このTaskでは、Tripo meshそのもののリギング、texture転写、UV bake、Hunyuan3D texture生成は行わない。既存リグとアニメーションを保持したまま、マテリアル色、ポリゴン単位の柄配置、fur shellの胸腹毛ボリュームだけを調整する。

## 入力

- 可動モデルBlend: `output/rigged/cat_fluffy_shortleg_pass.blend`
- Tripo v2.5参照GLB: `output/raw_3d/cloud_manual/tripo/calico_cat_v25/calico_cat_v25.glb`

## 実装ファイル

- `blender/cat_tripo_reference_visual_pass.py`
- `scripts/063_cat_tripo_reference_visual_pass.py`

## 出力

- `output/rigged/cat_tripo_reference_visual_pass.blend`
- `output/clean_3d/cat_tripo_reference_visual_pass.glb`
- `output/clean_3d/cat_tripo_reference_visual_pass.fbx`
- `output/godot/cat_tripo_reference_visual_pass.glb`
- `godot/Godot3dcat/cat_tripo_reference_visual_pass.glb`
- `output/reports/task63_cat_tripo_reference_visual_pass.json`
- `output/reports/task63_cat_tripo_reference_visual_pass_plan.json`
- `output/reports/task63_cat_tripo_reference_visual_glb_inspection.json`
- `output/reports/task63_cat_tripo_reference_visual_animation_validation.json`
- `output/reports/task63_cat_tripo_reference_side_preview.png`
- `output/reports/task63_cat_tripo_reference_front_preview.png`

Godot review scene:

- `godot/Godot3dcat/MainAppearance.tscn` を `res://cat_tripo_reference_visual_pass.glb` 参照へ更新。

## 実施内容

1. `cat_fluffy_shortleg_pass.blend` を入力にした。
2. Tripo v2.5 GLBをBlend内に参照オブジェクトとしてimportした。
3. export時はskinned meshとarmatureだけを選択し、Tripo参照meshをGLB/FBXに含めないようにした。
4. 白毛、茶毛、黒毛、クリーム影のマテリアル色をTripo参照と実画像の中間へ再調整した。
5. 背中、胴体側面、顔cap、尻尾のポリゴンmaterial assignmentを再調整した。
6. 初回出力では後脚に茶色が入りすぎたため、脚は白/クリーム中心になるよう柄ルールを修正して再生成した。
7. fur shellの胸、腹、肩、上脚、頭まわりを少し増量した。

## 検証結果

`output/clean_3d/cat_tripo_reference_visual_pass.glb`:

- mesh数: 2
  - main skinned mesh
  - fur shell mesh
- skin数: 1
- animation数: 12
- material数: 4
- Tripo参照mesh: exportに含まれない
- `Idle`: available
- `Walk`: available
- `Jump_ToIdle`: available
- sleep / lie-down: 従来どおり専用clipなし。`Eating` / `Idle_2_HeadLow` がfallback。

## 目視結果

改善点:

- 従来より白毛が少し落ち着き、クリーム影を含む色味になった。
- 茶毛が実画像/Tripo参照寄りに暖かくなった。
- 胴体側面の三毛patchが現行版より整理された。
- 胸毛・腹毛方向のfur shellが少し強まり、脚を毛で隠す方向を維持した。

注意点:

- texture transferはしていないため、Tripoの毛流れそのものはまだGLBには入っていない。
- 低ポリゴン/フラットマテリアルの限界は残る。
- 正面の顔・胸まわりはまだ実画像ほど丸く豊かではない。
- 本格的に実画像へ寄せるには、次段階でtexture生成またはUV/bake系の検討が必要。

## 判断

Task 6.3は、現行Frameworkで安全にできる範囲のTripo参照反映として完了。

Hunyuan3Dはまだ使わない。理由は、Tripo v2.5参照から色味と毛量方向の改善材料は得られており、先にGodotで今回版を確認する価値があるため。

## 次の確認

Godotで `MainAppearance.tscn` を開き、以下を確認する。

- 色味が前版より実画像寄りか。
- 後脚の茶色が強すぎないか。
- 胸毛・腹毛の増量が破綻していないか。
- `Walk` でfur shellが不自然にずれないか。
- `Jump_ToIdle` で外側shellが目立ちすぎないか。
