from rembrandt.scene import Scene
import datetime

scene = Scene()
scene.load_object("./test-obj/chess.obj")
scene.center_target()
scene.add_camera(location=(5, 5, 5), look_at=(0, 0, 0), focal_length=50)
scene.add_light(light_type="SUN", location=(2, -3, 5), energy=3.0)
scene.add_light(light_type="POINT", location=(-2, 2, 3))

date = datetime.datetime.now()

out = scene.render(f"output/test-{date}.png", resolution=(640, 640))
print(f"Rendered to {out}")