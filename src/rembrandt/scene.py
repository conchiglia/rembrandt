"""Scene management for synthetic dataset rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import bpy
from mathutils import Vector # type: ignore

from rembrandt.errors import ModelFileNotFoundError



class Scene:
    """Manages a Blender scene for synthetic dataset rendering.

    Wraps bpy's global scene state and keeps references to objects we
    create or import, so downstream code (bbox projection, randomization)
    can access them without re-querying bpy.
    """

    def __init__(self, *, clear: bool = True) -> None:
        """Initialize the scene.

        Args:
            clear: If True, remove all existing objects from the scene
                on init. Defaults to True since Rembrandt always renders
                from a fresh scene.
        """
        self.target: bpy.types.Object | None = None
        self.camera: bpy.types.Object | None = None
        self.lights: list[bpy.types.Object] = []
        if clear:
            self.clear()

    def clear(self) -> None:
        """Remove all objects from the scene and reset tracked references."""
        for obj in list(bpy.data.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        self.target = None
        self.camera = None
        self.lights = []

    def load_object(self, obj_path: str | Path) -> bpy.types.Object:
        """Load an .obj file as the target object for rendering.

        Args:
            obj_path: Path to the .obj file.

        Returns:
            The imported mesh object.

        Raises:
            ModelFileNotFoundError: If the file does not exist.
            RuntimeError: If the .obj contains no mesh objects.
        """
        path = Path(obj_path)
        if not path.exists():
            raise ModelFileNotFoundError(str(path))

        # Blender 4.x: bpy.ops.wm.obj_import (replaces import_scene.obj).
        bpy.ops.wm.obj_import(filepath=str(path))

        imported = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if not imported:
            raise RuntimeError(f"No mesh objects found in {path}")

        # If the .obj contains multiple meshes, take the first for now.
        # Multi-mesh handling can come later if a real .obj forces the issue.
        self.target = imported[0]
        return self.target

    def add_camera(
        self,
        location: tuple[float, float, float] = (5.0, 5.0, 5.0),
        look_at: tuple[float, float, float] = (0.0, 0.0, 0.0),
        focal_length: float = 50.0,
    ) -> bpy.types.Object:
        """Create a camera, point it at a target, and set it active.

        Args:
            location: Camera position (x, y, z) in world coordinates.
            look_at: World-space point the camera aims at.
            focal_length: Focal length in mm. 50mm is "standard" / human-eye.

        Returns:
            The created camera object.
        """
        camera_data = bpy.data.cameras.new("Camera")
        camera_data.lens = focal_length

        camera_obj = bpy.data.objects.new("Camera", camera_data)
        bpy.context.collection.objects.link(camera_obj)
        camera_obj.location = location

        # Blender cameras look down their local -Z axis with +Y as up.
        # to_track_quat('-Z', 'Y') gives the rotation that aligns the
        # camera's view direction with `direction`.
        direction = Vector(look_at) - Vector(location)
        camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        bpy.context.scene.camera = camera_obj
        self.camera = camera_obj
        return camera_obj
    
    def add_light(self,
                  *,
                  light_type: Literal["POINT", "SUN", "AREA"] = "POINT",
                  location: tuple[float, float, float],
                  look_at: tuple[float, float, float],
                  energy: float | None = None,
                  color: tuple[float, float, float] = (1.0, 1.0, 1.0),
                  size: float = 1.0,
                  ) -> bpy.types.Object:
        """
        Args:
            light_type: One of "POINT" (omnidirectional), "SUN" (parallel
                directional rays, location-independent), or "AREA"
                (rectangular soft light, good for studio-style renders).
            location: World-space position of the light. For SUN, only the
                direction from `location` to `look_at` matters; the actual
                position is irrelevant for shading.
            look_at: World-space point the light aims at. Used by SUN and
                AREA. Ignored for POINT (omnidirectional).
            energy: Light intensity. Units depend on type:
                POINT and AREA in Watts, SUN in unitless strength.
                If None, defaults are POINT=1000, SUN=5, AREA=100.
            color: RGB in [0, 1]. White by default.
            size: For AREA lights, the side length in meters. Ignored
                for other types.

        Returns:
            The created light object.
        """
        if energy is None:
            energy = {"POINT": 1000.0, "SUN": 5.0, "AREA": 100.0}[light_type]

        name = f"Light_{light_type.capitalize()}"
        light_data = bpy.data.lights.new(name=name, type=light_type)
        light_data.energy = energy
        light_data.color = color

        if light_type == "AREA":
            light_data.size = size

        light_obj = bpy.data.objects.new(name=name, object_data=light_data)
        bpy.context.collection.objects.link(light_obj)
        light_obj.location = location

        #POINT is omnidirectional - rotation has no effect.
        #SUN and AREA emit along their local -Z axis (same convention as the camera), so the same _to_track_quat trick aims them.
        if light_type != "POINT":
            direction = Vector(look_at) - Vector(location)
            light_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        self.lights.append(light_obj)
        return light_obj