# Rembrandt — Project Handoff

**What it is.** Rembrandt is an early-stage open-source Python tool for generating synthetic computer vision training datasets from 3D models. The user supplies a `.obj` file and some configuration; Rembrandt renders many images of the object with randomized camera angles, lighting, and backgrounds, applies 2D augmentations on top, and writes the result out in YOLO format alongside a ready-to-run training script. The goal is "easy mode" synthetic data — there are existing tools in this space (BlenderProc, NVIDIA Omniverse Replicator, Kubric) but they're heavy and not beginner-friendly.

**MVP scope (v0.1).** One `.obj` in, one class out (single-class detector). One object per image, no occlusion, no scenes with multiple objects. Object detection only — no segmentation, classification, or pose estimation. Domain randomization rather than photorealism. 2D augmentations include cutout-style masking, noise, and blur. The tool generates the dataset plus a training script template; it does *not* launch training itself. Train/val split defaults to 80/20 and is configurable. CLI is the primary interface; a light Gradio or Streamlit UI is post-MVP. Multi-class support, scene composition, and user-supplied background images are all deferred to later versions.

**Tech stack.** Rendering uses `bpy` (Blender 4.5 LTS as a pip-installable Python module), pinned strictly to Python 3.11 because bpy ties one-to-one to a specific Python minor version. Math is `numpy` (and `mathutils` which ships inside bpy). 2D augmentations use `albumentations`; image I/O uses `Pillow`. Configuration is `pydantic` v2 schemas loaded from YAML via `PyYAML`. The CLI is `typer` with `rich` for output. The training-script template is rendered via `jinja2` and targets the `ultralytics` package (YOLOv8/v11). Dev tooling is `pytest`, `ruff` (lint and format), and `mypy` in strict mode. Build backend is `hatchling`; distribution will be PyPI with GitHub Actions CI.

**Architecture pipeline.** At runtime: load YAML config → set up Blender scene (load `.obj`, place camera and lights) → loop N times, randomizing camera pose on a sphere around the object, lighting parameters, materials, and background → render frame → compute the 2D bounding box by projecting the object's 3D bounding box vertices through the camera matrix → apply 2D augmentations → write image and YOLO label file. After the loop, perform train/val split, write `data.yaml`, and emit the training script.

**Repository layout.**

```
rembrandt/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── .python-version
├── src/rembrandt/
│   ├── __init__.py
│   ├── cli.py            # typer entry point
│   ├── config.py         # pydantic schema, YAML loading
│   ├── scene.py          # Blender scene setup
│   ├── randomize.py      # camera/lighting/material sampling
│   ├── render.py         # main render loop
│   ├── annotations.py    # 3D→2D bbox projection, YOLO writing
│   ├── augment.py        # albumentations pipeline
│   ├── backgrounds.py    # background sampling
│   ├── dataset.py        # output layout, train/val split, data.yaml
│   └── templates/train_yolo.py.tmpl
├── tests/
└── examples/configs/
```

Most modules under `src/rembrandt/` don't exist yet — the tree shows the planned layout.

**Phased roadmap.** Phase 1 is the walking skeleton: load an `.obj`, fixed camera, render one image, output one valid YOLO label. The whole point is proving the bbox projection is correct end-to-end. Phase 2 adds randomization (camera pose sampling, lighting, backgrounds) and the N-image loop. Phase 3 adds 2D augmentations and the proper YOLO directory structure with train/val split. Phase 4 wraps everything in the CLI and emits the training script template. Phase 5 is polish: README with working example, PyPI packaging, CI.

**Current status.** Setup is complete and committed:

- Debian system libraries for bpy installed via apt (`libxrender1`, `libxi6`, `libxxf86vm1`, `libxfixes3`, `libxkbcommon0`, `libsm6`, `libgl1`).
- Python 3.11 installed via pyenv and pinned in `.python-version`.
- Virtualenv created at `.venv/`.
- bpy 4.5 LTS installed and importing cleanly.
- `pyproject.toml` configured with hatchling backend, runtime deps (`bpy==4.5.*`, `numpy>=1.26`), dev deps (pytest, ruff, mypy), and tool configs.
- `src/rembrandt/__init__.py` with version string, package installed editable via `pip install -e ".[dev]"`.
- Smoke tests in `tests/test_smoke.py` verifying both `rembrandt` and `bpy` import. Passing.
- `README.md`, `LICENSE` (MIT), `.gitignore` in place.

**Gotchas worth knowing.** bpy is strictly tied to Python 3.11 — bumping Python means bumping bpy and vice versa. The bpy wheel is roughly 700MB, so CI installs need aggressive caching. The `src/` layout means you must `pip install -e .` before `import rembrandt` works; running scripts from the project root won't find the package otherwise. mypy is in strict mode from day one with `ignore_missing_imports = true` because bpy ships no type stubs.