extends Node3D

## cat_koha9.glb のアニメーションを再生しながらスクリーンショットを保存する検証用シーン。
## 実行: godot --path . res://CaptureKoha9.tscn

const MODEL := "res://cat_koha.glb"
const PREFIX := "b6_godot_koha"
const OUTPUT_DIR := "D:/source/repos/3DModelDevPJ/image2sim-framework/output_v2/reports"
# アニメーション名と、キャプチャする再生位置（正規化 0-1）
const CAPTURES := [
	["Armature|Idle1", [0.3, 0.7]],
	["Armature|Walk", [0.25, 0.6]],
	["Armature|Run", [0.4]],
	["Armature|Atk1", [0.5]],
]

var _player: AnimationPlayer


func _ready() -> void:
	var packed_scene := load(MODEL)
	var cat: Node3D = packed_scene.instantiate()
	add_child(cat)

	_player = cat.find_child("AnimationPlayer", true, false) as AnimationPlayer
	if _player == null:
		push_error("AnimationPlayer not found")
		get_tree().quit(2)
		return

	# 床
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(2.0, 2.0)
	var floor_mat := StandardMaterial3D.new()
	floor_mat.albedo_color = Color(0.55, 0.55, 0.57)
	floor_mat.roughness = 1.0
	plane.material = floor_mat
	floor_mesh.mesh = plane
	add_child(floor_mesh)

	# ライト
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-45.0, 30.0, 0.0)
	sun.light_energy = 1.4
	sun.shadow_enabled = true
	add_child(sun)

	# 環境（単色背景 + アンビエント）
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color(0.72, 0.74, 0.76)
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.9, 0.9, 0.92)
	env.ambient_light_energy = 0.7
	var world_env := WorldEnvironment.new()
	world_env.environment = env
	add_child(world_env)

	# カメラ（側面やや斜め上から。モデルは全長 0.34m / 高さ 0.13m）
	var cam := Camera3D.new()
	cam.position = Vector3(0.55, 0.18, 0.28)
	add_child(cam)
	cam.look_at(Vector3(0.0, 0.06, 0.0))
	cam.current = true

	_run_captures.call_deferred()


func _run_captures() -> void:
	await get_tree().process_frame
	for capture in CAPTURES:
		var anim_name: String = capture[0]
		var positions: Array = capture[1]
		if not _player.has_animation(anim_name):
			print("SKIP: animation not found: ", anim_name)
			continue
		var anim := _player.get_animation(anim_name)
		for pos in positions:
			_player.play(anim_name)
			_player.seek(anim.length * pos, true)
			_player.pause()
			await RenderingServer.frame_post_draw
			await RenderingServer.frame_post_draw
			var img := get_viewport().get_texture().get_image()
			var safe_name: String = anim_name.replace("Armature|", "").to_lower()
			var path := "%s/%s_%s_%02d.png" % [OUTPUT_DIR, PREFIX, safe_name, int(pos * 100)]
			var err := img.save_png(path)
			print("CAPTURED" if err == OK else "SAVE FAILED (%d)" % err, ": ", path)
	print("DONE")
	get_tree().quit(0)
