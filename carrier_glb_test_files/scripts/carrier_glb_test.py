import bpy
import os
from mathutils import Vector

MODEL = os.path.abspath('generic-unarmed-aircraft-carrier.glb')
assert os.path.isfile(MODEL), f'Missing model: {MODEL}'
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=MODEL)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert meshes, 'GLB contained no meshes'
bpy.context.view_layer.update()
points = [obj.matrix_world @ Vector(c) for obj in meshes for c in obj.bound_box]
minimum = Vector(tuple(min(p[i] for p in points) for i in range(3)))
maximum = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (minimum + maximum) / 2
extent = max(maximum[i] - minimum[i] for i in range(3))
assert extent > 0, 'Model dimensions are zero'

bpy.ops.object.camera_add(location=center + Vector((extent * 1.2, -extent * 1.6, extent * 0.9)))
cam = bpy.context.object
cam.name = 'Animated cinematic camera'
cam.data.type = 'ORTHO'
cam.data.ortho_scale = extent * 2.5
cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
scene = bpy.context.scene
scene.camera = cam
cam.keyframe_insert(data_path='location', frame=1)
cam.keyframe_insert(data_path='rotation_euler', frame=1)
cam.location += Vector((-extent * .3, extent * .2, extent * .1))
cam.rotation_euler = (center - cam.location).to_track_quat('-Z', 'Y').to_euler()
cam.keyframe_insert(data_path='location', frame=120)
cam.keyframe_insert(data_path='rotation_euler', frame=120)
scene.frame_start = 1
scene.frame_end = 120
scene.render.fps = 24
scene.frame_set(1)
os.makedirs('output', exist_ok=True)
out = os.path.abspath('output/carrier_glb_test.blend')
bpy.ops.wm.save_as_mainfile(filepath=out)
print(f'SUCCESS: {len(meshes)} mesh objects imported. Saved: {out}')
