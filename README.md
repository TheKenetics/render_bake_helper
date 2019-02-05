# BakeHelper2.8
Blender 2.8 addon helps users prepare their objects for baking.

## Why  
I created this because I was tired going through the ol' baking checklist:  
- Did I add an image node?
- Did I select it?
- Oh, I edited my material... is my image still selected?  

Repeat for each material your objects have.

## Install  
1. Download the python file (put it in a place where you can easily find it, like your desktop)
2. In Blender's settings, go to the addons tab
3. At the bottom, click "Install from File"
4. Find where you put the python file, select it, and click "Install from File"

## Using  
Bake Helper is in Properties Window > Render Tab > Bake Helper

When you want to bake, simply press the Prepare Bake button in the Bake Helper panel.  
Bake Helper will create its nodes under the Material Output node in the objects' materials and select them.

Change the Bake Helper node's settings, e.g. the image you'll be baking to, if you need to.

After that, the selected objects should be ready to bake.

## Notes  
If a Bake Helper node was already created in your materials, pressing the Prepare Bake button *will not* overwrite them, it will just select them.

## Changelog  
### 0.5  
#### Features  
Added a Reset Node Image option to set the Bake Helper node's image back to the default Bake Helper image if it was changed to another image.  
#### Fixes  
Fixed trying to access UVs for object types that don't support UVs.  
Fixed trying to access the Bake Helper image when it doesn't exist.  
#### Rewriting
Changed many variable names to be more Pythonic.  
Changed class names to follow Blender guidelines more.  
