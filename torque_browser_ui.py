import bpy
import os
from . import import_dts

class AssetProperty(bpy.types.PropertyGroup):
    thumbnail: bpy.props.StringProperty()
    model: bpy.props.StringProperty()
    asset_name: bpy.props.StringProperty()
    thumbnail_id: bpy.props.IntProperty()

class TorqueBrowserProperties(bpy.types.PropertyGroup):
    asset_dir: bpy.props.StringProperty()
    assets: bpy.props.CollectionProperty(type=AssetProperty)
    active_asset: bpy.props.IntProperty()
    currently_loading: bpy.props.BoolProperty(default=True)
    reference_keyframe: bpy.props.BoolProperty(name="Use Reference Keyframe", description="Set a keyframe with the reference pose for blend animations", default=True)
    import_sequences: bpy.props.BoolProperty(name="Import Sequences", description="Automatically add keyframes for embedded sequences", default=True)
    use_armature: bpy.props.BoolProperty(name="Beta: Skeleton as armature", description="Import bones into an armature instead of empties. Does not work with 'Import sequences", default=False)
    
    
class ADFileSelector(bpy.types.Operator):
    bl_idname = "torque_browser.asset_directory_selector"
    bl_label = "Set Asset Folder"

    filename_ext = ""
    filepath: bpy.props.StringProperty(subtype="DIR_PATH")

    def execute(self, context):
        fdir = self.properties.filepath
        context.scene.torque_browser_addon.asset_dir = fdir
        return{'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}
    
class LoadAssetsOperator(bpy.types.Operator):
    bl_idname = "torque_browser.load_assets_button"
    bl_label = "Load Assets"

    def execute(self, context):
        # Get UI icons
        icon_items = bpy.types.UILayout.bl_rna.functions["prop"].parameters["icon"].enum_items
        missing_icon_default_id = icon_items["QUESTION"].value
        
        # Tell UI assets are loading
        context.scene.torque_browser_addon.currently_loading = True
        
        # Clean up old data
        if bpy.types.Scene.torque_icon_previews is not None:
            bpy.types.Scene.torque_icon_previews.clear()
            bpy.utils.previews.remove(bpy.types.Scene.torque_icon_previews)
            bpy.types.Scene.torque_icon_previews = None
          
        if len(context.scene.torque_browser_addon.assets) != 0:
            context.scene.torque_browser_addon.assets.clear()
            
        # Create icon previews collection
        preview_icons = bpy.utils.previews.new()
                    
        # Logic for getting assets
        asset_dir = context.scene.torque_browser_addon.asset_dir
        assets = {}
        
        images = []
        models = []
        for path, subdirs, files in os.walk(asset_dir):
            for name in files:
                full_path = os.path.join(path, name)
                file_name, file_extension = os.path.splitext(os.path.basename(name))
                
                if file_extension == ".dts":
                    # Model file
                    models.append((file_name, full_path))
                    
                elif file_extension == ".jpg" or file_extension == ".png":
                    # Image file
                    images.append((file_name, full_path))
                                
        for file_name, full_path in models:
            asset_name = file_name
            
            while assets.get(asset_name) is not None:
                print(f"Model \"{asset_name}\" ({full_path}) already exists ({assets[asset_name]['model']}): Renaming as: \"{asset_name}_alt\"")
                asset_name = f"{asset_name}_alt"
            
            assets[asset_name] = {}
            assets[asset_name]["model"] = full_path
                    
        for file_name, full_path in images:
            asset_name = file_name
            
            if file_name[-2:] == "_i":
                # Thumbnail
                asset_name = file_name[:-2]
            else:
                # Not thumbnail
                asset_name = file_name
                continue
            
            thumbnail_id = None
            
            for modifier in {"", "_f", "_m"}:
                mod_asset_name = f"{asset_name}{modifier}"
                while assets.get(mod_asset_name) is not None:
                    if assets[mod_asset_name].get("thumbnail") is not None:
                        print(f"Thumbnail \"{asset_name}\" ({full_path}) already exist for \"{mod_asset_name}\": {assets[mod_asset_name]['thumbnail']}")
                    else:
                        assets[mod_asset_name]["thumbnail"] = full_path
                        
                        if thumbnail_id is None:
                            # import thumbnail
                            icon_path = bpy.path.abspath(full_path)
                            preview_icons.load(f"{asset_name}_i", icon_path, 'IMAGE')
                            
                            thumbnail_id = preview_icons[f"{asset_name}_i"].icon_id
                        
                        assets[mod_asset_name]["thumbnail_id"] = thumbnail_id 
                    
                    mod_asset_name = f"{mod_asset_name}_alt"
                    
        asset_prop = context.scene.torque_browser_addon.assets
        for asset_name, asset in assets.items():
            if asset.get("model") is None:
                print(f"Asset {asset_name} has no model")
                continue
                
            new_asset = asset_prop.add()
            new_asset.thumbnail = asset.get("thumbnail", "")
            new_asset.thumbnail_id = asset.get("thumbnail_id", missing_icon_default_id)
            new_asset.model = asset.get("model", "")
            new_asset.asset_name = asset_name
            
        bpy.types.Scene.torque_icon_previews = preview_icons
        
        context.scene.torque_browser_addon.currently_loading = False
                
        self.report({'INFO'}, "Assets retrieved successfully")
        return {'FINISHED'}
    

class ImportAssetOperator(bpy.types.Operator):
    bl_idname = "torque_browser.import_asset_button"
    bl_label = "Import Asset"

    def execute(self, context):
        active_asset = context.scene.torque_browser_addon.active_asset
        filepath = context.scene.torque_browser_addon.assets[active_asset].model
        reference_keyframe = context.scene.torque_browser_addon.reference_keyframe
        import_sequences = context.scene.torque_browser_addon.import_sequences
        use_armature = context.scene.torque_browser_addon.use_armature
        
        import_dts.load(self, context, filepath, reference_keyframe=reference_keyframe, import_sequences=import_sequences, use_armature=use_armature)
        
        self.report({'INFO'}, "Assets retrieved successfully")
        return {'FINISHED'}

    
# class IconPanel(bpy.types.Panel):
#     """Creates a Panel width all possible icons"""
#     bl_label = "Icons"
#     bl_idname = "icons_panel"
#     bl_space_type = 'PROPERTIES'
#     bl_region_type = 'WINDOW'
#     bl_context = "object"

#     def draw(self, context):
#         icons = ['NONE', 'QUESTION', 'ERROR', 'CANCEL', 'TRIA_RIGHT', 'TRIA_DOWN', 'TRIA_LEFT', 'TRIA_UP', 'ARROW_LEFTRIGHT', 'PLUS', 'DISCLOSURE_TRI_RIGHT', 'DISCLOSURE_TRI_DOWN', 'RADIOBUT_OFF', 'RADIOBUT_ON', 'MENU_PANEL', 'BLENDER', 'GRIP', 'DOT', 'COLLAPSEMENU', 'X', 'DUPLICATE', 'TRASH', 'COLLECTION_NEW', 'OPTIONS', 'NODE', 'NODE_SEL', 'WINDOW', 'WORKSPACE', 'RIGHTARROW_THIN', 'BORDERMOVE', 'VIEWZOOM', 'ADD', 'REMOVE', 'PANEL_CLOSE', 'COPY_ID', 'EYEDROPPER', 'CHECKMARK', 'AUTO', 'CHECKBOX_DEHLT', 'CHECKBOX_HLT', 'UNLOCKED', 'LOCKED', 'UNPINNED', 'PINNED', 'SCREEN_BACK', 'RIGHTARROW', 'DOWNARROW_HLT', 'FCURVE_SNAPSHOT', 'OBJECT_HIDDEN', 'TOPBAR', 'STATUSBAR', 'PLUGIN', 'HELP', 'GHOST_ENABLED', 'COLOR', 'UNLINKED', 'LINKED', 'HAND', 'ZOOM_ALL', 'ZOOM_SELECTED', 'ZOOM_PREVIOUS', 'ZOOM_IN', 'ZOOM_OUT', 'DRIVER_DISTANCE', 'DRIVER_ROTATIONAL_DIFFERENCE', 'DRIVER_TRANSFORM', 'FREEZE', 'STYLUS_PRESSURE', 'GHOST_DISABLED', 'FILE_NEW', 'FILE_TICK', 'QUIT', 'URL', 'RECOVER_LAST', 'THREE_DOTS', 'FULLSCREEN_ENTER', 'FULLSCREEN_EXIT', 'BRUSHES_ALL', 'LIGHT', 'MATERIAL', 'TEXTURE', 'ANIM', 'WORLD', 'SCENE', 'OUTPUT', 'SCRIPT', 'PARTICLES', 'PHYSICS', 'SPEAKER', 'TOOL_SETTINGS', 'SHADERFX', 'MODIFIER', 'BLANK1', 'FAKE_USER_OFF', 'FAKE_USER_ON', 'VIEW3D', 'GRAPH', 'OUTLINER', 'PROPERTIES', 'FILEBROWSER', 'IMAGE', 'INFO', 'SEQUENCE', 'TEXT', 'SPREADSHEET', 'SOUND', 'ACTION', 'NLA', 'PREFERENCES', 'TIME', 'NODETREE', 'CONSOLE', 'TRACKER', 'ASSET_MANAGER', 'NODE_COMPOSITING', 'NODE_TEXTURE', 'NODE_MATERIAL', 'UV', 'OBJECT_DATAMODE', 'EDITMODE_HLT', 'UV_DATA', 'VPAINT_HLT', 'TPAINT_HLT', 'WPAINT_HLT', 'SCULPTMODE_HLT', 'POSE_HLT', 'PARTICLEMODE', 'TRACKING', 'TRACKING_BACKWARDS', 'TRACKING_FORWARDS', 'TRACKING_BACKWARDS_SINGLE', 'TRACKING_FORWARDS_SINGLE', 'TRACKING_CLEAR_BACKWARDS', 'TRACKING_CLEAR_FORWARDS', 'TRACKING_REFINE_BACKWARDS', 'TRACKING_REFINE_FORWARDS', 'SCENE_DATA', 'RENDERLAYERS', 'WORLD_DATA', 'OBJECT_DATA', 'MESH_DATA', 'CURVE_DATA', 'META_DATA', 'LATTICE_DATA', 'LIGHT_DATA', 'MATERIAL_DATA', 'TEXTURE_DATA', 'ANIM_DATA', 'CAMERA_DATA', 'PARTICLE_DATA', 'LIBRARY_DATA_DIRECT', 'GROUP', 'ARMATURE_DATA', 'COMMUNITY', 'BONE_DATA', 'CONSTRAINT', 'SHAPEKEY_DATA', 'CONSTRAINT_BONE', 'CAMERA_STEREO', 'PACKAGE', 'UGLYPACKAGE', 'EXPERIMENTAL', 'BRUSH_DATA', 'IMAGE_DATA', 'FILE', 'FCURVE', 'FONT_DATA', 'RENDER_RESULT', 'SURFACE_DATA', 'EMPTY_DATA', 'PRESET', 'RENDER_ANIMATION', 'RENDER_STILL', 'LIBRARY_DATA_BROKEN', 'BOIDS', 'STRANDS', 'LIBRARY_DATA_INDIRECT', 'GREASEPENCIL', 'LINE_DATA', 'LIBRARY_DATA_OVERRIDE', 'GROUP_BONE', 'GROUP_VERTEX', 'GROUP_VCOL', 'GROUP_UVS', 'FACE_MAPS', 'RNA', 'RNA_ADD', 'MOUSE_LMB', 'MOUSE_MMB', 'MOUSE_RMB', 'MOUSE_MOVE', 'MOUSE_LMB_DRAG', 'MOUSE_MMB_DRAG', 'MOUSE_RMB_DRAG', 'MEMORY', 'PRESET_NEW', 'DECORATE', 'DECORATE_KEYFRAME', 'DECORATE_ANIMATE', 'DECORATE_DRIVER', 'DECORATE_LINKED', 'DECORATE_LIBRARY_OVERRIDE', 'DECORATE_UNLOCKED', 'DECORATE_LOCKED', 'DECORATE_OVERRIDE', 'FUND', 'TRACKER_DATA', 'HEART', 'ORPHAN_DATA', 'USER', 'SYSTEM', 'SETTINGS', 'OUTLINER_OB_EMPTY', 'OUTLINER_OB_MESH', 'OUTLINER_OB_CURVE', 'OUTLINER_OB_LATTICE', 'OUTLINER_OB_META', 'OUTLINER_OB_LIGHT', 'OUTLINER_OB_CAMERA', 'OUTLINER_OB_ARMATURE', 'OUTLINER_OB_FONT', 'OUTLINER_OB_SURFACE', 'OUTLINER_OB_SPEAKER', 'OUTLINER_OB_FORCE_FIELD', 'OUTLINER_OB_GROUP_INSTANCE', 'OUTLINER_OB_GREASEPENCIL', 'OUTLINER_OB_LIGHTPROBE', 'OUTLINER_OB_IMAGE', 'OUTLINER_COLLECTION', 'RESTRICT_COLOR_OFF', 'RESTRICT_COLOR_ON', 'HIDE_ON', 'HIDE_OFF', 'RESTRICT_SELECT_ON', 'RESTRICT_SELECT_OFF', 'RESTRICT_RENDER_ON', 'RESTRICT_RENDER_OFF', 'RESTRICT_INSTANCED_OFF', 'OUTLINER_DATA_EMPTY', 'OUTLINER_DATA_MESH', 'OUTLINER_DATA_CURVE', 'OUTLINER_DATA_LATTICE', 'OUTLINER_DATA_META', 'OUTLINER_DATA_LIGHT', 'OUTLINER_DATA_CAMERA', 'OUTLINER_DATA_ARMATURE', 'OUTLINER_DATA_FONT', 'OUTLINER_DATA_SURFACE', 'OUTLINER_DATA_SPEAKER', 'OUTLINER_DATA_LIGHTPROBE', 'OUTLINER_DATA_GP_LAYER', 'OUTLINER_DATA_GREASEPENCIL', 'GP_SELECT_POINTS', 'GP_SELECT_STROKES', 'GP_MULTIFRAME_EDITING', 'GP_ONLY_SELECTED', 'GP_SELECT_BETWEEN_STROKES', 'MODIFIER_OFF', 'MODIFIER_ON', 'ONIONSKIN_OFF', 'ONIONSKIN_ON', 'RESTRICT_VIEW_ON', 'RESTRICT_VIEW_OFF', 'RESTRICT_INSTANCED_ON', 'MESH_PLANE', 'MESH_CUBE', 'MESH_CIRCLE', 'MESH_UVSPHERE', 'MESH_ICOSPHERE', 'MESH_GRID', 'MESH_MONKEY', 'MESH_CYLINDER', 'MESH_TORUS', 'MESH_CONE', 'MESH_CAPSULE', 'EMPTY_SINGLE_ARROW', 'LIGHT_POINT', 'LIGHT_SUN', 'LIGHT_SPOT', 'LIGHT_HEMI', 'LIGHT_AREA', 'CUBE', 'SPHERE', 'CONE', 'META_PLANE', 'META_CUBE', 'META_BALL', 'META_ELLIPSOID', 'META_CAPSULE', 'SURFACE_NCURVE', 'SURFACE_NCIRCLE', 'SURFACE_NSURFACE', 'SURFACE_NCYLINDER', 'SURFACE_NSPHERE', 'SURFACE_NTORUS', 'EMPTY_AXIS', 'STROKE', 'EMPTY_ARROWS', 'CURVE_BEZCURVE', 'CURVE_BEZCIRCLE', 'CURVE_NCURVE', 'CURVE_NCIRCLE', 'CURVE_PATH', 'COLOR_RED', 'COLOR_GREEN', 'COLOR_BLUE', 'TRIA_RIGHT_BAR', 'TRIA_DOWN_BAR', 'TRIA_LEFT_BAR', 'TRIA_UP_BAR', 'FORCE_FORCE', 'FORCE_WIND', 'FORCE_VORTEX', 'FORCE_MAGNETIC', 'FORCE_HARMONIC', 'FORCE_CHARGE', 'FORCE_LENNARDJONES', 'FORCE_TEXTURE', 'FORCE_CURVE', 'FORCE_BOID', 'FORCE_TURBULENCE', 'FORCE_DRAG', 'FORCE_FLUIDFLOW', 'RIGID_BODY', 'RIGID_BODY_CONSTRAINT', 'IMAGE_PLANE', 'IMAGE_BACKGROUND', 'IMAGE_REFERENCE', 'NODE_INSERT_ON', 'NODE_INSERT_OFF', 'NODE_TOP', 'NODE_SIDE', 'NODE_CORNER', 'ANCHOR_TOP', 'ANCHOR_BOTTOM', 'ANCHOR_LEFT', 'ANCHOR_RIGHT', 'ANCHOR_CENTER', 'SELECT_SET', 'SELECT_EXTEND', 'SELECT_SUBTRACT', 'SELECT_INTERSECT', 'SELECT_DIFFERENCE', 'ALIGN_LEFT', 'ALIGN_CENTER', 'ALIGN_RIGHT', 'ALIGN_JUSTIFY', 'ALIGN_FLUSH', 'ALIGN_TOP', 'ALIGN_MIDDLE', 'ALIGN_BOTTOM', 'BOLD', 'ITALIC', 'UNDERLINE', 'SMALL_CAPS', 'CON_ACTION', 'MOD_LENGTH', 'MOD_DASH', 'MOD_LINEART', 'HOLDOUT_OFF', 'HOLDOUT_ON', 'INDIRECT_ONLY_OFF', 'INDIRECT_ONLY_ON', 'CON_CAMERASOLVER', 'CON_FOLLOWTRACK', 'CON_OBJECTSOLVER', 'CON_LOCLIKE', 'CON_ROTLIKE', 'CON_SIZELIKE', 'CON_TRANSLIKE', 'CON_DISTLIMIT', 'CON_LOCLIMIT', 'CON_ROTLIMIT', 'CON_SIZELIMIT', 'CON_SAMEVOL', 'CON_TRANSFORM', 'CON_TRANSFORM_CACHE', 'CON_CLAMPTO', 'CON_KINEMATIC', 'CON_LOCKTRACK', 'CON_SPLINEIK', 'CON_STRETCHTO', 'CON_TRACKTO', 'CON_ARMATURE', 'CON_CHILDOF', 'CON_FLOOR', 'CON_FOLLOWPATH', 'CON_PIVOT', 'CON_SHRINKWRAP', 'MODIFIER_DATA', 'MOD_WAVE', 'MOD_BUILD', 'MOD_DECIM', 'MOD_MIRROR', 'MOD_SOFT', 'MOD_SUBSURF', 'HOOK', 'MOD_PHYSICS', 'MOD_PARTICLES', 'MOD_BOOLEAN', 'MOD_EDGESPLIT', 'MOD_ARRAY', 'MOD_UVPROJECT', 'MOD_DISPLACE', 'MOD_CURVE', 'MOD_LATTICE', 'MOD_TINT', 'MOD_ARMATURE', 'MOD_SHRINKWRAP', 'MOD_CAST', 'MOD_MESHDEFORM', 'MOD_BEVEL', 'MOD_SMOOTH', 'MOD_SIMPLEDEFORM', 'MOD_MASK', 'MOD_CLOTH', 'MOD_EXPLODE', 'MOD_FLUIDSIM', 'MOD_MULTIRES', 'MOD_FLUID', 'MOD_SOLIDIFY', 'MOD_SCREW', 'MOD_VERTEX_WEIGHT', 'MOD_DYNAMICPAINT', 'MOD_REMESH', 'MOD_OCEAN', 'MOD_WARP', 'MOD_SKIN', 'MOD_TRIANGULATE', 'MOD_WIREFRAME', 'MOD_DATA_TRANSFER', 'MOD_NORMALEDIT', 'MOD_PARTICLE_INSTANCE', 'MOD_HUE_SATURATION', 'MOD_NOISE', 'MOD_OFFSET', 'MOD_SIMPLIFY', 'MOD_THICKNESS', 'MOD_INSTANCE', 'MOD_TIME', 'MOD_OPACITY', 'REC', 'PLAY', 'FF', 'REW', 'PAUSE', 'PREV_KEYFRAME', 'NEXT_KEYFRAME', 'PLAY_SOUND', 'PLAY_REVERSE', 'PREVIEW_RANGE', 'ACTION_TWEAK', 'PMARKER_ACT', 'PMARKER_SEL', 'PMARKER', 'MARKER_HLT', 'MARKER', 'KEYFRAME_HLT', 'KEYFRAME', 'KEYINGSET', 'KEY_DEHLT', 'KEY_HLT', 'MUTE_IPO_OFF', 'MUTE_IPO_ON', 'DRIVER', 'SOLO_OFF', 'SOLO_ON', 'FRAME_PREV', 'FRAME_NEXT', 'NLA_PUSHDOWN', 'IPO_CONSTANT', 'IPO_LINEAR', 'IPO_BEZIER', 'IPO_SINE', 'IPO_QUAD', 'IPO_CUBIC', 'IPO_QUART', 'IPO_QUINT', 'IPO_EXPO', 'IPO_CIRC', 'IPO_BOUNCE', 'IPO_ELASTIC', 'IPO_BACK', 'IPO_EASE_IN', 'IPO_EASE_OUT', 'IPO_EASE_IN_OUT', 'NORMALIZE_FCURVES', 'VERTEXSEL', 'EDGESEL', 'FACESEL', 'CURSOR', 'PIVOT_BOUNDBOX', 'PIVOT_CURSOR', 'PIVOT_INDIVIDUAL', 'PIVOT_MEDIAN', 'PIVOT_ACTIVE', 'CENTER_ONLY', 'ROOTCURVE', 'SMOOTHCURVE', 'SPHERECURVE', 'INVERSESQUARECURVE', 'SHARPCURVE', 'LINCURVE', 'NOCURVE', 'RNDCURVE', 'PROP_OFF', 'PROP_ON', 'PROP_CON', 'PROP_PROJECTED', 'PARTICLE_POINT', 'PARTICLE_TIP', 'PARTICLE_PATH', 'SNAP_FACE_CENTER', 'SNAP_PERPENDICULAR', 'SNAP_MIDPOINT', 'SNAP_OFF', 'SNAP_ON', 'SNAP_NORMAL', 'SNAP_GRID', 'SNAP_VERTEX', 'SNAP_EDGE', 'SNAP_FACE', 'SNAP_VOLUME', 'SNAP_INCREMENT', 'STICKY_UVS_LOC', 'STICKY_UVS_DISABLE', 'STICKY_UVS_VERT', 'CLIPUV_DEHLT', 'CLIPUV_HLT', 'SNAP_PEEL_OBJECT', 'GRID', 'OBJECT_ORIGIN', 'ORIENTATION_GLOBAL', 'ORIENTATION_GIMBAL', 'ORIENTATION_LOCAL', 'ORIENTATION_NORMAL', 'ORIENTATION_VIEW', 'COPYDOWN', 'PASTEDOWN', 'PASTEFLIPUP', 'PASTEFLIPDOWN', 'VIS_SEL_11', 'VIS_SEL_10', 'VIS_SEL_01', 'VIS_SEL_00', 'AUTOMERGE_OFF', 'AUTOMERGE_ON', 'UV_VERTEXSEL', 'UV_EDGESEL', 'UV_FACESEL', 'UV_ISLANDSEL', 'UV_SYNC_SELECT', 'GP_CAPS_FLAT', 'GP_CAPS_ROUND', 'FIXED_SIZE', 'TRANSFORM_ORIGINS', 'GIZMO', 'ORIENTATION_CURSOR', 'NORMALS_VERTEX', 'NORMALS_FACE', 'NORMALS_VERTEX_FACE', 'SHADING_BBOX', 'SHADING_WIRE', 'SHADING_SOLID', 'SHADING_RENDERED', 'SHADING_TEXTURE', 'OVERLAY', 'XRAY', 'LOCKVIEW_OFF', 'LOCKVIEW_ON', 'AXIS_SIDE', 'AXIS_FRONT', 'AXIS_TOP', 'LAYER_USED', 'LAYER_ACTIVE', 'OUTLINER_OB_POINTCLOUD', 'OUTLINER_DATA_POINTCLOUD', 'POINTCLOUD_DATA', 'OUTLINER_OB_VOLUME', 'OUTLINER_DATA_VOLUME', 'VOLUME_DATA', 'CURRENT_FILE', 'HOME', 'DOCUMENTS', 'TEMP', 'SORTALPHA', 'SORTBYEXT', 'SORTTIME', 'SORTSIZE', 'SHORTDISPLAY', 'LONGDISPLAY', 'IMGDISPLAY', 'BOOKMARKS', 'FONTPREVIEW', 'FILTER', 'NEWFOLDER', 'FOLDER_REDIRECT', 'FILE_PARENT', 'FILE_REFRESH', 'FILE_FOLDER', 'FILE_BLANK', 'FILE_BLEND', 'FILE_IMAGE', 'FILE_MOVIE', 'FILE_SCRIPT', 'FILE_SOUND', 'FILE_FONT', 'FILE_TEXT', 'SORT_DESC', 'SORT_ASC', 'LINK_BLEND', 'APPEND_BLEND', 'IMPORT', 'EXPORT', 'LOOP_BACK', 'LOOP_FORWARDS', 'BACK', 'FORWARD', 'FILE_ARCHIVE', 'FILE_CACHE', 'FILE_VOLUME', 'FILE_3D', 'FILE_HIDDEN', 'FILE_BACKUP', 'DISK_DRIVE', 'MATPLANE', 'MATSPHERE', 'MATCUBE', 'MONKEY', 'ALIASED', 'ANTIALIASED', 'MAT_SPHERE_SKY', 'MATSHADERBALL', 'MATCLOTH', 'MATFLUID', 'WORDWRAP_OFF', 'WORDWRAP_ON', 'SYNTAX_OFF', 'SYNTAX_ON', 'LINENUMBERS_OFF', 'LINENUMBERS_ON', 'SCRIPTPLUGINS', 'DISC', 'DESKTOP', 'EXTERNAL_DRIVE', 'NETWORK_DRIVE', 'SEQ_SEQUENCER', 'SEQ_PREVIEW', 'SEQ_LUMA_WAVEFORM', 'SEQ_CHROMA_SCOPE', 'SEQ_HISTOGRAM', 'SEQ_SPLITVIEW', 'SEQ_STRIP_META', 'SEQ_STRIP_DUPLICATE', 'IMAGE_RGB', 'IMAGE_RGB_ALPHA', 'IMAGE_ALPHA', 'IMAGE_ZDEPTH', 'HANDLE_AUTOCLAMPED', 'HANDLE_AUTO', 'HANDLE_ALIGNED', 'HANDLE_VECTOR', 'HANDLE_FREE', 'VIEW_PERSPECTIVE', 'VIEW_ORTHO', 'VIEW_CAMERA', 'VIEW_PAN', 'VIEW_ZOOM', 'BRUSH_BLOB', 'BRUSH_BLUR', 'BRUSH_CLAY', 'BRUSH_CLAY_STRIPS', 'BRUSH_CLONE', 'BRUSH_CREASE', 'BRUSH_FILL', 'BRUSH_FLATTEN', 'BRUSH_GRAB', 'BRUSH_INFLATE', 'BRUSH_LAYER', 'BRUSH_MASK', 'BRUSH_MIX', 'BRUSH_NUDGE', 'BRUSH_PINCH', 'BRUSH_SCRAPE', 'BRUSH_SCULPT_DRAW', 'BRUSH_SMEAR', 'BRUSH_SMOOTH', 'BRUSH_SNAKE_HOOK', 'BRUSH_SOFTEN', 'BRUSH_TEXDRAW', 'BRUSH_TEXFILL', 'BRUSH_TEXMASK', 'BRUSH_THUMB', 'BRUSH_ROTATE', 'GPBRUSH_SMOOTH', 'GPBRUSH_THICKNESS', 'GPBRUSH_STRENGTH', 'GPBRUSH_GRAB', 'GPBRUSH_PUSH', 'GPBRUSH_TWIST', 'GPBRUSH_PINCH', 'GPBRUSH_RANDOMIZE', 'GPBRUSH_CLONE', 'GPBRUSH_WEIGHT', 'GPBRUSH_PENCIL', 'GPBRUSH_PEN', 'GPBRUSH_INK', 'GPBRUSH_INKNOISE', 'GPBRUSH_BLOCK', 'GPBRUSH_MARKER', 'GPBRUSH_FILL', 'GPBRUSH_AIRBRUSH', 'GPBRUSH_CHISEL', 'GPBRUSH_ERASE_SOFT', 'GPBRUSH_ERASE_HARD', 'GPBRUSH_ERASE_STROKE', 'KEYTYPE_KEYFRAME_VEC', 'KEYTYPE_BREAKDOWN_VEC', 'KEYTYPE_EXTREME_VEC', 'KEYTYPE_JITTER_VEC', 'KEYTYPE_MOVING_HOLD_VEC', 'HANDLETYPE_FREE_VEC', 'HANDLETYPE_ALIGNED_VEC', 'HANDLETYPE_VECTOR_VEC', 'HANDLETYPE_AUTO_VEC', 'HANDLETYPE_AUTO_CLAMP_VEC', 'COLORSET_01_VEC', 'COLORSET_02_VEC', 'COLORSET_03_VEC', 'COLORSET_04_VEC', 'COLORSET_05_VEC', 'COLORSET_06_VEC', 'COLORSET_07_VEC', 'COLORSET_08_VEC', 'COLORSET_09_VEC', 'COLORSET_10_VEC', 'COLORSET_11_VEC', 'COLORSET_12_VEC', 'COLORSET_13_VEC', 'COLORSET_14_VEC', 'COLORSET_15_VEC', 'COLORSET_16_VEC', 'COLORSET_17_VEC', 'COLORSET_18_VEC', 'COLORSET_19_VEC', 'COLORSET_20_VEC', 'COLLECTION_COLOR_01', 'COLLECTION_COLOR_02', 'COLLECTION_COLOR_03', 'COLLECTION_COLOR_04', 'COLLECTION_COLOR_05', 'COLLECTION_COLOR_06', 'COLLECTION_COLOR_07', 'COLLECTION_COLOR_08', 'SEQUENCE_COLOR_01', 'SEQUENCE_COLOR_02', 'SEQUENCE_COLOR_03', 'SEQUENCE_COLOR_04', 'SEQUENCE_COLOR_05', 'SEQUENCE_COLOR_06', 'SEQUENCE_COLOR_07', 'SEQUENCE_COLOR_08', 'SEQUENCE_COLOR_09', 'EVENT_A', 'EVENT_B', 'EVENT_C', 'EVENT_D', 'EVENT_E', 'EVENT_F', 'EVENT_G', 'EVENT_H', 'EVENT_I', 'EVENT_J', 'EVENT_K', 'EVENT_L', 'EVENT_M', 'EVENT_N', 'EVENT_O', 'EVENT_P', 'EVENT_Q', 'EVENT_R', 'EVENT_S', 'EVENT_T', 'EVENT_U', 'EVENT_V', 'EVENT_W', 'EVENT_X', 'EVENT_Y', 'EVENT_Z', 'EVENT_SHIFT', 'EVENT_CTRL', 'EVENT_ALT', 'EVENT_OS', 'EVENT_F1', 'EVENT_F2', 'EVENT_F3', 'EVENT_F4', 'EVENT_F5', 'EVENT_F6', 'EVENT_F7', 'EVENT_F8', 'EVENT_F9', 'EVENT_F10', 'EVENT_F11', 'EVENT_F12', 'EVENT_ESC', 'EVENT_TAB', 'EVENT_PAGEUP', 'EVENT_PAGEDOWN', 'EVENT_RETURN', 'EVENT_SPACEKEY']
#         for i in icons:
#             row = self.layout.row()
#             row.label(text=i, icon=i)

class TORQUE_ASSET_UL_list(bpy.types.UIList):
    # The draw_item function is called for each item of the collection that is visible in the list.
    #   data is the RNA object containing the collection,
    #   item is the current drawn item of the collection,
    #   icon is the "computed" icon for the item (as an integer, because some objects like materials or textures
    #   have custom icons ID, which are not available as enum items).
    #   active_data is the RNA object containing the active property for the collection (i.e. integer pointing to the
    #   active item of the collection).
    #   active_propname is the name of the active property (use 'getattr(active_data, active_propname)').
    #   index is index of the current item in the collection.
    #   flt_flag is the result of the filtering process for this item.
    #   Note: as index and flt_flag are optional arguments, you do not have to use/declare them here if you don't
    #         need them.
    
    ui_loaded: bpy.props.BoolProperty(name="List UI Loaded", default=False, description="Whether UI has been loaded")
    
    def __init__(self) -> None:
        super().__init__()
        if not self.ui_loaded:
            self.use_filter_show = True
            self.use_filter_sort_alpha = True
            self.ui_loaded = True
    
    def draw_item(self, context: bpy.types.Context, layout: bpy.types.UILayout, data, item, icon, active_data, active_propname):
        # draw_item must handle the three layout types... Usually 'DEFAULT' and 'COMPACT' can share the same code.
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            # You should always start your row layout by a label (icon + text), or a non-embossed text field,
            # this will also make the row easily selectable in the list! The later also enables ctrl-click rename.
            # We use icon_value of label, as our given icon is an integer value, not an enum ID.
            # Note "data" names should never be translated!
            
            col = layout.column(align=True)
            col.prop(item, "asset_name", text="", icon="OBJECT_DATA", emboss=False)
            box = col.box()
            split = box.split(factor=0.1, align=True)
            split.template_icon(item.thumbnail_id, scale=3.0)
            split.icon
            col2 = split.column(align=True)
            model_path: str = item.model
            model_live_assets_index = model_path.find("live_assets")
            if model_live_assets_index != -1:
                model_path = model_path[model_live_assets_index:]
            thumb_path: str = item.thumbnail
            thumb_live_assets_index = thumb_path.find("live_assets")
            if thumb_live_assets_index != -1:
                thumb_path = thumb_path[thumb_live_assets_index:]
            if not thumb_path:
                thumb_path = "No Thumbnail Found"
            col2.label(text=model_path, icon="MESH_DATA")
            col2.label(text=thumb_path, icon="IMAGE_DATA")
            
            col.separator(factor=1)
                
        # 'GRID' layout type should be as compact as possible (typically a single icon!).
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            col = layout.column(align=True)
            col.prop(item, "asset_name", text="", icon="OBJECT_DATA", emboss=False)
            box = col.box()
            box.template_icon(item.thumbnail_id, scale=3.5)
            col.separator(factor=1)
            
    def filter_items(self, context, data, propname):
        # Filter list
        items = getattr(data, propname)
        
        helpers = bpy.types.UI_UL_list
        filtered = helpers.filter_items_by_name(self.filter_name, self.bitflag_filter_item, items, "asset_name", reverse=False)
        
        if self.use_filter_sort_alpha:
            ordered = helpers.sort_items_by_name(items, 'asset_name')
        else:
            ordered = [index for index, item in enumerate(items)]
        
        return filtered, ordered

class TorqueBrowserPanel(bpy.types.Panel):
    bl_label = "Torque"
    bl_idname = "OBJECT_PT_torque_browser_tab"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Torque DTS Addon'  # Customize the tab category
            
    def draw(self, context):
        layout = self.layout
        scn = context.scene
        
        # Add UI elements here (e.g., buttons, properties, etc.)
        col = layout.column()        
        row = col.row(align=True)
        row.prop(scn.torque_browser_addon, 'asset_dir', text='asset folder')
        row.operator("torque_browser.asset_directory_selector", icon="FILE_FOLDER", text="").filepath = scn.torque_browser_addon.asset_dir
        
        col.operator("torque_browser.load_assets_button", text="Load Assets")
        
        if not context.scene.torque_browser_addon.currently_loading:
            list_num_cols = int((context.region.width - 100) / 250)
            col.template_list("TORQUE_ASSET_UL_list", "torque_assets_list", context.scene.torque_browser_addon, "assets", context.scene.torque_browser_addon, "active_asset", item_dyntip_propname="asset_name", type="DEFAULT", columns=list_num_cols)
            
            opts_row = col.row()
            opts_row.prop(context.scene.torque_browser_addon, "reference_keyframe", icon="KEYFRAME_HLT")
            opts_row.prop(context.scene.torque_browser_addon, "import_sequences", icon="ANIM_DATA")
            opts_row.prop(context.scene.torque_browser_addon, "use_armature", icon="OUTLINER_OB_ARMATURE")
            
            col.operator("torque_browser.import_asset_button", text="Import Asset")
            
            
    def get_assets():
        pass
        


def register():
    bpy.utils.register_class(AssetProperty)
    bpy.utils.register_class(TorqueBrowserProperties)
    bpy.utils.register_class(ADFileSelector)
    bpy.utils.register_class(LoadAssetsOperator)
    bpy.utils.register_class(ImportAssetOperator)
    bpy.utils.register_class(TORQUE_ASSET_UL_list)
    bpy.utils.register_class(TorqueBrowserPanel)
    # bpy.utils.register_class(IconPanel)
    
    bpy.types.Scene.torque_browser_addon = bpy.props.PointerProperty(type=TorqueBrowserProperties)
    bpy.types.Scene.torque_icon_previews = None
    
def unregister():    
    bpy.utils.unregister_class(AssetProperty)
    bpy.utils.unregister_class(TorqueBrowserProperties)
    bpy.utils.unregister_class(ADFileSelector)
    bpy.utils.unregister_class(LoadAssetsOperator)
    bpy.utils.unregister_class(ImportAssetOperator)
    bpy.utils.unregister_class(TORQUE_ASSET_UL_list)
    bpy.utils.unregister_class(TorqueBrowserPanel)
    # bpy.utils.unregister_class(IconPanel)
    
    del bpy.types.Scene.torque_browser_addon
    del bpy.types.Scene.torque_icon_previews