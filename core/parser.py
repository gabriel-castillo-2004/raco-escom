from io import BytesIO, StringIO
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
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

GRUPO_REGEX = re.compile(r"^(?P<semestre>[1-9])(?P<carrera>[A-Za-z]+)(?P<turno>[MVXmvx])\d+$")


def _load_raw_dataframe(file_source: Union[str, Path, BytesIO, StringIO, pd.DataFrame, Any]) -> pd.DataFrame:
    """Lee el archivo fuente como DataFrame desde CSV, Excel (.xlsx/.xls) o DataFrame directo."""
    if isinstance(file_source, pd.DataFrame):
        return file_source.copy()

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


def _detectar_esquema_saes(columns: List[str]) -> Optional[Dict[str, Optional[str]]]:
    """
    Detecta si las columnas del DataFrame corresponden a una tabla exportada del SAES.
    Retorna un diccionario con el mapeo de columnas si coincide, o None si no es esquema SAES.
    """
    col_set = set(columns)
    if "grupo" not in col_set or "disponibles" not in col_set:
        return None

    col_cupo = "cupo" if "cupo" in col_set else ("cupo_max" if "cupo_max" in col_set else None)
    col_inscritos = (
        "inscritos"
        if "inscritos" in col_set
        else ("inscritos_actuales" if "inscritos_actuales" in col_set else None)
    )
    if not col_cupo or not col_inscritos:
        return None

    # Identificar columna de nombre de materia y columna opcional de clave
    col_nombre = None
    col_clave = None

    for candidate in ("nombre de la materia", "nombre_materia", "asignatura", "unidad de aprendizaje"):
        if candidate in col_set:
            col_nombre = candidate
            break

    if col_nombre is not None:
        # Si existe una columna explícita para el nombre, 'materia' o 'clave' actúa como materia_id
        for c_id in ("clave", "materia_id", "materia"):
            if c_id in col_set and c_id != col_nombre:
                col_clave = c_id
                break
    elif "materia" in col_set:
        col_nombre = "materia"
        for c_id in ("clave", "materia_id"):
            if c_id in col_set:
                col_clave = c_id
                break

    if not col_nombre:
        return None

    col_semestre = "semestre" if "semestre" in col_set else None

    return {
        "grupo": "grupo",
        "nombre_materia": col_nombre,
        "materia_id": col_clave,
        "semestre": col_semestre,
        "cupo": col_cupo,
        "inscritos": col_inscritos,
        "disponibles": "disponibles",
    }


def _parse_saes_dataframe(
    df: pd.DataFrame, col_map: Dict[str, Optional[str]]
) -> Tuple[List[GrupoInput], Dict[Tuple[str, Turno], int]]:
    """Procesa un DataFrame con esquema de tabla exportada del SAES."""
    grupos: List[GrupoInput] = []
    demanda_agregada: Dict[Tuple[str, Turno], int] = {}

    for idx, row in df.iterrows():
        raw_grupo = row[col_map["grupo"]]
        if pd.isna(raw_grupo):
            continue
        grupo_token = str(raw_grupo).strip()
        if not grupo_token or grupo_token.lower() == "grupo":
            continue

        grupo_match = GRUPO_REGEX.match(grupo_token)
        if not grupo_match:
            continue

        raw_nombre = row[col_map["nombre_materia"]]
        nombre_materia = str(raw_nombre).strip() if pd.notna(raw_nombre) else ""
        if not nombre_materia:
            continue

        try:
            cupo = int(float(row[col_map["cupo"]]))
            inscritos = int(float(row[col_map["inscritos"]]))
            disponibles = int(float(row[col_map["disponibles"]]))
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"La fila {idx + 1} (grupo '{grupo_token}') contiene valores numéricos inválidos en Cupo/Inscritos/Disponibles: {exc}"
            ) from exc

        semestre_val = int(grupo_match.group("semestre"))
        col_sem = col_map.get("semestre")
        if col_sem and pd.notna(row[col_sem]):
            try:
                semestre_val = int(float(row[col_sem]))
            except (ValueError, TypeError):
                pass

        materia_id_val = None
        col_id = col_map.get("materia_id")
        if col_id and pd.notna(row[col_id]):
            materia_id_val = str(row[col_id]).strip()

        carrera_val = grupo_match.group("carrera").upper()
        turno_letra = grupo_match.group("turno").upper()
        if turno_letra == "M":
            turno_enum = Turno.M
        elif turno_letra == "V":
            turno_enum = Turno.V
        else:
            turno_enum = Turno.X

        demanda_calc = cupo - disponibles
        demanda_final = max(inscritos, demanda_calc)

        try:
            grupo_obj = GrupoInput(
                materia=nombre_materia,
                grupo=grupo_token,
                turno=turno_enum,
                cupo_max=cupo,
                inscritos_actuales=inscritos,
                demanda_estimada=demanda_final,
                materia_id=materia_id_val,
                semestre=semestre_val,
                carrera=carrera_val,
            )
            grupos.append(grupo_obj)
            key = (grupo_obj.materia, grupo_obj.turno)
            demanda_agregada[key] = demanda_agregada.get(key, 0) + grupo_obj.demanda_estimada
        except ValidationError as val_err:
            raise ValueError(f"Error de validación en la fila {idx + 1}: {val_err}") from val_err

    if not grupos:
        raise ValueError(
            "No se encontraron grupos válidos con nomenclatura SAES (ej. 1AM1, 3CV2, 7AX1) en el archivo."
        )

    return grupos, demanda_agregada


