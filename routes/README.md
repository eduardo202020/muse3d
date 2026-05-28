# Rutas Inmersivas

Esta carpeta contiene rutas de camara para experiencias inmersivas.

Cada archivo JSON describe un tour por un objeto o espacio 3D. La app puede usar
estos puntos para mover la camara del visitante en modo cardboard/SBS.

## Convencion

- `position`: ubicacion de la camara o visitante.
- `target`: punto hacia donde mira la camara.
- `duration`: segundos para viajar desde este punto al siguiente.
- `fov`: campo de vision sugerido para la camara.
- `pause`: segundos opcionales de pausa en el punto.

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
2. Crea camaras `Tour_01`, `Tour_02`, `Tour_03`.
3. Opcionalmente crea empties `Target_01`, `Target_02`, `Target_03`.
4. Ejecuta:

```bash
blender sala.blend --background --python muse3d/scripts/export_immersive_tour.py -- muse3d/routes/sala-litica-tour.json
```

Si no existe un `Target_NN`, el script usa la direccion frontal de la camara para
calcular el punto de mirada.
