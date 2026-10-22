# Fútbol Central · Marcadores en directo

Tablero responsive de partidos del día en HTML, CSS y JavaScript. Consume el endpoint diario de FotMob (`/api/data/matches?date=YYYYMMDD`), un servicio interno no oficial y sin garantía de disponibilidad. No intenta sortear medidas anti bot: cuando el origen rechaza una petición, presenta el error.

## Ejecutar localmente

Requiere Python 3.10 o posterior. Desde la carpeta del proyecto:

```sh
python server.py
```

Abre <http://127.0.0.1:8000>. El proxy consulta `/api/matches`, usa una caché corta de 30 segundos y el navegador vuelve a pedir los datos cada 60 segundos. Se envía un User-Agent transparente de la aplicación, encabezados normales de aceptación e idioma; no se falsifica una sesión de navegador.

## GitHub Pages

El workflow `.github/workflows/pages.yml` consulta FotMob cada cinco minutos y publica el sitio junto a `data/today.json`. El navegador solicita esa copia cada minuto. El refresco de la fuente queda sujeto al calendario y la carga de GitHub Actions; por tanto, Pages no garantiza datos en vivo segundo a segundo.

Para habilitar la publicación, en GitHub abre **Settings → Pages** y selecciona **GitHub Actions** como fuente de compilación. El primer despliegue se inicia automáticamente al subir el workflow. La URL será <https://p1x3l4118.github.io/prueba/> si Pages está habilitado en ese repositorio.

## Estructura

- `index.html`, `live.css`, `live.js`: interfaz y polling.
- `server.py`: proxy local a FotMob.
- `fetch_daily.py`: exportador de la instantánea para Pages.
- `.github/workflows/pages.yml`: actualización periódica y publicación.
- `data/today.json`: instantánea pública creada por Actions.

FotMob no ofrece aquí una API pública oficial; puede cambiar la respuesta o bloquear el acceso. Los nombres, escudos, marcadores y estados dependen de la fuente.
