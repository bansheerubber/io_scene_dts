import bpy
import os
from bpy_extras.io_utils import unpack_list
import mathutils

from .DtsShape import DtsShape
from .DtsTypes import *
from .write_report import write_debug_report
from .util import default_materials, resolve_texture, get_rgb_colors, fail, \
    ob_location_curves, ob_scale_curves, ob_rotation_curves, ob_vis_curves, ob_rotation_data, evaluate_all

import operator
from itertools import zip_longest, count
from functools import reduce
from random import random

def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

def dedup_name(group, name):
    if name not in group:
        return name

    for suffix in count(2):
        new_name = name + "#" + str(suffix)

        if new_name not in group:
            return new_name

def import_material(color_source, dmat, filepath):
    bmat = bpy.data.materials.new(dedup_name(bpy.data.materials, dmat.name))
    bmat.use_nodes = True
    bmat.roughness = 1

    texname = resolve_texture(filepath, dmat.name)

    if texname is not None:
        try:
            teximg = bpy.data.images.load(texname)
        except:
            print("Cannot load image", texname)

        #texslot = bmat.texture_paint_slots.add()
        #texslot.use_map_alpha = True
        #tex = texslot.texture = bpy.data.textures.new(dmat.name, "IMAGE")
        #tex.image = teximg

        bsdf = bmat.node_tree.nodes["Principled BSDF"]
        tex = bmat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image = teximg
        bmat.node_tree.links.new(bsdf.inputs["Base Color"], tex.outputs["Color"])

        # Try to figure out a diffuse color for solid shading
        if teximg.size[0] <= 16 and teximg.size[1] <= 16:
            if teximg.alpha_mode != "NONE":
                pixels = grouper(teximg.pixels, 4)
            else:
                pixels = grouper(teximg.pixels, 3)

            color = pixels.__next__()

            for other in pixels:
                if other != color:
                    break
            else:
                bmat.diffuse_color = color[:3] + (1,)
    elif dmat.name.lower() in default_materials:
        bmat.diffuse_color = default_materials[dmat.name.lower()]
    else: # give it a random color
        bmat.diffuse_color = color_source.__next__()

    if dmat.flags & Material.SelfIlluminating:
        bmat.torque_props.use_shadeless = True
    if dmat.flags & Material.Translucent:
        bmat.torque_props.use_transparency = True

    if dmat.flags & Material.Additive:
        bmat.torque_props.blend_mode = "ADDITIVE"
    elif dmat.flags & Material.Subtractive:
        bmat.torque_props.blend_mode = "SUBTRACTIVE"
    else:
        bmat.torque_props.blend_mode = "NONE"

    if dmat.flags & Material.SWrap:
        bmat.torque_props.s_wrap = True
    if dmat.flags & Material.TWrap:
        bmat.torque_props.t_wraps = True
    if dmat.flags & Material.IFLMaterial:
        bmat.torque_props.use_ifl = True

    if dmat.flags & Material.NoMipMap:
        bmat.torque_props.no_mip_mapping = True
    if dmat.flags & Material.MipMapZeroBorder:
        bmat.torque_props.mip_map_zero_border = True

    # TODO: MipMapZeroBorder, IFLFrame, DetailMap, BumpMap, ReflectanceMap
    # AuxilaryMask?

    return bmat

class index_pass:
    def __getitem__(self, item):
        return item