def parse_academic_data(
    file_source: Union[str, Path, BytesIO, StringIO, pd.DataFrame, Any]
) -> Tuple[List[GrupoInput], Dict[Tuple[str, Turno], int]]:
    """
    Carga y normaliza los datos académicos de oferta/demanda desde un archivo CSV o Excel.
    Soporta detección dual automática:
      1. Esquema interno estándar: materia, grupo, turno, cupo_max, inscritos_actuales, demanda_estimada.
      2. Esquema exportado de SAES: Grupo, [Clave], Materia/Asignatura/Nombre de la Materia, [Semestre], Cupo, Inscritos, Disponibles.

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

    # Verificar si cumple con el esquema interno estándar
    missing_internal = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if not missing_internal:
        # Limpieza, normalización y sanitización (Esquema Interno)
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
                raise ValueError(
                    f"La columna '{int_col}' contiene valores no numéricos o enteros inválidos: {exc}"
                ) from exc

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

    # Intentar detección automática de Esquema Exportado de SAES
    saes_col_map = _detectar_esquema_saes(list(df.columns))
    if saes_col_map is not None:
        return _parse_saes_dataframe(df, saes_col_map)

    raise ValueError(
        f"Columnas faltantes en el archivo: {missing_internal}. "
        f"Se requieren las columnas estándar {REQUIRED_COLUMNS} o el formato SAES "
        f"(['grupo', 'materia'/'asignatura', 'cupo', 'inscritos', 'disponibles'])."
    )


def generar_plantilla_excel() -> BytesIO:
    """
    Genera en memoria un archivo .xlsx de plantilla lista para usar en ESCOM,
    con encabezados compatibles con SAES y 3 filas de ejemplo.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plantilla_SAES_RACO"

    headers = ["Grupo", "Clave", "Materia", "Semestre", "Cupo", "Inscritos", "Disponibles"]
    header_fill = PatternFill(start_color="002B49", end_color="002B49", fill_type="solid")
    header_font = Font(name="Calibri", bold=True, color="FFFFFF")
    thin_border = Border(
        left=Side(style="thin", color="D0D5DD"),
        right=Side(style="thin", color="D0D5DD"),
        top=Side(style="thin", color="D0D5DD"),
        bottom=Side(style="thin", color="D0D5DD"),
    )

    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    ejemplos = [
        ["1AM1", "A101", "FUNDAMENTOS DE PROGRAMACION", 1, 33, 33, 0],
        ["2AM1", "A201", "ALGEBRA LINEAL", 2, 36, 37, -1],
        ["7AX1", "A703", "TRABAJO TERMINAL I", 7, 250, 0, 250],
    ]

    for row_idx, fila in enumerate(ejemplos, start=2):
        for col_idx, valor in enumerate(fila, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=valor)
            cell.border = thin_border
            cell.alignment = Alignment(
                horizontal="left" if col_idx == 3 else "center",
                vertical="center",
            )

    anchos = [12, 12, 36, 12, 12, 12, 14]
    for col_idx, ancho in enumerate(anchos, start=1):
        col_letter = openpyxl.utils.get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = ancho

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream


