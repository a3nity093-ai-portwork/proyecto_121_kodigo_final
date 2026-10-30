from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import joblib
import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field, validator

from preparacion import crear_variables, seleccionar_columnas_pipeline  # noqa: F401

CONTRACT_COLUMNS = (
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
)


class Pedido(BaseModel):
    order_id: str = Field(min_length=1)
    order_purchase_timestamp: datetime
    order_approved_at: Optional[datetime] = None
    order_delivered_carrier_date: Optional[datetime] = None
    order_delivered_customer_date: Optional[datetime] = None
    order_estimated_delivery_date: datetime
    estado_cliente: str = Field(min_length=1)
    n_items: int = Field(ge=1)
    n_vendedores: int = Field(ge=1)
    precio_total: float = Field(ge=0)
    flete_total: float = Field(ge=0)
    peso_total_g: float = Field(ge=0)
    fotos_promedio: float = Field(ge=0)
    categoria: str = Field(min_length=1)
    estado_vendedor: str = Field(min_length=1)
    tipo_pago: str = Field(min_length=1)
    cuotas_max: int = Field(ge=0, le=24)

    @validator(
        "precio_total",
        "flete_total",
        "peso_total_g",
        "fotos_promedio",
        pre=True,
    )
    def validar_finitos(cls, value):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("El valor debe ser finito.")
        return value


def _modelo():
    path = Path(
        os.environ.get(
            "OLIST_MODELO_PATH",
            str(Path(__file__).resolve().parent / "modelo_riesgo.joblib"),
        )
    )
    if not path.exists():
        raise RuntimeError(f"No se encontró el modelo en {path}.")
    return joblib.load(path)


app = FastAPI(title="API de riesgo Olist", version="1.0.0")
model = _modelo()
threshold = float(os.environ.get("OLIST_UMBRAL_RIESGO_ALTO", "0.37"))
if not 0 < threshold < 1:
    raise RuntimeError("OLIST_UMBRAL_RIESGO_ALTO debe estar entre 0 y 1.")


@app.get("/")
def health():
    return {"ok": True, "servicio": "olist-risk-api"}


@app.post("/riesgo")
def predict(pedido: Pedido):
    values = pedido.dict()
    row = pd.DataFrame([{column: values[column] for column in CONTRACT_COLUMNS}])
    probability = float(model.predict_proba(row)[0, 1])
    return {
        "probabilidad": probability,
        "riesgo_alto": probability >= threshold,
        "umbral_riesgo_alto": threshold,
        "order_id": pedido.order_id,
    }
