import bpy
import os
import json
import numpy as np 
from numpyencoder import NumpyEncoder 
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
import shortuuid

# Define some convenience variables
context = bpy.context
scene = bpy.context.scene
s3 = boto3.client('s3')
job_id = ""

# Define a callback function for the property updates... the ui won't work properly without this :(
def updated(self, context):
    return None 

# Define a PropertyGroup. These properties will be used in the UI Panel to let the user specify
    # the required resources on the AWS Swarm
class InstanceProperties(bpy.types.PropertyGroup):
    instance_count : bpy.props.IntProperty(name="Instance Count", default=1, min=1, max=6)
    instance_type : bpy.props.EnumProperty(
        name = "Instance Type",
        description = "Select the type of EC2 instance",
        items = [('xlarge', 'xlarge', ""),
                 ('2xlarge', '2xlarge', ""),
                 ('4xlarge', '4xlarge', ""),
                 ('8xlarge', '8xlarge', ""),
                 ('12xlarge', '12xlarge', ""),
                 ('16xlarge', '16xlarge', "")
        ]
    )
    time : bpy.props.StringProperty(name="Time", update=updated)
    check_time : bpy.props.BoolProperty(name="Auto Refresh", default=False, update=updated)
    render_complete : bpy.props.StringProperty(name="Render Status", default="", update=updated)

#Define a function to divide the scene into render chunks
def get_chunks(count, start, end):
    
    frame_chunks = []
    np_chunks = np.array_split(range(start, end + 1), count)

    for chunk in np_chunks:
        frame_chunks.append((chunk[0], chunk[-1]))

    return frame_chunks

# Define a function that will upload the saved blend file and the job.manifest file to s3
def submit(count, instance_type):

    global job_id

    # Create a job directory and a job_id
    job_id = shortuuid.uuid()
    job_directory = os.path.join(bpy.app.tempdir, job_id)
    os.mkdir(job_directory)

    # Save the current .blend file for good measure
    bpy.ops.wm.save_mainfile()

    # Create a job manifest
    manifest = os.path.join(job_directory, "job.manifest")
    print(manifest)

    # Save the name of the blender file and its path to a variable
    filepath = bpy.data.filepath
    blend = os.path.basename(filepath)

    # Call the function to get the render chunks
    chunks = get_chunks(count, scene.frame_start, scene.frame_end)

    # Create a dictionary object that can be converted into a json object
    manifest_dictionary = {
        'job_id' : job_id,
        'start_frame' : scene.frame_start,
        'end_frame' : scene.frame_end,
        'chunks' : chunks,
        'instance_count' : count,
        'instance_type' : instance_type,
        'key' : blend,
        'format' : scene.render.image_settings.file_format.lower()
    }

    # Write the manifest file out to the job directory
    with open(manifest, 'w') as json_file:
        json.dump(manifest_dictionary, json_file, indent=4, cls=NumpyEncoder)

    # Create some strings for the file location paths
    manifest_name = "{}/{}".format(job_id, "job.manifest")
    blend_name = "{}/{}".format(job_id, blend)

    # Upload the files to s3
    try:
        response = s3.upload_file(filepath, "hive-render-input", blend_name)
    except ClientError as e:
        print(e)

    try:
        response = s3.upload_file(manifest, "hive-render-input", manifest_name)
    except ClientError as e:
        print(e)

    # Start checking to see if the render is complete
    scene.instance_props.render_complete = "RENDERING..."
    scene.instance_props.check_time = True


# Define a function that polls the output bucket and determines if the render job is complete
def isRenderComplete():

    # Periodically check the output bucket. If the number of objects in the bucket is equal to the number of frames in the scene,
        # the job is complete
    try:
        response = s3.list_objects_v2(
            Bucket = "hive-render-output",
            Prefix = '{}/'.format(job_id)
        )
    except ClientError as e:
        print(e)
        return False

    frame_count = (scene.frame_end - scene.frame_start) + 1
    if response['KeyCount'] == frame_count:
        scene.instance_props.check_time = False
        return True
    else:
        return False

