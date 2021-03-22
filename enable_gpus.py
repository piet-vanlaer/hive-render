## Modified from code found at 
## https://blender.stackexchange.com/questions/156503/rendering-on-command-line-with-gpu/156680#156680

import bpy
import os
import sys

BLEND_FILE = os.getenv('BLEND_FILE')
print(BLEND_FILE)
RENDER_OUT = os.getenv('RENDER_OUT')
print(RENDER_OUT)
START = os.getenv('START')
print(START)
END = os.getenv('END')
print(END)
FORMAT = os.getenv('FORMAT').upper()
print(FORMAT)

def enable_gpus(device_type, use_cpus=False):
    preferences = bpy.context.preferences
    cycles_preferences = preferences.addons["cycles"].preferences
    cuda_devices, opencl_devices = cycles_preferences.get_devices()

    if device_type == "CUDA":
        devices = cuda_devices
    elif device_type == "OPENCL":
        devices = opencl_devices
    else:
        raise RuntimeError("Unsupported device type")

    activated_gpus = []

    for device in devices:
        if device.type == "CPU":
            device.use = use_cpus
        else:
            device.use = True
            activated_gpus.append(device.name)
    cycles_preferences.compute_device_type = device_type
    bpy.context.scene.cycles.device = "GPU"

    return activated_gpus

enable_gpus("CUDA")



bpy.ops.wm.open_mainfile(filepath="/tmp/{}".format(BLEND_FILE))
bpy.context.scene.frame_start = int(START)
bpy.context.scene.frame_end = int(END)
bpy.context.scene.render.filepath = "{}/{}_####".format(RENDER_OUT, BLEND_FILE)
bpy.context.scene.render.image_settings.file_format = FORMAT
bpy.ops.render.render(animation=True)


#bpy.ops.wm.quit_blender()
