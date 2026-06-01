# Modelos Inmersivos

Coloca aqui los modelos de salas o espacios recorribles, por ejemplo:

```txt
models/immersive/lugar.glb
models/immersive/sala-litica/lugar.glb
models/immersive/puerta_monumental_inca.glb
models/immersive/ushnu-2.glb
```

Cada modelo inmersivo puede tener una ruta asociada en `routes/`.
El flujo recomendado es mantener aqui el GLB fuente, generar/ajustar su tour con
Blender y luego sincronizarlo hacia `museiqApp/assets/models/immersive/` desde
`muse3d.py`.

Para generar una ruta base editable y sincronizarla con la app:

```bash
python3 muse3d.py
```

Durante la edicion abierta puedes usar la opcion `Anadir pares Tour/Target` para
sumar nuevas tomas al recorrido sin rehacer la ruta desde cero.
