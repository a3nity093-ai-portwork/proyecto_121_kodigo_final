# Ficha del modelo · Riesgo de mala reseña (Olist)

**Proyecto:** Olist: del pedido a la reseña
**Artefacto:** `modelo_riesgo.joblib` (pipeline de scikit-learn con XGBoost)
**Versión de la ficha:** 1.0 · **Última actualización:** pendiente de completar al entrenar
**Fuente de los resultados:** `Plantilla_Proyecto_Final_OLIST.ipynb`

## 1. Uso previsto

Estimar la probabilidad de que un pedido **ya entregado** reciba una mala reseña
(calificación de 1 o 2 estrellas) para que el equipo de atención priorice a quién
contactar. La capacidad operativa del proyecto es contactar cerca del **10 %** de
los pedidos.

**No** debe usarse para:

- decidir sanciones, precios o condiciones para el cliente;
- afirmar relaciones causales entre una variable y la reseña;
- predecir pedidos no entregados ni pedidos sin historial completo de fechas;
- inferir atributos personales de personas compradoras o vendedoras.

## 2. Datos

| Elemento | Detalle |
| :--- | :--- |
| Origen | Base del curso, esquema `final` (tablas `orders`, `order_items`, `order_payments`, `order_reviews`, `customers`, `products`, `sellers`, `category_translation`). |
| Unidad de análisis | Una fila por **pedido entregado y con reseña**. |
| Periodo | `[pendiente: indicar MIN/MAX de order_purchase_timestamp al ejecutar el notebook]` |
| Filtros | `order_status = 'delivered'`, con ítems, con reseña (la más reciente por `review_creation_date`). |
| Datos personales | Ninguno: no se usan identificadores de cliente ni textos de comentarios. |

## 3. Variable objetivo

`mala_resena = 1` si `review_score <= 2`; `0` en caso contrario.
La etiqueta **no** forma parte de las variables de entrada.

## 4. Variables de entrada (17)

`order_id`, `order_purchase_timestamp`, `order_approved_at`,
`order_delivered_carrier_date`, `order_delivered_customer_date`,
`order_estimated_delivery_date`, `estado_cliente`, `n_items`, `n_vendedores`,
`precio_total`, `flete_total`, `peso_total_g`, `fotos_promedio`, `categoria`,
`estado_vendedor`, `tipo_pago`, `cuotas_max`.

Variables derivadas por `preparacion.crear_variables` (idénticas en entrenamiento
y en la app):

| Variable | Cálculo | Lectura de negocio |
| :--- | :--- | :--- |
| `tiempo_a_despacho_dias` | despacho al transportista − compra | Velocidad de preparación del pedido. |
| `tiempo_transito_dias` | entrega al cliente − despacho | Duración real del transporte. |
| `dias_retraso` | entrega al cliente − entrega estimada, negativos a 0 | Incumplimiento de la promesa de entrega. |
| `dias_retraso_real` | igual, sin recorte | Se conserva para trazabilidad; no entra al modelo. |

Imputaciones (las mismas del notebook): `order_approved_at` vacío → fecha de
compra; `order_delivered_carrier_date` y `order_delivered_customer_date` vacíos →
entrega estimada.

## 5. Modelo

- Pipeline de `scikit-learn`: `FunctionTransformer(crear_variables)` →
  `FunctionTransformer(seleccionar_columnas_pipeline)` →
  `ColumnTransformer(OneHotEncoder(handle_unknown="ignore"))` → `XGBClassifier`.
- Hiperparámetros del notebook: `n_estimators=100`, `max_depth=5`,
  `learning_rate=0.1`, `random_state=42`, `eval_metric="logloss"`.
- Validación **temporal**: 80 % de pedidos más antiguos para entrenamiento y 20 %
  más recientes para evaluación; el artefacto final se reentrena con el 100 %.
- Categorías no vistas en entrenamiento se codifican como vector nulo
  (`handle_unknown="ignore"`), no como error.

## 6. Métricas reportadas (precisión en el 10 % de mayor riesgo)

| Estrategia | Precisión en el 10 % superior |
| :--- | :--- |
| Modelo XGBoost | **49.35 %** |
| Regla de negocio: ordenar por `dias_retraso` | 37.90 % |
| Línea base aleatoria (proporción de malas reseñas en test) | 11.89 % |

Lectura correcta de estas cifras: las tres filas son **estrategias distintas de
priorización**, evaluadas sobre el mismo periodo de test. El modelo no mejora la
regla del retraso "explicando" el retraso: la supera porque combina más señales
del pedido. Las cifras provienen del notebook (división temporal 80/20) y no se
recalculan en la app.

## 7. Umbrales de la app

Los niveles de riesgo son una **convención de la interfaz**, no una salida del
modelo:

| Nivel | Probabilidad estimada |
| :--- | :--- |
| Alto | ≥ 45 % |
| Medio | 20 % – 45 % |
| Bajo | < 20 % |

Se definen en `config.py` (`umbral_riesgo_alto`, `umbral_riesgo_medio`) y pueden
ajustarse sin reentrenar. El corte operativo (10 % superior) se calcula por orden
de probabilidad dentro del lote, no por umbral fijo.

## 8. Limitaciones

- Es una probabilidad de apoyo a la decisión: **no es una certeza ni una causa**.
- Usa información posterior a la entrega (fechas reales), por lo que solo aplica a
  pedidos ya entregados.
- Sensible al desbalance de clases: la proporción de malas reseñas es baja y la
  precisión del corte depende del periodo.
- Deriva de datos (*drift*): cambios en logística, categorías o política de
  entrega degradan la calibración; requiere monitoreo y reentrenamiento.
- Si bajara mucho la proporción de retrasos, el peso de `dias_retraso` caería y el
  modelo se apoyaría en variables secundarias.
- No evalúa calidad del producto ni del vendedor más allá de las señales incluidas.

## 9. Funcionalidades fuera de esta ficha

El notebook incluye exploración de datos, pronóstico/segmentación (Parte 3) y
clasificación de sentimiento de comentarios (Parte 4). Son entregables separados:
la app no las mezcla con la probabilidad de mala reseña.
