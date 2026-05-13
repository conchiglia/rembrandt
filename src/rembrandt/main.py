import datetime

from rembrandt.camera_poses import sample_camera_poses
from rembrandt.scene import Scene

poses = sample_camera_poses(
    n=20,
    azimuth_range=(0.0, 360.0),
    elevation_range=(-10.0, 30.0),
    distance_range=(3.0, 5.0),
    strategy="fibonacci",
    seed=42,
)

stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

scene = Scene()
scene.load_object("./test-obj/mercedes.obj")
scene.center_target()
scene.add_light(light_type="SUN", location=(2, -3, 5), energy=3.0)
scene.add_light(light_type="POINT", location=(-2, 2, 3))

for i, pose in enumerate(poses):
    scene.add_camera(location=pose.location, look_at=pose.look_at, focal_length=50)

    out = scene.render(f"output/{stamp}/frame_{i:04d}.png", resolution=(640, 640))
    print(f"Rendered frame {i} to {out}")
