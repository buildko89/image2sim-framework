extends SceneTree


const POSITION_TOLERANCE_M := 0.00002
const TRANSFORM_TOLERANCE := 0.00002
const ROTATION_ANGLE_RAD := 0.31
const IMPULSE_PER_ROTOR := 0.01

var _report := {
	"schema_version": "1.0",
	"status": "FAIL",
	"models": {},
}


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var manifest := _read_json("res://manifest.json")
	if manifest.is_empty():
		push_error("Phase 5 manifest could not be read")
		quit(2)
		return

	var all_passed := true
	for model_spec_variant in manifest.get("models", []):
		var model_result := await _test_model(model_spec_variant)
		_report.models[model_spec_variant["id"]] = model_result
		all_passed = all_passed and model_result["status"] == "PASS"

	_report.status = "PASS" if all_passed else "FAIL"
	_report["godot_version"] = Engine.get_version_info()
	_write_json("res://godot_phase5_report.json", _report)
	print("PHASE5_RESULT: %s" % _report.status)
	quit(0 if all_passed else 1)


func _test_model(spec: Dictionary) -> Dictionary:
	var result := {
		"status": "FAIL",
		"checks": {},
	}
	var packed := load(spec["scene_path"]) as PackedScene
	_check(result, "import", packed != null, {"scene_path": spec["scene_path"]})
	if packed == null:
		return result

	var model := packed.instantiate() as Node3D
	root.add_child(model)
	await process_frame
	var build_report := _read_json(spec["build_report_path"])
	var drone_root := DroneRuntime.find_named(model, "drone_root") as Node3D
	_check(result, "drone_root", drone_root != null, {})
	if drone_root == null:
		model.queue_free()
		await process_frame
		return result

	_test_nodes_and_transforms(result, model, spec)
	_test_meshes_and_materials(result, model, spec)
	var imported_metadata_count := _count_expected_imported_metadata(model, spec["nodes"])
	var extras_mapping := DroneRuntime.apply_node_extras(model, spec["nodes"])
	_check(result, "gltf_extras_mapping", extras_mapping["missing_nodes"].is_empty(), {
		"native_imported_properties": imported_metadata_count,
		"applied_nodes": extras_mapping["applied_nodes"],
		"applied_properties": extras_mapping["applied_properties"],
		"missing_nodes": extras_mapping["missing_nodes"],
		"note": "Godot keeps glTF extras for import extensions; the runtime adapter maps them to Node metadata.",
	})
	var anchor_result := _test_anchors_and_extras(result, model, build_report, spec)
	_test_rotor_spin(result, model, build_report)

	var center := anchor_result.get("center") as Node3D
	if center != null:
		var collision_names: Array = build_report.get("collision_proxies", {}).keys()
		var physics := DroneRuntime.build_rigid_body(root, model, collision_names, center)
		var body := physics["body"] as RigidBody3D
		var collision_passed: bool = (
			physics["errors"].is_empty()
			and physics["shape_names"].size() == collision_names.size()
		)
		var visible_proxies: Array[String] = []
		for collision_name_variant in collision_names:
			var proxy := DroneRuntime.find_named(model, str(collision_name_variant)) as MeshInstance3D
			if proxy != null and proxy.visible:
				visible_proxies.append(proxy.name)
		collision_passed = collision_passed and visible_proxies.is_empty()
		_check(result, "collision_shapes", collision_passed, {
			"rigid_body_count": 1,
			"expected": collision_names.size(),
			"actual": physics["shape_names"].size(),
			"shape_names": physics["shape_names"],
			"visible_proxies": visible_proxies,
			"errors": physics["errors"],
		})
		await _test_thrust(result, body, model, build_report)
		body.queue_free()
	else:
		_check(result, "collision_shapes", false, {"error": "center_of_mass is missing"})
		_check(result, "thrust_smoke", false, {"error": "center_of_mass is missing"})
		model.queue_free()
	await process_frame

	result.status = "PASS" if _checks_passed(result.checks) else "FAIL"
	print("PHASE5_MODEL: %s %s" % [spec["id"], result.status])
	return result


