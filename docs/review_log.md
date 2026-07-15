# レビューログ

このプロジェクトは、ChatGPT、Claude、Gemini、Codex、ユーザーからのレビューを統合しながら進める。

## レビュー形式

各レビューエントリは次の形式を使う。

```markdown
### REV-YYYYMMDD-XXX: タイトル

- レビュー担当: ChatGPT | Claude | Gemini | User | Codex
- 日付: YYYY-MM-DD
- 対象:
- 概要:
- 指摘事項:
  - [High]
  - [Medium]
  - [Low]
- 対応:
  - 採用:
  - 保留:
  - 不採用:
- 関連する意思決定:
```

## レビュー記録

### REV-20260528-001: 初期マルチエージェントレビュー方針

- レビュー担当: ChatGPT
- 日付: 2026-05-28
- 対象: MVPロードマップとプロジェクト運営
- 概要: ChatGPTはPM兼アーキテクトとして、レビュー横断でMVP範囲、ロードマップ、リスク、採否判断を整理する。
- 指摘事項:
  - [High] レビュー指摘と採否判断は、文脈が散らばらないよう永続的なドキュメントに残す必要がある。
  - [Medium] MVP範囲と将来のframework構想は分けて管理する必要がある。
  - [Low] タスクテンプレートにより、実装ターン間の曖昧さを減らせる。
- 対応:
  - 採用: `docs/review_log.md`、`docs/decisions.md`、`docs/backlog.md` を運用記録として使う。
  - 保留: 詳細なGitHub Issue/PRルールは、必要になれば後続のドキュメントタスクで扱う。
  - 不採用: なし。
- 関連する意思決定: DEC-20260528-001, DEC-20260528-002

### REV-20260528-002: Claude仕様レビュー要約

- レビュー担当: Claude
- 日付: 2026-05-28
- 対象: 初期プロジェクト仕様
- 概要: Claudeは仕様をレビューし、タスク分離、メタデータ管理、ディレクトリとドキュメントの一貫性を重視するよう指摘した。
- 指摘事項:
  - [High] API確認やBlender確認は環境依存の複雑さを持つため、Task 0.5をTask 0から分離するべき。
  - [Medium] Task 1とTask 1.5は分け、インベントリ生成と主観的な画像選択を混ぜないようにするべき。
  - [Medium] スクリプト追加に合わせて、メタデータとディレクトリ命名の一貫性を保つ必要がある。
  - [Low] 前提と未決事項をドキュメントに明示するべき。
- 対応:
  - 採用: Task 0.5、Task 1、Task 1.5を別々のbacklog項目として維持する。
  - 保留: メタデータスキーマの詳細はTask 1実装時に扱う。
  - 不採用: なし。
- 関連する意思決定: DEC-20260528-005

### REV-20260528-003: Gemini実装・ツールレビュー要約

- レビュー担当: Gemini
- 日付: 2026-05-28
- 対象: 3D生成と処理計画
- 概要: Geminiは、プロバイダー選定、画像マスクのリスク、Blender正規化、Windows/WSL2/Blender CLI境界を指摘した。
- 指摘事項:
  - [High] 自動化スクリプトがパスに依存する前に、Windows、WSL2、Docker、Blender CLIの境界を決める必要がある。
  - [Medium] より深いパイプライン作業の前に、Tripo優先、Quad出力、リトポロジーオプションを確認する必要がある。
  - [Medium] `rembg` は影やエッジのartifactを作る可能性があるため、レビュー出力が必要。
  - [Low] Blender cleanupでは足元原点配置とUnity軸設定を考慮するべき。
- 対応:
  - 採用: Task 0.5でruntimeとBlender CLI方針を決める。
  - 保留: `rembg`、Quad/Retopo検証、足元原点cleanupは後続実装タスクへ回す。
  - 不採用: なし。
- 関連する意思決定: DEC-20260528-003, DEC-20260528-004, DEC-20260528-005

