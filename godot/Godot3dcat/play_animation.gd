extends Node3D

@export var animation_name: String = "Cat_Idle"
@export var animation_sequence: PackedStringArray = ["Cat_Idle", "Cat_Walk", "Cat_Run", "Cat_Sleep", "Cat_Punch", "Cat_WakeUp"]
@export var force_cat_materials: bool = false
@export var rotate_preview: bool = false
@export var rotation_degrees_per_second: float = 18.0

const CAT_COLORS := [
	Color(0.92, 0.88, 0.80, 1.0),
	Color(0.62, 0.32, 0.13, 1.0),
	Color(0.035, 0.030, 0.026, 1.0),
	Color(0.78, 0.69, 0.55, 1.0),
]
const CAT_MATERIAL_NAMES := [
	"PhotoCat_White_Longhair_Override",
	"PhotoCat_Warm_Calico_Override",
	"PhotoCat_Dark_Calico_Override",
	"PhotoCat_Cream_Shadow_Override",
]

var _player: AnimationPlayer
var _current_animation_index: int = 0


func _ready() -> void:
	if force_cat_materials:
		_apply_cat_materials(self)

	_player = find_child("AnimationPlayer", true, false) as AnimationPlayer
	if _player == null:
		push_warning("AnimationPlayer was not found in the imported cat GLB.")
		return

	_remap_animation_tracks()

	_current_animation_index = max(animation_sequence.find(animation_name), 0)
	_play_animation(animation_name)

	if force_cat_materials:
		call_deferred("_apply_cat_materials", self)

	# 5秒後に自動的にゲームを終了する（自動テスト・キャプチャ検証用）
	var timer := get_tree().create_timer(5.0)
	timer.timeout.connect(func(): get_tree().quit())


func _process(delta: float) -> void:
	if rotate_preview:
		var cat := get_node_or_null("Cat") as Node3D
		if cat != null:
			cat.rotate_y(deg_to_rad(rotation_degrees_per_second) * delta)


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var key_event := event as InputEventKey
	if not key_event.pressed or key_event.echo:
		return

	match key_event.keycode:
		KEY_1:
			_play_sequence_index(0)
		KEY_2:
			_play_sequence_index(1)
		KEY_3:
			_play_sequence_index(2)
		KEY_4:
			_play_sequence_index(3)
		KEY_5:
			_play_sequence_index(4)
		KEY_6:
			_play_sequence_index(5)
		KEY_SPACE:
			_play_sequence_index(_current_animation_index + 1)
		KEY_R:
			rotate_preview = not rotate_preview


func _play_sequence_index(index: int) -> void:
	if animation_sequence.is_empty():
		return
	_current_animation_index = wrapi(index, 0, animation_sequence.size())
	_play_animation(animation_sequence[_current_animation_index])


func _play_animation(target_animation: String) -> void:
	if _player == null:
		return
	if _player.has_animation(target_animation):
		_player.play(target_animation)
		animation_name = target_animation
		return

	var animations := _player.get_animation_list()
	if animations.size() > 0:
		_player.play(animations[0])
		animation_name = animations[0]


func _apply_cat_materials(node: Node) -> void:
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		if mesh_instance.mesh != null:
			for surface_index in range(mesh_instance.mesh.get_surface_count()):
				var material := StandardMaterial3D.new()
				var color_index := surface_index % CAT_COLORS.size()
				material.resource_name = CAT_MATERIAL_NAMES[color_index]
				material.albedo_color = CAT_COLORS[color_index]
				material.roughness = 0.65
				mesh_instance.set_surface_override_material(surface_index, material)

	for child in node.get_children():
		_apply_cat_materials(child)


func _remap_animation_tracks() -> void:
	if _player == null:
		return
		
	var anim_list := _player.get_animation_list()
	for anim_name in anim_list:
		var anim := _player.get_animation(anim_name)
		if anim == null:
			continue
			
		var track_count := anim.get_track_count()
		var tracks_to_remove: Array[int] = []
		
		for i in range(track_count):
			var path := anim.track_get_path(i)
			var path_str := str(path)
			var original_path = path_str
			
			# プレフィックスのリターゲット
			if "shustrilo4_4:" in path_str:
				path_str = path_str.replace("shustrilo4_4:", "CatGirl2:")
			if "shustrilo4_6:" in path_str:
				path_str = path_str.replace("shustrilo4_6:", "CatGirl2:")
				
			# ルート以外の位置トラック (Location) の削除
			if path_str.ends_with(":location"):
				if "Root_M" not in path_str and "Root" not in path_str:
					tracks_to_remove.append(i)
					continue
					
			if path_str != original_path:
				anim.track_set_path(i, NodePath(path_str))
				
		# 逆順で削除してインデックス崩れを防ぐ
		tracks_to_remove.reverse()
		for idx in tracks_to_remove:
			anim.remove_track(idx)