func _test_nodes_and_transforms(result: Dictionary, model: Node3D, spec: Dictionary) -> void:
	var expected_nodes: Dictionary = spec["nodes"]
	var missing: Array[String] = []
	var parent_errors: Array[String] = []
	var transform_errors: Array[String] = []
	for node_name_variant in expected_nodes.keys():
		var node_name := str(node_name_variant)
		var expected: Dictionary = expected_nodes[node_name]
		var node := DroneRuntime.find_named(model, node_name) as Node3D
		if node == null:
			missing.append(node_name)
			continue
		var expected_parent = expected.get("parent")
		if expected_parent != null and node.get_parent().name != str(expected_parent):
			parent_errors.append("%s: %s != %s" % [node_name, node.get_parent().name, expected_parent])
		if not _local_transform_matches(node, expected):
			transform_errors.append(node_name)
	_check(result, "nodes_and_transforms", (
		missing.is_empty() and parent_errors.is_empty() and transform_errors.is_empty()
	), {
		"expected_count": expected_nodes.size(),
		"missing": missing,
		"parent_errors": parent_errors,
		"transform_errors": transform_errors,
	})


func _test_meshes_and_materials(result: Dictionary, model: Node3D, spec: Dictionary) -> void:
	var mesh_nodes: Array[String] = []
	var material_names: Dictionary = {}
	_collect_mesh_data(model, mesh_nodes, material_names)
	mesh_nodes.sort()
	var expected_mesh_nodes: Array = spec["mesh_node_names"].duplicate()
	expected_mesh_nodes.sort()
	var actual_materials: Array = material_names.keys()
	actual_materials.erase("")
	actual_materials.sort()
	var expected_materials: Array = spec["material_names"].duplicate()
	expected_materials.sort()
	_check(result, "meshes", mesh_nodes == expected_mesh_nodes, {
		"expected_count": expected_mesh_nodes.size(),
		"actual_count": mesh_nodes.size(),
		"missing": _array_difference(expected_mesh_nodes, mesh_nodes),
		"unexpected": _array_difference(mesh_nodes, expected_mesh_nodes),
	})
	_check(result, "materials", actual_materials == expected_materials, {
		"expected": expected_materials,
		"actual": actual_materials,
	})


func _test_anchors_and_extras(
	result: Dictionary,
	model: Node3D,
	build_report: Dictionary,
	spec: Dictionary,
) -> Dictionary:
	var center := DroneRuntime.find_named(model, "center_of_mass") as Node3D
	var errors: Array[String] = []
	if center == null:
		errors.append("center_of_mass is missing")
	else:
		var expected_center := _blender_mm_to_godot(build_report["center_of_mass"]["location_mm"])
		if center.global_position.distance_to(expected_center) > POSITION_TOLERANCE_M:
			errors.append("center_of_mass position mismatch")
		if center.get_meta("anchor_type", "") != "center_of_mass":
			errors.append("center_of_mass anchor_type extra mismatch")

	for rotor_id_variant in spec["rotor_ids"]:
		var rotor_id := str(rotor_id_variant)
		var expected_axis: Dictionary = build_report["motor_axes"][rotor_id]
		var axis := DroneRuntime.find_named(model, "motor_%s_axis" % rotor_id) as Node3D
		if axis == null:
			errors.append("motor_%s_axis is missing" % rotor_id)
			continue
		var expected_position := _blender_mm_to_godot(expected_axis["location_mm"])
		if axis.global_position.distance_to(expected_position) > POSITION_TOLERANCE_M:
			errors.append("motor_%s_axis position mismatch" % rotor_id)
		var expected_direction := _blender_direction_to_godot(expected_axis["world_thrust_axis"])
		var actual_direction := (axis.global_basis * Vector3.UP).normalized()
		if actual_direction.distance_to(expected_direction) > TRANSFORM_TOLERANCE:
			errors.append("motor_%s_axis direction mismatch" % rotor_id)
		if axis.get_meta("anchor_type", "") != "rotor_axis":
			errors.append("motor_%s_axis anchor_type extra mismatch" % rotor_id)
		if axis.get_meta("rotation_direction", "") != expected_axis["rotation_direction"]:
			errors.append("motor_%s_axis rotation_direction extra mismatch" % rotor_id)
		var spin := DroneRuntime.find_named(model, "rotor_%s_spin" % rotor_id) as Node3D
		if spin == null:
			errors.append("rotor_%s_spin is missing" % rotor_id)
		elif spin.get_meta("rotation_direction", "") != expected_axis["rotation_direction"]:
			errors.append("rotor_%s_spin rotation_direction extra mismatch" % rotor_id)

	_check(result, "anchors_and_extras", errors.is_empty(), {
		"rotor_count": spec["rotor_ids"].size(),
		"errors": errors,
	})
	return {"center": center}


