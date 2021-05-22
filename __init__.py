
bl_info = {
	"name": "Bake Helper",
	"author": "Kenetics",
	"version": (0, 6),
	"blender": (2, 80, 0),
	"location": "Properties > Render Tab > Bake Helper Section",
	"description": "Sets up object's materials for baking",
	"warning": "",
	"wiki_url": "",
	"category": "Render",
}

import bpy, os
from bpy.props import EnumProperty, IntProperty, FloatVectorProperty, BoolProperty, FloatProperty, StringProperty, PointerProperty
from bpy.types import PropertyGroup, UIList, Operator, Panel, AddonPreferences
from render_bake_helper.bnodelib import *

"""
TODO
Add Master BakeNode
	
Add bake single bakenode output right click context menu
Add bake active index to bakenode panel
"""

## Globals
# Dictionary that maps from possible special bakenode output names and the bake passes they correspond to
OUTPUT_NAME_TO_BAKETYPE_MAP = {
	"COMBINEDBAKE": "COMBINED",
	"NORMALBAKE": "NORMAL",
	"AOBAKE": "AO",
	"SHADOWBAKE": "SHADOW"
}

# Default name for BakeHelper image
BAKEHELPER_DEFAULT_IMAGE_NAME = "BakeHelper"

## Helper Functions

def get_image(name, size):
	"""Gets image with name if it exists, otherwise it creates a new square one with size."""
	if name in bpy.data.images:
		return bpy.data.images[name]
	else:
		return bpy.data.images.new(name, size, size)

def get_image_advanced(name, width=1024, height=1024, color_type="sRGB", file_path="", alpha=False, float_buffer=False, use_fake_user=False):
	"""Returns image if it exists, or creates new one if it doesn't exist."""
	image = bpy.data.images.get(name, None)
	
	# If image already exists
	if image:
		# if image isn't right size
		if image.size[0] != width or image.size[1] != height:
			# remove image
			bpy.data.images.remove(image)
			# Create new image
			image = bpy.data.images.new(name, width, height, alpha=alpha, float_buffer=float_buffer)
	else:
		# Create new image
		image = bpy.data.images.new(name, width, height, alpha=alpha, float_buffer=float_buffer)
	
	# Set other options
	image.alpha_mode = "STRAIGHT" if alpha else "NONE"
	image.filepath_raw = file_path
	image.colorspace_settings.name = color_type
	image.use_fake_user = use_fake_user
	
	return image

def create_bakenode(material):
	"""Attempts to create bakenode for material and will return None if BakeNode nodegroup doesn't already exist"""
	# Get bakenode nodegroup
	bakenode_nodegroup = get_master_bakenode_nodegroup()
	# If bakenode nodegroup doesn't exist
	if not bakenode_nodegroup:
		# Print error
		prefs = get_addon_preferences()
		print(f"ERROR: {prefs.master_bakenode_name} nodegroup not in current blend file.")
		
		return None
	
	# Create bakenode
	bakenode = material.node_tree.nodes.new("ShaderNodeGroup")
	bakenode.node_tree = bakenode_nodegroup
	mat_output = get_node("Material Output", material.node_tree.nodes, "ShaderNodeOutputMaterial")
	
	# Align bakenode to material output
	set_node_relative_location(mat_output, bakenode, 50, 40, "BOTTOM", "CENTER")
	
	return bakenode
	

def get_bakenode(material, force_create=False):
	"""
	Returns bakenode if it exists in material's node_tree, or returns None and warns if it doesn't exist.
	Can also create and return a new bakenode if one doesn't exist by force_create parameter.
	"""
	prefs = get_addon_preferences()
	bakenode_nodegroup_name = prefs.master_bakenode_name
	bakenode = None
	
	# Loop thru nodes in node tree
	for node in material.node_tree.nodes:
		# if this node is a bakenode and it's nodegroup name is the one 
		if is_node_bakenode(node) and node.node_tree.name == bakenode_nodegroup_name:
			bakenode = node
			break
	
	# if we didn't find bakenode
	if not bakenode:
		# print warning
		print(f"Warning: {material.name} did not have a valid bakenode!")
		if force_create:
			bakenode = create_bakenode(material)
	
	return bakenode

def get_enum_bake_outputs(self, context):
	"""Returns list of outputs of the active node as enums."""
	enum_list = []
	
	bake_output_names = [output.name for output in context.active_object.active_material.node_tree.nodes.active.outputs]
	
	for index, output_name in enumerate(bake_output_names):
		enum_list.append( (str(index), output_name, "", "", index) )
	
	return enum_list

def get_enum_master_bakenode_outputs(self, context):
	"""Returns list of outputs of the master bakenode nodegroup as enums."""
	enum_list = []
	
	bakenode_nodegroup = get_master_bakenode_nodegroup()
	
	bake_output_names = [output.name for output in bakenode_nodegroup.outputs]
	
	for index, output_name in enumerate(bake_output_names):
		enum_list.append( (str(index), output_name, "", "", index) )
	
	return enum_list

def is_node_bakenode(node):
	"""Checks if node is a valid nodegroup and ends with BakeNode"""
	return node.bl_idname == "ShaderNodeGroup" and node.node_tree and node.node_tree.name.endswith("BakeNode")

def create_image_file_path(base_path, prefix, name, suffix):
	# If path is relative
	if base_path.startswith("//"):
		base_path = "/".join( (os.path.dirname(os.path.realpath(bpy.data.filepath)), base_path[len("//"):]) )
	
	# make sure it ends with /
	if not base_path.endswith("/"):
		base_path += "/"
	
	return base_path, f"{prefix}{name}{suffix}.png"

def calc_padding(padding_per_128, image_width_px):
	"""Calculates padding using padding per multiple of 128 and image width, and returns it as rounded int."""
	return round(padding_per_128 * (image_width_px / 128))

def is_valid_mat(obj, material_slot):
	"""Checks if material and nodetree in material slot is valid, prints warning to console if not valid and returns false"""
	if not material_slot.material:
		print(f"WARNING: {obj.name} has a material slot that has no material!")
		return False
	
	if not material_slot.material.node_tree:
		print(f"WARNING: {obj.name} has a material that has no nodetree!")
		return False
	
	return True
	
