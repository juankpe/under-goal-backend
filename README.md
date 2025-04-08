# Under Goal Backend

Este backend usa FastAPI y se conecta a la API-FOOTBALL para obtener partidos en vivo y clasificarlos por riesgo de goles.

## Cómo ejecutar

1. Instala las dependencias:

```bash
pip install -r requirements.txt
```

2. Ejecuta el servidor:

```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```

## Cómo desplegar en Render

- Crea un nuevo Web Service
- Elige entorno Python
- Comando de inicio:

```
uvicorn main:app --host 0.0.0.0 --port 10000
```