def create_bobj(context, dmesh, materials, shape, obj):
    me = bpy.data.meshes.new("Mesh")

    faces = []
    face_mats = []
    material_indices = {}

    indices_pass = index_pass()
    for prim in dmesh.primitives:
        if prim.type & Primitive.Indexed:
            indices = dmesh.indices
        else:
            indices = indices_pass

        dmat = None

        if not (prim.type & Primitive.NoMaterial):
            dmat = shape.materials[prim.type & Primitive.MaterialMask]

            if dmat not in material_indices:
                material_indices[dmat] = len(me.materials)
                me.materials.append(materials[dmat])

        if prim.type & Primitive.Strip:
            even = True
            for i in range(prim.firstElement + 2, prim.firstElement + prim.numElements):
                if even:
                    faces.append((indices[i], indices[i - 1], indices[i - 2]))
                    face_mats.append(dmat)
                else:
                    faces.append((indices[i - 2], indices[i - 1], indices[i]))
                    face_mats.append(dmat)
                even = not even
        elif prim.type & Primitive.Fan:
            even = True
            for i in range(prim.firstElement + 2, prim.firstElement + prim.numElements):
                if even:
                    faces.append((indices[i], indices[i - 1], indices[0]))
                    face_mats.append(dmat)
                else:
                    faces.append((indices[0], indices[i - 1], indices[i]))
                    face_mats.append(dmat)
                even = not even
        else: # Default to Triangle Lists (prim.type & Primitive.Triangles)
            for i in range(prim.firstElement + 2, prim.firstElement + prim.numElements, 3):
                faces.append((indices[i], indices[i - 1], indices[i - 2]))
                face_mats.append(dmat)

    
    me.from_pydata(dmesh.verts, [], faces)
    for poly, mat_index in zip(me.polygons, face_mats):
        poly.material_index = material_indices[mat_index]

    # Create a new UV map if it doesn't exist
    if not me.uv_layers:
        me.uv_layers.new()
        
    # Assign UV coordinates to the vertices
    uv_layer = me.uv_layers.active.data
    for poly in me.polygons:
        for loop_index in poly.loop_indices:
            loop = me.loops[loop_index]
            uv_layer[loop.index].uv = (dmesh.tverts[loop.vertex_index][0], 1 - dmesh.tverts[loop.vertex_index][1])

    # gyt add: we have to create the bobj here, because we need it to do UV shit in 2.8
    bobj = bpy.data.objects.new(dedup_name(bpy.data.objects, shape.names[obj.name]), me)

    me.validate()
    me.update()

    return bobj


def file_base_name(filepath):
    return os.path.basename(filepath).rsplit(".", 1)[0]

def insert_reference(frame, shape_nodes):
    for node in shape_nodes:
        ob = node.bl_ob

        curves = ob_location_curves(ob)
        for curve in curves:
            curve.keyframe_points.add(1)
            key = curve.keyframe_points[-1]
            key.interpolation = "LINEAR"
            key.co = (frame, ob.location[curve.array_index])

        curves = ob_scale_curves(ob)
        for curve in curves:
            curve.keyframe_points.add(1)
            key = curve.keyframe_points[-1]
            key.interpolation = "LINEAR"
            key.co = (frame, ob.scale[curve.array_index])

        _, curves = ob_rotation_curves(ob)
        rot = ob_rotation_data(ob)
        for curve in curves:
            curve.keyframe_points.add(1)
            key = curve.keyframe_points[-1]
            key.interpolation = "LINEAR"
            key.co = (frame, rot[curve.array_index])

