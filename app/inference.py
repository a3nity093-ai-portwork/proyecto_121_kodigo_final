"""Carga del modelo y cálculo de probabilidades.

Único camino de inferencia de la app:

- `modo_inferencia = "local"` (por defecto): pipeline serializado en
  `modelo_riesgo.joblib`, cargado una sola vez con `st.cache_resource`.
- `modo_inferencia = "api"`: `POST {api_url}/riesgo` con las 17 columnas del
  contrato, un pedido por petición.

Nunca se recalcula ni se reentrena nada aquí: solo se aplica el pipeline
guardado, que ya incluye `preparacion.crear_variables`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd
import streamlit as st

import api_client
import preparacion  # noqa: F401  (joblib necesita este módulo para despicklear)
from config import Configuracion
from contract import CONTRATO_INFERENCIA

NIVEL_ALTO = "Alto"
NIVEL_MEDIO = "Medio"
NIVEL_BAJO = "Bajo"

PASOS_ESPERADOS = ("preparador", "filtro_columnas", "preprocesador", "clasificador")


class ErrorInferencia(RuntimeError):
    """No se puede predecir con el modelo o la API configurados."""


# --------------------------------------------------------------------------- #
# Modelo local
# --------------------------------------------------------------------------- #
def cargar_modelo_desde_archivo(ruta: str | Path):
    """Carga y comprueba el pipeline serializado."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorInferencia(
            f"No se encontró el modelo en '{ruta}'. Copia `modelo_riesgo.joblib` "
            "(generado en el notebook) en `model/` o define "
            "`OLIST_MODELO_PATH`. Ver ACCESO_APP.md."
        )

    import joblib

    try:
        modelo = joblib.load(ruta)
    except Exception as exc:  # archivo corrupto o versiones incompatibles
        raise ErrorInferencia(
            "No se pudo deserializar `modelo_riesgo.joblib`. Revisa que el archivo no esté "
            "corrupto y que las versiones de scikit-learn/xgboost coincidan con las del "
            f"entrenamiento (notebook, Parte 5). Detalle: {type(exc).__name__}: {exc}"
        ) from exc

    if not hasattr(modelo, "predict_proba"):
        raise ErrorInferencia(
            "El archivo cargado no expone `predict_proba`: no parece el pipeline de riesgo."
        )

    pasos = getattr(modelo, "named_steps", None)
    if pasos is not None:
        ausentes = [paso for paso in PASOS_ESPERADOS if paso not in pasos]
        if ausentes:
            raise ErrorInferencia(
                "El pipeline cargado no tiene los pasos esperados del notebook: "
                + ", ".join(ausentes)
            )
    return modelo


@st.cache_resource(show_spinner=False)
def obtener_modelo(ruta: str):
    """Carga perezosa y cacheada del pipeline (una sola vez por proceso)."""
    return cargar_modelo_desde_archivo(ruta)


def obtener_categorias_conocidas(modelo) -> dict[str, list[str]]:
    """Categorías vistas en entrenamiento, leídas del OneHotEncoder del pipeline."""
    try:
        preprocesador = modelo.named_steps["preprocesador"]
        for nombre, transformador, columnas in preprocesador.transformers_:
            if nombre != "cat" or not hasattr(transformador, "categories_"):
                continue
            categorias = {
                str(columna): [str(valor) for valor in valores]
                for columna, valores in zip(columnas, transformador.categories_)
            }
            if categorias:
                return categorias
    except Exception:  # estructura inesperada: no es crítico para predecir
        return {}
    return {}


