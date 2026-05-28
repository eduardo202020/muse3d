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
- Definir rutas de navegacion para experiencias inmersivas usando Blender como
  editor visual.
- Exportar rutas a JSON para que la app reproduzca el tour con la camara 3D.

## Estructura propuesta

```txt
muse3d/
  models/
    catalog/                    # Modelos 3D de obras y piezas
    immersive/                  # Modelos 3D de salas o espacios inmersivos
  routes/                       # Rutas inmersivas exportadas desde Blender
  scripts/
    setup_immersive_tour.py     # Crea una ruta base editable en Blender
    export_immersive_tour.py    # Exportador Blender: camaras/targets -> JSON
```

## Estado actual

- Proyecto Git independiente inicializado como `muse3d`.
- Los modelos 3D existentes viven en `models/catalog/`.
- Las rutas inmersivas viven en `routes/`.
- `routes/lugar-walking-tour.json` contiene una ruta caminable generada desde
  Blender para `lugar.glb`.
- Blender puede usarse manualmente o mediante MCP de Codex para crear y ajustar
  `Tour_XX` y `Target_XX`.

## Flujo automatizado para una sala inmersiva

1. Preparar el modelo de sala en Blender.
2. Ejecutar `scripts/setup_immersive_tour.py` para crear una ruta base.
3. Ajustar visualmente las camaras `Tour_01`, `Tour_02`, etc. y los targets
   `Target_01`, `Target_02`, etc.
4. Ejecutar el script `scripts/export_immersive_tour.py`.
5. Copiar el `.json` resultante a la app y asociarlo con la sala.

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

Crear una ruta base dentro de Blender:

```bash
blender sala.blend --python muse3d/scripts/setup_immersive_tour.py
```

Exportar `Tour_XX` y `Target_XX` a JSON:

```bash
blender sala.blend --background --python muse3d/scripts/export_immersive_tour.py -- muse3d/routes/lugar-walking-tour.json
```

Validar scripts:

```bash
python3 -m py_compile scripts/setup_immersive_tour.py scripts/export_immersive_tour.py
```