def get_valid_mats(objects, check_for_bakenode=False):
	"""
	Returns a list of valid materials node trees.
	If check_for_bakenode, returns materials that already have a bakenode
	"""
	mats = []
	
	for obj in objects:
		for material_slot in obj.material_slots:
			# Validate mat and nodetree
			if not is_valid_mat(obj, material_slot):
				continue
			
			mat = material_slot.material
			
			if check_for_bakenode:
				current_bakenode = get_bakenode(mat, get_addon_preferences().create_missing_bakenode)
				if current_bakenode is None:
					continue
			
			mats.append(mat)
	
	return mats

def bake_bakenode_output(self, context, bakenode_output_index):
	bakenode_nodegroup = get_master_bakenode_nodegroup()
	
	bakenode_nodegroup_output = bakenode_nodegroup.outputs[bakenode_output_index]
	bakenode_output_settings = bakenode_nodegroup_output.bakenode_output_settings
	
	# Save original settings
	orig_render_samples = context.scene.cycles.samples
	orig_padding = context.scene.render.bake.margin
	
	# Set BakeHelper node as active
	bpy.ops.render.bh_ot_prepare_bake()
	
	mats = get_valid_mats(context.selected_objects, check_for_bakenode=True)
	for mat in mats:
		current_bakenode = get_bakenode(mat)
		
		# Get Bakenode Emission and Material Output
		bakenode_emission = get_node("BakeNode_Emission", mat.node_tree.nodes, "ShaderNodeEmission")
		material_output = get_node("Material Output", mat.node_tree.nodes, "ShaderNodeOutputMaterial")
		bakehelper_node = mat.node_tree.nodes.active
		
		# Connect Bakenode output to BakeNode_Emission
		if bakenode_nodegroup_output.name.upper() in OUTPUT_NAME_TO_BAKETYPE_MAP.keys():
			if "BSDF" not in current_bakenode.outputs:
				print("BSDF output needed for special bakes.")
			else:
				# Connect BSDF to mat output
				mat.node_tree.links.new(current_bakenode.outputs["BSDF"], material_output.inputs[0])
		else:
			mat.node_tree.links.new(current_bakenode.outputs[bakenode_output_index], bakenode_emission.inputs[0])
		
			# Connect BakeNode_Emission to Material Output
			mat.node_tree.links.new(bakenode_emission.outputs[0], material_output.inputs[0])
		
		# Switch active BakeHelper image to output bake image, or use BakeHelper image if no image
		if bakenode_output_settings.output_image_name:
			bakehelper_node.image = bpy.data.images[bakenode_output_settings.output_image_name]
		else:
			bakehelper_node.image = bpy.data.images[BAKEHELPER_DEFAULT_IMAGE_NAME]
	
	# Use samples from bakenode output
	context.scene.cycles.samples = bakenode_output_settings.samples
	
	# Calc padding
	if self.autopadding:
		image_width = bpy.data.images[bakenode_output_settings.output_image_name].size[0]
		context.scene.render.bake.margin = calc_padding(bakenode_output_settings.padding_per_128, image_width)
	
	# Do other special bakes based on output name, like NormalBAKE or AOBAKE
	# Bake emission if name isn't special
	bpy.ops.object.bake(
		type=OUTPUT_NAME_TO_BAKETYPE_MAP.get(bakenode_nodegroup_output.name.upper(), "EMIT")
	)
	
	# Save image if autosave is on
	#if context.scene.bakenode_bake_settings.bake_image_autosave:
	if self.bake_image_autosave:
		if (not bakenode_output_settings.output_image_name and not bpy.data.images[BAKEHELPER_DEFAULT_IMAGE_NAME].filepath) \
				or not bpy.data.images[bakenode_output_settings.output_image_name].filepath:
			print("Image is not saved! " + bakenode_output_settings.output_image_name)
		else:
			bpy.data.images[bakenode_output_settings.output_image_name].save()
	
	if self.autopack and not bpy.data.images[bakenode_output_settings.output_image_name].filepath_raw:
		bpy.data.images[bakenode_output_settings.output_image_name].pack()
	
	# Restore original settings
	context.scene.cycles.samples = orig_render_samples
	context.scene.render.bake.margin = orig_padding

def get_addon_preferences():
	return bpy.context.preferences.addons[__package__].preferences

def get_master_bakenode_nodegroup():
	prefs = get_addon_preferences()
	return bpy.data.node_groups.get(prefs.master_bakenode_name, None)

## Structs

class BH_bakenode_output_settings(PropertyGroup):
	"""Struct to hold bake settings for individual outputs"""
	enabled : BoolProperty(
		name="Enabled",
		default=False
	)
	
	output_image_name : StringProperty(
		name="BakeNode Output Image",
		default=""
	)

	samples : IntProperty(
		name="Samples",
		default=10
	)
	
	normal_swizzle_r : EnumProperty(
		items=[
			("POS_X","+X","","",0),
			("POS_Y","+Y","","",1),
			("POS_Z","+Z","","",2),
			("NEG_X","-X","","",3),
			("NEG_Y","-Y","","",4),
			("NEG_Z","-Z","","",5)
			],
		name="Swizzle",
		default="POS_X"
	)
	
	normal_swizzle_g : EnumProperty(
		items=[
			("POS_X","+X","","",0),
			("POS_Y","+Y","","",1),
			("POS_Z","+Z","","",2),
			("NEG_X","-X","","",3),
			("NEG_Y","-Y","","",4),
			("NEG_Z","-Z","","",5)
			],
		name="Swizzle",
		default="POS_Y"
	)
	
	normal_swizzle_b : EnumProperty(
		items=[
			("POS_X","+X","","",0),
			("POS_Y","+Y","","",1),
			("POS_Z","+Z","","",2),
			("NEG_X","-X","","",3),
			("NEG_Y","-Y","","",4),
			("NEG_Z","-Z","","",5)
			],
		name="Swizzle",
		default="POS_Z"
	)
	
	normal_space : EnumProperty(
		items=[
			("OBJECT","Object","","",0),
			("TANGENT","Tangent","","",1)
			],
		name="Normal Space",
		default="TANGENT"
	)
	
	padding_per_128 : FloatProperty(
		name="Padding per 128",
		description="Padding to add per multiple of 128. EG: 1p for 128px, 2px for 256px...",
		default=1.0
	)