# Define a function to retrieve the rendered frames from the s3 output bucket
def get_final_frames():

    # If an output directory does not already exist for the current job id, create one
    output_directory = "{}{}/render_out".format(bpy.app.tempdir, job_id)
    if not os.path.exists(output_directory):
        os.mkdir(output_directory)

    print("OUTPUT DIRECORY: ", output_directory)

    # Get a list of keys from the output bucket
    try:
        response = s3.list_objects_v2(
            Bucket = 'hive-render-output',
            Prefix = '{}/'.format(job_id)
        )

        print("List objects complete")
    except ClientError as e:
        print(e)

    # Store the contents of the list bucket response in an iterable
    images = response['Contents']

    # Iterate over the image list and download the files to the local output directory
    for image in images:
        key_base = image['Key'].split('/')[-1]
        output_file = "{}{}/render_out/{}".format(bpy.app.tempdir, job_id, key_base)
        try:
            reply = s3.download_file("hive-render-output", image['Key'], output_file)
            print("DOWNLOAD SUCCEDED: ", image['Key'])
        except ClientError as e:
            print(e)

# Define a timer to be used to check the output directory for finished images
def run_timer():
    if scene.instance_props.check_time:
        bpy.ops.app.get_time()
        bpy.ops.app.check_render_complete()
        
    return 1

# Operator for checking if the render has completed
class CheckRenderComplete(bpy.types.Operator):
    bl_idname = "app.check_render_complete"
    bl_label = "Check Render"

    def execute(self, context):
        
        if isRenderComplete():
            scene.instance_props.render_complete = "COMPLETE!"
        else:
            scene.instance_props.render_complete = "RENDERING..."
    
        return {'FINISHED'}

# Operator for debugging time and ui display
class GetTime(bpy.types.Operator):
    bl_idname = "app.get_time"
    bl_label = "Get Time"

    def execute(self, context):
        scene.instance_props.time = str(datetime.now())
        return{'FINISHED'}

# Operator to retrieve the finished renders from the s3 output bucket
class GetFrames(bpy.types.Operator):
    bl_idname = "ops.get_final_frames"
    bl_label = "Get Final Frames"

    def execute(self, context):
        get_final_frames()
        return {'FINISHED'}

# DEBUG Operator
class PrintDebug(bpy.types.Operator):
    bl_idname = "ops.print_debug"
    bl_label = "Print Debug Info"

    def execute(self, context):
        print(job_id)
        return {'FINISHED'}

# Define a blender internal Operator to call the upload function
class SubmitOperator(bpy.types.Operator):
    bl_idname = "ops.hive_render_submit"
    bl_label = "Submit to Hive Render"

    def execute(self, context):

        # Call the upload function
        submit(scene.instance_props.instance_count, scene.instance_props.instance_type)
        return {'FINISHED'}

# Create a panel and add the Operator to it as a button
class HiveRenderPanel(bpy.types.Panel):
    bl_label = "HiveRender v0.1"
    bl_idname = "OBJECT_PT_hiverender"
    bl_space_type = 'VIEW_3D'
    bl_region_type = "UI"
    bl_category = "Hive_Render"

    def draw(self, context):
        
        layout = self.layout

        row = layout.row()
        row.prop(scene.instance_props, "instance_count")

        separator = layout.separator(factor=1.0)

        row = layout.row()
        row.prop(scene.instance_props, "instance_type")

        separator = layout.separator(factor=1.0)

        row = layout.row()
        row.scale_y = 3.0
        row.operator("ops.hive_render_submit")

        row = layout.row()
        row.prop(scene.instance_props, "render_complete", emboss=False)

        row = layout.row()
        row.operator("ops.get_final_frames")

        row = layout.row()
        row.prop(scene.instance_props, "time", emboss=False, text='')
        row.prop(scene.instance_props, "check_time", text='')

        row = layout.row()
        row.operator("ops.print_debug")

# Register the classes with blender
def register():
    bpy.utils.register_class(SubmitOperator)
    bpy.utils.register_class(HiveRenderPanel)
    bpy.utils.register_class(InstanceProperties)
    bpy.utils.register_class(GetTime)
    bpy.utils.register_class(CheckRenderComplete)
    bpy.utils.register_class(GetFrames)
    bpy.utils.register_class(PrintDebug)

    bpy.app.timers.register(run_timer)

    bpy.types.Scene.instance_props = bpy.props.PointerProperty(type=InstanceProperties)

# Unregister the classes with blender
def unregister():
    bpy.utils.unregister_class(SubmitOperator)
    bpy.utils.unregister_class(HiveRenderPanel)
    bpy.utils.unregister_class(InstanceProperties)
    bpy.utils.unregister_class(GetTime)
    bpy.utils.unregister_class(CheckRenderComplete)
    bpy.utils.unregister_class(GetFrames)
    bpy.utils.unregister_class(PrintDebug)

    bpy.app.timers.unregister(run_timer)

    del bpy.type.Scene.instance_props

if __name__ == "__main__":
    register()