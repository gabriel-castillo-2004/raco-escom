from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union

import pandas as pd
from pydantic import ValidationError

from core.models import GrupoInput, Turno

REQUIRED_COLUMNS: list[str] = [
    "materia",
    "grupo",
    "turno",
    "cupo_max",
    "inscritos_actuales",
    "demanda_estimada",
]


def _load_raw_dataframe(file_source: Union[str, Path, BytesIO, StringIO, Any]) -> pd.DataFrame:
    """Lee el archivo fuente como DataFrame desde CSV o Excel (.xlsx/.xls)."""
    file_str = str(file_source).lower() if isinstance(file_source, (str, Path)) else ""
    source_name = getattr(file_source, "name", "").lower()
    target_identifier = file_str or source_name

    try:
        if target_identifier.endswith((".xlsx", ".xls")):
            return pd.read_excel(file_source, engine="openpyxl")
        if target_identifier.endswith(".csv"):
            return pd.read_csv(file_source)

        # Fallback de autodetección para streams en memoria sin extensión en nombre
        if hasattr(file_source, "seek"):
            file_source.seek(0)
        try:
            return pd.read_csv(file_source)
        except Exception:
            if hasattr(file_source, "seek"):
                file_source.seek(0)
            return pd.read_excel(file_source, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Error al leer el archivo fuente: {exc}") from exc


def parse_academic_data(
    file_source: Union[str, Path, BytesIO, StringIO, Any]
) -> Tuple[List[GrupoInput], Dict[Tuple[str, Turno], int]]:
    """
    Carga y normaliza los datos académicos de oferta/demanda desde un archivo CSV o Excel.

    Returns:
        - List[GrupoInput]: Lista de instancias validadas y normalizadas con Pydantic.
        - Dict[Tuple[str, Turno], int]: Demanda total agregada por (materia, turno).

    Raises:
        - ValueError: Si faltan columnas requeridas, si hay valores/turnos inválidos o si el archivo está vacío.
    """
    df = _load_raw_dataframe(file_source)

    if df.empty:
        raise ValueError("El archivo proporcionado está vacío o no contiene registros.")

    # Sanitizar nombres de columnas
    df.columns = [str(col).strip().lower() for col in df.columns]

    # Validación de columnas mínimas requeridas
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        raise ValueError(
            f"Columnas faltantes en el archivo: {missing_columns}. "
            f"Se requieren: {REQUIRED_COLUMNS}"
        )

    # Limpieza, normalización y sanitización
    df["materia"] = df["materia"].astype(str).str.strip()
    df["grupo"] = df["grupo"].astype(str).str.strip()
    df["turno"] = df["turno"].astype(str).str.strip().str.upper()

    # Validación estricta de turnos permitidos
    valid_turnos = {t.value for t in Turno}
    invalid_turnos = df[~df["turno"].isin(valid_turnos)]
    if not invalid_turnos.empty:
        unsupported_values = invalid_turnos["turno"].unique().tolist()
        raise ValueError(
            f"Valores de turno inválidos encontrados: {unsupported_values}. "
            f"Los valores permitidos son: {sorted(list(valid_turnos))}"
        )

    # Conversión y validación de enteros
    for int_col in ["cupo_max", "inscritos_actuales", "demanda_estimada"]:
        try:
            df[int_col] = pd.to_numeric(df[int_col], errors="raise").astype(int)
        except Exception as exc:
            raise ValueError(f"La columna '{int_col}' contiene valores no numéricos o enteros inválidos: {exc}") from exc

    grupos: List[GrupoInput] = []
    demanda_agregada: Dict[Tuple[str, Turno], int] = {}

    for idx, row in df.iterrows():
        try:
            grupo_obj = GrupoInput(
                materia=row["materia"],
                grupo=row["grupo"],
                turno=Turno(row["turno"]),
                cupo_max=int(row["cupo_max"]),
                inscritos_actuales=int(row["inscritos_actuales"]),
                demanda_estimada=int(row["demanda_estimada"]),
            )
            grupos.append(grupo_obj)
            key = (grupo_obj.materia, grupo_obj.turno)
            demanda_agregada[key] = demanda_agregada.get(key, 0) + grupo_obj.demanda_estimada
        except ValidationError as val_err:
            raise ValueError(f"Error de validación en la fila {idx + 1}: {val_err}") from val_err

    return grupos, demanda_agregada

