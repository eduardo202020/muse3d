# Experiencias inmersivas

`immersive-experiences.json` es el manifiesto que usa `muse3d.py` para generar
la lista de experiencias disponibles en MuseIQ App.

Cada entrada conecta:

- un `roomId` de la app
- un modelo `.glb` copiado a `museiqApp/assets/models/immersive/`
- una ruta exportada a TypeScript en `museiqApp/lib/immersive-tours.ts`
- los textos que se muestran en la lista de experiencias inmersivas

Normalmente no hace falta editar este archivo a mano. Usa:

```bash
python3 muse3d.py
```