func _test_rotor_spin(result: Dictionary, model: Node3D, build_report: Dictionary) -> void:
	var errors: Array[String] = []
	for rotor_id_variant in build_report["rotor_assemblies"].keys():
		var rotor_id := str(rotor_id_variant)
		var assembly: Dictionary = build_report["rotor_assemblies"][rotor_id]
		var spin := DroneRuntime.find_named(model, assembly["spin"]) as Node3D
		if spin == null:
			errors.append("%s is missing" % assembly["spin"])
			continue
		var fixed_before := {}
		var spinning_before := {}
		for child_name_variant in assembly["fixed_children"]:
			var child := DroneRuntime.find_named(model, str(child_name_variant)) as Node3D
			if child != null:
				fixed_before[child.name] = child.global_transform
		for child_name_variant in assembly["spinning_children"]:
			var child := DroneRuntime.find_named(model, str(child_name_variant)) as Node3D
			if child != null:
				spinning_before[child.name] = child.global_transform
		spin.rotate_y(ROTATION_ANGLE_RAD)
		for child_name_variant in assembly["fixed_children"]:
			var child := DroneRuntime.find_named(model, str(child_name_variant)) as Node3D
			if child == null or not _transform_close(child.global_transform, fixed_before.get(str(child_name_variant))):
				errors.append("fixed child moved: %s" % child_name_variant)
		for child_name_variant in assembly["spinning_children"]:
			var child := DroneRuntime.find_named(model, str(child_name_variant)) as Node3D
			if child == null or _transform_close(child.global_transform, spinning_before.get(str(child_name_variant))):
				errors.append("spinning child did not move: %s" % child_name_variant)
		spin.rotate_y(-ROTATION_ANGLE_RAD)
	_check(result, "rotor_spin", errors.is_empty(), {"errors": errors})


func _test_thrust(
	result: Dictionary,
	body: RigidBody3D,
	model: Node3D,
	build_report: Dictionary,
) -> void:
	var rotor_ids: Array = build_report["motor_axes"].keys()
	var application := DroneRuntime.apply_rotor_impulses(
		body,
		model,
		rotor_ids,
		IMPULSE_PER_ROTOR,
	)
	await physics_frame
	await physics_frame
	var resultant: Vector3 = application["resultant_impulse"]
	var torque: Vector3 = application["resultant_torque"]
	var expected_velocity_direction := resultant.normalized()
	var forward_velocity := body.linear_velocity.dot(expected_velocity_direction)
	var passed: bool = (
		application["applied"] == rotor_ids.size()
		and resultant.length() > 0.0
		and forward_velocity > 0.0
		and torque.length() < 0.00001
		and body.angular_velocity.length() < 0.001
	)
	_check(result, "thrust_smoke", passed, {
		"applied_rotors": application["applied"],
		"resultant_impulse": _vector_to_array(resultant),
		"resultant_torque": _vector_to_array(torque),
		"linear_velocity": _vector_to_array(body.linear_velocity),
		"angular_velocity": _vector_to_array(body.angular_velocity),
		"forward_velocity": forward_velocity,
	})


