"""Transformaciones de variables del contrato de Olist.

Este módulo reproduce **exactamente** las funciones que el notebook
`Plantilla_Proyecto_Final_OLIST.ipynb` escribe con `%%writefile preparacion.py`.

El pipeline serializado en `modelo_riesgo.joblib` guarda referencias a
`preparacion.crear_variables` y `preparacion.seleccionar_columnas_pipeline`,
por lo que:

- el módulo debe estar importable como `preparacion` (raíz del proyecto);
- no se deben renombrar las funciones ni cambiar sus reglas.

Cualquier cambio de reglas aquí invalida el modelo entrenado.
"""

import pandas as pd
import numpy as np


def crear_variables(df):
    """
    Función de preparación de variables para el modelo de riesgo de Olist.
    Recibe el DataFrame con las columnas del contrato original y aplica transformaciones.
    """
    df_transformed = df.copy()

    # 1. Imputación de fechas vacías usando las de referencia
    df_transformed['order_approved_at'] = df_transformed['order_approved_at'].fillna(df_transformed['order_purchase_timestamp'])
    df_transformed['order_delivered_carrier_date'] = df_transformed['order_delivered_carrier_date'].fillna(df_transformed['order_estimated_delivery_date'])
    df_transformed['order_delivered_customer_date'] = df_transformed['order_delivered_customer_date'].fillna(df_transformed['order_estimated_delivery_date'])

    # 2. Conversión a formato datetime si no lo están
    for col in ['order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_date', 'order_delivered_customer_date', 'order_estimated_delivery_date']:
        df_transformed[col] = pd.to_datetime(df_transformed[col])

    # 3. Creación de variables de tiempo (días de tránsito, retrasos prometidos)
    # Tiempo real en que tardó en llegar el pedido al transportista
    df_transformed['tiempo_a_despacho_dias'] = (df_transformed['order_delivered_carrier_date'] - df_transformed['order_purchase_timestamp']).dt.total_seconds() / 86400.0
    # Tiempo en tránsito real
    df_transformed['tiempo_transito_dias'] = (df_transformed['order_delivered_customer_date'] - df_transformed['order_delivered_carrier_date']).dt.total_seconds() / 86400.0
    # Días de retraso respecto a la estimación (si llegó antes, el valor será negativo o cero)
    df_transformed['dias_retraso_real'] = (df_transformed['order_delivered_customer_date'] - df_transformed['order_estimated_delivery_date']).dt.total_seconds() / 86400.0
    df_transformed['dias_retraso'] = df_transformed['dias_retraso_real'].clip(lower=0)  # Forzar negativos a 0

    return df_transformed


def seleccionar_columnas_pipeline(df):
    """
    Filtra y ordena las columnas del dataframe para el preprocesamiento final.
    """
    features_numericas = [
        'n_items', 'n_vendedores', 'precio_total', 'flete_total', 'peso_total_g',
        'fotos_promedio', 'cuotas_max', 'tiempo_a_despacho_dias', 'tiempo_transito_dias', 'dias_retraso'
    ]
    features_categoricas = ['estado_cliente', 'estado_vendedor', 'tipo_pago', 'categoria']
    return df[features_numericas + features_categoricas]
