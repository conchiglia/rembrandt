from rembrandt.scene import Scene

scene = Scene()
scene.load_object("./test-obj/mercedes.obj")
scene.add_camera(location=(5, 5, 5), look_at=(0, 0, 0))
scene.add_light(light_type="SUN", location=(2, -3, 5), energy=3.0)
scene.add_light(light_type="POINT", location=(-2, 2, 3))

out = scene.render("output/test.png", resolution=(640, 640))
print(f"Rendered to {out}")