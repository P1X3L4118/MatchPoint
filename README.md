# Futbol Central

Panel de futbol en HTML, CSS y JavaScript. OpenFootball aporta el calendario completo y Football-Data.co.uk aporta los resultados de los partidos jugados. La clasificacion se calcula localmente con esos marcadores, sin usar ESPN.

## Fuentes de datos

- Calendario completo: [OpenFootball/football.json](https://github.com/openfootball/football.json).
- Resultados: [Football-Data.co.uk](https://www.football-data.co.uk/), archivos CSV de LaLiga, Premier League, Serie A y Bundesliga. Se solicita la edicion vigente de la temporada al proveedor.
- Clasificacion: se calcula a partir de los partidos con marcador final del CSV. Los partidos pasados sin resultado confirmado aparecen como "Sin resultado".
- Escudos: FootyLogos, con iniciales del club como respaldo visual.

El proyecto incluye un servidor local de Python que evita el bloqueo CORS del CSV. Python 3.9 o posterior es el unico requisito; no se necesita clave API. Abre la pagina desde ese servidor, no desde la extension Live Server.

## Ejecutar

```sh
python server.py
```

Abre `http://127.0.0.1:8000`. El servidor guarda cada CSV en memoria durante 15 minutos y lo vuelve a consultar al expirar la cache.