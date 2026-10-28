"""Olist · del pedido a la reseña — app de Streamlit.

Capa de presentación del proyecto final: estima la probabilidad de que un pedido
entregado reciba una mala reseña (1 o 2 estrellas) y prioriza el 10 % de mayor
riesgo para el equipo de atención.

La app no entrena ni recalcula el modelo: aplica `modelo_riesgo.joblib` (o la API
configurada) siguiendo el contrato del notebook. Ver `ACCESO_APP.md`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
import streamlit as st

import inference
from config import Configuracion, obtener_configuracion
from contract import (
    CONTRATO_INFERENCIA,
    ESTADOS_BRASIL,
    TIPOS_PAGO_CONOCIDOS,
    ErrorContrato,
    ResultadoValidacion,
    validar_lote,
)

TITULO = "Olist · del pedido a la reseña"
SUBTITULO = (
    "Probabilidad de mala reseña (1 o 2 estrellas) para pedidos ya entregados, "
    "ordenada por riesgo para priorizar el contacto."
)
AVISO_DECISION = (
    "La probabilidad es una estimación de apoyo a la decisión: no es una certeza ni "
    "implica causalidad. El contacto humano decide siempre el curso de acción."
)
ETIQUETAS_FECHA = {
    "order_purchase_timestamp": "Fecha de compra",
    "order_approved_at": "Fecha de aprobación del pago",
    "order_delivered_carrier_date": "Fecha de despacho al transportista",
    "order_delivered_customer_date": "Fecha de entrega al cliente",
    "order_estimated_delivery_date": "Fecha estimada de entrega",
}


# --------------------------------------------------------------------------- #
# Arranque
# --------------------------------------------------------------------------- #
def inicializar_estado() -> None:
    st.session_state.setdefault("resultados_lote", None)


def cabecera() -> None:
    st.title(TITULO)
    st.write(SUBTITULO)
    st.caption(AVISO_DECISION)


def barra_lateral(
    config: Configuracion,
    motor: inference.MotorRiesgo | None,
    error_motor: str | None,
) -> None:
    with st.sidebar:
        st.subheader("Estado de la app")
        if motor is not None:
            st.success("Inferencia disponible")
            st.caption(f"Camino: {motor.descripcion}")
        else:
            st.error("Inferencia no disponible", icon="⛔")
            if error_motor:
                st.caption(error_motor)

        st.divider()
        st.caption(f"Capacidad operativa: **{config.capacidad_contacto:.0%}** de los pedidos.")
        st.caption(
            f"Umbrales de riesgo → alto ≥ {config.umbral_riesgo_alto:.0%} · "
            f"medio ≥ {config.umbral_riesgo_medio:.0%}"
        )
        st.divider()
        st.caption("Rutas y acceso: `ACCESO_APP.md`")
        st.caption("Ficha del modelo: `ficha_modelo.md`")


def cargar_motor(config: Configuracion) -> tuple[inference.MotorRiesgo | None, str | None]:
    try:
        return inference.crear_motor(config), None
    except inference.ErrorInferencia as exc:
        return None, str(exc)


def mostrar_error_motor(error_motor: str | None) -> None:
    st.error(
        "**No se puede calcular la probabilidad de mala reseña todavía.**\n\n"
        f"{error_motor or 'El modelo o la API no están configurados.'}\n\n"
        "Revisa `ACCESO_APP.md` para ver la ruta exacta del artefacto esperado."
    )


# --------------------------------------------------------------------------- #
# Predicción individual
# --------------------------------------------------------------------------- #
def _selector_estado(
    etiqueta: str, por_defecto: str, clave: str, contenedor: Any = None
) -> str:
    destino = contenedor if contenedor is not None else st
    opciones = sorted(ESTADOS_BRASIL)
    indice = opciones.index(por_defecto) if por_defecto in opciones else 0
    return destino.selectbox(etiqueta, opciones, index=indice, key=clave)


def _selector_categoria(
    categorias_conocidas: dict[str, list[str]], clave: str, contenedor: Any = None
) -> str:
    destino = contenedor if contenedor is not None else st
    opciones = sorted(categorias_conocidas.get("categoria", []))
    if opciones:
        return destino.selectbox(
            "Categoría del producto",
            opciones,
            key=clave,
            help="Categorías vistas en entrenamiento (OneHotEncoder).",
        )
    return destino.text_input(
        "Categoría del producto",
        value="bed_bath_table",
        key=clave,
        help="El modelo ignora categorías no vistas en entrenamiento.",
    )


def formulario_individual(
    categorias_conocidas: dict[str, list[str]], habilitado: bool
) -> dict[str, Any] | None:
    hoy = date.today()
    with st.form("formulario_individual"):
        st.markdown("**Identificación y fechas** (un pedido entregado)")
        col_id, col_cat = st.columns(2)
        order_id = col_id.text_input("order_id", value="demo-0001", max_chars=64)
        categoria_valor = _selector_categoria(
            categorias_conocidas, "categoria_individual", contenedor=col_cat
        )

        col_f1, col_f2, col_f3 = st.columns(3)
        fecha_compra = col_f1.date_input("Fecha de compra", value=hoy - timedelta(days=20))
        fecha_aprobacion = col_f2.date_input(
            "Aprobación del pago", value=hoy - timedelta(days=19)
        )
        fecha_despacho = col_f3.date_input(
            "Despacho al transportista", value=hoy - timedelta(days=16)
        )
        col_f4, col_f5, _ = st.columns(3)
        fecha_entrega = col_f4.date_input("Entrega al cliente", value=hoy - timedelta(days=8))
        fecha_estimada = col_f5.date_input("Entrega estimada", value=hoy - timedelta(days=6))

        st.markdown("**Logística y vendedores**")
        col_e1, col_e2, col_e3, col_e4 = st.columns(4)
        estado_cliente = _selector_estado("Estado del cliente (UF)", "SP", "uf_cliente", col_e1)
        estado_vendedor = _selector_estado(
            "Estado del vendedor (UF)", "SP", "uf_vendedor", col_e2
        )
        tipo_pago = col_e3.selectbox(
            "Tipo de pago", list(TIPOS_PAGO_CONOCIDOS), index=0, help="Método predominante."
        )
        cuotas_max = col_e4.number_input(
            "Cuotas máximas", min_value=0, max_value=24, value=1, step=1
        )

        st.markdown("**Importes y paquete**")
        col_n1, col_n2, col_n3 = st.columns(3)
        n_items = col_n1.number_input("Artículos (n_items)", min_value=1, max_value=99, value=1, step=1)
        n_vendedores = col_n2.number_input(
            "Vendedores distintos (n_vendedores)", min_value=1, max_value=99, value=1, step=1
        )
        fotos_promedio = col_n3.number_input(
            "Fotos promedio del producto", min_value=0.0, max_value=20.0, value=2.0, step=0.5,
            help="Cantidad promedio de fotos publicadas.",
        )

        col_m1, col_m2, col_m3 = st.columns(3)
        precio_total = col_m1.number_input(
            "Precio total (R$)", min_value=0.0, value=149.90, step=10.0, format="%.2f"
        )
        flete_total = col_m2.number_input(
            "Flete total (R$)", min_value=0.0, value=15.90, step=1.0, format="%.2f"
        )
        peso_total_g = col_m3.number_input(
            "Peso total (g)", min_value=0.0, value=800.0, step=100.0, format="%.0f"
        )

        enviado = st.form_submit_button(
            "Calcular riesgo", type="primary", disabled=not habilitado
        )

    if not enviado:
        return None

    return {
        "order_id": order_id,
        "order_purchase_timestamp": fecha_compra,
        "order_approved_at": fecha_aprobacion,
        "order_delivered_carrier_date": fecha_despacho,
        "order_delivered_customer_date": fecha_entrega,
        "order_estimated_delivery_date": fecha_estimada,
        "estado_cliente": estado_cliente,
        "n_items": n_items,
        "n_vendedores": n_vendedores,
        "precio_total": precio_total,
        "flete_total": flete_total,
        "peso_total_g": peso_total_g,
        "fotos_promedio": fotos_promedio,
        "categoria": categoria_valor,
        "estado_vendedor": estado_vendedor,
        "tipo_pago": tipo_pago,
        "cuotas_max": cuotas_max,
    }


def mostrar_resultado_individual(
    probabilidad: float, config: Configuracion, order_id: str
) -> None:
    nivel = inference.clasificar_riesgo(
        probabilidad, config.umbral_riesgo_alto, config.umbral_riesgo_medio
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Probabilidad de mala reseña", f"{probabilidad:.1%}")
    col2.metric("Nivel de riesgo", nivel)
    col3.metric("Corte operativo", f"{config.capacidad_contacto:.0%} superior")
    st.progress(max(0.0, min(1.0, probabilidad)))

    st.info(inference.recomendacion_prioridad(nivel, config.capacidad_contacto))
    st.caption(f"Pedido evaluado: `{order_id}` · {AVISO_DECISION}")


def pestana_individual(
    motor: inference.MotorRiesgo | None,
    config: Configuracion,
    error_motor: str | None,
) -> None:
    st.subheader("Predicción individual")
    st.write(
        "Completa el contrato del pedido entregado. El formulario valida tipos, fechas "
        "imposibles, valores negativos y combinaciones incoherentes antes de predecir."
    )
    if motor is None:
        mostrar_error_motor(error_motor)

    datos = formulario_individual(
        motor.categorias_conocidas if motor else {}, habilitado=motor is not None
    )
    if datos is None:
        return
    if motor is None:
        st.error("No hay un camino de inferencia disponible; no se muestra ninguna probabilidad.")
        return

    with st.spinner("Validando el pedido y calculando la probabilidad…"):
        try:
            validacion = validar_lote(
                pd.DataFrame([datos]), categorias_conocidas=motor.categorias_conocidas
            )
        except ErrorContrato as exc:
            st.error(f"No se pudo procesar el pedido: {exc}")
            return

        if validacion.n_rechazadas:
            st.error("El pedido no cumple el contrato y no se calculó ninguna probabilidad.")
            st.table(validacion.rechazados[["order_id", "motivo"]])
            return

        for advertencia in validacion.advertencias:
            st.warning(advertencia)

        try:
            probabilidades, fallos = motor.predecir(validacion.datos)
        except inference.ErrorInferencia as exc:
            st.error(str(exc))
            return

    if not fallos.empty:
        st.error(f"No se pudo obtener la probabilidad: {fallos.iloc[0]['motivo']}")
        return

    mostrar_resultado_individual(
        float(probabilidades.iloc[0]), config, str(validacion.datos.iloc[0]["order_id"])
    )


# --------------------------------------------------------------------------- #
# Priorización por lote
# --------------------------------------------------------------------------- #
def construir_tabla_priorizacion(
    validacion: ResultadoValidacion,
    probabilidades: pd.Series,
    config: Configuracion,
) -> tuple[pd.DataFrame, int]:
    """Ordena de mayor a menor riesgo y marca el corte de capacidad."""
    base = pd.DataFrame(
        {
            "order_id": validacion.datos["order_id"].to_numpy(),
            "probabilidad_mala_resena": probabilidades.reindex(validacion.datos.index).to_numpy(),
        }
    )
    if validacion.objetivo is not None:
        base["mala_resena_real"] = pd.to_numeric(
            validacion.objetivo, errors="coerce"
        ).to_numpy()

    base = base.dropna(subset=["probabilidad_mala_resena"])
    base = base.sort_values("probabilidad_mala_resena", ascending=False).reset_index(drop=True)
    base.insert(0, "prioridad", range(1, len(base) + 1))

    corte = inference.cortar_capacidad(len(base), config.capacidad_contacto)
    base["top_capacidad"] = base["prioridad"] <= corte
    base["probabilidad_pct"] = (base["probabilidad_mala_resena"] * 100).round(1)
    base["nivel_riesgo"] = [
        inference.clasificar_riesgo(p, config.umbral_riesgo_alto, config.umbral_riesgo_medio)
        for p in base["probabilidad_mala_resena"]
    ]
    return base, corte


def generar_csv(tabla: pd.DataFrame) -> bytes:
    """CSV descargable con trazabilidad por `order_id`."""
    columnas = [
        "prioridad",
        "order_id",
        "probabilidad_mala_resena",
        "probabilidad_pct",
        "nivel_riesgo",
        "top_capacidad",
    ]
    if "mala_resena_real" in tabla.columns:
        columnas.append("mala_resena_real")
    salida = tabla[columnas].rename(
        columns={
            "prioridad": "orden_prioridad",
            "probabilidad_mala_resena": "probabilidad",
            "probabilidad_pct": "probabilidad_pct",
            "nivel_riesgo": "nivel_riesgo",
            "top_capacidad": "en_10_por_ciento_superior",
            "mala_resena_real": "mala_resena_real",
        }
    )
    return salida.to_csv(index=False).encode("utf-8-sig")


def tabla_visible(tabla: pd.DataFrame) -> pd.DataFrame:
    columnas = {
        "prioridad": "Prioridad",
        "order_id": "order_id",
        "probabilidad_pct": "Probabilidad (%)",
        "nivel_riesgo": "Nivel de riesgo",
        "top_capacidad": "En el 10 % superior",
    }
    if "mala_resena_real" in tabla.columns:
        columnas["mala_resena_real"] = "Mala reseña real"
    return tabla[list(columnas)].rename(columns=columnas)


def mostrar_tabla(tabla: pd.DataFrame) -> None:
    st.dataframe(
        tabla_visible(tabla),
        hide_index=True,
        column_config={
            "Probabilidad (%)": st.column_config.ProgressColumn(
                "Probabilidad (%)", format="%.1f", min_value=0.0, max_value=100.0
            ),
            "Nivel de riesgo": st.column_config.TextColumn("Nivel de riesgo"),
            "En el 10 % superior": st.column_config.CheckboxColumn("En el 10 % superior"),
        },
    )


def ejecutar_lote(
    df_crudo: pd.DataFrame,
    motor: inference.MotorRiesgo,
    config: Configuracion,
    origen: str,
) -> None:
    try:
        validacion = validar_lote(df_crudo, categorias_conocidas=motor.categorias_conocidas)
    except ErrorContrato as exc:
        st.error(f"No se pudo procesar el archivo: {exc}")
        return

    st.caption(
        f"Filas leídas: {len(df_crudo)} · válidas: {validacion.n_validas} · "
        f"rechazadas: {validacion.n_rechazadas}"
    )
    for advertencia in validacion.advertencias:
        st.warning(advertencia)

    if validacion.n_rechazadas:
        with st.expander(f"Filas rechazadas ({validacion.n_rechazadas})", expanded=True):
            st.dataframe(validacion.rechazados, hide_index=True)

    if validacion.n_validas == 0:
        st.error(
            "Ninguna fila cumple el contrato: no hay resultados que mostrar. "
            "Corrige los motivos indicados y vuelve a cargar el archivo."
        )
        return

    with st.spinner("Calculando probabilidades…"):
        try:
            probabilidades, fallos = motor.predecir(validacion.datos)
        except inference.ErrorInferencia as exc:
            st.error(str(exc))
            return

    if not fallos.empty:
        st.warning(
            f"{len(fallos)} pedido(s) no pudieron puntuarse y quedan fuera de la tabla: "
            "revisa el detalle y reintenta."
        )
        st.dataframe(fallos, hide_index=True)

    tabla, corte = construir_tabla_priorizacion(validacion, probabilidades, config)
    if tabla.empty:
        st.error("No se obtuvo ninguna probabilidad válida; no se genera la priorización.")
        return

    st.session_state["resultados_lote"] = {
        "tabla": tabla,
        "corte": corte,
        "origen": origen,
        "advertencias": validacion.advertencias,
        "rechazados": validacion.rechazados,
        "fallos": fallos,
        "tiene_etiqueta": "mala_resena_real" in tabla.columns,
    }

    resumen = st.columns(4)
    resumen[0].metric("Pedidos priorizados", f"{len(tabla)}")
    resumen[1].metric("En el corte", f"{corte}", help=f"{config.capacidad_contacto:.0%} superior")
    resumen[2].metric("Riesgo alto", f"{int((tabla['nivel_riesgo'] == inference.NIVEL_ALTO).sum())}")
    resumen[3].metric(
        "Probabilidad media",
        f"{tabla['probabilidad_mala_resena'].mean():.1%}",
    )

    if "mala_resena_real" in tabla.columns:
        etiqueta = tabla.dropna(subset=["mala_resena_real"])
        if not etiqueta.empty:
            precision = etiqueta.loc[etiqueta["top_capacidad"], "mala_resena_real"].mean()
            st.metric(
                f"Malas reseñas reales en el {config.capacidad_contacto:.0%} superior",
                f"{precision:.1%}",
                help=(
                    "Calculado solo con la columna `mala_resena` que traía el archivo, "
                    "usada como etiqueta de evaluación y nunca como predictor."
                ),
            )

    mostrar_tabla(tabla)
    st.download_button(
        "Descargar priorización (CSV)",
        data=generar_csv(tabla),
        file_name="priorizacion_riesgo.csv",
        mime="text/csv",
        key="descarga_lote",
    )


def pestana_lote(
    motor: inference.MotorRiesgo | None,
    config: Configuracion,
    error_motor: str | None,
) -> None:
    st.subheader("Priorización por lote")
    st.write(
        f"El equipo puede contactar cerca del {config.capacidad_contacto:.0%} de los "
        "pedidos: la tabla ordena por riesgo y marca ese corte."
    )
    if motor is None:
        mostrar_error_motor(error_motor)

    with st.expander("Columnas esperadas del CSV"):
        st.code(", ".join(CONTRATO_INFERENCIA), language="text")
        st.caption(
            "`mala_resena` es opcional: si aparece, se usa solo como etiqueta de "
            "evaluación y nunca como predictor."
        )

    origen = st.radio(
        "Origen de los pedidos",
        ["Conjunto de ejemplo de la app", "Subir un CSV"],
        horizontal=True,
    )

    df_crudo: pd.DataFrame | None = None
    if origen == "Conjunto de ejemplo de la app":
        ruta = config.ruta_datos_ejemplo
        if ruta.exists():
            try:
                df_crudo = pd.read_csv(ruta)
            except Exception as exc:
                st.error(f"No se pudo leer el conjunto de ejemplo: {exc}")
            else:
                st.info(f"Conjunto de ejemplo: `{ruta.name}` con {len(df_crudo)} pedidos ficticios.")
                st.dataframe(df_crudo.head(8), hide_index=True)
        else:
            st.error(
                f"No se encontró el conjunto de ejemplo en `{ruta}`. "
                "Carga un CSV o restaura el archivo desde el repositorio."
            )
    else:
        archivo = st.file_uploader("CSV con el contrato de entrada", type=["csv"])
        if archivo is not None:
            try:
                df_crudo = pd.read_csv(archivo)
            except Exception as exc:
                st.error(f"No se pudo leer el CSV: {exc}")
            else:
                st.success(f"Archivo cargado: {archivo.name} ({len(df_crudo)} filas).")

    if st.button("Calcular prioridades", type="primary", disabled=(df_crudo is None or motor is None)):
        if df_crudo is not None and motor is not None:
            ejecutar_lote(df_crudo, motor, config, origen)


# --------------------------------------------------------------------------- #
# Resultados
# --------------------------------------------------------------------------- #
def pestana_resultados(config: Configuracion) -> None:
    st.subheader("Resultados")
    estado = st.session_state.get("resultados_lote")
    if not estado:
        st.info(
            "Todavía no hay una priorización calculada. Ve a **Priorización por lote**, "
            "carga los pedidos y pulsa «Calcular prioridades»."
        )
        return

    tabla: pd.DataFrame = estado["tabla"]
    st.write(
        f"Origen: **{estado['origen']}** · {len(tabla)} pedidos priorizados · "
        f"corte en los primeros {estado['corte']}."
    )

    resumen = st.columns(3)
    resumen[0].metric("Riesgo alto", f"{int((tabla['nivel_riesgo'] == inference.NIVEL_ALTO).sum())}")
    resumen[1].metric("Riesgo medio", f"{int((tabla['nivel_riesgo'] == inference.NIVEL_MEDIO).sum())}")
    resumen[2].metric("Riesgo bajo", f"{int((tabla['nivel_riesgo'] == inference.NIVEL_BAJO).sum())}")

    mostrar_tabla(tabla)
    st.download_button(
        "Descargar priorización (CSV)",
        data=generar_csv(tabla),
        file_name="priorizacion_riesgo.csv",
        mime="text/csv",
        key="descarga_resultados",
    )

    if estado["rechazados"] is not None and not estado["rechazados"].empty:
        with st.expander(f"Filas rechazadas ({len(estado['rechazados'])})"):
            st.dataframe(estado["rechazados"], hide_index=True)
    if estado["fallos"] is not None and not estado["fallos"].empty:
        with st.expander(f"Pedidos sin probabilidad ({len(estado['fallos'])})"):
            st.dataframe(estado["fallos"], hide_index=True)

    st.caption(
        f"Umbrales: alto ≥ {config.umbral_riesgo_alto:.0%}, medio ≥ "
        f"{config.umbral_riesgo_medio:.0%}. {AVISO_DECISION}"
    )


# --------------------------------------------------------------------------- #
# Ficha del modelo
# --------------------------------------------------------------------------- #
def pestana_ficha(config: Configuracion) -> None:
    st.subheader("Ficha del modelo")
    if config.ruta_ficha.exists():
        st.markdown(config.ruta_ficha.read_text(encoding="utf-8"))
    else:
        st.warning(
            f"No se encontró la ficha del modelo en `{config.ruta_ficha}`. "
            "Restaúrala desde el repositorio: la app solo muestra ese archivo."
        )
    st.caption(
        "Las métricas provienen del notebook y de la ficha; la app no las recalcula "
        "ni las presenta como relaciones causales."
    )


# --------------------------------------------------------------------------- #
def main() -> None:
    st.set_page_config(page_title=TITULO, page_icon="📦", layout="wide")
    inicializar_estado()
    config = obtener_configuracion()
    motor, error_motor = cargar_motor(config)

    cabecera()
    barra_lateral(config, motor, error_motor)

    pestana_1, pestana_2, pestana_3, pestana_4 = st.tabs(
        ["Predicción individual", "Priorización por lote", "Resultados", "Ficha del modelo"]
    )
    with pestana_1:
        pestana_individual(motor, config, error_motor)
    with pestana_2:
        pestana_lote(motor, config, error_motor)
    with pestana_3:
        pestana_resultados(config)
    with pestana_4:
        pestana_ficha(config)


if __name__ == "__main__":
    main()
