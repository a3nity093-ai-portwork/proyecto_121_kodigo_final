"""Contrato de datos, catálogos del dominio y validación de entradas.

El contrato proviene de `Plantilla_Proyecto_Final_OLIST.ipynb` (variable
`CONTRATO`). No se agregan ni renombran columnas: la app valida estrictamente
sobre estas listas y rechaza con un motivo explícito lo que no cumple.

Diferencia clave: `mala_resena` es el objetivo, nunca una variable de entrada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

import pandas as pd

OBJETIVO = "mala_resena"

CONTRATO_COMPLETO: tuple[str, ...] = (
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
    OBJETIVO,
)

#: Columnas que la app debe recibir para predecir (17, sin el objetivo).
CONTRATO_INFERENCIA: tuple[str, ...] = CONTRATO_COMPLETO[:17]

COLUMNAS_FECHA: tuple[str, ...] = (
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
)

#: Sin estas dos fechas no se puede preparar el pedido.
FECHAS_OBLIGATORIAS: tuple[str, ...] = (
    "order_purchase_timestamp",
    "order_estimated_delivery_date",
)

#: Fechas que `preparacion.crear_variables` imputa cuando llegan vacías.
FECHAS_IMPUTABLES: tuple[str, ...] = (
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
)

COLUMNAS_ENTERAS: tuple[str, ...] = ("n_items", "n_vendedores", "cuotas_max")

COLUMNAS_DECIMALES: tuple[str, ...] = (
    "precio_total",
    "flete_total",
    "peso_total_g",
    "fotos_promedio",
)

COLUMNAS_NUMERICAS: tuple[str, ...] = COLUMNAS_ENTERAS + COLUMNAS_DECIMALES

COLUMNAS_CATEGORICAS: tuple[str, ...] = (
    "estado_cliente",
    "estado_vendedor",
    "tipo_pago",
    "categoria",
)

#: Unidades federativas de Brasil (valor tal como lo entrega `customers.customer_state`).
ESTADOS_BRASIL = frozenset(
    {
        "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
        "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
        "SE", "SP", "TO",
    }
)

#: Métodos de pago observados en el esquema `final` (se admite `unknown`).
TIPOS_PAGO_CONOCIDOS: tuple[str, ...] = (
    "credit_card",
    "boleto",
    "voucher",
    "debit_card",
    "not_defined",
    "unknown",
)

MAXIMO_CUOTAS_PLAUSIBLE = 24


class ErrorContrato(ValueError):
    """El archivo o formulario no cumple el contrato del proyecto."""


@dataclass
class ResultadoValidacion:
    """Salida de `validar_lote`.

    - `datos`: filas aceptadas, en el orden exacto de `CONTRATO_INFERENCIA`.
    - `rechazados`: tabla con la fila de origen, `order_id` y el motivo.
    - `objetivo`: etiqueta real (`mala_resena`) alineada con `datos`, solo si el
      archivo la traía; se usa para evaluación, jamás como predictor.
    """

    datos: pd.DataFrame
    rechazados: pd.DataFrame
    advertencias: list[str] = field(default_factory=list)
    objetivo_incluido: bool = False
    objetivo: pd.Series | None = None

    @property
    def n_validas(self) -> int:
        return len(self.datos)

    @property
    def n_rechazadas(self) -> int:
        return len(self.rechazados)


def columnas_faltantes(columnas: Sequence[str]) -> list[str]:
    """Columnas del contrato de inferencia ausentes en la entrada."""
    presentes = {str(c) for c in columnas}
    return [c for c in CONTRATO_INFERENCIA if c not in presentes]


def _texto_limpio(serie: pd.Series) -> pd.Series:
    return serie.astype("string").str.strip()


def _vacio_o_nulo(original: pd.Series) -> pd.Series:
    texto = _texto_limpio(original)
    return original.isna() | texto.isna() | texto.eq("")


def validar_lote(
    df_crudo: pd.DataFrame,
    *,
    categorias_conocidas: Mapping[str, Sequence[str]] | None = None,
) -> ResultadoValidacion:
    """Valida y normaliza un lote de pedidos contra el contrato.

    Lanza `ErrorContrato` si falta alguna columna obligatoria o no hay filas.
    Los problemas por fila no lanzan excepción: se devuelven en `rechazados`.
    """
    if not isinstance(df_crudo, pd.DataFrame):
        raise ErrorContrato("La entrada debe ser un DataFrame.")
    if df_crudo.empty:
        raise ErrorContrato("El conjunto de datos está vacío: no hay pedidos que procesar.")

    faltantes = columnas_faltantes(df_crudo.columns)
    if faltantes:
        raise ErrorContrato(
            "Faltan columnas obligatorias del contrato: " + ", ".join(faltantes) + "."
        )

    advertencias: list[str] = []

    extras = [c for c in df_crudo.columns if c not in CONTRATO_COMPLETO]
    if extras:
        advertencias.append(
            "Se ignoran columnas fuera del contrato: " + ", ".join(map(str, extras)) + "."
        )

    objetivo_incluido = OBJETIVO in df_crudo.columns
    objetivo_crudo = df_crudo[OBJETIVO].reset_index(drop=True) if objetivo_incluido else None
    if objetivo_incluido:
        advertencias.append(
            "La columna `mala_resena` se excluye de los predictores: solo se conserva "
            "como etiqueta real para evaluar el resultado."
        )

    trabajo = df_crudo.loc[:, list(CONTRATO_INFERENCIA)].reset_index(drop=True).copy()
    motivos: list[list[str]] = [[] for _ in range(len(trabajo))]

    def anotar(mascara: pd.Series, motivo: str) -> None:
        for posicion in trabajo.index[mascara.fillna(True).astype(bool)]:
            motivos[posicion].append(motivo)

    # --- order_id ---------------------------------------------------------
    trabajo["order_id"] = _texto_limpio(trabajo["order_id"])
    anotar(_vacio_o_nulo(trabajo["order_id"]), "order_id vacío o ausente")

    # --- fechas -----------------------------------------------------------
    for columna in COLUMNAS_FECHA:
        original = trabajo[columna]
        convertidas = pd.to_datetime(original, errors="coerce")
        no_parseable = ~_vacio_o_nulo(original) & convertidas.isna()
        anotar(no_parseable, f"{columna} no es una fecha válida")
        trabajo[columna] = convertidas

    for columna in FECHAS_OBLIGATORIAS:
        anotar(trabajo[columna].isna(), f"{columna} es obligatoria")

    # --- numéricos --------------------------------------------------------
    for columna in COLUMNAS_NUMERICAS:
        original = trabajo[columna]
        convertidos = pd.to_numeric(original, errors="coerce")
        no_numerico = ~_vacio_o_nulo(original) & convertidos.isna()
        anotar(no_numerico, f"{columna} no es un valor numérico")
        anotar(convertidos.isna(), f"{columna} es obligatoria")
        trabajo[columna] = convertidos

    for columna in COLUMNAS_ENTERAS:
        decimales = trabajo[columna].notna() & (trabajo[columna] % 1 != 0)
        anotar(decimales, f"{columna} debe ser un número entero")

    # --- categóricos ------------------------------------------------------
    for columna in ("estado_cliente", "estado_vendedor"):
        valores = _texto_limpio(trabajo[columna]).str.upper()
        # 'unknown' es la categoría que usa la consulta del notebook para faltantes.
        trabajo[columna] = valores.mask(valores.eq("UNKNOWN"), "unknown")

    for columna in ("tipo_pago", "categoria"):
        trabajo[columna] = _texto_limpio(trabajo[columna]).str.lower()

    anotar(_vacio_o_nulo(trabajo["estado_cliente"]), "estado_cliente es obligatorio")
    for columna in ("estado_vendedor", "tipo_pago", "categoria"):
        vacios = _vacio_o_nulo(trabajo[columna])
        if vacios.any():
            advertencias.append(
                f"{vacios.sum()} fila(s) sin {columna}: se completan con 'unknown', "
                "igual que en la consulta del notebook."
            )
        trabajo.loc[vacios, columna] = "unknown"

    # --- reglas de negocio ------------------------------------------------
    anotar(trabajo["n_items"] < 1, "n_items debe ser mayor o igual a 1")
    anotar(trabajo["n_vendedores"] < 1, "n_vendedores debe ser mayor o igual a 1")
    anotar(
        trabajo["n_vendedores"] > trabajo["n_items"],
        "n_vendedores no puede ser mayor que n_items",
    )
    for columna in COLUMNAS_DECIMALES:
        anotar(trabajo[columna] < 0, f"{columna} no puede ser negativo")
    anotar(trabajo["cuotas_max"] < 0, "cuotas_max no puede ser negativo")
    anotar(
        trabajo["cuotas_max"] > MAXIMO_CUOTAS_PLAUSIBLE,
        f"cuotas_max supera el máximo plausible ({MAXIMO_CUOTAS_PLAUSIBLE})",
    )

    estados_validos = ESTADOS_BRASIL | {"unknown"}
    for columna in ("estado_cliente", "estado_vendedor"):
        invalidos = trabajo[columna].notna() & ~trabajo[columna].isin(estados_validos)
        anotar(invalidos, f"{columna} debe ser una UF de Brasil de 2 letras")

    # Fechas imposibles (solo se comparan filas con ambas fechas presentes).
    compra = trabajo["order_purchase_timestamp"]
    for columna, etiqueta in (
        ("order_approved_at", "la aprobación del pago"),
        ("order_delivered_carrier_date", "el despacho al transportista"),
        ("order_delivered_customer_date", "la entrega al cliente"),
        ("order_estimated_delivery_date", "la entrega estimada"),
    ):
        anotar(
            trabajo[columna] < compra,
            f"{columna} ({etiqueta}) es anterior a la compra",
        )

    entrega_antes_despacho = (
        trabajo["order_delivered_customer_date"] < trabajo["order_delivered_carrier_date"]
    ).fillna(False)
    if entrega_antes_despacho.any():
        advertencias.append(
            f"{int(entrega_antes_despacho.sum())} fila(s) registran la entrega antes del "
            "despacho: se conservan porque el notebook recorta los tiempos negativos a 0."
        )

    if categorias_conocidas:
        for columna, valores in categorias_conocidas.items():
            if columna not in trabajo.columns:
                continue
            conocidos = {str(v) for v in valores}
            observados = {str(v) for v in trabajo[columna].dropna().unique()}
            nuevas = sorted(observados - conocidos)
            if nuevas:
                advertencias.append(
                    f"Valores de {columna} no vistos en entrenamiento (el modelo los "
                    "trata como categoría desconocida): " + ", ".join(nuevas[:8])
                    + ("…" if len(nuevas) > 8 else "")
                )

    # --- separar aceptadas y rechazadas -----------------------------------
    motivos_unidos = ["; ".join(dict.fromkeys(m)) for m in motivos]
    aceptadas = pd.Series([m == "" for m in motivos_unidos], index=trabajo.index)

    datos = trabajo.loc[aceptadas].reset_index(drop=True)
    for columna in COLUMNAS_ENTERAS:
        datos[columna] = datos[columna].astype("int64")
    for columna in COLUMNAS_DECIMALES:
        datos[columna] = datos[columna].astype("float64")
    for columna in COLUMNAS_CATEGORICAS:
        datos[columna] = datos[columna].astype(object)

    objetivo = objetivo_crudo.loc[aceptadas].reset_index(drop=True) if objetivo_crudo is not None else None

    rechazados = pd.DataFrame(
        {
            "fila_archivo": (trabajo.index[~aceptadas] + 2).tolist(),
            "order_id": trabajo.loc[~aceptadas, "order_id"].fillna("(sin order_id)").tolist(),
            "motivo": [m for m, ok in zip(motivos_unidos, aceptadas) if not ok],
        }
    )

    return ResultadoValidacion(
        datos=datos,
        rechazados=rechazados,
        advertencias=advertencias,
        objetivo_incluido=objetivo_incluido,
        objetivo=objetivo,
    )
