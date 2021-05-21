
"""
Library of functions to help with Blender nodes
"""

import bpy

## Helper Functions

def deselect_all_nodes(nodes):
	"""Deselects all nodes."""
	for node in nodes:
		node.select = False

def get_node(node_name, nodes, node_type):
	"""Returns node if it exists in node_tree, or creates a new one if it doesn't exist."""
	node = nodes.get(node_name, None)
	
	if node is None:
		node = create_node(node_name, nodes, node_type)

	return node

def create_node(node_name, nodes, node_type):
	"""Creates a new node."""
	node = nodes.new(node_type)
	node.name = node_name
	node.label = node_name
	# Deselect since it automatically gets selected when created
	node.select = False

	return node
	
def set_node_relative_location(parent_node, child_node, vert_padding=20, horz_padding=40, vert_align="CENTER", horz_align="RIGHT"):
	if horz_align == "CENTER":
		new_x = parent_node.location[0]
	elif horz_align == "RIGHT":
		new_x = parent_node.location[0] + parent_node.height + horz_padding
	elif horz_align == "LEFT":
		new_x = parent_node.location[0] - parent_node.height - horz_padding

	if vert_align == "CENTER":
		new_y = parent_node.location[1]
	elif vert_align == "TOP":
		new_y = parent_node.location[1] + parent_node.width + vert_padding
	elif vert_align == "BOTTOM":
		new_y = parent_node.location[1] - parent_node.width - vert_padding
	
	child_node.location = (new_x, new_y)
	