### REV-20260621-004: Codex Task 2実装レビュー

- レビュー担当: Codex
- 日付: 2026-06-21
- 対象: Task 2 背景除去実装
- 概要: 生成画像artifactをGit外に置き、レビュー可能なマスク指標を記録するローカル背景除去ステップを実装した。
- 指摘事項:
  - [High] エッジartifactや前景欠落は下流のgeometryに影響するため、3D生成前に背景除去出力を手動レビューする必要がある。
  - [Medium] ONNXモデルのダウンロードと実行性能は、ローカルマシンとcache状態に依存する。
  - [Low] 前景coverage警告は軽量なsmoke checkであり、semantic品質スコアではない。
- 対応:
  - 採用: 透明cutout、alpha mask、checkerboard review画像、JSON/CSVレポートを追加する。
  - 保留: 自動semantic mask scoringと代替背景除去プロバイダーは将来作業とする。
  - 不採用: Task 2中に3D生成APIを呼び出すこと。
- 関連する意思決定: DEC-20260621-008

### REV-20260621-005: Codex Task 3プロトタイプレビュー

- レビュー担当: Codex
- 日付: 2026-06-21
- 対象: Task 3 Tripo Image-to-3Dプロトタイプ
- 概要: デフォルトdry-run、明示的submit、raw API response保存、polling、任意のoutput downloadを持つTripoプロトタイプスクリプトを追加した。
- 指摘事項:
  - [High] 実API送信はクレジットを消費する可能性があるため、明示的な `--submit` を必須にする必要がある。
  - [Medium] Tripoの出力URLは短時間で失効するため、成功直後にraw responseと必要なdownloadを保存する必要がある。
  - [Low] 最初のプロトタイプは単一画像のImage-to-Modelのみを扱い、single-image flowが実証されるまでmultiview生成は対象外とする。
- 対応:
  - 採用: dry-run request planning、upload/create/poll flow、raw response files、normalized report outputを追加する。
  - 保留: Multi-image Tripo生成、streaming progress、provider abstraction。
  - 不採用: smoke check中にAPI jobを自動送信すること。
- 関連する意思決定: DEC-20260621-009

### REV-20260622-006: Codex Task 3 Blender-first実装レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3 Blender-first Asset Baseline
- 概要: selected/masked imagesを集め、scene計画を作り、Blender Pythonで参照画像をplaneまたはimage emptyとして配置するBlender-first参照シーンパイプラインを実装した。
- 指摘事項:
  - [High] 実際の `.blend` 生成には入力画像と有効な `BLENDER_PATH` の両方が必要なため、前提がない環境ではdry-runが必要。
  - [Medium] 参照シーンはmodeling baselineであり、自動3D生成ではないため、下流のcleanup/exportはTask 4に残す。
  - [Low] `.blend` がmanual modelingとbase-model transferの主な受け渡しなので、GLB exportは任意でよい。
- 対応:
  - 採用: `scripts/03_blender_reference_scene.py`、`blender/create_reference_scene.py`、dry-run planning、`.blend` output、任意GLB export、日本語進捗レポートを追加する。
  - 保留: cleanup normalization、foot-origin placement、GLB/FBX production export、game-engine import validation。
  - 不採用: Task 3の一部としてTripo、Meshy、有料3D生成APIを呼び出すこと。
- 関連する意思決定: DEC-20260622-010

### REV-20260622-007: Codex Task 4 Blender cleanup/export実装レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 4 Blender Cleanup and Export
- 概要: asset位置とscaleを正規化し、必要に応じて参照objectを削除し、game-engine確認向けにGLB/FBXを出力するBlender cleanup/export pipelineを実装した。
- 指摘事項:
  - [High] 実exportには既存input assetと有効な `BLENDER_PATH` が必要で、dry-runはcommand planの検証のみを行う。
  - [Medium] reference object削除はproduction exportには有用だがmodeling reviewには有害なため、automatic cleanupは保守的にするべき。
  - [Low] engine固有のimport tuningはBlender cleanupに早期に埋め込まず、Task 5からTask 7で検証するべき。
