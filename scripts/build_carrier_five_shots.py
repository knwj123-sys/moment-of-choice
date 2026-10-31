"""Five-shot batch camera study for the existing carrier GLB. Blender 4.0+."""
import bpy
import json
import math
import os
import sys
from mathutils import Vector

ROOT = os.getcwd()
MODEL = os.path.join(ROOT, "generic-unarmed-aircraft-carrier.glb")
CONFIG = os.path.join(ROOT, "shots", "carrier_shots.json")
OUTPUT = os.path.join(ROOT, "output")
os.makedirs(OUTPUT, exist_ok=True)

if not os.path.isfile(MODEL):
    raise RuntimeError("Missing source GLB: " + MODEL)
with open(CONFIG, encoding="utf-8") as f:
    cfg = json.load(f)
shots = cfg["shots"]
if len(shots) != 5 or len({s["name"] for s in shots}) != 5:
    raise RuntimeError("Expected five uniquely named shots")
if any(int(s["frames"]) < 2 for s in shots):
    raise RuntimeError("Every shot needs at least two frames")

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.import_scene.gltf(filepath=MODEL)
meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
if not meshes:
    raise RuntimeError("GLB import produced no meshes")
bpy.context.view_layer.update()
points = [ob.matrix_world @ Vector(c) for ob in meshes for c in ob.bound_box]
minimum = Vector(tuple(min(p[i] for p in points) for i in range(3)))
maximum = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (minimum + maximum) * .5
dims = maximum - minimum
length_index = 0 if dims.x >= dims.y else 1
forward = Vector((1, 0, 0)) if length_index == 0 else Vector((0, 1, 0))
side = Vector((-forward.y, forward.x, 0))
length = max(dims.x, dims.y)
beam = min(dims.x, dims.y)
height = dims.z
if length <= 0 or beam <= 0:
    raise RuntimeError("Invalid GLB bounding box: " + str(tuple(dims)))
# Use the real bounding box instead of assuming a fixed orientation or scale.
pivot = Vector((center.x, center.y, minimum.z + height * .60))
scale = length

# Approximate sea level. This is a cinematic staging reference, not a hull draft measurement.
sea_z = minimum.z + height * 0.15
bpy.ops.mesh.primitive_plane_add(size=2, location=(center.x, center.y, sea_z))
sea = bpy.context.object
sea.name = "STAGING_OCEAN_not_physical_simulation"
sea.scale = (length * 7, length * 7, 1)
mat = bpy.data.materials.new("Ocean_deep_blue")
mat.diffuse_color = (.028, .10, .18, 1)
sea.data.materials.append(mat)

world = bpy.context.scene.world
if world is None:
    world = bpy.data.worlds.new("Overcast maritime light")
    bpy.context.scene.world = world
world.color = (.38, .45, .52)

bpy.ops.object.light_add(type="AREA", location=center + forward * length * .25 + side * length * .4 + Vector((0, 0, length * .6)))
light = bpy.context.object
light.name = "Large soft daylight"
light.data.energy = 3200
light.data.shape = "DISK"
light.data.size = length * .8
light.rotation_euler = (pivot - light.location).to_track_quat("-Z", "Y").to_euler()

scene = bpy.context.scene
scene.render.fps = 24
scene.render.resolution_x = 1280
scene.render.resolution_y = 720
scene.render.resolution_percentage = 100
scene.frame_start = 1
scene.camera = None

# Shot positions: all offsets are relative to the imported ship length.
# Each shot is independently editable and automatically switched via timeline markers.
preset = {
    "01_establishing": ((-.95, 1.1, .38), (-.77, .96, .42), (0, 0, 0), 52),
    "02_low_side_track": ((-.40, .72, .18), (.44, .73, .20), (0, 0, .03), 58),
    "03_bow_approach": ((-1.45, .08, .28), (-.72, .15, .28), (0, 0, .03), 49),
    "04_aerial_deck": ((.15, .22, 1.45), (.26, -.06, 1.22), (0, 0, .02), 43),
    "05_stern_departure": ((1.12, -.72, .40), (1.53, -.93, .50), (0, 0, 0), 53),
}
def locate(relative):
    along, across, above = relative
    return pivot + forward * (along * scale) + side * (across * scale) + Vector((0, 0, above * scale))
def point_at(camera, target):
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()

report = {"source_model": os.path.basename(MODEL), "mesh_count": len(meshes),
          "bounding_dimensions": list(dims), "shots": [], "fps": 24}
frame = 1
for idx, spec in enumerate(shots):
    name = spec["name"]
    if name not in preset:
        raise RuntimeError("Unknown camera preset: " + name)
    start_offset, end_offset, target_offset, lens_mm = preset[name]
    shot_frames = int(spec["frames"])
    last = frame + shot_frames - 1
    bpy.ops.object.camera_add()
    camera = bpy.context.object
    camera.name = "CAM_" + name
    camera.data.type = "PERSP"
    camera.data.lens = lens_mm
    camera.data.clip_end = max(1000, scale * 50)
    target = locate(target_offset)
    for f, relative in ((frame, start_offset), (last, end_offset)):
        camera.location = locate(relative)
        point_at(camera, target)
        camera.keyframe_insert(data_path="location", frame=f)
        camera.keyframe_insert(data_path="rotation_euler", frame=f)
    if camera.animation_data and camera.animation_data.action:
        for curve in camera.animation_data.action.fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
    marker = scene.timeline_markers.new(name, frame=frame)
    marker.camera = camera
    if idx == 0:
        scene.camera = camera
    report["shots"].append({"name": name, "start_frame": frame, "end_frame": last,
                            "camera": camera.name, "description": spec.get("description", "")})
    frame = last + 1

scene.frame_end = frame - 1
scene.frame_set(1)
# Keep this .blend intentionally editable: five real cameras, real imported mesh, one timeline.
blend_path = os.path.join(OUTPUT, "carrier_five_shots.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
if not os.path.isfile(blend_path) or os.path.getsize(blend_path) < 1024:
    raise RuntimeError("Saved blend missing or unexpectedly small")
report["total_frames"] = scene.frame_end
report["seconds"] = round(scene.frame_end / scene.render.fps, 2)
report["blend_size_bytes"] = os.path.getsize(blend_path)
with open(os.path.join(OUTPUT, "shot_report.json"), "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print("BATCH_SUCCESS", json.dumps(report, ensure_ascii=False))
