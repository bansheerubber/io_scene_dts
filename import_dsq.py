import math
from typing import Dict, List
import bpy
from math import ceil, pi

from .DsqFile import DsqFile
from .DtsTypes import Sequence, Quaternion, Vector, Matrix
from .util import fail, ob_location_curves, ob_scale_curves, ob_rotation_curves, ob_rotation_data, arm_location_curves, arm_scale_curves, arm_rotation_curves, \
  evaluate_all, find_reference

def get_free_name(name, taken):
  if name not in taken:
    return name

  suffix = 1

  while True:
    name_try = name + "." + str(suffix)

    if name_try not in taken:
      return name_try

    suffix += 1

# action.fcurves.new(data_path, array_index)
# action.fcurves[].keyframe_points.add(number)
# action.fcurves[].keyframe_points[].interpolation = "LINEAR"
# action.fcurves[].keyframe_points[].co

def load(operator, context, filepath,
         debug_report=False):
  dsq = DsqFile()

  with open(filepath, "rb") as fd:
    dsq.read(fd)

  if debug_report:
      with open(filepath + ".txt", "w") as fd:
        dsq.write_dump(fd)

  print("Resolving nodes...")

  found_obs = {}
  found_armatures: Dict[str, bpy.types.Object] = {}
  found_bones = {}

  # Find all our candidate nodes
  # DSQ is case-insensitive, that's why we can't just [] lookup
  for ob in context.scene.objects:
    if ob.type in ("EMPTY"):
      name = ob.name.lower()

      if name in found_obs:
        print("Warning: Nodes with varying capitalization found ('{}', '{}'), ignoring second".format(found_obs[name].name, ob.name))
        continue

      found_obs[name] = ob
      
    if ob.type in ("ARMATURE"):
      name = ob.name.lower()

      if name in found_armatures:
        print("Warning: Armatures with varying capitalization found ('{}', '{}'), ignoring second".format(found_armatures[name].name, ob.name))
        continue

      found_armatures[name] = ob
  
  use_armature = None
  for arm_name, armature in found_armatures.items():    
    for bone in armature.pose.bones:
      name = bone.name.lower()

      if name in found_bones:
        print("Warning: Bones with varying capitalization found ('{}', '{}'), ignoring second".format(found_bones[name].name, bone.name))
        continue

      use_armature = armature
      found_bones[name] = bone
        
    if use_armature is not None:
      break

  nodes = [None] * len(dsq.nodes)
  node_missing = []

  # Now associate DSQ node indices with Blender objects
  for index, name in enumerate(dsq.nodes):
    lower = name.lower()

    if use_armature is not None:
      # Use bones as nodes
      if lower in found_bones:
        nodes[index] = found_bones[lower]
      else:
        node_missing.append(name)
    else:
      # Use objects as nodes
      if lower in found_obs:
        nodes[index] = found_obs[lower]
      else:
        node_missing.append(name)

  if node_missing:
    return fail(operator, "The following nodes from the DSQ file could not be found in your scene:\n" + ", ".join(node_missing))

  # Now, find all the existing sequence names so we can rename duplicates
  # Also find out where the last user-defined animation data is
  last_frame = 1
  scene_sequences = set()

  for marker in context.scene.timeline_markers:
    last_frame = max(last_frame, int(ceil(marker.frame + 10)))

    if ":" not in marker.name:
      continue

    name, what = marker.name.rsplit(":", 1)
    scene_sequences.add(name)

  for action in bpy.data.actions:
    last_frame = max(last_frame, int(ceil(action.frame_range[1] + 10)))

  if "Sequences" in bpy.data.texts:
    for line in bpy.data.texts["Sequences"].as_string().split("\n"):
      line = line.strip()

      if not line or line == "strict" or ":" not in line:
        continue

      name, flags = line.split(":", 1)
      scene_sequences.add(name)

  sequences_text = []
  reference_frame = find_reference(context.scene)

  # Create Blender keyframes and markers for each sequence
  for seq in dsq.sequences:
    name = get_free_name(seq.name, scene_sequences)
    print("found seq", seq.name, "to", name)

    flags = []
    flags.append("priority {}".format(seq.priority))

    if seq.flags & Sequence.Cyclic:
      flags.append("cyclic")

    if seq.flags & Sequence.Blend:
      flags.append("blend")

    flags.append("duration {}".format(seq.duration))

    if flags:
      sequences_text.append(name + ": " + ", ".join(flags))

    nodesRotation = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(nodes, seq.rotationMatters))))
    nodesTranslation = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(nodes, seq.translationMatters))))
    nodesScale = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(nodes, seq.scaleMatters))))      

    step = 1

    for mattersIndex, ob in enumerate(nodesTranslation):
      curves: List[bpy.types.FCurve] = None
      if use_armature is not None:
        curves = arm_location_curves(use_armature, ob)
      else:
        curves = ob_location_curves(ob)

      for frameIndex in range(seq.numKeyframes):
        vec = dsq.translations[seq.baseTranslation + mattersIndex * seq.numKeyframes + frameIndex]
          
        if use_armature is not None:
          # Armature positions need adjustments because bones are animated in bone local space rather than parent space
          if ob.parent is not None:
            vec = Vector((vec.y, vec.x, -1 * vec.z))
            parent_rest_matrix = ob.bone.parent.matrix_local
          else:
            parent_rest_matrix = use_armature.matrix_local
            
          pose_bone_rest_matrix = parent_rest_matrix.inverted() @ ob.bone.matrix_local
          if frameIndex == 0:
            print(f"{vec} => {pose_bone_rest_matrix.inverted() @ vec}")
          vec = pose_bone_rest_matrix.inverted() @ vec
                      
        if seq.flags & Sequence.Blend:
          if reference_frame is None:
            return fail(operator, "Missing 'reference' marker for blend animation '{}'".format(name))
          ref_vec = Vector(evaluate_all(curves, reference_frame))
          vec = ref_vec + vec

        for curve in curves:
          curve.keyframe_points.add(1)
          key = curve.keyframe_points[-1]
          key.interpolation = "LINEAR"
          key.co = (last_frame + frameIndex * step, vec[curve.array_index])

    for mattersIndex, ob in enumerate(nodesRotation):
      curves: List[bpy.types.FCurve] = None
      if use_armature is not None:
        mode, curves = arm_rotation_curves(use_armature, ob)
      else:
        mode, curves = ob_rotation_curves(ob)

      for frameIndex in range(seq.numKeyframes):
        rot = dsq.rotations[seq.baseRotation + mattersIndex * seq.numKeyframes + frameIndex]
        
        if use_armature:
          if ob.parent is not None:
            # The quaternion data is assuming a Z-up coordinate system, but we're working with an X-up coordinate system (I know it's weird, but it works). This just transforms the data to that coordinate system.
            # Also, it only needs to happen for bones with a parent. The root bone is fine without any transformation since it's relative to the armature which is a Z-up coordinate system.
            rot = Quaternion((rot.w, rot.y, rot.x, -1 * rot.z))
            parent_rest_matrix = ob.bone.parent.matrix_local
            # This just transforms the quaternion from parent space to child space (since the data for each bone is relative to the parent of the bone but Blender expects rotations relative to the rest position of the bone.)
            pose_bone_rest_matrix = parent_rest_matrix.inverted() @ ob.bone.matrix_local
            rot = pose_bone_rest_matrix.inverted().to_quaternion() @ rot
          else:
            # Ok, we do need to do a transformation for parentless bones, but it's different since it's relative to the armature rather than another bone.
            rot = (ob.bone.matrix_local.inverted().to_quaternion() @ rot ) @ (Quaternion((math.sqrt(2) / 2, 0, 0, -math.sqrt(2) / 2))) @ Quaternion((0, 0, 1, 0))
        
        if seq.flags & Sequence.Blend:
          if reference_frame is None:
            return fail(operator, "Missing 'reference' marker for blend animation '{}'".format(name))
          ref_rot = Quaternion(evaluate_all(curves, reference_frame))
          rot = ref_rot @ rot
        if mode == 'AXIS_ANGLE':
          rot = rot.to_axis_angle()
        elif mode != 'QUATERNION':
          rot = rot.to_euler(mode)

        for curve in curves:
          curve.keyframe_points.add(1)
          key = curve.keyframe_points[-1]
          key.interpolation = "LINEAR"
          key.co = (last_frame + frameIndex * step, rot[curve.array_index])

    for mattersIndex, ob in enumerate(nodesScale):
      curves: List[bpy.types.FCurve] = None
      if use_armature is not None:
        curves = arm_scale_curves(use_armature, ob)
      else:
        curves = ob_scale_curves(ob)

      for frameIndex in range(seq.numKeyframes):
        index = seq.baseScale + mattersIndex * seq.numKeyframes + frameIndex

        if seq.flags & Sequence.UniformScale:
          s = dsq.uniform_scales[index]
          scale = s, s, s
        elif seq.flags & Sequence.AlignedScale:
          scale = dsq.aligned_scales[index]
        elif seq.flags & Sequence.ArbitraryScale:
          print("Warning: Arbitrary scale animation not implemented")
          break
        else:
          print("Warning: Invalid scale flags found in sequence")
          break

        for curve in curves:
          curve.keyframe_points.add(1)
          key = curve.keyframe_points[-1]
          key.interpolation = "LINEAR"
          key.co = (last_frame + frameIndex * step, scale[curve.array_index])

    context.scene.timeline_markers.new(name + ":start", frame=last_frame)
    context.scene.timeline_markers.new(name + ":end", frame=(last_frame + seq.numKeyframes))

    last_frame += seq.numKeyframes + 10

  if "Sequences" in bpy.data.texts:
    sequences_buf = bpy.data.texts["Sequences"]
  else:
    sequences_buf = bpy.data.texts.new("Sequences")

  if not sequences_buf.as_string():
    sequences_buf.from_string("\n".join(sequences_text))
  else:
    sequences_buf.from_string(sequences_buf.as_string() + "\n" + "\n".join(sequences_text))

  return {"FINISHED"}