- 対応:
  - 採用: `scripts/04_blender_cleanup_export.py`、`blender/cleanup_export.py`、dry-run planning、foot/base origin placement、target-height scaling、GLB export、FBX export、`docs/game_engine_export_policy.md`を追加する。
  - 保留: Godot、Unity、Unreal import validationは別タスクに残す。
  - 不採用: 有料生成APIやengine固有自動化をTask 4に含めること。
- 関連する意思決定: DEC-20260622-010

### REV-20260622-008: Codex Task 5 Godot import check実装レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 5 Godot Import Check
- 概要: Task 4のGLBをGodot staging directoryへcopyし、Godot sceneで表示確認するためのGodot import準備ステップと手動ガイドを実装した。
- 指摘事項:
  - [High] 実際のGodot表示確認にはTask 4で生成したGLBが必要で、dry-runは準備経路の検証しかできない。
  - [Medium] import成功だけではscale、origin、床接地、material品質は証明できないため、手動のvisual inspectionが必要。
  - [Low] 繰り返しimport確認が高コストになった場合、Godot automationを後で追加できる。
- 対応:
  - 採用: `scripts/05_godot_import_check.py`、`godot/GodotImportGuide.md`、`output/godot/`、dry-run planning、GLB copy preparation、日本語進捗レポートを追加する。
  - 保留: Automated Godot editor/headless validationとscreenshot capture。
  - 不採用: Godot installationやeditor automationをTask 5の前提にすること。
- 関連する意思決定: DEC-20260622-010

### REV-20260622-009: Codex Task 3A計画リセットレビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3A Free/Local Image-to-3D Survey とworkflow再設計
- 概要: MVP方針を、無料/ローカル/OSS優先の半自動Image-to-3D生成、Blender自動import/cleanup/export、Godot/Unity/Unreal import check中心に再編した。
- 指摘事項:
  - [High] MVPをcreditなしで再現可能にするため、有料APIプロバイダーはoptional/deferredのままにする必要がある。
  - [High] Blenderは中心に置くが、完全手動modeling専用stageとして扱うべきではない。
  - [Medium] Task 3はsurvey、local prototype、Blender import/normalize、base-model transfer routeに分け、リスクを見えるようにする必要がある。
  - [Low] 既存Tripo作業はexperimental/deferredと明示すればrepositoryに残せる。
- 対応:
  - 採用: `docs/local_3d_generation_survey.md` を追加し、DEC-20260622-LOCAL-FIRST-3Dを追加し、Task 3AからTask 3Dを再定義し、Task 4からTask 7を新しいlocal-first flowへresetし、pipeline設定を更新する。
  - 保留: 実際のlocal model installation、generation、Blender import execution、game-engine import execution。
  - 不採用: Tripo/Meshyまたはcloud-credit APIをdefault MVP pathにすること。
- 関連する意思決定: DEC-20260622-LOCAL-FIRST-3D

### REV-20260622-010: Codex Task 3A調査実行レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3A Free/Local Image-to-3D Survey
- 概要: 無料/ローカル/OSS優先のImage-to-3D prototype pathとして、TripoSR、InstantMesh、Hunyuan3D、Blender addon/wrapper経路を調査した。
- 指摘事項:
  - [High] TripoSRは単純なsingle-image path、MIT license、標準VRAM約6GBの記載があるため、最初のprototype候補として最適。
  - [Medium] Hunyuan3Dは高品質なtextured assetとBlender integrationが有望だが、licenseとVRAM制約によりsecond-stage候補がよい。
  - [Medium] InstantMeshはpermissive licenseでOBJ出力を通じてBlenderに取り込めるが、setupとmemory riskはTripoSRより高い。
  - [Low] Blender addon/wrapper経路は、最初のprototypeにするより、検証済みlocal CLI/API pathをwrapする形がよい。
