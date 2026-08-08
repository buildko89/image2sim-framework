class_name DroneRuntime
extends RefCounted


static func find_named(root: Node, target_name: String) -> Node:
	if root.name == target_name:
		return root
	for child in root.get_children():
		var found := find_named(child, target_name)
		if found != null:
			return found
	return null


static func apply_node_extras(model: Node, expected_nodes: Dictionary) -> Dictionary:
	var applied_nodes := 0
	var applied_properties := 0
	var missing_nodes: Array[String] = []
	for node_name_variant in expected_nodes.keys():
		var node_name := str(node_name_variant)
		var extras: Dictionary = expected_nodes[node_name].get("extras", {})
		if extras.is_empty():
			continue
		var node := find_named(model, node_name)
		if node == null:
			missing_nodes.append(node_name)
			continue
		for property_name in extras.keys():
			node.set_meta(str(property_name), extras[property_name])
			applied_properties += 1
		applied_nodes += 1
	return {
		"applied_nodes": applied_nodes,
		"applied_properties": applied_properties,
		"missing_nodes": missing_nodes,
	}


static func build_rigid_body(
	world: Node,
	model: Node3D,
	collision_names: Array,
	center_of_mass: Node3D,
) -> Dictionary:
	var body := RigidBody3D.new()
	body.name = "%s_physics" % model.name
	body.mass = 1.0
	body.gravity_scale = 0.0
	body.linear_damp = 0.0
	body.angular_damp = 0.0
	world.add_child(body)
	model.reparent(body, true)
	body.center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM
	body.center_of_mass = body.to_local(center_of_mass.global_position)

	var shape_names: Array[String] = []
	var errors: Array[String] = []
	for collision_name_variant in collision_names:
		var collision_name := str(collision_name_variant)
		var proxy := find_named(model, collision_name) as MeshInstance3D
		if proxy == null or proxy.mesh == null:
			errors.append("%s is not an imported MeshInstance3D" % collision_name)
			continue
		var shape := CollisionShape3D.new()
		shape.name = "%s_shape" % collision_name
		shape.shape = proxy.mesh.create_convex_shape()
		shape.global_transform = proxy.global_transform
		body.add_child(shape)
		shape.global_transform = proxy.global_transform
		proxy.visible = false
		shape_names.append(shape.name)

	return {
		"body": body,
		"shape_names": shape_names,
		"errors": errors,
	}


static func apply_rotor_impulses(
	body: RigidBody3D,
	model: Node3D,
	rotor_ids: Array,
	impulse_per_rotor: float,
) -> Dictionary:
	var resultant := Vector3.ZERO
	var torque := Vector3.ZERO
	var applied := 0
	for rotor_id_variant in rotor_ids:
		var rotor_id := str(rotor_id_variant)
		var axis := find_named(model, "motor_%s_axis" % rotor_id) as Node3D
		if axis == null:
			continue
		var direction := (axis.global_basis * Vector3.UP).normalized()
		var impulse := direction * impulse_per_rotor
		var application_position := body.to_local(axis.global_position)
		var lever_from_com := application_position - body.center_of_mass
		body.apply_impulse(impulse, application_position)
		resultant += impulse
		torque += lever_from_com.cross(impulse)
		applied += 1
	return {
		"applied": applied,
		"resultant_impulse": resultant,
		"resultant_torque": torque,
	}
