extends SceneTree


func _initialize() -> void:
	var packed_scene := load("res://cat_rigged_clean.glb")
	if packed_scene == null:
		print("ERROR: cat_rigged_clean.glb could not be loaded.")
		quit(2)
		return

	var instance: Node = packed_scene.instantiate()
	root.add_child(instance)

	var animation_players: Array = []
	_collect_animation_players(instance, animation_players)

	var result := {
		"loaded": true,
		"root_name": instance.name,
		"animation_player_count": animation_players.size(),
		"animation_players": animation_players,
	}
	print(JSON.stringify(result))
	quit(0)


func _collect_animation_players(node: Node, result: Array) -> void:
	if node is AnimationPlayer:
		var player := node as AnimationPlayer
		result.append({
			"path": str(player.get_path()),
			"animations": Array(player.get_animation_list()),
		})

	for child in node.get_children():
		_collect_animation_players(child, result)