- 対応:
  - 採用: Task 3AをDoneにし、Task 3BをPlannedにし、TripoSRを最初に推奨し、Hunyuan3D-2mini shape-only / InstantMeshをfallback候補として記録する。
  - 保留: model dependenciesのinstall、local generation実行、VRAM/runtime測定、generated assetのBlender import。
  - 不採用: Tripo/Meshyまたはcloud-credit APIから始めること。
- 関連する意思決定: DEC-20260622-LOCAL-FIRST-3D

### REV-20260622-011: Codex Task 3B TripoSR prototype setupレビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3B Local Image-to-3D Prototype
- 概要: Task 2 cutout imagesを使ってTripoSR local prototype pathを開始し、専用local environmentを作成し、PyTorchからRTX 4060が見えることを確認した。
- 指摘事項:
  - [High] TripoSR setupは、現在のCUDA PyTorch環境で `torchmcubes` がCUDA Toolkit/NVCCを要求する一方、このマシンにCUDA Toolkitがないためblocked。
  - [Medium] blockerは入力画像ではなく、environment/toolchainの問題。
  - [Medium] OBJ/GLB/PLYは生成されていないため、TripoSR出力からBlender importやTask 3Cを開始できない。
  - [Low] CPU fallbackは可能かもしれないが、意図したRTX 4060 local GPU pathの検証にはならない。
- 対応:
  - 採用: `external/` にTripoSRをcloneし、`.venv_triposr` を作成し、CUDA PyTorchをinstallし、CUDA availabilityを確認し、blockerを日本語で記録する。
  - 保留: 実際のlocal 3D generation、runtime/VRAM measurement、Blender importability check、Task 3C execution。
  - 不採用: Tripo/Meshy有料cloud APIへ切り替えること。
- 関連する意思決定: DEC-20260622-LOCAL-FIRST-3D

### REV-20260622-012: Codex Task 3B Hunyuan3D fallback生成レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3B Local Image-to-3D Prototype
- 概要: blockedになったTripoSR経路からHunyuan3D-2mini shape-onlyへ切り替え、Task 2 cutout imageからlocal GLBを生成した。
- 指摘事項:
  - [High] Hunyuan3D-2mini shape-onlyにより、有料APIなしで `output/raw_3d/local/hunyuan3d/side_right_hunyuan3d_shape.glb` を生成できた。
  - [Medium] 初回実行はHugging Face model downloadが必要だったため、総経過時間はgenerationよりmodel retrievalに支配された。
  - [Medium] 生成メッシュは208,506 vertices、417,000 facesと高密度なので、Task 3CまたはTask 4でBlender cleanup/decimationを検討するべき。
  - [Low] 最初のlocal prototypeをRTX 4060 8GB path内に収めるため、texture generationは意図的にskipした。
- 対応:
  - 採用: `scripts/03b_hunyuan3d_shape_prototype.py` を追加し、`.venv_hunyuan3d` を作成し、Hunyuan3D dependenciesをinstallし、GLBを生成し、Task 3B progressを日本語で更新する。
  - 保留: Blender import/normalize、mesh cleanup、decimation、texture evaluation、engine import validation。
  - 不採用: 別local候補を試す前に、TripoSRをunblockするためだけにCUDA Toolkitをinstallすること。
- 関連する意思決定: DEC-20260622-LOCAL-FIRST-3D

### REV-20260622-013: Codex Task 3C Blender import/normalizeレビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3C Blender Import and Normalize
- 概要: Hunyuan3D-2mini GLBをBlenderへimportし、scale/origin/base positionを正規化し、clean GLB/FBX出力を作成した。
- 指摘事項:
  - [High] Blender CLI実行は当初、`blender/cleanup_export.py` が `--` 後の引数だけをparseしていなかったため失敗した。この問題は再実行前に修正した。
  - [Medium] 正規化後のassetも417,000 facesと高密度なので、engine import時に性能が悪い場合はTask 4でdecimationを検討するべき。
  - [Low] texture generationはこのpassでは引き続き対象外。出力はまずshape/display validationに適している。