class BH_bakenode_bake_settings(PropertyGroup):
	"""Struct to hold settings for baking with bakenodes"""
	bake_image_autosave : BoolProperty(
		name="Bake Image Autosave",
		description="Automatically saves image after each bake in Batch Bake",
		default=False
	)


class BH_bakenode_ui_settings(PropertyGroup):
	"""Struct to hold settings for UI tools"""
	batch_image_name_prefix : StringProperty(
		name="Batch Image Name Prefix",
		description="Prefix to apply to image names.",
		default=""
	)
	
	batch_image_name_suffix : StringProperty(
		name="Batch Image Name Suffix",
		description="Suffix to apply to image names.",
		default=""
	)
	
	batch_image_base_path : StringProperty(
		name="Batch Image Base Path",
		description="Base Path to apply to images.",
		default=""
	)
	
	batch_image_save : BoolProperty(
		name="Batch Image Save",
		description="If enabled, will batch save images.",
		default=False
	)
	
	batch_bake_autopack : BoolProperty(
		name="Batch Bake Autopack",
		description="If enabled, will pack images that don't have paths or aren't saved.",
		default=False
	)
	
	batch_bake_autopadding : BoolProperty(
		name="Batch Bake Autopadding",
		description="If enabled, will calculate padding using image size.",
		default=True
	)

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
		mats = get_valid_mats(context.selected_objects)
		for mat in mats:
			node_tree = mat.node_tree
			# set bake image
			# if an image isn't set for material, use default bakehelper image
			bake_image_name = BAKEHELPER_DEFAULT_IMAGE_NAME
			
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

			# Create BakeHelper image if there is no image in the BakeHelper Image node
			# or if reset image flag is set
			if not bake_helper_node.image or \
					(self.reset_bake_helper_image and bake_helper_node.image != bake_image_name):
				
				bake_helper_node.image = get_image(
					bake_image_name,
					1024
				)

			# Set location
			set_node_relative_location(mat_output, bake_helper_node, horz_align="RIGHT", vert_align="BOTTOM")

			# Deselect all nodes
			deselect_all_nodes(node_tree.nodes)

			# Select BakeHelperNode
			bake_helper_node.select = True
			node_tree.nodes.active = bake_helper_node
		
		return {'FINISHED'}


class BH_OT_connect_bakenode_output(Operator):
	"""Connects selected objects' bakenodes to material output"""
	bl_idname = "bake.bh_ot_connect_bakenode_output"
	bl_label = "Connect BakeNode Output"
	bl_options = {'REGISTER','UNDO', 'INTERNAL'}
	
	# Properties
	bakenode_output_index : IntProperty(
		name="Bake Output",
		description="Index of node output to bake."
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree and
			get_master_bakenode_nodegroup() is not None
		)
	
	def execute(self, context):
		prefs = get_addon_preferences()
		
		mats = get_valid_mats(context.selected_objects, check_for_bakenode=True)
		
		for mat in mats:
			current_bakenode = get_bakenode(mat)
			
			# Get nodes
			bakenode_emission = get_node("BakeNode_Emission", mat.node_tree.nodes, "ShaderNodeEmission")
			material_output = get_node("Material Output", mat.node_tree.nodes, "ShaderNodeOutputMaterial")
			
			# Position BakeNode Emission
			set_node_relative_location(material_output, bakenode_emission, horz_align="CENTER", vert_align="TOP", vert_padding=80)
			
			# Hide BakeNode Emission
			bakenode_emission.hide = True
			
			# connect bake output to BakeNode_Emission
			mat.node_tree.links.new(current_bakenode.outputs[int(self.bakenode_output_index)], bakenode_emission.inputs[0])
			# connect BakeNode_Emission to Material Output
			mat.node_tree.links.new(bakenode_emission.outputs[0], material_output.inputs[0])
		
		return {'FINISHED'}


class BH_OT_connect_bakenode_output_dialog(Operator):
	"""Connects selected objects' bakenodes to material output"""
	bl_idname = "bake.bh_ot_connect_bakenode_output_dialog"
	bl_label = "Connect BakeNode Output"
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	bakenode_output_index : EnumProperty(
		items=get_enum_master_bakenode_outputs,
		name="Bake Output",
		description="Node Output to bake."
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree and
			get_master_bakenode_nodegroup() is not None
		)
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		BH_OT_connect_bakenode_output.execute(self, context)
		
		return {'FINISHED'}


