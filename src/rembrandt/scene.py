import bpy
from pathlib import Path
from rembrandt.errors import ModelFileNotFoundError
from mathutils import Vector, Matrix # type: ignore

def load_obj(obj_path: str) -> None:
    """
    Loads an .obj 3D model to Blender scene.

    Args:
        obj_path: Path to .obj file
    """
    obj_file = Path(obj_path)
    if not obj_file.exists():
        raise ModelFileNotFoundError(obj_path)
    
    bpy.ops.import_scene.obj(filepath=str(obj_file))

def clear_scene() -> None:
    """
    Removes all objects from Blender scene.
    """
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

def setup_camera(location: tuple[float, float, float] = (5.0, 5.0, 5.0),
                 look_at: tuple[float, float, float] = (0.0, 0.0, 0.0), 
                 focal_length: float = 50.0
                 ) -> None:
    """
    Creates and positions camera pointing towards the 3D model in the scene.

    Args:
        location: Camera position (x, y, z)
        look_at: 3D Model position at which camera looks at (x, y, z)
        focal_length: Camera focal length in mm (default 50mm is standard)
    """

    #Create a camera
    camera_data = bpy.data.cameras.new("Camera")
    camera_obj = bpy.data.objects.new("Camera", camera_data)

    #Add to the scene
    bpy.context.collection.objects.link(camera_obj)

    #Set up camera location
    camera_obj.location = location

    #Look at specific point (default: (0,0,0))
    direction = Vector(look_at) - Vector(location)
    camera_rotation = direction.to_track_quat('-Z', 'Y') #camera's rotation quaternion
    camera_obj.rotation_euler = camera_rotation.to_euler()

    #Set up focal length of camera
    camera_data.lens = focal_length

    #Set up camera as active
    bpy.context.scene.camera = camera_obj