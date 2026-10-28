"""Cliente mínimo de la API de riesgo (Render, `POST /riesgo`).

Se usa **solo** cuando `modo_inferencia = "api"`. El contrato de entrada es el
mismo del modelo: las 17 columnas de `CONTRATO_INFERENCIA`.

Cualquier fallo (timeout, HTTP no exitoso, JSON inválido, respuesta sin
probabilidad) se convierte en `ErrorAPI`: la app nunca inventa una probabilidad.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any, Mapping

import pandas as pd
import requests

from contract import CONTRATO_INFERENCIA

#: Nombres aceptados para la probabilidad en la respuesta de la API.
CLAVES_PROBABILIDAD = (
    "probabilidad",
    "probabilidad_mala_resena",
    "probability",
    "prob",
    "riesgo",
    "score",
    "p_mala_resena",
)

_LARGO_MAXIMO_DETALLE = 300


class ErrorAPI(RuntimeError):
    """La API no respondió como se esperaba."""


def _serializar(valor: Any) -> Any:
    """Convierte valores de pandas/numpy a JSON estricto."""
    if valor is None:
        return None
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return valor.isoformat()
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(valor, "item"):
        try:
            return valor.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(valor, str):
        return valor
    return valor


def _buscar_probabilidad(payload: Any, profundidad: int = 3) -> float | None:
    if profundidad < 0:
        return None
    if isinstance(payload, Mapping):
        for clave in CLAVES_PROBABILIDAD:
            if clave in payload:
                valor = payload[clave]
                if isinstance(valor, (int, float)):
                    return float(valor)
                if isinstance(valor, str):
                    try:
                        return float(valor)
                    except ValueError:
                        continue
        for valor in payload.values():
            encontrado = _buscar_probabilidad(valor, profundidad - 1)
            if encontrado is not None:
                return encontrado
    elif isinstance(payload, (list, tuple)):
        for elemento in payload:
            encontrado = _buscar_probabilidad(elemento, profundidad - 1)
            if encontrado is not None:
                return encontrado
    return None


def _normalizar_probabilidad(valor: float) -> float:
    if math.isnan(valor) or math.isinf(valor):
        raise ErrorAPI("La API devolvió una probabilidad no numérica.")
    if valor > 1.0:
        valor = valor / 100.0
    if not 0.0 <= valor <= 1.0:
        raise ErrorAPI(f"La API devolvió una probabilidad fuera de rango: {valor}.")
    return valor


def predecir_una(url: str, fila: Mapping[str, Any], timeout: float) -> float:
    """Pide la probabilidad de mala reseña de un pedido a la API."""
    if not url:
        raise ErrorAPI("No hay URL de API configurada (modo_inferencia = 'api').")

    cuerpo = {columna: _serializar(fila[columna]) for columna in CONTRATO_INFERENCIA}
    endpoint = url.rstrip("/") + "/riesgo"

    try:
        respuesta = requests.post(endpoint, json=cuerpo, timeout=timeout)
    except requests.Timeout as exc:
        raise ErrorAPI(f"La API no respondió en {timeout:.0f} segundos.") from exc
    except requests.RequestException as exc:
        raise ErrorAPI(f"No se pudo conectar con la API: {exc}") from exc

    if respuesta.status_code != 200:
        detalle = (respuesta.text or "").strip()[:_LARGO_MAXIMO_DETALLE]
        raise ErrorAPI(
            f"La API respondió HTTP {respuesta.status_code}."
            + (f" Detalle: {detalle}" if detalle else "")
        )

    try:
        payload = respuesta.json()
    except ValueError as exc:
        raise ErrorAPI("La API devolvió una respuesta que no es JSON válido.") from exc

    probabilidad = _buscar_probabilidad(payload)
    if probabilidad is None:
        raise ErrorAPI(
            "La respuesta de la API no incluye una probabilidad reconocible "
            f"(claves esperadas: {', '.join(CLAVES_PROBABILIDAD[:3])})."
        )
    return _normalizar_probabilidad(probabilidad)