def parse_saes_clipboard_text(raw_text: str) -> pd.DataFrame:
    r"""
    Procesa cadenas de texto continuas copiadas directamente desde el SAES de ESCOM.
    Utiliza delimitación robusta por tabulaciones (\t) o dos o más espacios consecutivos (\s{2,})
    para evitar que materias con números (ej. 'TRABAJO TERMINAL 1', 'INGLES 2') rompan el orden.

    Extrae:
        - grupo (ej. 1AM1, 3AV2, 7AX1)
        - materia_id (ej. A101, A204, A703)
        - nombre_materia (ej. CALCULO MULTIVARIABLE, TRABAJO TERMINAL I)
        - semestre (entero del grupo o columna)
        - carrera (siglas de la carrera, ej. 'A', 'C')
        - turno (Turno.M, Turno.V o Turno.X)
        - cupo (int)
        - inscritos (int)
        - disponibles (int, soporta números negativos como -1, -3)
        - discrepancia_saes (bool: True si cupo - inscritos != disponibles)
    """
    columns = [
        "grupo", "materia_id", "nombre_materia", "semestre",
        "carrera", "turno", "cupo", "inscritos", "disponibles",
        "discrepancia_saes"
    ]
    if not raw_text or not raw_text.strip():
        return pd.DataFrame(columns=columns)

    records: List[Dict[str, Any]] = []

    for line in raw_text.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        # Dividir por tabulación (\t) si está presente, o por 2 o más espacios consecutivos (\s{2,})
        if "\t" in line_clean:
            tokens = [t.strip() for t in line_clean.split("\t") if t.strip()]
        else:
            tokens = [t.strip() for t in re.split(r"\s{2,}", line_clean) if t.strip()]

        # Se requieren al menos 6 tokens: grupo, materia_id, nombre_materia, [semestre opcional], cupo, inscritos, disponibles
        if len(tokens) < 6:
            continue

        # Validar identificador de grupo
        grupo_token = tokens[0]
        grupo_match = GRUPO_REGEX.match(grupo_token)
        if not grupo_match:
            continue

        materia_id = tokens[1]
        nombre_materia = tokens[2]

        # Casos según cantidad de tokens numéricos al final
        # Formato A: grupo, materia_id, nombre_materia, cupo, inscritos, disponibles (len 6)
        # Formato B: grupo, materia_id, nombre_materia, semestre, cupo, inscritos, disponibles (len 7)
        try:
            if len(tokens) >= 7 and tokens[3].isdigit():
                semestre = int(tokens[3])
                cupo = int(tokens[4])
                inscritos = int(tokens[5])
                disponibles = int(tokens[6])
            else:
                semestre = int(grupo_match.group("semestre"))
                cupo = int(tokens[3])
                inscritos = int(tokens[4])
                disponibles = int(tokens[5])
        except (ValueError, IndexError):
            continue

        carrera = grupo_match.group("carrera").upper()
        turno_letra = grupo_match.group("turno").upper()
        if turno_letra == "M":
            turno_enum = Turno.M
        elif turno_letra == "V":
            turno_enum = Turno.V
        else:
            turno_enum = Turno.X

        discrepancia = (cupo - inscritos) != disponibles

        records.append(
            {
                "grupo": grupo_token,
                "materia_id": materia_id,
                "nombre_materia": nombre_materia,
                "semestre": semestre,
                "carrera": carrera,
                "turno": turno_enum,
                "cupo": cupo,
                "inscritos": inscritos,
                "disponibles": disponibles,
                "discrepancia_saes": discrepancia,
            }
        )

    return pd.DataFrame(records)
