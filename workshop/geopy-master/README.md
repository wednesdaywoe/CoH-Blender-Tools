# geopy

A Blender add-on and Python tools for manipulating .geo and .anim files.

# Blender Add-On

The Blender add-on allows you to:
 - export .geo files
 - import .geo files
 - import skeletons from skel_*.anim files

## Installing the Add-On

1. Download geopy-v0.2.5.zip
2. In Blender open "User Preferences" then select the "Add-ons" tab.
3. Click the "Install Add-on from File..." button and select the downloaded zip.
4. Enable the add-on and click the "Save User Preferences" button.

## Using the Add-On
### Exporting models

1. Select 1 or more meshes to export in object mode.
2. From the menu select File->Export->"City of Heroes (Feet) (.geo)"  (or "City of Heroes (Meters) (.geo)" if your meshes have been scaled in meters).
3. Browse to the file you want to create and click "Export GEO".

Notes: Models are exported with the name of the mesh they come from, so having the meshes named correctly is recommended.

### Importing models

1. From the menu select File->Import->"City of Heroes (Feet) (.geo)"  (or "City of Heroes (Meters) (.geo)" if your converting to meters).
2. Browse to the file you want to import and click "Import GEO". All models in the .geo file will then be imported.

Note: A model's name is expected to be in the format of "GEO_<bone>_<name>", where <bone> is the bone the model will be anchored to. 

Note: If multiple armatures exist, the armature you wish to use must be selected. Otherwise it will use the first armature it will find.

Note: Presently LOD models are excluded from imports.

### Importing skeletons

1. From the menu select File->Import->"City of Heroes Skeleton (skel_*.anim).
2. Browse to the file you want to import and click "Import".

Note: A new aramature will be created using the name found inside the file.

Note: The import will fail if the .anim file is missing a skeleton hierarchy.

### Importing animations

1. From the menu select File->Import->"City of Heroes Animation (*.anim).
2. Browse to the file you want to import and click "Import".

Note: It will import as a NLA track to the currently selected armature.

Note: If bone in the animation is missing from armature, the import will fail.
Note: If there is an existing animation in the armature with the same name as what you're trying to import, the import will fail. Rename your existing animation, and retry the import.

# Tools

These command line tools allow inspection and modification of .geo files.

## geo.py
Contains the Geo class, which represents the contents of .geo files. Can be run to test the reading and writing functionality.

geo.py &lt;infile.geo&gt; [&lt;outfile.geo&gt;]

If only an input .geo file is specified, it will read the input and dump the contents of the .geo to the console.

If an output .geo file is specified, it will read the input .geo file, and write the contents to the output as a new .geo file.

## stl_dump.py
Dumps the meshes of a .geo file to .stl files. Used for testing and validation, as .stl isn't useful for games.

stl_dump.py &lt;file.geo&gt;

Dumps all the meshes contained in &lt;file.geo&gt; to &lt;geo_name&gt;/&lt;model_name.stl&gt;. &lt;geo_name&gt; and &lt;model_name&gt; are read from the .geo.

## geo_edit.py
A command line tool for modifying a .geo file

geo_edit.py &lt;infile.geo&gt; &lt;outfile.geo&gt; &lt;operation&gt; [&lt;operation options&gt; ...]

Operation                   | Description
--------------------------- | ---------------------------
  del_model &lt;reg_ex&gt;  | Deletes all models whose name contains the regular expression &lt;reg_ex&gt;.
  geo_name &lt;name&gt;     | Change the .geo's name to &lt;name&gt;.
  swap_left_right &lt;reg_ex&gt; | Swap left and right bones for all models matching &lt;reg_ex&gt;.
  rename_model &lt;old&gt; &lt;new&gt; | Rename a model from &lt;old&gt; to &lt;new&gt;.
  rename_texture &lt;old&gt; &lt;new&gt; | Rename a texture from &lt;old&gt; to &lt;new&gt;.
  rescale_all &lt;scale&gt; | Rescale all vertices in all models by multiplying them all by &lt;scale&gt; .
  set_model_scale &lt;model&gt; &lt;x&gt; &lt;y&gt; &lt;z&gt; | Set the scale properties of the given model (not the same as rescaling).
Multiple operations can be specified and performed in the same run.

Unless noted otherwise, model names and regular expressions are case sensitive.

## geo_list.py

A command line tool for list the model name inside of 1 or more .geo files.

geo_list.py [&lt;output_options&gt;] &lt;file.geo&gt; [&lt;file.geo&gt; ...]

The output format is:
&lt;geo_name&gt; : &lt;model_name&gt;

&lt;output_options&gt; adds additional items that can be outputted:
 -t Prints the triangle count of the model. Added output format:  ": &lt;tri_count&gt;"
 -s Prints the scale of the model. Added output format:  ": &lt;sacle_x&gt;, &lt;sacle_y&gt;, &lt;sacle_z&gt;"

## texture.py
Contains the Texture class, which represents .texture files. Can be run to test the reading and writing functionality.

Note: Requires Wand to be installed: http://wand-py.org/

texture.py &lt;infile.texture&gt; [&lt;outfile.texture&gt;]

If only an input .texture is specified, it will read the input file and dump the contents to the console.

If an output .texture is specified, it will read the input.texture file, and write the contents to the output .texture file.

## texture_extract.py
A command line tool for extracting an image from a .texture file.

Note: Requires Wand to be installed: http://wand-py.org/

texture_extract.py &lt;infile.texture&gt; [&lt;outfile&gt;]

Reads the file &lt;infile.texture&gt; and writes the contained image to an output file.

If &lt;outfile&gt; is specified it will write to this file. If no &lt;outfile&gt; is specified it will use the file name contained inside the .texture file, recreating the directory structure.

## dds2tex.py
A command line tool for converting a .dds file into a .texture .

Note: Requires Wand to be installed: http://wand-py.org/

texture_extract.py &lt;infile.dds&gt; [&lt;outfile.texture&gt; [&lt;texture_filename&gt;]]

&lt;infile.dds&gt; is the input file.

&lt;outfile.texture&gt; is the output file. If not specified it will use the same file name as the input except with a .texture extension. If &lt;outfile.texture&gt; is a directory it will use &lt;texture_filename&gt; with a .texture extension as the file name and directory, but placed under the directory &lt;outfile.texture&gt; .

&lt;texture_filename&gt; the filename to store inside the .texture file. If this not specified, it defaults to &lt;infile.dds&gt; . If &lt;infile.dds&gt; contains "texture_library" it will discard everything before "texture_library" use the remainder.


## Known Issues
 - Not all structures are handled (reflection quads)
 - Not all structures are regenerated when writing a .geo file. (Reductions)
 - Blender import of .geo files is currently a stub.
