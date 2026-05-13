"""Scene management for synthetic dataset rendering."""

from __future__ import annotations

from math import sin
from pathlib import Path
from typing import Literal

import bpy
from mathutils import Vector  # type: ignore

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
        fit_target: bool = True,
        fit_margin: float = 1.2,
    ) -> bpy.types.Object:
        """Create a camera, point it at a target, and set it active.

        Args:
            location: Camera position (x, y, z) in world coordinates.
            look_at: World-space point the camera aims at.
            focal_length: Focal length in mm. 50mm is "standard" / human-eye.
            fit_target: If True and a target is loaded, move the camera back
                along the requested view direction until the target fits.
            fit_margin: Extra framing margin around the target.

        Returns:
            The created camera object.
        """
        camera_data = bpy.data.cameras.new("Camera")
        camera_data.lens = focal_length

        camera_obj = bpy.data.objects.new("Camera", camera_data)
        bpy.context.collection.objects.link(camera_obj)
        camera_obj.location = location

        look_at_vec = Vector(look_at)

        if fit_target and self.target is not None:
            if fit_margin <= 0:
                raise ValueError("fit_margin must be greater than 0.")

            bpy.context.view_layer.update()
            corners = [
                self.target.matrix_world @ Vector(corner)
                for corner in self.target.bound_box
            ]
            radius = max((corner - look_at_vec).length for corner in corners)
            current_direction = look_at_vec - Vector(location)

            if current_direction.length == 0:
                raise ValueError("Camera location and look_at cannot be the same point.")

            fov = min(camera_data.angle_x, camera_data.angle_y)
            fit_distance = (radius * fit_margin) / sin(fov / 2)
            distance = max(current_direction.length, fit_distance)
            camera_obj.location = look_at_vec - current_direction.normalized() * distance

        # Blender cameras look down their local -Z axis with +Y as up.
        # to_track_quat('-Z', 'Y') gives the rotation that aligns the
        # camera's view direction with `direction`.
        direction = look_at_vec - Vector(camera_obj.location)
        if direction.length == 0:
            raise ValueError("Camera location and look_at cannot be the same point.")
        camera_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        bpy.context.scene.camera = camera_obj
        self.camera = camera_obj
        bpy.context.view_layer.update()
        return camera_obj

    def add_light(
        self,
        *,
        light_type: Literal["POINT", "SUN", "AREA"] = "POINT",
        location: tuple[float, float, float] = (5.0, 5.0, 5.0),
        look_at: tuple[float, float, float] = (1.0, 1.0, 1.0),
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

        # POINT is omnidirectional - rotation has no effect.
        # SUN and AREA emit along local -Z, so the camera aiming logic applies.
        if light_type != "POINT":
            direction = Vector(look_at) - Vector(location)
            light_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

        self.lights.append(light_obj)
        bpy.context.view_layer.update()
        return light_obj

    def render(
        self,
        output_path: str | Path,
        *,
        resolution: tuple[int, int] = (256, 256),
        engine: Literal["EEVEE", "CYCLES"] = "EEVEE",
        samples: int = 32,
    ) -> Path:
        """Renders the current scene to a PNG file.

        Args:
            output_path: Where to write rendered PNG.
            resolution: (width, height) in pixels.
            engine:
                - EEVEE for fast rasterization (good for high-volume data)
                - CYCLES for path-traced realism (slower)
            samples: Render samples. For EEVEE this is TAA samples;
                     for CYCLES, path samples per pixel.
                     Higher = less noise, slower.

            Returns:
                The output path as a Path object.

            Raises:
                RuntimeError: If no camera has been added to the scene.
        """
        if self.camera is None:
            raise RuntimeError("No camera in the scene. Call add_camera() before render().")

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        # Map friendly names to bpy's internal engine identifiers.
        # Note: Blender 5.x renamed BLENDER_EEVEE_NEXT back to BLENDER_EEVEE.
        # We're pinned to bpy 4.5 LTS, so NEXT is correct.
        engine_id = {
            "EEVEE": "BLENDER_EEVEE_NEXT",
            "CYCLES": "CYCLES",
        }[engine]

        bpy_scene = bpy.context.scene
        bpy_scene.camera = self.camera

        # `bpy_scene.render` here is bpy's render-settings struct —
        # not a method on our Scene class. Naming overlap, no conflict.
        bpy_scene.render.engine = engine_id
        bpy_scene.render.resolution_x = resolution[0]
        bpy_scene.render.resolution_y = resolution[1]
        bpy_scene.render.resolution_percentage = 100
        bpy_scene.render.image_settings.file_format = "PNG"
        bpy_scene.render.image_settings.color_mode = "RGB"

        if engine == "EEVEE":
            bpy_scene.eevee.taa_render_samples = samples
        else:
            bpy_scene.cycles.samples = samples

        # Two-step render: render to internal buffer, then explicitly save.
        # Avoids Blender's quirks around appending frame numbers and
        # extra extensions to render.filepath.
        bpy.ops.render.render()
        bpy.data.images["Render Result"].save_render(filepath=str(output))

        return output

    def center_target(self) -> None:
        """Translate the target so its bounding-box center is at (0, 0, 0).

        .obj files don't guarantee where the geometry sits relative to
        the object origin — exporters often put the origin at floor
        level, one corner, or somewhere arbitrary. This normalizes the
        target so camera and light placement relative to the world
        origin actually frames the model.

        Raises:
            RuntimeError: If no target has been loaded.
        """
        if self.target is None:
            raise RuntimeError("No target loaded. Call load_object() first.")

        # bound_box is 8 corner points in the target's *local* space.
        # We multiply each by matrix_world to get world-space corners,
        # then average them to find the world-space bbox center.
        world_corners = [
            self.target.matrix_world @ Vector(corner)
            for corner in self.target.bound_box
        ]
        center = sum(world_corners, Vector()) / 8

        # Translating the origin by -center shifts the whole object
        # so its bbox center lands at (0, 0, 0).
        self.target.location -= center
        bpy.context.view_layer.update()
