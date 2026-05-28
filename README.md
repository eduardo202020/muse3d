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
    export_immersive_tour.py    # Exportador Blender: camaras/targets -> JSON
```

## Flujo para una sala inmersiva

1. Preparar el modelo de sala en Blender.
2. Crear puntos de recorrido como camaras llamadas `Tour_01`, `Tour_02`, etc.
3. Crear targets opcionales llamados `Target_01`, `Target_02`, etc.
4. Ejecutar el script `scripts/export_immersive_tour.py`.
5. Copiar el `.json` resultante a la app y asociarlo con la sala.

El render de la app no decide la ruta. Solo reproduce los puntos exportados.
