from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
CONTRACT = [
    "order_id",
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
    "estado_cliente",
    "n_items",
    "n_vendedores",
    "precio_total",
    "flete_total",
    "peso_total_g",
    "fotos_promedio",
    "categoria",
    "estado_vendedor",
    "tipo_pago",
    "cuotas_max",
]


DEFAULT_API_URL = "http://localhost:8000"


def api_url() -> str:
    return str(st.session_state.get("api_url", "")).strip().rstrip("/")


def call_api(row: dict) -> dict:
    url = api_url()
    if not url:
        raise RuntimeError("Escribe la URL de la API en el panel lateral.")
    response = requests.post(f"{url}/riesgo", json=row, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(
            f"La API respondió HTTP {response.status_code}: {response.text[:300]}"
        )
    return response.json()


def load_examples() -> pd.DataFrame:
    path = BASE_DIR / "datos" / "ejemplo_pedidos.csv"
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=CONTRACT)


def risk_page() -> None:
    st.title("Riesgo de mala reseña")
    st.write(
        "Consulta la probabilidad de que un pedido entregado reciba una reseña "
        "de 1 o 2 estrellas."
    )
    st.info(
        "El umbral de riesgo alto lo determina la API. La app no modifica ni "
        "recalcula ese valor."
    )
    data = load_examples()
    if data.empty:
        st.info("No hay pedidos de ejemplo. Completa el formulario para consultar la API.")
        row = {column: "" for column in CONTRACT}
        row.update(
            {
                "order_id": "pedido-manual",
                "order_purchase_timestamp": "2018-03-07 22:02:23",
                "order_estimated_delivery_date": "2018-03-15 00:00:00",
                "estado_cliente": "SP",
                "n_items": 1,
                "n_vendedores": 1,
                "precio_total": 0.0,
                "flete_total": 0.0,
                "peso_total_g": 0.0,
                "fotos_promedio": 0.0,
                "categoria": "unknown",
                "estado_vendedor": "unknown",
                "tipo_pago": "credit_card",
                "cuotas_max": 1,
            }
        )
    else:
        selected = st.selectbox("Pedido de ejemplo", data["order_id"].tolist())
        row = data.loc[data["order_id"].eq(selected), CONTRACT].iloc[0].to_dict()

    with st.form("risk-form"):
        st.caption("Las fechas deben usar el formato AAAA-MM-DD HH:MM:SS.")
        edited = {}
        cols = st.columns(2)
        for index, column in enumerate(CONTRACT):
            value = row.get(column)
            edited[column] = cols[index % 2].text_input(column, "" if pd.isna(value) else str(value))
        submitted = st.form_submit_button("Consultar riesgo")

    if submitted:
        try:
            result = call_api(edited)
            probability = float(result["probabilidad"])
            threshold = result.get("umbral_riesgo_alto")
            riesgo_alto = bool(result.get("riesgo_alto"))

            probability_col, threshold_col, status_col = st.columns(3)
            probability_col.metric(
                "Probabilidad de mala reseña", f"{probability:.1%}"
            )
            threshold_col.metric(
                "Umbral de riesgo alto",
                f"{float(threshold):.1%}" if threshold is not None else "No informado",
            )
            if riesgo_alto:
                status_col.error("Riesgo alto")
            else:
                status_col.success("Riesgo no alto")

            st.subheader("Interpretación")
            if threshold is None:
                st.warning("La API no informó el umbral utilizado.")
            elif riesgo_alto:
                st.warning(
                    "La probabilidad alcanza o supera el umbral operativo. "
                    "Este pedido debería priorizarse para contacto humano."
                )
            else:
                st.success(
                    "La probabilidad está por debajo del umbral operativo de "
                    "priorización."
                )

            st.subheader("Respuesta completa de la API")
            st.json(result)
            with st.expander("Ver respuesta JSON como texto"):
                st.code(json.dumps(result, ensure_ascii=False, indent=2), language="json")
        except (requests.RequestException, RuntimeError, ValueError, KeyError) as error:
            st.error(f"No fue posible consultar la API. Detalle: {error}")


def comments_page() -> None:
    st.title("Comentarios y sentimiento")
    path = BASE_DIR.parent / "sentimiento_muestra.csv"
    if not path.exists():
        st.warning("No se encontró sentimiento_muestra.csv.")
        return
    data = pd.read_csv(path)
    st.dataframe(data, use_container_width=True)
    if {"sentimiento_estrellas", "sentimiento_modelo"}.issubset(data.columns):
        st.metric(
            "Coincidencia sentimiento-estrellas",
            f"{data['sentimiento_estrellas'].eq(data['sentimiento_modelo']).mean():.1%}",
        )
        st.subheader("Desacuerdos para explorar")
        st.dataframe(
            data.loc[
                ~data["sentimiento_estrellas"].eq(data["sentimiento_modelo"])
            ].head(20),
            use_container_width=True,
        )


def forecast_page() -> None:
    st.title("Pronóstico de pedidos de junio de 2018")
    path = BASE_DIR.parent / "pronostico_junio.csv"
    if not path.exists():
        st.info(
            "La app está preparada para esta página, pero todavía no existe "
            "`pronostico_junio.csv`. Genéralo desde el notebook."
        )
        return
    data = pd.read_csv(path)
    st.line_chart(data.set_index("fecha")[["pronostico", "bajo", "alto"]])
    st.dataframe(data, use_container_width=True)


def model_card_page() -> None:
    st.title("Ficha del modelo")
    path = BASE_DIR.parent / "app" / "ficha_modelo.md"
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8"))
    else:
        st.warning("Todavía no existe ficha_modelo.md.")


st.set_page_config(page_title="Olist", page_icon="📦", layout="wide")
st.sidebar.header("Conexión con la API")
st.sidebar.text_input(
    "URL de la API",
    value=st.session_state.get("api_url", DEFAULT_API_URL),
    key="api_url",
    help="Ejemplo local: http://localhost:8000. No agregues /riesgo al final.",
)
st.sidebar.caption(
    "La URL se configura aquí dentro de la app; no se usan secrets.toml."
)
pages = {
    "Aplicación": [
        st.Page(risk_page, title="Riesgo", icon=":material/warning:"),
        st.Page(comments_page, title="Comentarios", icon=":material/forum:"),
        st.Page(forecast_page, title="Pronóstico", icon=":material/show_chart:"),
        st.Page(model_card_page, title="Ficha del modelo", icon=":material/article:"),
    ]
}
st.navigation(pages).run()