- 対応:
  - 採用: Blender script argument parsingを修正し、Blender 5.0 CLI import/normalize/exportを実行し、`cat_clean.glb` と `cat_clean.fbx` を出力し、Task 3C progressを日本語で記録する。
  - 保留: Mesh decimation、material cleanup、texture generation、visual engine checks。
  - 不採用: 有料APIやcloud conversion serviceを使うこと。
- 関連する意思決定: DEC-20260622-LOCAL-FIRST-3D

### REV-20260622-014: Codex Task 3D リグ付き猫ベースモデル経路調査

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3D Rigged Cat Base Model Route Survey
- 概要: 静的な猫風生成メッシュから、リグ付き・アニメーション可能な猫ワークフローへ進む現実的な経路を調査した。
- 指摘事項:
  - [High] Hunyuan3Dの高密度メッシュを直接アニメーションさせるのはMVP向けではなく、reference/shape candidateとして残すべき。
  - [High] 最初の実用的MVP経路は、既存CC0 animated quadruped assetを使い、Blender -> GLB/FBX -> Godot animation playbackを検証すること。
  - [Medium] Quaternius Ultimate Animated Animal PackはCC0、animated、FBX/OBJ/Blend/glTF提供のため、最初のvalidation candidateとして最適。
  - [Medium] Quaternius packはcat-specificではないため、Task 3Fでcat-like appearanceとproportionsを扱う必要がある。
  - [Low] SMAL/3D Menagerie系研究モデルは参考になるが、production assetへの最短経路ではない。
- 対応:
  - 採用: `docs/rigged_cat_base_model_survey.md` を追加し、日本語Task 3D progress reportを追加し、Task 3DをDoneにし、Task 3EをPlannedにする。
  - 保留: asset packのdownload/import、Blender armature inspection、animation export、Godot playback validation。
  - 不採用: fully automatic riggingやdirect dense generated mesh animationをMVP経路にすること。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-015: Codex Task 3E リグ付きベースモデル準備レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3E Rigged Cat Base Model Preparation
- 概要: Quaternius Ultimate Animated Animal Packをdownloadし、最初のCC0 animated quadruped validation assetとして `Fox.gltf` を選び、Blender/GLB/FBX出力を準備した。
- 指摘事項:
  - [High] Blender 5.0はrigged glTF assetを正常にimportし、armatureを保持し、animated GLB/FBXをexportできた。
  - [High] exported GLBには12 animationsと1 skinが含まれており、animation-capable asset pathは成立している。
  - [Medium] 選択したFox modelは最終的なcat appearanceではないため、Task 3Fでcat-like proportions、materials、visual adaptationを扱う必要がある。
  - [Medium] sleep/lie-down animationはsource packに含まれておらず、Task 3Gで扱う必要がある。
  - [Low] Blender 5.0ではAction APIが変わったため、inspection scriptでは `action.fcurves` への直接アクセスを避けた。
- 対応:
  - 採用: `blender/prepare_rigged_base_model.py` を追加し、`cat_base_rigged.blend`、`cat_base_rigged.glb`、`cat_base_rigged.fbx` を生成し、`rigged_cat_base_model.json` を書き出し、Task 3E progressを日本語で記録する。
  - 保留: Cat appearance transfer、lie-down animation creation、詳細origin/scale cleanup、game engine playback validation。
  - 不採用: MVPで高密度Hunyuan3D meshへ直接riggingすること。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-016: Codex Task 3F 外観・形状転写計画レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 3F Appearance / Shape Transfer Planning