func _local_transform_matches(node: Node3D, expected: Dictionary) -> bool:
	if expected.get("matrix") != null:
		return _transform_close(node.transform, _matrix_to_transform(expected["matrix"]))
	var translation_value = expected.get("translation")
	var scale_value = expected.get("scale")
	var rotation_value = expected.get("rotation")
	var expected_position := _array_to_vector(
		translation_value if translation_value != null else [0.0, 0.0, 0.0]
	)
	var expected_scale := _array_to_vector(
		scale_value if scale_value != null else [1.0, 1.0, 1.0]
	)
	if node.position.distance_to(expected_position) > TRANSFORM_TOLERANCE:
		return false
	if node.scale.distance_to(expected_scale) > TRANSFORM_TOLERANCE:
		return false
	var rotation: Array = rotation_value if rotation_value != null else [0.0, 0.0, 0.0, 1.0]
	var expected_quaternion := Quaternion(rotation[0], rotation[1], rotation[2], rotation[3]).normalized()
	return abs(node.quaternion.dot(expected_quaternion)) >= 1.0 - TRANSFORM_TOLERANCE


func _matrix_to_transform(values: Array) -> Transform3D:
	return Transform3D(
		Basis(
			Vector3(values[0], values[1], values[2]),
			Vector3(values[4], values[5], values[6]),
			Vector3(values[8], values[9], values[10]),
		),
		Vector3(values[12], values[13], values[14]),
	)


func _collect_mesh_data(node: Node, mesh_nodes: Array[String], materials: Dictionary) -> void:
	if node is MeshInstance3D:
		var mesh_instance := node as MeshInstance3D
		mesh_nodes.append(mesh_instance.name)
		if mesh_instance.mesh != null:
			for surface_index in mesh_instance.mesh.get_surface_count():
				var material := mesh_instance.get_active_material(surface_index)
				if material != null:
					materials[material.resource_name] = true
	for child in node.get_children():
		_collect_mesh_data(child, mesh_nodes, materials)


func _count_expected_imported_metadata(model: Node, expected_nodes: Dictionary) -> int:
	var count := 0
	for node_name_variant in expected_nodes.keys():
		var node_name := str(node_name_variant)
		var extras: Dictionary = expected_nodes[node_name].get("extras", {})
		var node := DroneRuntime.find_named(model, node_name)
		if node == null:
			continue
		for property_name in extras.keys():
			if node.has_meta(str(property_name)):
				count += 1
	return count


func _transform_close(actual: Variant, expected: Variant) -> bool:
	if actual == null or expected == null:
		return false
	return (
		actual.origin.distance_to(expected.origin) <= TRANSFORM_TOLERANCE
		and actual.basis.x.distance_to(expected.basis.x) <= TRANSFORM_TOLERANCE
		and actual.basis.y.distance_to(expected.basis.y) <= TRANSFORM_TOLERANCE
		and actual.basis.z.distance_to(expected.basis.z) <= TRANSFORM_TOLERANCE
	)


func _blender_mm_to_godot(value: Array) -> Vector3:
	return Vector3(value[0], value[2], -value[1]) / 1000.0


func _blender_direction_to_godot(value: Array) -> Vector3:
	return Vector3(value[0], value[2], -value[1]).normalized()


func _array_to_vector(value: Array) -> Vector3:
	return Vector3(value[0], value[1], value[2])


func _vector_to_array(value: Vector3) -> Array:
	return [value.x, value.y, value.z]


func _array_difference(left: Array, right: Array) -> Array:
	var result: Array = []
	for item in left:
		if item not in right:
			result.append(item)
	return result


func _check(result: Dictionary, name: String, passed: bool, details: Dictionary) -> void:
	details["pass"] = passed
	result.checks[name] = details


func _checks_passed(checks: Dictionary) -> bool:
	for check in checks.values():
		if not check.get("pass", false):
			return false
	return true


func _read_json(path: String) -> Dictionary:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return {}
	var parsed = JSON.parse_string(file.get_as_text())
	return parsed if parsed is Dictionary else {}


func _write_json(path: String, value: Dictionary) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	file.store_string(JSON.stringify(value, "  "))
