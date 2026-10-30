# Acceso a la app

## Ejecutar en local

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r app\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app\app.py
```

La app se abrirá en la URL local que muestre Streamlit, normalmente:

```text
http://localhost:8501
```

Pruebas:

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests -q
```

## Rutas

| Recurso | Ruta |
| :--- | :--- |
| App | `app/app.py` |
| Modelo local | `model/modelo_riesgo.joblib` |
| Configuración API | Panel lateral de la app |
| CSV de ejemplo | `app/datos/ejemplo_pedidos.csv` |
| Ficha del modelo | `app/ficha_modelo.md` |

## Comunicación con la app

### Modelo local

La app carga automáticamente:

```text
model/modelo_riesgo.joblib
```

### API externa

Escribe la URL base de la API directamente en el panel lateral de la app.
Ejemplos:

```text
http://localhost:8000
https://TU-API.onrender.com
```

No agregues `/riesgo` al final: la app lo agrega automáticamente.

La app envía:

```http
POST {api_url}/riesgo
Content-Type: application/json
```

El cuerpo contiene las 17 columnas de entrada del contrato. No incluye `mala_resena`.

Respuesta mínima esperada:

```json
{"probabilidad": 0.37}
```

La app también muestra el umbral usado por la API, el estado `riesgo_alto` y la
respuesta JSON completa.
