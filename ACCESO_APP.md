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
| Configuración API | `app/.streamlit/secrets.toml` |
| CSV de ejemplo | `app/datos/ejemplo_pedidos.csv` |
| Ficha del modelo | `app/ficha_modelo.md` |

## Comunicación con la app

### Modelo local

La app carga automáticamente:

```text
model/modelo_riesgo.joblib
```

### API externa

Configura la URL:

```toml
modo_inferencia = "api"
api_url = "https://TU-API.onrender.com"
```

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

También se acepta una probabilidad entre 0 y 100.

No hay API propia en este repositorio todavía; la app solo puede consumir una API externa cuando exista y esté configurada.
