"""Transformaciones exactas usadas por el pipeline de riesgo de Olist."""

import numpy as np
import pandas as pd


def crear_variables(df):
    df_transformed = df.copy()
    df_transformed["order_approved_at"] = df_transformed[
        "order_approved_at"
    ].fillna(df_transformed["order_purchase_timestamp"])
    df_transformed["order_delivered_carrier_date"] = df_transformed[
        "order_delivered_carrier_date"
    ].fillna(df_transformed["order_estimated_delivery_date"])
    df_transformed["order_delivered_customer_date"] = df_transformed[
        "order_delivered_customer_date"
    ].fillna(df_transformed["order_estimated_delivery_date"])

    for col in [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ]:
        df_transformed[col] = pd.to_datetime(df_transformed[col])

    df_transformed["tiempo_a_despacho_dias"] = (
        df_transformed["order_delivered_carrier_date"]
        - df_transformed["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400.0
    df_transformed["tiempo_transito_dias"] = (
        df_transformed["order_delivered_customer_date"]
        - df_transformed["order_delivered_carrier_date"]
    ).dt.total_seconds() / 86400.0
    df_transformed["dias_retraso_real"] = (
        df_transformed["order_delivered_customer_date"]
        - df_transformed["order_estimated_delivery_date"]
    ).dt.total_seconds() / 86400.0
    df_transformed["dias_retraso"] = df_transformed["dias_retraso_real"].clip(lower=0)
    return df_transformed


def seleccionar_columnas_pipeline(df):
    features_numericas = [
        "n_items",
        "n_vendedores",
        "precio_total",
        "flete_total",
        "peso_total_g",
        "fotos_promedio",
        "cuotas_max",
        "tiempo_a_despacho_dias",
        "tiempo_transito_dias",
        "dias_retraso",
    ]
    features_categoricas = [
        "estado_cliente",
        "estado_vendedor",
        "tipo_pago",
        "categoria",
    ]
    return df[features_numericas + features_categoricas]
