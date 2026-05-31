# Rutas Inmersivas

Esta carpeta contiene rutas de camara para experiencias inmersivas.

Cada archivo JSON describe un tour por un objeto o espacio 3D. La app puede usar
estos puntos para mover la camara del visitante en modo cardboard/SBS.

## Ruta actual

- `lugar-walking-tour.json`: ruta caminable para `lugar.glb`, generada desde
  Blender con Codex/MCP. Incluye un primer punto panoramico para ver el lugar y
  puntos posteriores mas cercanos para sentir avance dentro del espacio.

## Convencion

- `position`: ubicacion de la camara o visitante.
- `target`: punto hacia donde mira la camara.
- `duration`: segundos para viajar desde este punto al siguiente.
- `fov`: campo de vision sugerido para la camara.
- `pause`: segundos opcionales de pausa en el punto.
- `coordinateSystem`: sistema de coordenadas usado por la ruta. Para Blender se
  usa `blender-z-up`; la app lo convierte a Three/GLTF.

## Ejemplo

```json
{
  "id": "sala-litica-tour",
  "model": "lugar.glb",
  "units": "blender",
  "points": [
    {
      "id": "entrada",
      "duration": 5,
      "position": { "x": 0, "y": 1.6, "z": 2.2 },
      "target": { "x": 0, "y": 1.1, "z": 0 },
      "fov": 50
    }
  ]
}
```

## Uso con Blender

El flujo recomendado es usar el asistente interactivo:

```bash
python3 muse3d.py
```

Ese comando te guia para:

1. seleccionar el `.glb`
2. crear una ruta base de 10, 12, 15 o mas puntos
3. abrir Blender y esperar tu ajuste manual
4. exportar la ruta
5. sincronizar la experiencia en la app

En Blender, ajusta visualmente las camaras `Tour_01`, `Tour_02`, `Tour_03` y los
   empties `Target_01`, `Target_02`, `Target_03`.

Si necesitas operar manualmente sin el asistente:

```bash
blender workspaces/lugar-tour.blend --background --python scripts/export_immersive_tour.py -- routes/sala-litica-tour.json
```

Si no existe un `Target_NN`, el script usa la direccion frontal de la camara para
calcular el punto de mirada.

## Editar manualmente una ruta existente

Para reabrir una ruta JSON y convertirla en objetos editables:

```bash
blender sala.blend --python muse3d/scripts/prepare_manual_tour_editing.py -- muse3d/routes/lugar-walking-tour.json
```

El script crea:

- `Tour_XX`: camaras editables, posicion del visitante.
- `Target_XX`: empties editables, mirada del visitante.
- `Label_XX`: etiquetas visibles para identificar el punto.
- `Muse3D_Tour_Path`: curva visual que conecta el recorrido.

Despues de ajustar la ruta visualmente, exporta de nuevo con
`export_immersive_tour.py`.

## Reglas practicas para evitar problemas

- Mantener el primer punto algo alejado y con `fov` amplio para presentar el
  espacio.
- Evitar puntos demasiado cerca de los bordes del modelo, porque el raycast de
  suelo puede caer en zonas bajas o vacias.
- Usar targets un poco por delante del visitante para simular caminata natural.
- Si el recorrido se mete debajo del plano, subir la camara o moverla hacia el
  centro del espacio en Blender.
- Para headset, el tour debe mover la posicion y el usuario debe controlar la
  mirada con sensores; no conviene fijar la vista completamente al target.
