# MatchPoint

Panel responsive de las cinco grandes ligas europeas, construido con HTML, CSS y JavaScript. Cada liga muestra sus partidos de toda la temporada por fecha, la clasificación y los líderes de goles y asistencias, con logos de liga, escudos de clubes y fotos de jugadores.

## Ligas incluidas

- LaLiga
- Premier League
- Serie A
- Bundesliga
- Ligue 1 McDonald's

## Ejecutar localmente

Requiere Python 3.10 o posterior. Ejecuta:

```sh
python server.py
```

Abre <http://127.0.0.1:8000>. El servidor obtiene y guarda en memoria cinco minutos de datos para cada liga desde FotMob. El calendario de temporada permite consultar fechas anteriores y futuras incluidas por FotMob. El navegador refresca los datos cada minuto; el botón «Actualizar» permite solicitar una carga inmediata.

## Publicación en GitHub Pages

El workflow `.github/workflows/pages.yml` actualiza `data/football.json` desde FotMob cada cinco minutos y despliega el sitio. En GitHub, la fuente de Pages debe estar configurada como **GitHub Actions**. El sitio público es <https://p1x3l4118.github.io/prueba/>.

## Archivos

- `index.html`, `live.css`, `live.js`: interfaz y navegación por ligas/fechas.
- `server.py`: proxy local y normalizador de FotMob.
- `fetch_daily.py`: genera el paquete completo usado por Pages.
- `data/football.json`: calendario, tabla, goleadores y asistencias de las cinco ligas.

FotMob no ofrece una API pública oficial para estos datos. Su API interna puede cambiar o rechazar solicitudes; la interfaz muestra el error sin intentar eludir protecciones. Escudos y fotos se sirven desde sus recursos de imagen. La estructura de endpoints puede consultarse en el cliente comunitario [FotMob-API](https://github.com/writeshh/FotMob-API), que se declara no oficial.
