"""Configuración de la app: rutas, secretos y umbrales de decisión.

Precedencia: variable de entorno > `st.secrets` > valor por defecto.
Ningún secreto se escribe en el código ni se versiona.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent

MODOS_VALIDOS = ("local", "api")


@dataclass(frozen=True)
class Configuracion:
    """Parámetros efectivos de una ejecución de la app."""

    modo_inferencia: str
    ruta_modelo: Path
    ruta_ficha: Path
    ruta_datos_ejemplo: Path
    api_url: str | None
    api_timeout_segundos: float
    capacidad_contacto: float
    umbral_riesgo_alto: float
    umbral_riesgo_medio: float

    @property
    def usa_api(self) -> bool:
        return self.modo_inferencia == "api"


def _desde_secrets(clave: str) -> Any:
    try:
        import streamlit as st

        return st.secrets.get(clave)  # type: ignore[union-attr]
    except Exception:  # sin secrets.toml, sin runtime o clave ausente
        return None


def _valor(clave_secreto: str, variable_entorno: str, por_defecto: Any) -> Any:
    valor = os.environ.get(variable_entorno)
    if valor is not None and str(valor).strip() != "":
        return valor
    valor = _desde_secrets(clave_secreto)
    if valor is not None and str(valor).strip() != "":
        return valor
    return por_defecto


def _flotante(valor: Any, por_defecto: float) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return por_defecto


def obtener_configuracion() -> Configuracion:
    """Lee la configuración del entorno/secrets con valores por defecto seguros."""
    modo = str(_valor("modo_inferencia", "OLIST_MODO_INFERENCIA", "local")).strip().lower()
    if modo not in MODOS_VALIDOS:
        modo = "local"

    api_url = _valor("api_url", "OLIST_API_URL", None)
    api_url = str(api_url).strip() if api_url else None

    ruta_modelo = Path(str(_valor("modelo_path", "OLIST_MODELO_PATH", BASE_DIR.parent / "model" / "modelo_riesgo.joblib")))
    ruta_ficha = Path(str(_valor("ficha_path", "OLIST_FICHA_PATH", BASE_DIR / "ficha_modelo.md")))
    ruta_datos = Path(str(_valor("datos_ejemplo_path", "OLIST_DATOS_EJEMPLO_PATH", BASE_DIR / "datos" / "ejemplo_pedidos.csv")))

    return Configuracion(
        modo_inferencia=modo,
        ruta_modelo=ruta_modelo,
        ruta_ficha=ruta_ficha,
        ruta_datos_ejemplo=ruta_datos,
        api_url=api_url,
        api_timeout_segundos=_flotante(_valor("api_timeout_segundos", "OLIST_API_TIMEOUT", 60), 60.0),
        capacidad_contacto=_flotante(_valor("capacidad_contacto", "OLIST_CAPACIDAD_CONTACTO", 0.10), 0.10),
        umbral_riesgo_alto=_flotante(_valor("umbral_riesgo_alto", "OLIST_UMBRAL_ALTO", 0.45), 0.45),
        umbral_riesgo_medio=_flotante(_valor("umbral_riesgo_medio", "OLIST_UMBRAL_MEDIO", 0.20), 0.20),
    )