- 概要: selected photos、masks、Hunyuan3D static mesh、Task 3E Fox rigをどう使い、cat-like animated assetへ近づけるかを定義した。
- 指摘事項:
  - [High] Task 3E Fox rigはanimation-capable baseとして維持し、aggressive shape editsよりarmature、weights、clipsの保持を優先するべき。
  - [High] Hunyuan3D meshはdirect animation targetではなく、static visual referenceとして使うべき。
  - [Medium] source photosとmasksはplanningには十分だが、final appearance作業にはreference image priorityの選択が必要。
  - [Medium] MVP appearance transferはmaterial color、simple patterning、conservative proportion editsから始めるべき。
  - [Low] fully automatic texture projection、fur rendering、direct dense-mesh riggingはMVP外に残す。
- 対応:
  - 採用: `docs/appearance_shape_transfer_plan.md` を追加し、日本語Task 3F progress reportを追加し、Task 3FをDoneにし、Task 3GをPlannedにする。
  - 保留: 実際のBlender appearance editing、texture painting/projection、shape edits、animation set completion。
  - 不採用: photo-perfect texture transferやautomatic riggingを次のMVP stepに含めること。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-017: Codex参照画像背景除去とTask 3Gアニメーションセットレビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Reference image background removal と Task 3G Basic Cat Animation Set
- 概要: selected reference imagesの背景除去を再実行し、cutout品質を確認し、rigged GLB内の基本animation clipsを検証した。
- 指摘事項:
  - [High] 選択された12画像すべてで背景除去が完了し、failureやwarningはなかった。
  - [High] rigged GLBには12 animations、1 skin、1 meshがあり、animation-capable pathが保持されている。
  - [High] Idle、Walk、Jump要件は `Idle`、`Walk`、`Jump_ToIdle` でカバーできる。
  - [Medium] 真のsleep/lie-down clipはなく、`Eating` または `Idle_2_HeadLow` は一時的なrest-like placeholderにしかならない。
  - [Medium] selected reference cutoutsはBlender reference placementに十分で、特にside body、front face、back/tail referencesが有用。
- 対応:
  - 採用: `scripts/02_remove_backgrounds.py` を実行し、reference background removal progressを追加し、`scripts/03g_validate_basic_animation_set.py` を追加し、`task3g_basic_animation_set.json` を書き出し、Task 3GをDoneにし、Task 4をPlannedにする。
  - 保留: 本物のlie-down animation作成、Godotでのvisual animation playback、final rig cleanup/export validation。
  - 不採用: `Eating` をfinal sleep animationとして扱うこと。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-018: Codex Task 4 Blender rig cleanup/animation exportレビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 4 Blender Rig Cleanup and Animation Export
- 概要: rig-safeなBlender cleanup/export pathを追加し、animated modelをgame engine import check向けの正規化済みBlend、GLB、FBXとしてexportした。
- 指摘事項:
  - [High] cleaned GLBはBlender export後も12 animations、1 skin、1 meshを保持している。
  - [High] root-object normalizationによりarmature/mesh関係を保ち、rig/animation integrityを損なう可能性がある破壊的mesh transform applicationを避けた。
  - [Medium] modelはtarget height 1.0、base Z=0に正規化されており、最初のGodot import validationに適している。
  - [Medium] sleep/lie-downは `Eating` または `Idle_2_HeadLow` を使うplaceholder pathのままで、真のsleep animationはまだ存在しない。
  - [Low] cleaned modelは見た目としてまだFox-basedであり、cat-specific appearance transferは後続実装に残る。
- 対応:
  - 採用: `blender/rig_cleanup_export.py`、`scripts/04_blender_rig_cleanup_export.py` を追加し、`cat_rigged_clean.blend`、`cat_rigged_clean.glb`、`cat_rigged_clean.fbx` をexportし、clean GLB animationsを検証し、Task 4をDoneにし、Task 5をPlannedにする。
  - 保留: Godot playback validation、Unity/Unreal checks、real lie-down animation、cat appearance editing。
  - 不採用: static mesh cleanup scriptをrigged assetsに使うこと。transform適用によりrig/animation integrityを損なう可能性があるため。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-019: Codex Task 5 Godot animated import準備レビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 5 Godot Animated Import Check
