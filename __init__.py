
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
from bpy.props import EnumProperty, IntProperty, FloatVectorProperty, BoolProperty, FloatProperty, StringProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel, AddonPreferences

## Helper Functions

def deselect_all_nodes(nodes):
	"""Deselects all nodes."""
	for node in nodes:
		node.select = False

def get_image(name, size, images):
	"""Returns image if it exists, or creates new one if it doesn't exist."""
	image = images.get(name, None)
	
	if image is None:
		image = images.new(name, size, size)

	return image

def get_node(node_name, nodes, node_type):
	"""Returns node if it exists in node_tree, or creates a new one if it doesn't exist."""
	node = nodes.get(node_name, None)
	
	if node is None:
		node = nodes.new(node_type)
		node.name = node_name
		node.label = node_name
		# Deselect since it automatically gets selected when created
		node.select = False

	return node

def get_enum_bake_outputs(self, context):
	"""Returns list of outputs as enums of the active BakeNode."""
	enum_list = []
	
	bake_output_names = [output.name for output in context.active_object.active_material.node_tree.nodes.active.outputs]
	
	for index, output_name in enumerate(bake_output_names):
		enum_list.append( (str(index), output_name, "", "", index) )
	
	return enum_list

## Operators

class BH_OT_prepare_bake(Operator):
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
		return context.active_object

	def execute(self, context):
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

				# Create BakeHelper image if there is no image in the BakeHelper Image node
				# or if reset image flag is set
				if bake_helper_node.image is None or \
					(self.reset_bake_helper_image and bake_helper_node.image != bake_image_name):
					
					bake_helper_node.image = get_image(
						bake_image_name,
						1024,
						context.blend_data.images
					)

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
		return {'FINISHED'}


