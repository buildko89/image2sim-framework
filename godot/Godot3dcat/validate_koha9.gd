extends SceneTree


func _initialize() -> void:
	var packed_scene := load("res://cat_koha9.glb")
	if packed_scene == null:
		print("ERROR: cat_koha9.glb could not be loaded.")
		quit(2)
		return

	var instance: Node = packed_scene.instantiate()
	root.add_child(instance)

	var animation_players: Array = []
	_collect_animation_players(instance, animation_players)
	var meshes: Array = []
	_collect_meshes(instance, meshes)
	var skeletons: Array = []
	_collect_skeletons(instance, skeletons)

	var result := {
		"loaded": true,
		"root_name": instance.name,
		"animation_players": animation_players,
		"meshes": meshes,
		"skeletons": skeletons,
	}
	print(JSON.stringify(result, "  "))
	quit(0)


func _collect_animation_players(node: Node, result: Array) -> void:
	if node is AnimationPlayer:
		var player := node as AnimationPlayer
		var animations: Array = []
		for anim_name in player.get_animation_list():
			var anim := player.get_animation(anim_name)
			animations.append({
				"name": anim_name,
				"length_sec": anim.length,
				"tracks": anim.get_track_count(),
			})
		result.append({
			"path": str(player.get_path()),
			"animations": animations,
		})
	for child in node.get_children():
		_collect_animation_players(child, result)


func _collect_meshes(node: Node, result: Array) -> void:
	if node is MeshInstance3D:
		var mi := node as MeshInstance3D
		var aabb := mi.get_aabb()
		result.append({
			"name": mi.name,
			"surfaces": mi.mesh.get_surface_count() if mi.mesh else 0,
			"aabb_size": [aabb.size.x, aabb.size.y, aabb.size.z],
			"aabb_position": [aabb.position.x, aabb.position.y, aabb.position.z],
		})
	for child in node.get_children():
		_collect_meshes(child, result)


func _collect_skeletons(node: Node, result: Array) -> void:
	if node is Skeleton3D:
		var sk := node as Skeleton3D
		result.append({"name": sk.name, "bones": sk.get_bone_count()})
	for child in node.get_children():
		_collect_skeletons(child, result)