- 概要: Task 4 animated GLBをGodot import用に準備し、copy後のGLBにもanimationsとskin dataが残っていることを確認し、Godot import guideをanimation playback check向けに更新した。
- 指摘事項:
  - [High] Task 4 cleaned rigged GLBから `output/godot/cat_rigged_clean.glb` を作成した。
  - [High] staged Godot GLBは12 animations、1 skin、1 meshを保持している。
  - [Medium] Godot executableがPATHで見つからなかったため、この環境ではautomated/editor-based visual playback confirmationは実施していない。
  - [Medium] 手動Godot確認では、model displayに加えて `Idle`、`Walk`、`Jump_ToIdle` playbackを確認するべき。
  - [Low] sleep/lie-downはTask 3G由来のplaceholder問題であり、import validationでは解決しない。
- 対応:
  - 採用: rigged clean GLBで `scripts/05_godot_import_check.py` を実行し、assetを `output/godot/` へcopyし、`godot/GodotImportGuide.md` を更新し、Task 5 progressを追加し、Task 5をDoneにし、Task 6をPlannedにする。
  - 保留: GodotがPATHで使えるか手動で開けるまで、Godot Editor visual playback confirmation。
  - 不採用: 現在のMVP targetはanimated rigged GLBなので、static `cat_clean.glb` をTask 5 targetとして扱うこと。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-020: Codex Godot3dcatプロジェクトレビュー

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: `godot/Godot3dcat`
- 概要: ユーザー作成のGodot projectを確認し、rigged GLB import setupを確認し、手動animation review用の簡易playback sceneを追加した。
- 指摘事項:
  - [High] projectには `cat_rigged_clean.glb` があり、Godotが対応する `.import` fileを生成している。
  - [High] imported source GLBには12 animations、1 skin、1 meshが残っている。
  - [High] Godot上でfoxに見えるのは想定通り。現在のrigged base modelはQuaternius Foxであり、cat appearance transferはまだ実装されていないため。
  - [Medium] projectにmain `.tscn` sceneがなかったため、light、camera、model instanceを持つ簡易 `Main.tscn` を追加した。
  - [Medium] 通常のGodot executableはprojectをheadlessで開けるが、この環境ではconsole `--script` validation pathがsignal 11でcrashした。
- 対応:
  - 採用: `Main.tscn`、`play_animation.gd`、`validate_import.gd` を追加し、`run/main_scene` を設定し、Godot project reviewを記録する。
  - 保留: `Idle`、`Walk`、`Jump_ToIdle` のeditor-side visual playback verification。
  - 不採用: fox appearanceをGodot import bugとして扱うこと。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION

### REV-20260622-021: Codex cat appearance pass向けbacklog調整

- レビュー担当: Codex
- 日付: 2026-06-22
- 対象: Task 5 Godot visual confirmation後のbacklog
- 概要: Unity/Unreal確認へ進む前に、Fox-based rigを見た目として猫に近づける新しいTask 5.5を追加した。
- 指摘事項:
  - [High] ユーザーがGodotでmodel表示を確認したため、Task 5 display confirmationは完了。
  - [High] cat appearance transferがまだ実装されていないため、表示modelはまだfox-like。
  - [Medium] そのままUnity/Unrealへ進むとengine compatibilityは検証できるが、主要なvisual issueは解決しない。
  - [Medium] 広いengine checkの前に、focused Blender appearance passを行うべき。
- 対応:
  - 採用: `Task 5.5: Cat Appearance Pass on Fox Rig` を追加し、Plannedに設定し、Task 6をBacklogへ戻す。
  - 保留: 実際のBlender editing、updated GLB/FBX export、Godot re-check。
  - 不採用: fox appearanceをfinal animated cat goalとして許容すること。
- 関連する意思決定: DEC-20260622-RIGGED-CAT-ANIMATION
