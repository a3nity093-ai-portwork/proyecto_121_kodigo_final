# Acceso a la app

## Flujo actual

La app funciona exclusivamente mediante la API. Primero se inicia la API y
después la app de Streamlit. La URL de la API se escribe directamente en el
panel lateral de la app; no se usan `secrets.toml`.

## Ejecutar la API en local

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r api\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload
```

La API quedará disponible en:

```text
http://localhost:8000
```

Documentación interactiva:

```text
http://localhost:8000/docs
```

| Método | Ruta | Función |
| :--- | :--- | :--- |
| `GET` | `/` | Confirma que el servicio está activo |
| `POST` | `/riesgo` | Calcula la probabilidad de mala reseña |

## Ejecutar la app en local

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r app\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app\app.py
```

La app se abrirá normalmente en:

```text
http://localhost:8501
```

En el panel lateral, configura la URL base de la API:

```text
http://localhost:8000
```

No agregues `/riesgo`; la app lo añade automáticamente.

## Rutas y archivos principales

| Recurso | Ruta |
| :--- | :--- |
| API | `api/main.py` |
| Modelo utilizado por la API | `api/modelo_riesgo.joblib` |
| Preparación del modelo | `api/preparacion.py` |
| App | `app/app.py` |
| CSV de ejemplo | `app/datos/ejemplo_pedidos.csv` |
| Pronóstico | `pronostico_junio.csv` |
| Resultados de sentimiento | `sentimiento_muestra.csv` |
| Ficha del modelo | `app/ficha_modelo.md` |

## Comunicación con la API

La app envía:

```http
POST {api_url}/riesgo
Content-Type: application/json
```

El cuerpo contiene las 17 columnas de entrada del contrato y no incluye
`mala_resena`.

Respuesta:

```json
{
  "probabilidad": 0.0743,
  "riesgo_alto": false,
  "umbral_riesgo_alto": 0.37,
  "order_id": "pedido_entrega_anticipada_bajo_riesgo"
}
```

La app muestra la probabilidad, el umbral utilizado, el estado
`riesgo_alto`, una interpretación y la respuesta JSON completa.

## Secciones de la app

- **Riesgo:** selecciona un pedido de ejemplo y consulta la API.
- **Comentarios:** muestra los resultados de `sentimiento_muestra.csv`.
- **Pronóstico:** muestra `pronostico_junio.csv`.
- **Ficha del modelo:** muestra `app/ficha_modelo.md`.