# --------------------------------------------------------------------------- #
# Motor de inferencia
# --------------------------------------------------------------------------- #
@dataclass
class MotorRiesgo:
    """Ejecuta la predicción con el único camino configurado."""

    modo: str
    modelo: object | None = None
    api_url: str | None = None
    api_timeout: float = 60.0
    categorias_conocidas: dict[str, list[str]] = field(default_factory=dict)

    @property
    def descripcion(self) -> str:
        if self.modo == "api":
            return f"API en Render ({self.api_url}/riesgo)"
        return "Modelo local (`modelo_riesgo.joblib`)"

    def predecir(
        self, datos: pd.DataFrame
    ) -> tuple[pd.Series, pd.DataFrame]:
        """Devuelve (probabilidades, fallos) alineados con `datos`.

        `fallos` solo se llena en modo API, donde una petición puede fallar sin
        invalidar el resto del lote.
        """
        if list(datos.columns) != list(CONTRATO_INFERENCIA):
            raise ErrorInferencia(
                "Las columnas enviadas al modelo no coinciden con el contrato de inferencia."
            )
        if datos.empty:
            raise ErrorInferencia("No hay pedidos válidos para predecir.")

        if self.modo == "api":
            return self._predecir_api(datos)
        return self._predecir_local(datos)

    def _predecir_local(self, datos: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
        if self.modelo is None:
            raise ErrorInferencia("El modelo local no está cargado.")
        try:
            probabilidades = self.modelo.predict_proba(datos)
        except Exception as exc:
            raise ErrorInferencia(
                "El modelo no pudo calcular la probabilidad con estas filas. Verifica que "
                "el archivo `modelo_riesgo.joblib` corresponda al contrato del notebook. "
                f"Detalle: {type(exc).__name__}: {exc}"
            ) from exc

        if probabilidades.ndim != 2 or probabilidades.shape[1] < 2:
            raise ErrorInferencia("El modelo no devolvió probabilidades de dos clases.")

        serie = pd.Series(probabilidades[:, 1], index=datos.index, name="probabilidad")
        serie = serie.clip(lower=0.0, upper=1.0)
        return serie, pd.DataFrame(columns=["order_id", "motivo"])

    def _predecir_api(self, datos: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
        valores: list[float] = []
        fallos: list[dict[str, str]] = []
        for indice, fila in datos.iterrows():
            try:
                valores.append(
                    api_client.predecir_una(
                        self.api_url or "", fila.to_dict(), self.api_timeout
                    )
                )
            except api_client.ErrorAPI as exc:
                valores.append(float("nan"))
                fallos.append({"order_id": str(fila["order_id"]), "motivo": str(exc)})

        serie = pd.Series(valores, index=datos.index, name="probabilidad").clip(0.0, 1.0)
        return serie, pd.DataFrame(fallos, columns=["order_id", "motivo"])


def crear_motor(config: Configuracion) -> MotorRiesgo:
    """Construye el motor según `config.modo_inferencia`."""
    if config.modo_inferencia == "api":
        if not config.api_url:
            raise ErrorInferencia(
                "El modo de inferencia es 'api' pero no hay URL configurada. Define "
                "`OLIST_API_URL` o `api_url` en `.streamlit/secrets.toml`."
            )
        return MotorRiesgo(
            modo="api", api_url=config.api_url, api_timeout=config.api_timeout_segundos
        )

    modelo = obtener_modelo(str(config.ruta_modelo))
    return MotorRiesgo(
        modo="local",
        modelo=modelo,
        categorias_conocidas=obtener_categorias_conocidas(modelo),
    )


# --------------------------------------------------------------------------- #
# Reglas de presentación
# --------------------------------------------------------------------------- #
def clasificar_riesgo(probabilidad: float, umbral_alto: float, umbral_medio: float) -> str:
    """Clasifica la probabilidad en una etiqueta comprensible."""
    if probabilidad is None or (isinstance(probabilidad, float) and math.isnan(probabilidad)):
        return "Sin dato"
    if probabilidad >= umbral_alto:
        return NIVEL_ALTO
    if probabilidad >= umbral_medio:
        return NIVEL_MEDIO
    return NIVEL_BAJO


def recomendacion_prioridad(nivel: str, capacidad: float) -> str:
    """Traduce el nivel de riesgo a una acción operativa sugerida."""
    if nivel == NIVEL_ALTO:
        return (
            "Prioridad alta: contactar primero. Solo hay capacidad para el "
            f"{capacidad:.0%} de los pedidos, así que este caso compite por ese cupo."
        )
    if nivel == NIVEL_MEDIO:
        return (
            "Prioridad media: incluir en la cola de contacto si queda capacidad "
            f"después del {capacidad:.0%} de mayor riesgo."
        )
    return "Prioridad baja: no requiere contacto proactivo con la capacidad actual."


def cortar_capacidad(n_filas: int, capacidad: float) -> int:
    """Número de pedidos que entran en el corte operativo (al menos 1)."""
    if n_filas <= 0:
        return 0
    return max(1, math.ceil(n_filas * capacidad))
