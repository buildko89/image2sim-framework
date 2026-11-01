作成した USD モデルを目視で確認するには、現在の環境ですぐに使える 2つの方法 があります。                                                                
  ──────                                                                                                                                                  
  ### 方法 1: Blender 5.2 LTS で開いて確認する（最も詳細に確認可能・推奨）                                                                                
                                                                                                                                                          
  すでに本環境にインストールされている Blender を使い、作成した USD モデル（.usda / .usdc）をマテリアル付きで直接確認できます。                           
                                                                                                                                                          
  ワンコマンドで Blender の GUI が起動し、モデルが自動読み込みされるスクリプトを用意しました：                                                            
                                                                                                                                                          
  #### ① ドローンモデル (drone_assembly.usda) を確認する場合                                                                                              
                                                                                                                                                          
    python scripts/usd/open_in_blender_gui.py --asset drone                                                                                               
                                                                                                                                                          
  #### ② 猫モデル (root_cat.usda) を確認する場合                                                                                                          
                                                                                                                                                          
    python scripts/usd/open_in_blender_gui.py --asset cat                                                                                                 
                                                                                                                                                          
  │ 画面が開いた後の操作ポイント:                                                                                                                         
  │                                                                                                                                                       
  │ • マウス中ボタンドラッグ: 視点の回転                                                                                                                  
  │ • Shift + マウス中ボタンドラッグ: 視点の平行移動                                                                                                      
  │ • ホイール回転: ズーム                                                                                                                                
  │ • 右側の「アウトライナー（階層ツリー）」で、Drone_Root 配下の Frame, Guards, LandingGear, Rotor_FL やセンサー・コライダの構造を確認できます。         
  ──────                                                                                                                                                  
  ### 方法 2: Windows 標準の「3D ビューアー」で確認する（最も手軽）                                                                                       
                                                                                                                                                          
                                                                                                                                                          
  エクスプローラーで以下のフォルダを開き、ファイルをダブルクリックしてください：                                                                          
                                                                                                                                                          
  • ドローン:                                                                                                                                             
  drone2_derived.glb                                                                                                                                      
  • 猫モデル:                                                                                                                                             
  cat_derived.glb                                                                                                                                         
                                                                                                                                                          
  マウスでドラッグするだけで、360度自由に回転・拡大して外観やテクスチャの仕上がりを確認できます。                                                         
  ──────                                                                                                                                                  
  ### 方法 3: Blender を手動で起動して USD を開く場合                                                                                                     
                                                                                                                                                          
  Blender を普通に起動して確認したい場合は、以下の手順でも開くことができます：                                                                            
                                                                                                                                                          
  1. スタートメニューから Blender 5.2 を起動します。                                                                                                      
  2. 上部メニューから ファイル → 新規 → 全般 を選び、初期配置の立方体（Cube）を削除します。                                                               
  3. ファイル → インポート → Universal Scene Description (.usd, .usdc, .usda) を選択します。                                                              
  4. 以下のいずれかのファイルを選択して「USDをインポート」をクリックします：                                                                              
      • ドローン: D:\source\repos\3DModelDevPJ\image2sim-framework\output\drone2_parametric\usd\drone_assembly.usda                                       
      • 猫: D:\source\repos\3DModelDevPJ\image2sim-framework\output_v2\usd\root_cat.usda                                                                  
  5. 画面右上の球体アイコン（ビューポートシェーディング）を 「マテリアルプレビュー」（右から2番目）に切り替えると、カラーやテクスチャが表示されます。     
                                                                                                                                                          
  まずは 方法 1（python scripts/usd/open_in_blender_gui.py --asset drone） または 方法 2（GLB ダブルクリック） をお試しください！
  