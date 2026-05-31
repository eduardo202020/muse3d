# Muse3D

Muse3D agrupa el pipeline de activos 3D de MuseIQ. Su objetivo no es solo
almacenar modelos `.glb`, sino preparar los insumos que la app movil usa para
mostrar obras, salas inmersivas y recorridos guiados.

## Responsabilidades

- Generar o preparar modelos 3D desde imagenes de obras mediante flujos de IA,
  fotogrametria y/o Blender.
- Optimizar modelos para movil: reduccion de peso, texturas, escala, origen y
  orientacion.
- Exportar modelos finales en `.glb` para `museiqApp/assets/models`.
- Convertir cielos HDR a texturas JPG livianas para runtime movil.
- Definir rutas de navegacion para experiencias inmersivas usando Blender como
  editor visual.
- Exportar rutas a JSON para que la app reproduzca el tour con la camara 3D.

## Estructura propuesta

```txt
muse3d/
  muse3d.py                     # Asistente interactivo del pipeline
  experiences/                  # Manifiesto de experiencias para la app
  models/
    catalog/                    # Modelos 3D de obras y piezas
    immersive/                  # Modelos 3D de salas o espacios inmersivos
  routes/                       # Rutas inmersivas exportadas desde Blender
  scripts/
    create_immersive_tour_workspace.py
                                  # Abre Blender, importa un GLB y crea puntos
    setup_immersive_tour.py     # Crea una ruta base editable en Blender
    prepare_manual_tour_editing.py
                                  # Reconstruye un JSON como objetos editables
    export_immersive_tour.py    # Exportador Blender: camaras/targets -> JSON
    convert_hdr_sky.py          # Convierte HDR Radiance a JPG para la app
    sync_route_to_app.py         # Copia una ruta JSON a TypeScript
  workspaces/                    # .blend temporales de edicion manual
```

## Estado actual

- Proyecto Git independiente inicializado como `muse3d`.
- Los modelos 3D existentes viven en `models/catalog/`.
- Las rutas inmersivas viven en `routes/`.
- `routes/lugar-walking-tour.json` contiene una ruta caminable generada desde
  Blender para `lugar.glb`.
- Blender puede usarse manualmente o mediante MCP de Codex para crear y ajustar
  `Tour_XX` y `Target_XX`.

## Pipeline interactivo sin IA

El pipeline genera un recorrido base por heuristica geometrica. No usa IA: solo
calcula el bounding box del GLB, crea una linea caminable y deja camaras/targets
editables para que el criterio curatorial se ajuste manualmente.

La entrada normal es un solo comando:

```bash
python3 muse3d.py
```

El asistente permite:

- seleccionar un `.glb` desde `models/immersive/`
- elegir cuántos puntos crear para el recorrido
- abrir Blender con el modelo y la ruta editable
- esperar a que ajustes manualmente `Tour_XX` y `Target_XX`
- exportar la ruta a `routes/*.json`
- copiar el `.glb` a `museiqApp/assets/models/immersive/`
- sincronizar el tour en `museiqApp/lib/immersive-tours.ts`
- regenerar la lista de experiencias en `museiqApp/lib/immersive-experiences.generated.ts`

Los scripts de `scripts/` quedan como piezas internas/avanzadas. En el flujo
normal no hace falta correrlos uno por uno.

## Lista de experiencias en la app

La app ya no reemplaza una experiencia por otra. `muse3d.py` actualiza
`experiences/immersive-experiences.json` y desde ese manifiesto genera una lista
seleccionable en MuseIQ App.

Cada experiencia tiene:

- `id`: identificador de experiencia
- `roomId`: sala asociada de MuseIQ
- `title`, `description`, `ctaLabel`: textos visibles
- `modelAssetPath`: GLB disponible en la app
- `tourExportName`: constante TypeScript del recorrido

El render de la app no decide la ruta. Solo reproduce los puntos exportados.

## Flujo trabajado con Codex + Blender MCP

Cuando Blender expone el MCP, Codex puede operar sobre la escena abierta:

- leer los limites reales del modelo
- crear una coleccion `Muse3D_Tour`
- generar camaras `Tour_01`, `Tour_02`, etc.
- generar targets `Target_01`, `Target_02`, etc.
- exportar la ruta a JSON en `routes/`
- ajustar la ruta para evitar que la camara caiga debajo del plano
- mover el primer punto a una vista panoramica antes de entrar al recorrido

El flujo actual genera una caminata, no un vuelo: las posiciones intentan quedar
a altura de visitante, centradas en el espacio y con targets hacia el siguiente
tramo del recorrido.

## Flujo manual recomendado

Para ajustar una ruta punto por punto sin perder lo generado automaticamente:

1. Cargar el modelo en Blender.
2. Reconstruir la ruta existente:

   ```bash
   blender sala.blend --python muse3d/scripts/prepare_manual_tour_editing.py -- muse3d/routes/lugar-walking-tour.json
   ```

3. En Blender, mover `Tour_01`, `Tour_02`, etc. para definir la posicion del
   visitante.
4. Mover `Target_01`, `Target_02`, etc. para definir hacia donde mira cada
   tramo.
5. Usar la curva `Muse3D_Tour_Path` y los labels `Label_XX` como guia visual.
6. Exportar la ruta final:

   ```bash
   blender sala.blend --background --python muse3d/scripts/export_immersive_tour.py -- muse3d/routes/lugar-walking-tour.json
   ```

Tambien se puede hacer con Codex via MCP: pedir mover un punto especifico,
exportar y probar en la app.

## Integracion con MuseIQ App

La app no ejecuta Blender. Consume rutas exportadas desde Muse3D. En el prototipo
actual, `lugar-walking-tour.json` se trasladó a
`museiqApp/lib/immersive-tours.ts` como `lugarWalkingTour` y se asocia a
`SALA_1` desde `museiqApp/lib/room-experiences.ts`.

Las rutas exportadas usan coordenadas Blender `Z-up`. La app las convierte a
Three/GLTF con el mapeo:

```txt
Blender: x, y, z
Three:   x, z, -y
```

## Comandos utiles

Abrir el asistente interactivo:

```bash
python3 muse3d.py
```

Regenerar solo la lista de experiencias de la app desde el manifiesto:

```bash
python3 muse3d.py --sync-app
```

Crear una ruta base dentro de Blender, modo avanzado:

```bash
blender sala.blend --python muse3d/scripts/setup_immersive_tour.py -- --points 12
```

Abrir Blender con un GLB nuevo y una ruta editable, modo avanzado:

```bash
python3 scripts/create_immersive_tour_workspace.py models/immersive/lugar.glb --points 12
```

Exportar `Tour_XX` y `Target_XX` a JSON:

```bash
blender sala.blend --background --python muse3d/scripts/export_immersive_tour.py -- muse3d/routes/lugar-walking-tour.json
```

Validar scripts:

```bash
python3 -m py_compile scripts/*.py
```

Convertir un cielo HDR a textura de app:

```bash
python3 scripts/convert_hdr_sky.py ../mañana.hdr ../museiqApp/assets/skies/morning.jpg
```
