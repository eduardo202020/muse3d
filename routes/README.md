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

1. Importa el `.glb`.
2. Ejecuta el generador automatico:

```bash
blender sala.blend --python muse3d/scripts/setup_immersive_tour.py
```

3. Ajusta visualmente las camaras `Tour_01`, `Tour_02`, `Tour_03` y los
   empties `Target_01`, `Target_02`, `Target_03`.
4. Exporta:

```bash
blender sala.blend --background --python muse3d/scripts/export_immersive_tour.py -- muse3d/routes/sala-litica-tour.json
```

Si no existe un `Target_NN`, el script usa la direccion frontal de la camara para
calcular el punto de mirada.

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