class BH_OT_bake_material_results_dialog(Operator):
	"""Bakes selected objects' material results"""
	bl_idname = "bake.bh_ot_bake_material_results_dialog"
	bl_label = "Bake Material Results..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	bake_type : EnumProperty(
		items=[
			("EMIT", "Emission", "", "", 0)
		],
		name="Bake Type",
		description="Bake Type to bake."
	)
	
	bake_image_autosave : BoolProperty(
		name="Autosave Bake Image",
		default=False
	)
	
	autopadding : BoolProperty(
		name="Autopadding",
		description="Calculate padding based on image width.",
		default=True
	)
	
	bake_samples : IntProperty(
		name="Bake Samples",
		default=10
	)
	
	bake_image_width : IntProperty(
		name="Bake Image Width",
		default=1024
	)
	
	bake_image_height : IntProperty(
		name="Bake Image Height",
		default=1024
	)
	
	padding_per_128 : IntProperty(
		name="Padding Per 128",
		default=1
	)
	
	color_type : EnumProperty(
		items=[
			("sRGB","Color","","",0),
			("Non-Color","Non-Color","","",1)
			],
		name="Color Type",
		default="sRGB"
	)

	alpha : BoolProperty(
		name="Alpha",
		default=False
	)

	float_buffer : BoolProperty(
		name="32 bit Float",
		default=False
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree.nodes.active
		)
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		active_mat_nodes = context.active_object.active_material.node_tree.nodes
		active_node = active_mat_nodes.active
		
		""" """
		# Save original settings
		orig_render_samples = context.scene.cycles.samples
		orig_padding = context.scene.render.bake.margin
		
		# Set BakeHelper node as active
		bpy.ops.render.bh_ot_prepare_bake()
		
		# create image for bakehelper nodes to use
		bake_image = get_image_advanced(
			BAKEHELPER_DEFAULT_IMAGE_NAME,
			self.bake_image_width,
			self.bake_image_height,
			self.color_type,
			"",
			self.alpha,
			self.float_buffer
		)
		
		mats = get_valid_mats(context.selected_objects)
		for mat in mats:
			bakehelper_node = mat.node_tree.nodes.active
			bakehelper_node.image = bake_image
		
		# Use samples from bakenode output
		context.scene.cycles.samples = self.bake_samples
		
		# Calc padding
		if self.autopadding:
			context.scene.render.bake.margin = calc_padding(self.padding_per_128, self.bake_image_width)
		
		# Do other special bakes based on output name, like NormalBAKE or AOBAKE
		# Bake emission if name isn't special
		bpy.ops.object.bake(type="EMIT")
		
		# Restore original settings
		context.scene.cycles.samples = orig_render_samples
		context.scene.render.bake.margin = orig_padding
		""" """
		
		# Make BakeNode active again
		deselect_all_nodes(active_mat_nodes)
		active_node.select = True
		active_mat_nodes.active = active_node
		
		return {'FINISHED'}


class BH_OT_bake_single_bakenode_output_dialog(Operator):
	"""Bakes selected objects' bakenodes to material output"""
	bl_idname = "bake.bh_ot_bake_single_bakenode_output_dialog"
	bl_label = "Bake BakeNode Output..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	bakenode_output_index : EnumProperty(
		items=get_enum_master_bakenode_outputs,
		name="Bake Output",
		description="Node Output to bake."
	)
	
	bake_image_autosave : BoolProperty(
		name="Autosave Bake Image",
		default=False
	)
	
	autopack : BoolProperty(
		name="Autopack Bake Image",
		description="Autopacks bake image if not on disk.",
		default=False
	)
	
	autopadding : BoolProperty(
		name="Autopadding",
		description="Calculate padding based on image width.",
		default=True
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree and
			get_master_bakenode_nodegroup() is not None
		)
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		#mat = context.active_object.active_material
		bakenode_output_index = int(self.bakenode_output_index)
		#active_mat_nodes = mat.node_tree.nodes
		#active_bakenode = get_bakenode(mat)
		
		# Bake single output
		bake_bakenode_output(self, context, bakenode_output_index)
		
		# Make BakeNode active again
		#deselect_all_nodes(active_mat_nodes)
		#active_bakenode.select = True
		#active_mat_nodes.active = active_bakenode
		
		return {'FINISHED'}


class BH_OT_batch_bake_bakenode_outputs(Operator):
	"""Bakes multiple BakeNode outputs for selected objects"""
	bl_idname = "bake.bh_ot_batch_bake_bakenode_outputs"
	bl_label = "Connect BakeNode Output"
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	bake_image_autosave : BoolProperty(
		name="Bake Image Autosave",
		default=False
	)
	
	autopack : BoolProperty(
		name="Autopack",
		description="Packs image if not on disk",
		default=False
	)
	
	autopadding : BoolProperty(
		name="Autopadding",
		description="Calculates padding based on image width.",
		default=True
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree and
			get_master_bakenode_nodegroup() is not None
		)

	def execute(self, context):
		# save bakenode to variable
		#active_mat_nodes = context.active_object.active_material.node_tree.nodes
		#active_node = context.active_object.active_material.node_tree.nodes.active
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		
		# Get enabled outputs
		enabled_outputs = tuple( (index, output) for index, output in enumerate(bakenode_nodegroup.outputs) if output.bakenode_output_settings.enabled )
		
		for output_index, output in enabled_outputs:
			print(f"Baking output: {str(output_index)}, {output}")
			bake_bakenode_output(self, context, output_index)
		
		# Make BakeNode active again
		#deselect_all_nodes(active_mat_nodes)
		#active_node.select = True
		#active_mat_nodes.active = active_node
		
		return {'FINISHED'}