def load(operator, context, filepath,
         reference_keyframe=True,
         import_sequences=True,
         use_armature=False,
         debug_report=False):
    shape = DtsShape()

    with open(filepath, "rb") as fd:
        shape.load(fd)

    if debug_report:
        write_debug_report(filepath + ".txt", shape)
        with open(filepath + ".pass.dts", "wb") as fd:
            shape.save(fd)

    # Create a Blender material for each DTS material
    materials = {}
    color_source = get_rgb_colors()

    for dmat in shape.materials:
        materials[dmat] = import_material(color_source, dmat, filepath)

    # Now assign IFL material properties where needed
    for ifl in shape.iflmaterials:
        mat = materials[shape.materials[ifl.slot]]
        assert mat.torque_props.use_ifl == True
        mat.torque_props.ifl_name = shape.names[ifl.name]

    # First load all the nodes into armatures
    lod_by_mesh = {}

    for lod in shape.detail_levels:
        lod_by_mesh[lod.objectDetail] = lod

    node_obs = []
    node_obs_val = {}

    if use_armature:
        root_arm = bpy.data.armatures.new(file_base_name(filepath))
        root_ob = bpy.data.objects.new(root_arm.name, root_arm)
        root_ob.show_in_front = True

        context.collection.objects.link(root_ob)
        context.view_layer.objects.active = root_ob
        root_arm.display_type = "STICK" #"OCTAHEDRAL"
        
        # bpy.ops.object.mode_set(mode="EDIT")
        # edit_bones = root_arm.edit_bones
        
        # Create an empty for every node
        # node_bones = {}
        # for i, node in enumerate(shape.nodes):
        #     node_name = shape.names[i]
        #     node_index = i
        #     # bone = root_arm.edit_bones.new(shape.names[node.name])
        #     bone = root_arm.edit_bones.new(shape.names[node_index])
            
        #     node.bl_ob = bone
        #     bone["nodeIndex"] = i
            
        #     node.mat = shape.default_rotations[i].to_matrix()
        #     node.mat = Matrix.Translation(shape.default_translations[i]) * node.mat.to_4x4()
        #     # if node.parent != -1:
        #     #     node.mat = shape.nodes[node.parent].mat * node.mat
            
        #     node_head = node.mat.to_translation()
        #     node_tail = node.head + Vector((0, 0, 0.25))
        #     # node_tail = node.mat.to_translation()
        #     # node_head = node.tail - Vector((0, 0, 0.25))
            
        #     # bone.head = shape.default_translations[i]
        #     bone.head = node_head
        #     bone.tail = node_tail

        #     if node.parent != -1:
        #         bone.parent = node_bones[node.parent]
                
        #     bone.matrix = node.mat

        #     # bone.location = shape.default_translations[i]
        #     # bone.rotation_mode = "QUATERNION"
        #     # bone.rotation_quaternion = shape.default_rotations[i]
        #     # if shape.names[node.name] == "__auto_root__" and ob.rotation_quaternion.magnitude == 0:
        #     #     ob.rotation_quaternion = (1, 0, 0, 0)
            
        #     node_bones[node.name] = bone
        #     node_obs_val[node] = ob
        
        
        
        
        
        
        
        

        # Calculate armature-space matrix, head and tail for each node
        shape_nodes = {x.name: x for x in shape.nodes}
        print(len(shape.names))
        print(len(shape_nodes.keys()))
        print(shape.names)
        print(shape_nodes.keys())
        # for i, node in enumerate(shape.nodes):
        #     node.mat = shape.default_rotations[i].to_matrix()
        #     node.mat = Matrix.Translation(shape.default_translations[i]) * node.mat.to_4x4()
        #     print(f"{shape.names[node.name]}: -> {shape.names[shape.nodes[node.parent].name]}")
            
        #     if node.parent != -1:
        #         node.mat = shape.nodes[node.parent].mat * node.mat
                
            
        #     # print(f" MATRIX: {node.mat}")
        #     # print(f" CHILD: {node.firstChild}")
        #     # print(f" PARENT: {node.parent}")
        #     # node.head = node.mat.to_translation()
        #     # node.tail = node.head + Vector((0, 0, 0.25))
        #     # node.tail = node.mat.to_translation()
        #     # node.head = node.tail - Vector((0, 0, 0.25))

        bpy.ops.object.mode_set(mode="EDIT")

        edit_bone_table = []
        bone_names = []

        for i, node in enumerate(shape.nodes):
            print(f"{shape.names[node.name]}: -> {shape.names[shape.nodes[node.parent].name]}")

            bone = root_arm.edit_bones.new(shape.names[node.name])
            # bone.use_connect = True
            # bone.head = node.head
            # bone.tail = node.tail
            bone.head = (0, 0, 0)
            bone.tail = (0, 0, 0.25)

            bone.use_relative_parent = True
            if node.parent != -1:
                bone.parent = edit_bone_table[node.parent]

            # bone.matrix = node.mat
            node_quaternion = shape.default_rotations[i]
            node_rot = node_quaternion.to_matrix().to_4x4()
            node_loc = shape.default_translations[i]
            bone.transform(node_rot)
            bone.translate(node_loc)
                        
            # bone.head = node_loc
            # bone.tail = shape.default_translations[i]
            # bone.tail[0] += 0.25
            # bone.matrix = node_loc @ node_rot
            
            
            
            #apply parent locs
            # parent = node.parent
            # while parent != -1:
            #     parent_rotation = shape.default_rotations[node.parent]
            #     parent_translation = shape.default_translations[node.parent]
            #     bone.transform(parent_rotation, scale=False)
            #     bone.translate(parent_translation)
            #     parent = shape.nodes[parent].parent
            # if node.parent != -1:
            #     parent_matrix = edit_bone_table[node.parent].matrix
            #     bone.transform(parent_matrix, scale=False)
                #parent_loc = edit_bone_table[node.parent].head
                #bone.translate(parent_loc)
            # bone.translate(shape.default_translations[node.parent])
            
            bone["nodeIndex"] = i

            edit_bone_table.append(bone)
            bone_names.append(bone.name)

        bpy.ops.object.mode_set(mode="OBJECT")
    else:
        if reference_keyframe:
            reference_marker = context.scene.timeline_markers.get("reference")
            if reference_marker is None:
                reference_frame = 0
                context.scene.timeline_markers.new("reference", frame=reference_frame)
            else:
                reference_frame = reference_marker.frame
        else:
            reference_frame = None

        # Create an empty for every node
        for i, node in enumerate(shape.nodes):
            ob = bpy.data.objects.new(dedup_name(bpy.data.objects, shape.names[node.name]), None)
            node.bl_ob = ob
            ob["nodeIndex"] = i
            ob.empty_display_type = "SINGLE_ARROW"
            ob.empty_display_size = 0.5

            if node.parent != -1:
                ob.parent = node_obs[node.parent]

            ob.location = shape.default_translations[i]
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = shape.default_rotations[i]
            if shape.names[node.name] == "__auto_root__" and ob.rotation_quaternion.magnitude == 0:
                ob.rotation_quaternion = (1, 0, 0, 0)

            context.collection.objects.link(ob)
            node_obs.append(ob)
            node_obs_val[node] = ob

        if reference_keyframe:
            insert_reference(reference_frame, shape.nodes)

    # Try animation?
    if import_sequences:
        globalToolIndex = 10
        fps = context.scene.render.fps

        sequences_text = []

        for seq in shape.sequences:
            name = shape.names[seq.nameIndex]
            print("Importing sequence", name)

            flags = []
            flags.append("priority {}".format(seq.priority))

            if seq.flags & Sequence.Cyclic:
                flags.append("cyclic")

            if seq.flags & Sequence.Blend:
                flags.append("blend")

            flags.append("duration {}".format(seq.duration))

            if flags:
                sequences_text.append(name + ": " + ", ".join(flags))

            nodesRotation = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(shape.nodes, seq.rotationMatters))))
            nodesTranslation = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(shape.nodes, seq.translationMatters))))
            nodesScale = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(shape.nodes, seq.scaleMatters))))
            nodesVis = tuple(map(lambda p: p[0], filter(lambda p: p[1], zip(shape.nodes, seq.visMatters))))

            step = 1

            for mattersIndex, node in enumerate(nodesTranslation):
                ob = node_obs_val[node]
                curves = ob_location_curves(ob)

                for frameIndex in range(seq.numKeyframes):
                    vec = shape.node_translations[seq.baseTranslation + mattersIndex * seq.numKeyframes + frameIndex]
                    if seq.flags & Sequence.Blend:
                        if reference_frame is None:
                            return fail(operator, "Missing 'reference' marker for blend animation '{}'".format(name))
                        ref_vec = Vector(evaluate_all(curves, reference_frame))
                        vec = ref_vec + vec

                    for curve in curves:
                        curve.keyframe_points.add(1)
                        key = curve.keyframe_points[-1]
                        key.interpolation = "LINEAR"
                        key.co = (
                            globalToolIndex + frameIndex * step,
                            vec[curve.array_index])

            for mattersIndex, node in enumerate(nodesRotation):
                ob = node_obs_val[node]
                mode, curves = ob_rotation_curves(ob)

                for frameIndex in range(seq.numKeyframes):
                    rot = shape.node_rotations[seq.baseRotation + mattersIndex * seq.numKeyframes + frameIndex]
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
                        key.co = (
                            globalToolIndex + frameIndex * step,
                            rot[curve.array_index])

            for mattersIndex, node in enumerate(nodesScale):
                ob = node_obs_val[node]
                curves = ob_scale_curves(ob)

                for frameIndex in range(seq.numKeyframes):
                    index = seq.baseScale + mattersIndex * seq.numKeyframes + frameIndex

                    if seq.flags & Sequence.UniformScale:
                        s = shape.node_uniform_scales[index]
                        vec = (s, s, s)
                    elif seq.flags & Sequence.AlignedScale:
                        vec = shape.node_aligned_scales[index]
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
                        key.co = (
                            globalToolIndex + frameIndex * step,
                            vec[curve.array_index])

            for mattersIndex, node in enumerate(nodesVis):
                ob = node_obs_val[node]
                curves = ob_vis_curves(ob)

                # if not hasattr(ob, 'vis'):
                #    ob['vis'] = shape.objectstates[seq.baseObjectState].vis

                ob.torque_vis_props.vis_value = shape.objectstates[seq.baseObjectState].vis

                for frameIndex in range(seq.numKeyframes):
                    vis = shape.objectstates[seq.baseObjectState + mattersIndex * seq.numKeyframes + frameIndex].vis

                    for curve in curves:
                        curve.keyframe_points.add(1)
                        key = curve.keyframe_points[-1]
                        key.interpolation = "LINEAR"
                        key.co = (
                            globalToolIndex + frameIndex * step,
                            vis)

                        print(vis)

            # Insert a reference frame immediately before the animation
            # insert_reference(globalToolIndex - 2, shape.nodes)

            context.scene.timeline_markers.new(name + ":start", frame=globalToolIndex)
            context.scene.timeline_markers.new(name + ":end", frame=(globalToolIndex + seq.numKeyframes * step - 1))
            globalToolIndex += seq.numKeyframes * step + 30

        if "Sequences" in bpy.data.texts:
            sequences_buf = bpy.data.texts["Sequences"]
        else:
            sequences_buf = bpy.data.texts.new("Sequences")

        sequences_buf.from_string("\n".join(sequences_text))

    # Then put objects in the armatures
    for obj in shape.objects:
        for meshIndex in range(obj.numMeshes):
            mesh = shape.meshes[obj.firstMesh + meshIndex]
            mtype = mesh.type

            if mtype == Mesh.NullType:
                continue

            if mtype != Mesh.StandardType and mtype != Mesh.SkinType:
                print('Warning: Mesh #{} of object {} is of unsupported type {}, ignoring'.format(
                    meshIndex + 1, mtype, shape.names[obj.name]))
                continue

            bobj = create_bobj(context, mesh, materials, shape, obj)
            context.collection.objects.link(bobj)

            add_vertex_groups(mesh, bobj, shape)

            if obj.node != -1:
                if use_armature:
                    bobj.parent = root_ob
                    bobj.parent_bone = bone_names[obj.node]
                    bobj.parent_type = "BONE"
                    bobj.matrix_world = shape.nodes[obj.node].mat

                    if mtype == Mesh.SkinType:
                        modifier = bobj.modifiers.new('Armature', 'ARMATURE')
                        modifier.object = root_ob
                else:
                    bobj.parent = node_obs[obj.node]

            lod_name = shape.names[lod_by_mesh[meshIndex].name]

            if lod_name not in bpy.data.collections:
                bpy.data.collections.new(lod_name)

            bpy.data.collections[lod_name].objects.link(bobj)

    # Import a bounds mesh
    me = bpy.data.meshes.new("Mesh")
    me.vertices.add(8)
    me.vertices[0].co = (shape.bounds.min.x, shape.bounds.min.y, shape.bounds.min.z)
    me.vertices[1].co = (shape.bounds.max.x, shape.bounds.min.y, shape.bounds.min.z)
    me.vertices[2].co = (shape.bounds.max.x, shape.bounds.max.y, shape.bounds.min.z)
    me.vertices[3].co = (shape.bounds.min.x, shape.bounds.max.y, shape.bounds.min.z)
    me.vertices[4].co = (shape.bounds.min.x, shape.bounds.min.y, shape.bounds.max.z)
    me.vertices[5].co = (shape.bounds.max.x, shape.bounds.min.y, shape.bounds.max.z)
    me.vertices[6].co = (shape.bounds.max.x, shape.bounds.max.y, shape.bounds.max.z)
    me.vertices[7].co = (shape.bounds.min.x, shape.bounds.max.y, shape.bounds.max.z)
    me.validate()
    me.update()
    ob = bpy.data.objects.new("bounds", me)
    ob.display_type = "BOUNDS"
    context.collection.objects.link(ob)

    return {"FINISHED"}

def add_vertex_groups(mesh, ob, shape):
    for node, initial_transform in mesh.bones:
        # TODO: Handle initial_transform
        if node != -1:
            ob.vertex_groups.new(name=shape.names[shape.nodes[node].name])

    for vertex, bone, weight in mesh.influences:
        ob.vertex_groups[bone].add((vertex,), weight, 'REPLACE')
