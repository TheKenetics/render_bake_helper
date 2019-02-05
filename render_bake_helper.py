
bl_info = {
	"name": "Bake Helper",
	"author": "Kenetics",
	"version": (0, 5),
	"blender": (2, 80, 0),
	"location": "Properties > Render Tab > Bake Helper Section",
	"description": "Sets up object's materials for baking",
	"warning": "",
	"wiki_url": "",
	"category": "Render",
}

import bpy
from bpy.props import BoolProperty

def deselect_all_nodes(nodes):
	for node in nodes:
		node.select = False

def get_image(name, size, images):
	"""
	Checks given images for a certain image and returns it, or
	makes new one if it doesn't exist
	"""
	
	image = images.get(name, None)
	
	if image is None:
		image = images.new(name, size, size)

	return image

def get_node(name, nodes, node_type):
	"""
	Checks for given node_name and returns it if it exists in node_tree, or
	makes a new one if it doesn't exist
	"""
	node = nodes.get(name, None)
	
	if node is None:
		node = nodes.new(node_type)
		node.name = name
		node.label = name
		# Deselect since it automatically gets selected when created
		node.select = False

	return node


def prepare_bake(self, context):
	for obj in context.selected_objects:
		# Loop thru material slots
		for material_slot in obj.material_slots:
			node_tree = material_slot.material.node_tree
			
			# padding for positioning nodes
			padding = 20
			
			# set bake image
			# if an image isn't set for material, use default bakehelper image
			bake_image_name = "BakeHelper"
			
			# Get or create necessary nodes
			mat_output = get_node(
				"Material Output",
				node_tree.nodes,
				"ShaderNodeOutputMaterial"
			)
			bake_helper_node = get_node(
				"BakeHelperNode",
				node_tree.nodes,
				"ShaderNodeTexImage"
			)
			bake_helper_uv = get_node(
				"BakeHelperUV",
				node_tree.nodes,
				"ShaderNodeUVMap"
			)

			# Create BakeHelper image if necessary
			if bake_helper_node.image is None or \
				(self.reset_bake_helper_image and bake_helper_node.image != bake_image_name):
				bake_helper_image = get_image(
					bake_image_name,
					1024,
					context.blend_data.images
				)
				#
				bake_helper_node.image = bake_helper_image

			# Set locations
			bake_helper_uv.location = (
				mat_output.location[0],
				mat_output.location[1] - mat_output.height
			)
			bake_helper_node.location = (
				bake_helper_uv.location[0] + bake_helper_uv.width + padding,
				bake_helper_uv.location[1]
			)

			# Link UV node to BakeHelperNode
			node_tree.links.new(bake_helper_node.inputs["Vector"], bake_helper_uv.outputs["UV"])

			# Deselect all nodes
			deselect_all_nodes(node_tree.nodes)

			# Select BakeHelperNode
			bake_helper_node.select = True
			node_tree.nodes.active = bake_helper_node


class BH_OT_prepare_bake(bpy.types.Operator):
	"""Select BakeHelper's nodes and create them if necessary"""
	bl_idname = "render.bh_ot_prepare_bake"
	bl_label = "Prepare Bake"
	
	# Properties
	reset_bake_helper_image : BoolProperty(
		name="Reset Bake Helper Image",
		description="If the Bake Helper node's image is different from the default Bake Helper image, set the node's image back to default.",
		default=False
	)

	@classmethod
	def poll(cls, context):
		return context.active_object is not None

	def execute(self, context):
		prepare_bake(self, context)
		return {'FINISHED'}


class BH_PT_bake_helper_panel(bpy.types.Panel):
	"""Creates panel in the Properties window/Render Tab"""
	bl_label = "Bake Helper"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "render"

	def draw(self, context):
		layout = self.layout

		row = layout.row()
		row.operator(BH_OT_prepare_bake.bl_idname, text = "Prepare Bake")
		row = layout.row()
		row.operator(BH_OT_prepare_bake.bl_idname, text = "Prepare Bake (Reset node image)").reset_bake_helper_image=True
		row = layout.row()
		row.label(text="Bake Checklist")

		row = layout.row()
		# If active object has at least one UV
		if context.active_object is not None and context.active_object.type == "MESH":
			if context.active_object.data.uv_layers:
				row.label(text="This model has a UV", icon="FILE_TICK")
			else:
				row.label(text="This model doesn't have a UV!", icon="CANCEL")
		else:
			row.label(text="This object doesn't support UVs.")
		
		if bpy.data.images.get("BakeHelper", None) is not None:
			image = bpy.data.images["BakeHelper"]
			
			row = layout.row()
			row.label(text="Bake Helper Image Settings")
			row = layout.row()
			row.prop(image, "size")
			row = layout.row()
			row.prop(image, "use_generated_float")
			row = layout.row()
			row.prop(image.colorspace_settings, "name")


classes = [BH_OT_prepare_bake, BH_PT_bake_helper_panel]

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

def unregister():
	for cls in classes:
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	register()
