extends SceneTree


func _initialize() -> void:
	var packed_scene := load("res://cat_appearance_pass.glb")
	if packed_scene == null:
		print("ERROR: cat_appearance_pass.glb could not be loaded.")
		quit(2)
		return

	var instance: Node = packed_scene.instantiate()
	root.add_child(instance)

	var before := _snapshot(instance)
	var player := _find_animation_player(instance)
	if player != null and player.has_animation("Walk"):
		player.play("Walk")
		await process_frame
		await process_frame
	var after := _snapshot(instance)

	var result := {
		"loaded": true,
		"root_name": instance.name,
		"played_walk": player != null and player.has_animation("Walk"),
		"animation_player_path": str(player.get_path()) if player != null else "",
		"before": before,
		"after_walk": after,
	}
	var file := FileAccess.open("res://appearance_import_inspection.json", FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(result, "\t"))
		file.close()
	print(JSON.stringify(result))
	quit(0)


func _find_animation_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child in node.get_children():
		var found := _find_animation_player(child)
		if found != null:
			return found
	return null


func _snapshot(node: Node) -> Dictionary:
	var meshes: Array = []
	var animation_players: Array = []
	_collect(node, meshes, animation_players)
	return {
		"meshes": meshes,
		"animation_players": animation_players,
	}


func _collect(node: Node, meshes: Array, animation_players: Array) -> void:
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		var surfaces: Array = []
		if mesh_instance.mesh != null:
			for index in range(mesh_instance.mesh.get_surface_count()):
				var override_material := mesh_instance.get_surface_override_material(index)
				var material := override_material
				if material == null:
					material = mesh_instance.mesh.surface_get_material(index)
				surfaces.append(_material_info(index, material))
		meshes.append({
			"path": str(mesh_instance.get_path()),
			"name": mesh_instance.name,
			"surface_count": surfaces.size(),
			"surfaces": surfaces,
		})

	if node is AnimationPlayer:
		var player := node as AnimationPlayer
		animation_players.append({
			"path": str(player.get_path()),
			"animations": Array(player.get_animation_list()),
			"current_animation": player.current_animation,
		})

	for child in node.get_children():
		_collect(child, meshes, animation_players)


func _material_info(index: int, material: Material) -> Dictionary:
	if material == null:
		return {
			"surface": index,
			"material": "",
			"albedo": [],
		}

	var albedo: Array = []
	if material is BaseMaterial3D:
		var base := material as BaseMaterial3D
		albedo = [base.albedo_color.r, base.albedo_color.g, base.albedo_color.b, base.albedo_color.a]

	return {
		"surface": index,
		"material": material.resource_name,
		"albedo": albedo,
	}