class BH_OT_create_bakenode_output_image_name(Operator):
	"""Creates new image datablock for selected BakeNode output."""
	bl_idname = "bake.bh_ot_create_bakenode_output_image_name"
	bl_label = "Create BakeNode Output Image"
	bl_options = {'REGISTER','UNDO', 'INTERNAL'}
	
	# Properties
	image_name : StringProperty(
		name="Image Name",
		default="New BakeNode Image"
	)

	file_path : StringProperty(
		name="Image File Path",
		default="//Textures/"
	)

	width : IntProperty(
		name="Width",
		default=1024
	)

	height : IntProperty(
		name="Height",
		default=1024
	)

	color_type : EnumProperty(
		items=[
			("sRGB","Color","","",0),
			("Non-Color","Non-Color","","",1)
			],
		name="Color Type",
		default="sRGB"
	)

	alpha : BoolProperty(
		name="Alpha",
		default=False
	)

	float_buffer : BoolProperty(
		name="32 bit Float",
		default=False
	)
	
	use_fake_user : BoolProperty(
		name="Fake User",
		description="Keep this image even if it has no users.",
		default=True
	)
	
	save_to_disk : BoolProperty(
		name="Save to Disk",
		description="Save image to disk after creation, otherwise, image will be packed inside blend file.",
		default=False
	)
	
	bakenode_output_index = IntProperty(
		name="BakeNode Output Index",
		default=0
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup()

	def execute(self, context):
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		active_output_index = self.bakenode_output_index
		
		image = get_image_advanced(self.image_name, width=self.width, height=self.height, color_type=self.color_type, alpha=self.alpha, float_buffer=self.float_buffer, use_fake_user=self.use_fake_user)
		
		if self.save_to_disk:
			if self.file_path.startswith("//"):
				self.file_path = "/".join( (os.path.dirname(os.path.realpath(bpy.data.filepath)), self.file_path[len("//"):]) )
			
			if not self.file_path.endswith("/"):
				self.file_path += "/"
			
			image.filepath_raw = self.file_path + image.name + ".png"
			image.save()
		
		bakenode_nodegroup.outputs[active_output_index].bakenode_output_settings.output_image_name = image.name
		
		return {'FINISHED'}


class BH_OT_create_bakenode_output_image_name_dialog(Operator):
	"""Creates new image datablock for selected BakeNode output."""
	bl_idname = "bake.bh_ot_create_bakenode_output_image_name_dialog"
	bl_label = "Create BakeNode Output Image..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	name : StringProperty(
		name="Image Name",
		default="New BakeNode Image"
	)

	file_path : StringProperty(
		name="Image File Path",
		default="//Textures/"
	)

	width : IntProperty(
		name="Width",
		default=1024
	)

	height : IntProperty(
		name="Height",
		default=1024
	)

	color_type : EnumProperty(
		items=[
			("sRGB","Color","","",0),
			("Non-Color","Non-Color","","",1)
			],
		name="Color Type",
		default="sRGB"
	)

	alpha : BoolProperty(
		name="Alpha",
		default=False
	)

	float_buffer : BoolProperty(
		name="32 bit Float",
		default=False
	)
	
	use_fake_user : BoolProperty(
		name="Fake User",
		description="Keep this image even if it has no users.",
		default=True
	)
	
	save_to_disk : BoolProperty(
		name="Save to Disk",
		description="Save image to disk after creation, otherwise, image will be packed inside blend file.",
		default=False
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup()
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		self.bakenode_output_index = context.scene.bakenode_output_active_index
		
		BH_OT_create_bakenode_output_image_name.execute(self, context)
		
		return {'FINISHED'}


class BH_OT_batch_create_bakenode_output_image_name_dialog(Operator):
	"""Creates new image datablock for selected BakeNode output."""
	bl_idname = "bake.bh_ot_batch_create_bakenode_output_image_name_dialog"
	bl_label = "Batch Create BakeNode Output Images..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	width : IntProperty(
		name="Width",
		default=1024
	)

	height : IntProperty(
		name="Height",
		default=1024
	)
	
	alpha : BoolProperty(
		name="Alpha",
		default=False
	)

	float_buffer : BoolProperty(
		name="32 bit Float",
		default=False
	)
	
	use_fake_user : BoolProperty(
		name="Fake User",
		description="Keep this image even if it has no users.",
		default=True
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup()
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		self.save_to_disk = False
		self.file_path = ""
		prefix = bakenode_nodegroup.name[:bakenode_nodegroup.name.find("BakeNode")]
		
		for i, output in enumerate(bakenode_nodegroup.outputs):
			if not output.bakenode_output_settings.enabled:
				continue
			
			self.bakenode_output_index = i
			self.image_name = prefix + output.name
			if output.type == "RGBA":
				self.color_type = "sRGB"
			else:
				self.color_type = "Non-Color"
			
			BH_OT_create_bakenode_output_image_name.execute(self, context)
			
		return {'FINISHED'}


class BH_OT_batch_set_bakenode_output_image_name_fake_user_dialog(Operator):
	"""Creates new image datablock for selected BakeNode output."""
	bl_idname = "bake.bh_ot_batch_set_bakenode_output_image_fake_user_dlg"
	bl_label = "Batch Set BakeNode Output Images Fake User..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	use_fake_user : BoolProperty(
		name="Fake User",
		description="Keep this image even if it has no users.",
		default=True
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup() is not None
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		
		for output in bakenode_nodegroup.outputs:
			if output.bakenode_output_settings.enabled:
				if output.bakenode_output_settings.output_image_name:
					bpy.data.images[output.bakenode_output_settings.output_image_name].use_fake_user = self.use_fake_user
		
		return {'FINISHED'}


class BH_OT_create_bakenode_output_dialog(Operator):
	"""Creates new output for selected BakeNode."""
	bl_idname = "bake.bh_ot_create_bakenode_output_dialog"
	bl_label = "Create BakeNode Output..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	color_type  : EnumProperty(
		items=[
			("NodeSocketColor","Color","","",0),
			("NodeSocketVector","Vector","","",1),
			("NodeSocketFloat","Value","","",2),
			],
		name="Color Type",
		default="NodeSocketColor"
	)
	
	name : StringProperty(
		name="Output Name",
		default="Output"
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup()
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		
		input_node = get_node("Group Input", bakenode_nodegroup.nodes, "NodeGroupInput")
		output_node = get_node("Group Output", bakenode_nodegroup.nodes, "NodeGroupOutput")
		
		input = bakenode_nodegroup.inputs.new(self.color_type, self.name)
		output = bakenode_nodegroup.outputs.new(self.color_type, self.name)
		
		bakenode_nodegroup.links.new(input_node.outputs[input.name], output_node.inputs[output.name])
		
		return {'FINISHED'}


class BH_OT_batch_save_bakenode_outputs(Operator):
	"""Saves BakeNode outputs."""
	bl_idname = "bake.bh_ot_batch_save_bakenode_outputs"
	bl_label = "Batch Save BakeNode Output Images"
	bl_options = {'REGISTER','UNDO','INTERNAL'}
	
	# Properties
	base_path : StringProperty(
		name="Base Path",
		default=""
	)

	suffix : StringProperty(
		name="Suffix",
		default=""
	)
	
	prefix : StringProperty(
		name="Prefix",
		default=""
	)
	
	save : BoolProperty(
		name="Save",
		default=False
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup()

	def execute(self, context):
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		
		for output in bakenode_nodegroup.outputs:
			if not output.bakenode_output_settings.output_image_name or not output.bakenode_output_settings.enabled:
				continue
			
			image = bpy.data.images[output.bakenode_output_settings.output_image_name]
			
			base_path, file_name = create_image_file_path(self.base_path, self.prefix, image.name, self.suffix)
			
			print("path in batch save", base_path)
			
			if not os.path.exists(base_path):
				os.makedirs(base_path)
			
			image.filepath_raw = base_path + file_name
			
			print("path in batch save", image.filepath_raw)
			
			if self.save:
				if image.packed_file:
					image.unpack(method="WRITE_LOCAL")
				else:
					image.save()
		
		return {'FINISHED'}


class BH_OT_create_bakenode_output_image_name_node_dialog(Operator):
	"""Creates an image node with selected bakenode output."""
	bl_idname = "bake.bh_ot_create_bakenode_output_image_name_node_dialog"
	bl_label = "Create BakeNode Output Image Node..."
	bl_options = {'REGISTER','UNDO'}
	
	# Properties
	bakenode_output_index : EnumProperty(
		items=get_enum_master_bakenode_outputs,
		name="Bake Output",
	)
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree and
			get_master_bakenode_nodegroup() and
			get_bakenode(obj.active_material)
		)
		
	def invoke(self, context, event):
		return context.window_manager.invoke_props_dialog(self)

	def execute(self, context):
		active_mat = context.active_object.active_material
		bakenode_output_index = int(self.bakenode_output_index)
		active_mat_nodes = active_mat.node_tree.nodes
		active_bakenode = get_bakenode(active_mat)
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		bake_nodegroup_output = bakenode_nodegroup.outputs[bakenode_output_index]
		bake_nodegroup_output_settings = bake_nodegroup_output.bakenode_output_settings
		
		output_image_name = bake_nodegroup_output_settings.output_image_name
		
		if output_image_name and output_image_name in bpy.data.images:
			image_node = create_node(
					"Image Texture",
					active_mat_nodes,
					"ShaderNodeTexImage"
				)
			image_node.image = bpy.data.images[output_image_name]
		
		image_node.label = ""
		set_node_relative_location(active_bakenode, image_node, vert_align="CENTER", horz_align="CENTER")
		
		deselect_all_nodes(active_mat_nodes)
		image_node.select = True
		active_mat_nodes.active = image_node
		
		return {'FINISHED'}


class BH_OT_create_bakenode_output_image_name_nodes(Operator):
	"""Creates image nodes from selected bakenode."""
	bl_idname = "bake.bh_ot_create_bakenode_output_image_name_nodes"
	bl_label = "Create BakeNode Output Image Nodes"
	bl_options = {'REGISTER','UNDO'}
	
	@classmethod
	def poll(cls, context):
		obj = context.active_object
		return (
			obj and
			obj.active_material and
			obj.active_material.node_tree and
			get_master_bakenode_nodegroup() and
			get_bakenode(obj.active_material)
		)

	def execute(self, context):
		mat = context.active_object.active_material
		active_mat_nodes = mat.node_tree.nodes
		bakenode = get_bakenode(mat)
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		
		# For positioning image nodes
		last_node = bakenode
		
		deselect_all_nodes(active_mat_nodes)
		
		for output in bakenode_nodegroup.outputs:
			output_image_name = output.bakenode_output_settings.output_image_name
		
			if output_image_name and output_image_name in bpy.data.images:
				image_node = create_node(
						"Image Texture",
						active_mat_nodes,
						"ShaderNodeTexImage"
					)
				image_node.image = bpy.data.images[output_image_name]
			else:
				continue
			
			image_node.label = ""
			set_node_relative_location(last_node, image_node, horz_align="CENTER", vert_align="BOTTOM")
			
			image_node.select = True
			
			last_node = image_node
		
		active_mat_nodes.active = image_node
		
		return {'FINISHED'}


class BH_OT_show_bakenode_output_image_name_in_editor(Operator):
	"""Shows bakenode output image in Image editor."""
	bl_idname = "bake.bh_ot_show_bakenode_output_image_name_in_editor"
	bl_label = "Show Bakenode Output Image"
	bl_options = {'REGISTER','UNDO','INTERNAL'}
	
	# Properties
	bakenode_output_index : IntProperty(
		name="Bake Output",
		default=0
	)
	
	@classmethod
	def poll(cls, context):
		return get_master_bakenode_nodegroup()

	def execute(self, context):
		bakenode_output_index = int(self.bakenode_output_index)
		bakenode_nodegroup = get_master_bakenode_nodegroup()
		bakenode_nodegroup_output = bakenode_nodegroup.outputs[bakenode_output_index]
		bakenode_nodegroup_output_settings = bakenode_nodegroup_output.bakenode_output_settings
		
		for area in context.screen.areas:
			if area.type == "IMAGE_EDITOR":
				# check if output image is valid
				if bakenode_nodegroup_output_settings.output_image_name in bpy.data.images:
					area.spaces[0].image = bpy.data.images[bakenode_nodegroup_output_settings.output_image_name]
				else:
					area.spaces[0].image = bpy.data.images[BAKEHELPER_DEFAULT_IMAGE_NAME]
				break
		
		return {'FINISHED'}

## UI

class BH_UL_active_bakenode_outputs_list(UIList):
	"""List to show all active bakenode outputs."""
	def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
		if self.layout_type in {"DEFAULT", "COMPACT"}:
			icon = 'NONE'
			
			layout.prop(item.bakenode_output_settings, "enabled", text="")
			if not item.bakenode_output_settings.output_image_name or item.bakenode_output_settings.output_image_name not in bpy.data.images:
				icon = "X"
			elif not bpy.data.images[item.bakenode_output_settings.output_image_name].filepath:
				icon = "IMPORT"
			
			layout.label(text=item.name, icon=icon)
			
		elif self.layout_type == "GRID":
			layout.alignment = "CENTER"
			layout.label(label="", icon="SELECT_SET")


class BH_PT_bake_helper_panel(Panel):
	"""Creates panel in the Properties window/Render Tab"""
	bl_idname = "BH_PT_bake_helper_panel"
	bl_label = "Bake Helper"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "render"

	def draw(self, context):
		layout = self.layout
		obj = context.active_object
			
		layout.separator()
		
		layout.operator(BH_OT_prepare_bake.bl_idname, text = "Prepare Bake")
		layout.operator(BH_OT_prepare_bake.bl_idname, text = "Prepare Bake (Reset node image)").reset_bake_helper_image=True
		layout.label(text="Bake Checklist")

		# If active object has at least one UV
		if obj and obj.type == "MESH":
			if obj.data.uv_layers:
				layout.label(text="This model has a UV", icon="FILE_TICK")
			else:
				layout.label(text="This model doesn't have a UV!", icon="CANCEL")
		else:
			layout.label(text="This object doesn't support UVs.")
		
		if BAKEHELPER_DEFAULT_IMAGE_NAME in bpy.data.images:
			image = bpy.data.images[BAKEHELPER_DEFAULT_IMAGE_NAME]
			
			layout.label(text="Bake Helper Image Settings")
			layout.prop(image, "size")
			layout.prop(image, "use_generated_float")
			layout.prop(image.colorspace_settings, "name")


class BH_PT_bake_helper_panel_node_editor(Panel):
	bl_idname = "BH_PT_bake_helper_panel_node_editor"
	bl_label = "BakeNode Settings"
	bl_space_type = 'NODE_EDITOR'
	bl_region_type = 'UI'
	#bl_context = "render"
	bl_category = "Bake"
	
	draw = BH_PT_bake_helper_panel.draw

class BH_PT_bakenode_settings(Panel):
	"""Sub-panel in BakeHelper Panel for BakeNode Settings"""
	bl_idname = "BH_PT_bakenode_settings"
	bl_label = "BakeNode Settings"
	bl_parent_id = "BH_PT_bake_helper_panel"
	bl_options = {'DEFAULT_CLOSED'}
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "render"
	#COMPAT_ENGINES = {'BLENDER_RENDER', 'BLENDER_EEVEE', 'BLENDER_WORKBENCH'}

	def draw(self, context):
		layout = self.layout
		obj = context.active_object
		
		if get_master_bakenode_nodegroup():
			bakenode_nodegroup = get_master_bakenode_nodegroup()
			bakenode_active_output_index = context.scene.bakenode_output_active_index
			active_bakenode_output_settings = bakenode_nodegroup.outputs[bakenode_active_output_index].bakenode_output_settings
			
			layout.label(text="BakeNode Outputs")
			# List of bakenode outputs
			layout.template_list("BH_UL_active_bakenode_outputs_list", "", bakenode_nodegroup, "outputs", context.scene, "bakenode_output_active_index")
			# Connect active bakenode output
			layout.operator(BH_OT_connect_bakenode_output.bl_idname).bakenode_output_index = bakenode_active_output_index
			
			layout.separator()
			
			layout.label(text="Output Settings")
			# Change active bakenode output image
			layout.prop_search(active_bakenode_output_settings, "output_image_name", bpy.data, "images")
			
			if not active_bakenode_output_settings.output_image_name:
				# Create new image for active bakenode output
				layout.operator(BH_OT_create_bakenode_output_image_name_dialog.bl_idname, text="New Image...")
			else:
				# Show active bakenode output picture in image editor
				layout.operator(BH_OT_show_bakenode_output_image_name_in_editor.bl_idname).bakenode_output_index = bakenode_active_output_index
			# Active bakenode output settings
			layout.prop(active_bakenode_output_settings, "samples")
			layout.prop(active_bakenode_output_settings, "padding_per_128")

			layout.separator()
			# Batch operators
			layout.operator(BH_OT_batch_create_bakenode_output_image_name_dialog.bl_idname, text="Batch Create Output Images")
			layout.operator(BH_OT_batch_set_bakenode_output_image_name_fake_user_dialog.bl_idname, text="Batch Set Output Image Fake Users")

			layout.separator()
			# 
			op_settings = layout.operator(BH_OT_batch_bake_bakenode_outputs.bl_idname, text="BakeNode Batch Bake")
			op_settings.bake_image_autosave = context.scene.bakenode_bake_settings.bake_image_autosave
			op_settings.autopack = context.scene.bakenode_ui_settings.batch_bake_autopack
			
			layout.prop(context.scene.bakenode_bake_settings, "bake_image_autosave")
			layout.prop(context.scene.bakenode_ui_settings, "batch_bake_autopack")
			
			layout.separator()
			
			layout.label(text="Batch Path Change")
			base_path, file_name = create_image_file_path(
				context.scene.bakenode_ui_settings.batch_image_base_path,
				context.scene.bakenode_ui_settings.batch_image_name_prefix,
				"NAME",
				context.scene.bakenode_ui_settings.batch_image_name_suffix
			)
			layout.label(text=base_path+file_name)
			
			layout.prop(context.scene.bakenode_ui_settings, "batch_image_base_path", text="Base Path")
			layout.prop(context.scene.bakenode_ui_settings, "batch_image_name_prefix", text="Prefix")
			layout.prop(context.scene.bakenode_ui_settings, "batch_image_name_suffix", text="Suffix")
			layout.prop(context.scene.bakenode_ui_settings, "batch_image_save", text="Batch Save")
			
			op_settings = layout.operator(BH_OT_batch_save_bakenode_outputs.bl_idname)
			op_settings.base_path = context.scene.bakenode_ui_settings.batch_image_base_path
			op_settings.suffix = context.scene.bakenode_ui_settings.batch_image_name_prefix
			op_settings.prefix = context.scene.bakenode_ui_settings.batch_image_name_suffix
			op_settings.save = context.scene.bakenode_ui_settings.batch_image_save
			
		else:
			prefs = get_addon_preferences()
			layout.label(text=f"BakeNode '{prefs.master_bakenode_name}' doesn't exist.")

class BH_PT_bakenode_settings_node_editor(Panel):
	bl_idname = "BH_PT_bakenode_settings_node_editor"
	bl_label = "BakeNode Settings"
	bl_space_type = 'NODE_EDITOR'
	bl_region_type = 'UI'
	#bl_context = "render"
	bl_category = "Bake"
	bl_parent_id = "BH_PT_bake_helper_panel_node_editor"
	bl_options = {'DEFAULT_CLOSED'}
	
	draw = BH_PT_bakenode_settings.draw

## Preferences
class BH_addon_preferences(AddonPreferences):
	"""Bake Helper Addon Preferences"""
	bl_idname = __package__
	
	# Properties
	master_bakenode_name : StringProperty(
		name = "Master BakeNode Name",
		description = "Name for Master BakeNode nodegroup to use as default",
		default = "BakeNode"
	)
	
	create_missing_bakenode : BoolProperty(
		name="Create Missing BakeNodes",
		default=False
	)
	
	show_mini_manual : BoolProperty(
		name="Show Mini Manual",
		default=False
	)

	def draw(self, context):
		layout = self.layout
		
		layout.prop(self, "master_bakenode_name")
		layout.prop(self, "create_missing_bakenode")
		
		layout.prop(self, "show_mini_manual", toggle=True)
		
		if self.show_mini_manual:
			layout.label(text="Using Prepare Bake:", icon="DOT")
			layout.label(text="Go to Properties window > Render tab > Bake Helper section",icon="THREE_DOTS")
			layout.label(text="When you want to bake, click the Prepare Bake button.",icon="THREE_DOTS")
			layout.label(text="Bake Helper will create and select its nodes under the Material Output node.",icon="THREE_DOTS")
			layout.label(text="Change the Bake Helper node's settings, e.g. the image you'll be baking to, if you need to.",icon="THREE_DOTS")
			layout.label(text="After that, the selected objects should be ready to bake.",icon="THREE_DOTS")
			
			layout.label(text="Using BakeNode:", icon="DOT")
			layout.label(text="Create a Node Group with a name that ends with BakeNode, ie: Name_BakeNode",icon="THREE_DOTS")
			layout.label(text="Connect Node Group's inputs directly to its outputs",icon="THREE_DOTS")
			layout.label(text="Add the Node Group to any materials you want to bake",icon="THREE_DOTS")
			layout.label(text="When ready to bake, select the BakeNode and run 'Connect BakeNode Outputs'",icon="THREE_DOTS")
			
			layout.label(text="BakeNode Image Icons:", icon="DOT")
			row = layout.row(align=True)
			row.label(text="",icon="THREE_DOTS")
			row.label(text=" means that there is no image associated with the output, BakeHelper image will be used.",icon="X")
			
			row = layout.row(align=True)
			row.label(text="",icon="THREE_DOTS")
			row.label(text=" means that the image associated with the output is not saved, save it somewhere before baking",icon="IMPORT")
			
			layout.label(text="Baking Single Bakenode Output:", icon="DOT")
			layout.label(text="Select object you want to bake.",icon="THREE_DOTS")
			layout.label(text="Right click Bakenode.",icon="THREE_DOTS")
			layout.label(text="Click 'Bake Bakenode Output'",icon="THREE_DOTS")
			
			layout.label(text="Packed Images:", icon="DOT")
			layout.label(text="If an image has no path, they will automatically be packed when baked.",icon="THREE_DOTS")

## Append to UI Helper Functions
def add_connect_bakenode_outputs_button(self, context):
	orig_context = self.layout.operator_context
	
	self.layout.operator_context = "INVOKE_DEFAULT"
	self.layout.operator(BH_OT_connect_bakenode_output_dialog.bl_idname)
	self.layout.operator(BH_OT_bake_single_bakenode_output_dialog.bl_idname)
	self.layout.operator(BH_OT_create_bakenode_output_image_name_node_dialog.bl_idname)
	self.layout.operator(BH_OT_create_bakenode_output_image_name_nodes.bl_idname)
	self.layout.operator(BH_OT_bake_material_results_dialog.bl_idname)
	
	self.layout.operator_context = orig_context

## Register

classes = (
	BH_bakenode_output_settings,
	BH_bakenode_bake_settings,
	BH_bakenode_ui_settings,
	BH_OT_prepare_bake,
	BH_OT_connect_bakenode_output,
	BH_OT_connect_bakenode_output_dialog,
	BH_OT_bake_single_bakenode_output_dialog,
	BH_OT_batch_bake_bakenode_outputs,
	BH_OT_create_bakenode_output_image_name,
	BH_OT_create_bakenode_output_image_name_dialog,
	BH_OT_batch_create_bakenode_output_image_name_dialog,
	BH_OT_batch_set_bakenode_output_image_name_fake_user_dialog,
	BH_OT_create_bakenode_output_dialog,
	BH_OT_batch_save_bakenode_outputs,
	BH_OT_create_bakenode_output_image_name_node_dialog,
	BH_OT_create_bakenode_output_image_name_nodes,
	BH_OT_show_bakenode_output_image_name_in_editor,
	BH_UL_active_bakenode_outputs_list,
	BH_PT_bake_helper_panel,
	BH_PT_bake_helper_panel_node_editor,
	BH_PT_bakenode_settings,
	BH_PT_bakenode_settings_node_editor,
	BH_OT_bake_material_results_dialog,
	BH_addon_preferences
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)
		
	bpy.types.Scene.bakenode_output_active_index = IntProperty(name = "Active Bakenode Output Index", default = 0)
	bpy.types.Scene.bakenode_bake_settings = PointerProperty(type=BH_bakenode_bake_settings)
	bpy.types.Scene.bakenode_ui_settings = PointerProperty(type=BH_bakenode_ui_settings)
	bpy.types.NodeSocketInterfaceStandard.bakenode_output_settings = PointerProperty(
		type=BH_bakenode_output_settings
	)
	
	bpy.types.NODE_MT_context_menu.append(add_connect_bakenode_outputs_button)

def unregister():
	bpy.types.NODE_MT_context_menu.remove(add_connect_bakenode_outputs_button)
	
	del bpy.types.NodeSocketInterfaceStandard.bakenode_output_settings
	del bpy.types.Scene.bakenode_output_active_index
	del bpy.types.Scene.bakenode_ui_settings
	del bpy.types.Scene.bakenode_bake_settings
	
	for cls in classes:
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	register()
