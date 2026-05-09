import bpy
from pathlib import Path
from rembrandt.errors import ModelFileNotFoundError

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