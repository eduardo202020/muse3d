# Muse3D

Muse3D is the open source asset pipeline for MuseIQ 3D/AR works.

It converts editable 3D sources into mobile-ready `.glb` files, validates them, generates AR metadata, and publishes the result so MuseRAG can serve it from `/media/ar`.

## Role in MuseIQ

```text
Blender source / existing GLB
-> Muse3D export
-> glTF Transform optimization
-> Khronos glTF validation
-> metadata.json + ar-catalog.json
-> museRAG/assets/ar
-> mobile AR / 3D viewer
```

## Open source stack

- Python 3.11+ for the CLI and pipeline orchestration.
- Blender in background mode for `.blend` or imported model export to `.glb`.
- glTF Transform for GLB optimization.
- Khronos glTF Validator through the `gltf-validator` npm package.

## Setup from VS Code

Open this folder in VS Code:

```powershell
cd C:\Users\pc\Documents\museIQ\muse3d
code .
```

Install Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

Install Node tools:

```powershell
npm install
```

If Blender is not in `PATH`, copy `.env.example` to `.env` and set `BLENDER_PATH`.

```env
BLENDER_PATH=C:\Program Files\Blender Foundation\Blender 4.3\blender.exe
MUSERAG_AR_DIR=..\museRAG\assets\ar
```

This workstation is currently configured with:

```env
BLENDER_PATH=C:\Program Files\Blender Foundation\Blender 5.1\blender.exe
```

## Commands

Check local tooling:

```powershell
python -m muse3d doctor
```

Build one artwork:

```powershell
python -m muse3d build obra-1-1-L
```

Build and publish to MuseRAG:

```powershell
python -m muse3d build obra-1-1-L --publish
```

Build every manifest:

```powershell
python -m muse3d build-all --publish
```

Rebuild only the AR catalog:

```powershell
python -m muse3d catalog --publish
```

Dry-run without requiring Blender or a real source file:

```powershell
python -m muse3d build obra-1-1-L --dry-run --skip-validate
```

Smoke-test the full installed stack with the generated sample cube:

```powershell
.\.venv\Scripts\python.exe -m muse3d build smoke-cube --publish
```

## Manifest format

Each artwork gets a manifest in `manifests/`.

```yaml
artwork_id: obra-1-1-L
title: Senor de Sipan
museum_id: tumbas-reales-de-sipan
room_id: SALA_1

source:
  blend: assets/sources/tumbas-reales-de-sipan/obra-1-1-L/model.blend

transform:
  scale: 0.7
  position: [0, -0.5, -2]
  rotation: [0, 0, 0]

hotspots:
  - id: emblema_poder
    label: Emblema de poder
    query: Explica el simbolo de poder asociado al Senor de Sipan.
```

You can use an existing GLB instead of Blender:

```yaml
source:
  model: assets/sources/tumbas-reales-de-sipan/obra-1-1-L/model.glb
```

## Output

Muse3D writes:

```text
assets/dist/ar/{museum_id}/{artwork_slug}/model.glb
assets/dist/ar/{museum_id}/{artwork_slug}/metadata.json
catalog/ar-catalog.json
```

With `--publish`, it copies the same artifact to:

```text
..\museRAG\assets\ar\{museum_id}\{artwork_slug}
..\museRAG\assets\ar\catalog.json
```

The metadata shape is ready for MuseRAG and the mobile app:

```json
{
  "artwork_id": "obra-1-1-L",
  "title": "Senor de Sipan",
  "museum_id": "tumbas-reales-de-sipan",
  "room_id": "SALA_1",
  "model_3d": {
    "url": "/media/ar/tumbas-reales-de-sipan/obra-1-1-L/model.glb",
    "format": "GLB",
    "scale": 0.7,
    "position": [0, -0.5, -2],
    "rotation": [0, 0, 0],
    "fallback_mode": "viewer_3d"
  },
  "hotspots": []
}
```

## Notes

This first version does not create artistic geometry by itself. Modeling, sculpting, photogrammetry cleanup, and texture authoring remain creative tasks. Muse3D automates the repeatable engineering part: export, optimize, validate, catalog, and publish.

## Pruebas en Windows (PowerShell)

Preparacion inicial:

```powershell
cd C:\Users\pc\Documents\proyectos\Museiq\muse3d
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
npm ci
```

Comprueba Python, Node, Blender y el destino de MuseRAG:

```powershell
.\.venv\Scripts\python.exe -m muse3d doctor
```

Prueba el pipeline sin generar archivos y luego ejecutalo realmente cuando el
diagnostico sea correcto:

```powershell
.\.venv\Scripts\python.exe -m muse3d build smoke-cube --dry-run
.\.venv\Scripts\python.exe -m muse3d build smoke-cube --publish
```

Si Blender no esta en `PATH`, define `BLENDER_PATH` en `.env` antes del build.
