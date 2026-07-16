# Guia para agentes

## Alcance

Este archivo aplica a todo `muse3d`. El repositorio contiene dos flujos
relacionados pero distintos:

1. pipeline de obras 3D/AR basado en manifiestos;
2. pipeline de experiencias inmersivas y tours editables en Blender.

No uses una pieza del catalogo AR como entorno caminable ni publiques un tour
inmersivo como si fuera una obra AR.

## Rol dentro del ecosistema

```text
Fuente Blender o GLB
-> exportar
-> optimizar
-> validar
-> catalogar
-> publicar a museRAG o sincronizar con museiqApp
```

La marca externa puede ser ArkeIA, pero conserva por ahora nombres tecnicos
`Muse3D`, `MuseIQ`, IDs de obra y nombres de exportacion usados por otros
repositorios.

## Mapa del proyecto

- `muse3d/`: CLI Python del pipeline de obras.
- `manifests/`: fuente de verdad declarativa por obra.
- `assets/sources/`: fuentes editables.
- `assets/work/`: intermedios generados, ignorados por Git.
- `assets/dist/`: artefactos generados, ignorados por Git.
- `catalog/ar-catalog.json`: catalogo AR publicado.
- `scripts/`: Blender, optimizacion, validacion, preview y sincronizacion.
- `routes/`: tours JSON versionados.
- `experiences/immersive-experiences.json`: catalogo de experiencias VR.
- `workspaces/`: archivos `.blend` de trabajo manual.
- `muse3d.py`: asistente interactivo para crear/editar/sincronizar tours.

## Contratos entre repositorios

El pipeline AR publica en `museRAG/assets/ar`:

```text
{museum_id}/{artwork_slug}/model.glb
{museum_id}/{artwork_slug}/metadata.json
catalog.json
```

El metadata debe conservar `artwork_id`, `museum_id`, `room_id`,
`model_3d.url`, transformaciones, `fallback_mode` y `hotspots`.

El pipeline inmersivo sincroniza con `museiqApp`:

- modelos en `assets/models/immersive/`;
- rutas en `lib/immersive-tours.ts`;
- catalogo en `lib/immersive-experiences.generated.ts`.

No edites manualmente una salida generada si puedes corregir el manifiesto, la
ruta JSON o el script generador. Al cambiar un contrato, valida tambien el
consumidor correspondiente.

## Coordenadas y tours

- Blender usa `Z-up`; Three/GLTF en la app requiere conversion.
- Cada punto editable se representa con una camara `Tour_XX` y un target
  `Target_XX`.
- `position` mueve al visitante; `target` orienta el tramo, pero el headset
  conserva control de mirada.
- El primer punto debe presentar el lugar desde una distancia razonable.
- Evita puntos bajo el suelo, fuera del footprint o pegados a geometria.
- `duration` y `pause` forman parte de la experiencia y no deben recalcularse
  silenciosamente.
- Al mover puntos, la previsualizacion debe reconstruir
  `Muse3D_Tour_Path` antes de exportar.

## Dependencias y comandos

Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Node usa `npm` porque este repo versiona `package-lock.json`:

```bash
npm ci
```

Diagnostico y pipeline de obras:

```bash
python -m muse3d doctor
python -m muse3d build smoke-cube --dry-run --skip-validate
python -m muse3d build obra-1-1-L
python -m muse3d build obra-1-1-L --publish
python -m muse3d catalog --publish
```

Asistente de tours:

```bash
python3 muse3d.py
```

No ejecutes `--publish` ni sincronices hacia la app como efecto secundario de
una prueba si la tarea no pide modificar otros repositorios.

## Reglas para GLB

- Conserva siempre el original; genera una variante optimizada.
- No cambies escala, origen, ejes, materiales o compresion sin revisar el
  resultado visual.
- Usa glTF Transform para optimizar y Khronos Validator para validar.
- Un archivo que carga no necesariamente es apto para movil: revisa peso,
  texturas, primitivas y extensiones.
- No simplifiques geometria por defecto; habilita `simplify` solo con una
  comparacion visual.
- Los materiales y texturas son contenido del activo, no deben reemplazarse por
  un material gris de diagnostico.

## Validacion minima

Para cambios del CLI o manifiestos:

```bash
python -m muse3d doctor
python -m muse3d build smoke-cube --dry-run --skip-validate
```

Para cambios reales del pipeline, construye al menos `smoke-cube` y revisa:

- GLB final;
- `metadata.json`;
- reporte de validacion;
- catalogo reconstruido.

Para cambios de tours:

1. abrir workspace en Blender;
2. previsualizar recorrido;
3. exportar JSON;
4. revisar `coordinateSystem`, orden y duraciones;
5. sincronizar con la app solo si fue solicitado;
6. probar `sala-inmersiva` en dispositivo.

## Archivos y Git

- No versionar `.env`, `.venv/`, `node_modules/`, `assets/work/` ni
  `assets/dist/`.
- Los `.blend1` son backups locales.
- No borres workspaces o GLB locales no versionados: pueden contener ajustes
  manuales no recuperables.
- Revisa archivos grandes antes de agregarlos.
- Usa commits enfocados, por ejemplo `feat: add immersive tour manifest` o
  `fix: preserve glb materials during export`.