class BH_OT_connect_outputs(Operator):
	"""Connects bake nodes to material output"""
	bl_idname = "bake.bh_ot_connect_outputs"
	bl_label = "Connect BakeNode Outputs"
	bl_options = {'REGISTER','UNDO', 'INTERNAL'}
	
	# Properties
	bake_output_index : IntProperty(
		name="Bake Output",
		description="Index of node output to bake."
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return obj and \
			obj.active_material and \
			obj.active_material.node_tree.nodes.active and \
			obj.active_material.node_tree.nodes.active.bl_idname == "ShaderNodeGroup" and \
			obj.active_material.node_tree.nodes.active.node_tree.name.endswith("BakeNode")
	
	def execute(self, context):
		active_node = context.active_object.active_material.node_tree.nodes.active
		bake_node_name = active_node.node_tree.name
		
		for obj in context.selected_objects:
			for material_slot in obj.material_slots:
				for node in material_slot.material.node_tree.nodes:
					if node.bl_idname == "ShaderNodeGroup" and node.node_tree.name == bake_node_name:
						bakenode_emission = get_node("BakeNode_Emission", material_slot.material.node_tree.nodes, "ShaderNodeEmission")
						material_output = get_node("Material Output", material_slot.material.node_tree.nodes, "ShaderNodeOutputMaterial")
						
						# Position BakeNode Emission
						bakenode_emission.location = material_output.location.copy()
						bakenode_emission.location[1] += 100
						
						# Hide BakeNode Emission
						bakenode_emission.hide = True
						
						# connect bake output to BakeNode_Emission
						material_slot.material.node_tree.links.new(node.outputs[int(self.bake_output_index)], bakenode_emission.inputs[0])
						# connect BakeNode_Emission to Material Output
						material_slot.material.node_tree.links.new(bakenode_emission.outputs[0], material_output.inputs[0])
		
		return {'FINISHED'}


class BN_OT_connect_outputs_dialog(Operator):
	"""Connects bake nodes to material output"""
	bl_idname = "bake.bn_ot_connect_outputs_dialog"
	bl_label = "Connect BakeNode Outputs"
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	bake_output : EnumProperty(
		items=get_enum_bake_outputs,
		name="Bake Output",
		description="Node Output to bake."
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return obj and \
			obj.active_material and \
			obj.active_material.node_tree.nodes.active and \
			obj.active_material.node_tree.nodes.active.bl_idname == "ShaderNodeGroup" and \
			obj.active_material.node_tree.nodes.active.node_tree.name.endswith("BakeNode")
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		active_node = context.active_object.active_material.node_tree.nodes.active
		bake_node_name = active_node.node_tree.name
		
		for obj in context.selected_objects:
			for material_slot in obj.material_slots:
				for node in material_slot.material.node_tree.nodes:
					if node.bl_idname == "ShaderNodeGroup" and node.node_tree.name == bake_node_name:
						bakenode_emission = get_node("BakeNode_Emission", material_slot.material.node_tree.nodes, "ShaderNodeEmission")
						material_output = get_node("Material Output", material_slot.material.node_tree.nodes, "ShaderNodeOutputMaterial")
						# connect bake output to BakeNode_Emission
						material_slot.material.node_tree.links.new(node.outputs[int(self.bake_output)], bakenode_emission.inputs[0])
						# connect BakeNode_Emission to Material Output
						material_slot.material.node_tree.links.new(bakenode_emission.outputs[0], material_output.inputs[0])
		
		return {'FINISHED'}

## UI

class BH_UL_active_bakenode_outputs_list(UIList):
	"""List to show all active bakenode outputs."""
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		if self.layout_type in {"DEFAULT", "COMPACT"}:
			layout.label(text=item.name, icon="SELECT_SET")
			
		elif self.layout_type == "GRID":
			layout.alignment = "CENTER"
			layout.label(label="", icon="SELECT_SET")


class BH_PT_bake_helper_panel(Panel):
	"""Creates panel in the Properties window/Render Tab"""
	bl_label = "Bake Helper"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "render"

	def draw(self, context):
		layout = self.layout
		obj = context.active_object
		
		if obj and \
				obj.active_material and \
				obj.active_material.node_tree.nodes.active and \
				obj.active_material.node_tree.nodes.active.bl_idname == "ShaderNodeGroup" and \
				obj.active_material.node_tree.nodes.active.node_tree.name.endswith("BakeNode"):
			
			row = layout.row()
			row.template_list("BH_UL_active_bakenode_outputs_list", "", obj.active_material.node_tree.nodes.active, "outputs", context.scene, "bakenode_output_active_index")
			row = layout.row()
			row.operator(BH_OT_connect_outputs.bl_idname).bake_output_index = context.scene.bakenode_output_active_index
			row = layout.row()
		else:
			row = layout.row()
			row.label(text="BakeNode not selected.")
			
		row.separator()
		
		row = layout.row()
		row.operator(BH_OT_prepare_bake.bl_idname, text = "Prepare Bake")
		row = layout.row()
		row.operator(BH_OT_prepare_bake.bl_idname, text = "Prepare Bake (Reset node image)").reset_bake_helper_image=True
		row = layout.row()
		row.label(text="Bake Checklist")

		row = layout.row()
		# If active object has at least one UV
		if obj and obj.type == "MESH":
			if obj.data.uv_layers:
				row.label(text="This model has a UV", icon="FILE_TICK")
			else:
				row.label(text="This model doesn't have a UV!", icon="CANCEL")
		else:
			row.label(text="This object doesn't support UVs.")
		
		#if bpy.data.images.get("BakeHelper", None) is not None:
		if "BakeHelper" in bpy.data.images:
			image = bpy.data.images["BakeHelper"]
			
			row = layout.row()
			row.label(text="Bake Helper Image Settings")
			row = layout.row()
			row.prop(image, "size")
			row = layout.row()
			row.prop(image, "use_generated_float")
			row = layout.row()
			row.prop(image.colorspace_settings, "name")


## Preferences
class BH_addon_preferences(AddonPreferences):
	"""Bake Helper Addon Preferences"""
	bl_idname = __name__
	
	# Properties
	show_mini_manual : BoolProperty(
		name="Show Mini Manual",
		default=False
	)

	def draw(self, context):
		layout = self.layout
		
		col = layout.column()
		col.prop(self, "show_mini_manual", toggle=True)
		
		if self.show_mini_manual:
			row = col.row(align=True)
			row.label(text="Using Prepare Bake:", icon="DOT")
			
			row = col.row(align=True)
			row.label(text="Go to Properties window > Render tab > Bake Helper section",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="When you want to bake, click the Prepare Bake button.",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="Bake Helper will create and select its nodes under the Material Output node.",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="Change the Bake Helper node's settings, e.g. the image you'll be baking to, if you need to.",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="After that, the selected objects should be ready to bake.",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="Using BakeNode:", icon="DOT")
			
			row = col.row(align=True)
			row.label(text="Create a Node Group with a name that ends with BakeNode, ie: Name_BakeNode",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="Connect Node Group's inputs directly to its outputs",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="Add the Node Group to any materials you want to bake",icon="THREE_DOTS")
			
			row = col.row(align=True)
			row.label(text="When ready to bake, select the BakeNode and run 'Connect BakeNode Outputs'",icon="THREE_DOTS")

## Register

classes = (
	BH_OT_prepare_bake,
	BH_OT_connect_outputs,
	BN_OT_connect_outputs_dialog,
	BH_UL_active_bakenode_outputs_list,
	BH_PT_bake_helper_panel,
	BH_addon_preferences
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
		
	bpy.types.Scene.bakenode_output_active_index = IntProperty(name = "Active Bakenode Output Index", default = 0)

def unregister():
	del bpy.types.Scene.bakenode_output_active_index
	
	for cls in classes:
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	register()
