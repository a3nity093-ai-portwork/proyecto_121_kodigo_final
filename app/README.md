# App Olist

Aplicación Streamlit que estima el riesgo de una mala reseña para pedidos entregados y permite priorizar el 10 % de mayor riesgo.

## Ejecutar

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r app\requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app\app.py
```

La aplicación necesita el modelo en:

```text
model/modelo_riesgo.joblib
```

Si el modelo todavía no existe, la interfaz arranca y muestra el error correspondiente, pero no genera probabilidades.

## Funciones

- Predicción individual.
- Priorización de pedidos desde un CSV.
- Marcado del 10 % superior de riesgo.
- Descarga de resultados.
- Consulta de la ficha del modelo.

## Comunicación

La app puede usar uno de estos caminos:

- **Modelo local:** `model/modelo_riesgo.joblib`.
- **API:** petición `POST` a `{API_URL}/riesgo` con las 17 columnas de entrada del contrato, sin `mala_resena`.

Para usar la API, configura en `app/.streamlit/secrets.toml`:

```toml
modo_inferencia = "api"
api_url = ""
```

La respuesta debe incluir una probabilidad, por ejemplo:

```json
{"probabilidad": 0.37}
```

Las rutas y métodos están resumidos en [`ACCESO_APP.md`](../ACCESO_APP.md).

## Estructura

```text
app/
├── app.py                 # Interfaz Streamlit
├── config.py              # Configuración y rutas
├── contract.py            # Validación del contrato
├── inference.py           # Inferencia local o por API
├── api_client.py          # Cliente HTTP de la API
├── preparacion.py         # Preparación usada por el modelo
├── ficha_modelo.md        # Ficha visible en la app
├── datos/                 # CSV de ejemplo
├── tests/                 # Pruebas
├── requirements.txt       # Dependencias de ejecución
└── .streamlit/            # Configuración local
```

El modelo se guarda fuera de esta carpeta, en `model/`.
