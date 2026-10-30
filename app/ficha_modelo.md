# Ficha del modelo de riesgo

El modelo estima la probabilidad de una mala reseña (1 o 2 estrellas) para un
pedido ya entregado. Sirve para priorizar aproximadamente el 10% de pedidos que
atención al cliente puede contactar; no debe usarse para sancionar vendedores ni
para tomar decisiones automáticas sobre personas.

Se entrenó con el contrato de Olist y no usa comentarios, estrellas ni fechas de
reseña. Las variables derivadas incluyen tiempos de despacho, tránsito y retraso.
En la validación temporal del notebook, el XGBoost obtuvo 49.35% de precisión en
el 10% de mayor riesgo, frente a 37.90% de la regla de retraso y 11.89% del azar.

La probabilidad no es una certeza. Puede degradarse si cambian la logística,
categorías o proporción de retrasos. Los falsos positivos consumen una llamada y
los falsos negativos dejan sin atención a un cliente potencialmente insatisfecho.
Debe existir supervisión humana y revisión periódica con datos nuevos.
