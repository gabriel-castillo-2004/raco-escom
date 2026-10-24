from datetime import datetime
import hashlib
from io import BytesIO
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from core.models import GrupoInput, ResumenMateria, Turno

# Paleta de colores institucionales y semáforos
HEADER_BG = "002B49"  # Azul institucional profundo
HEADER_FG = "FFFFFF"
ZEBRA_BG = "F7F9FB"
BORDER_COLOR = "D0D5DD"

# Acciones y alertas
FILL_CONSERVAR = "D1E7DD"
FONT_CONSERVAR = "0F5132"
FILL_ABRIR = "CFE2FF"
FONT_ABRIR = "084298"
FILL_CERRAR = "F8D7DA"
FONT_CERRAR = "842029"


def _aplicar_estilo_tabla(ws, min_row, max_row, min_col, max_col):
    """Aplica formato de celdas, fuentes, bordes y zebra a un rango de datos."""
    thin_border = Border(
        left=Side(style="thin", color=BORDER_COLOR),
        right=Side(style="thin", color=BORDER_COLOR),
        top=Side(style="thin", color=BORDER_COLOR),
        bottom=Side(style="thin", color=BORDER_COLOR),
    )

    for row_idx in range(min_row, max_row + 1):
        is_zebra = (row_idx % 2 == 0)
        for col_idx in range(min_col, max_col + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.border = thin_border
            if cell.fill.fill_type is None:
                if is_zebra:
                    cell.fill = PatternFill(start_color=ZEBRA_BG, end_color=ZEBRA_BG, fill_type="solid")


def _autoajustar_columnas(ws, min_col=1, max_col=None):
    """Autoajusta el ancho de las columnas con un margen de lectura y un tope de 50."""
    if max_col is None:
        max_col = ws.max_column

    # Obtener celdas combinadas que comiencen en la hoja para no inflar columnas individuales
    merged_cell_ranges = ws.merged_cells.ranges

    for col in range(min_col, max_col + 1):
        col_letter = get_column_letter(col)
        max_len = 0
        for cell in ws[col_letter]:
            # Ignorar si es celda combinada de más de una columna
            es_combinada = any(
                cell.coordinate in rng and (rng.max_col > rng.min_col)
                for rng in merged_cell_ranges
            )
            if es_combinada:
                continue

            val_str = str(cell.value or "")
            if "\n" in val_str:
                val_str = max(val_str.split("\n"), key=len)
            max_len = max(max_len, len(val_str))

        ancho_calculado = max(max_len + 4, 12)
        ws.column_dimensions[col_letter].width = min(ancho_calculado, 50)


def generar_dictamen_excel(
    raw_input_text: str,
    optimizaciones: List[ResumenMateria],
    grupos_input: List[GrupoInput],
    parametros: Dict[str, Any],
    alertas_saes: Optional[List[Dict[str, Any]]] = None,
) -> BytesIO:
    """
    Genera el libro de Excel oficial del Dictamen/Informe Técnico RACO en memoria.
    Contiene exactamente 4 pestañas:
      1. Carátula y Supuestos
      2. Resumen Directivo
      3. Detalle por Grupo
      4. Semáforo de Tiras
    """
    wb = openpyxl.Workbook()
    # Habilitar recálculo forzado en visores de Excel / web / móviles
    wb.calculation.fullCalcOnLoad = True

    ws_caratula = wb.active
    ws_caratula.title = "Carátula y Supuestos"

    ws_resumen = wb.create_sheet(title="Resumen Directivo")
    ws_detalle = wb.create_sheet(title="Detalle por Grupo")
    ws_tiras = wb.create_sheet(title="Semáforo de Tiras")

    ws_caratula.views.sheetView[0].showGridLines = True
    ws_resumen.views.sheetView[0].showGridLines = True
    ws_detalle.views.sheetView[0].showGridLines = True
    ws_tiras.views.sheetView[0].showGridLines = True

    # 1. Normalización estricta de entrada para SHA-256 (Fila 43)
    text_normalized = (raw_input_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    sha256_hash = hashlib.sha256(text_normalized.encode("utf-8")).hexdigest().upper()

    # Fecha oficial en zona horaria America/Mexico_City
    tz_cdmx = ZoneInfo("America/Mexico_City")
    fecha_emision = datetime.now(tz_cdmx).strftime("%Y-%m-%d %H:%M:%S (%Z)")

    # ==========================================
    # PESTAÑA 1: Carátula y Supuestos (Filas 45 y 49)
    # ==========================================
    ws_caratula.merge_cells("B2:G2")
    cell_title = ws_caratula["B2"]
    cell_title.value = "INFORME TÉCNICO DE APOYO - PLANIFICACIÓN DE CAPACIDAD DOCENTE"
    cell_title.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    cell_title.fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
    cell_title.alignment = Alignment(horizontal="center", vertical="center")
    ws_caratula.row_dimensions[2].height = 36

    ws_caratula["B4"] = "Institución:"
    ws_caratula["C4"] = "Escuela Superior de Cómputo (ESCOM) — IPN"
    ws_caratula["B5"] = "Fecha y Hora de Emisión:"
    ws_caratula["C5"] = fecha_emision
    ws_caratula["B6"] = "Versión del Motor:"
    ws_caratula["C6"] = "RACO Core v1.2 (ADR-0002: Soft Capacity & Modal Model)"
    ws_caratula["B7"] = "Etiqueta Git / Commit:"
    ws_caratula["C7"] = str(parametros.get("git_commit_tag", "main-v1.2"))

    ws_caratula["B9"] = "PARÁMETROS DEL MODELO"
    ws_caratula["B9"].font = Font(bold=True, size=11, color="002B49")

    ws_caratula["B10"] = "Tolerancia de Sobrecupo (τ):"
    ws_caratula["C10"] = f"{parametros.get('tolerancia_tau', 2)} alumnos (cupo blando)"
    ws_caratula["B11"] = "Régimen de Cupo Base:"
    override = parametros.get("override_cupo")
    ws_caratula["C11"] = f"Override Uniforme ({override})" if override else "Cupo Modal por Asignatura"
    ws_caratula["B12"] = "Horas Semanales Base por Materia:"
    horas_materia = int(parametros.get("horas_materia", 4))
    ws_caratula["C12"] = f"{horas_materia} hrs/semana frente a grupo"

    # Bloque explícito de supuestos del modelo
    ws_caratula["B14"] = "SUPUESTOS DEL MODELO:"
    ws_caratula["B14"].font = Font(bold=True, size=11, color="002B49")
    ws_caratula.merge_cells("C14:G14")
    ws_caratula["C14"] = (
        "Capacidad modal estimada por asignatura; tolerancia tau considerada como sobrecupo admisible; "
        "horas frente a grupo configuradas como parámetro de apoyo."
    )
    ws_caratula["C14"].font = Font(size=9, color="333333")

    # Sello criptográfico
    ws_caratula["B16"] = "SELLO DIGITAL DE INTEGRIDAD (SHA-256)"
    ws_caratula["B16"].font = Font(bold=True, size=11, color="002B49")
    ws_caratula["B17"] = "Hash Criptográfico de Entrada:"
    ws_caratula["C17"] = sha256_hash
    ws_caratula["C17"].font = Font(name="Consolas", size=10, bold=True, color="0A58CA")

    # Leyenda institucional formal
    ws_caratula.merge_cells("B19:G21")
    cell_leyenda = ws_caratula["B19"]
    cell_leyenda.value = (
        "Dictamen técnico de apoyo basado en registros observados en SAES. "
        "No sustituye la validación de comités de academia ni la normatividad del IPN. "
        "Este documento provee modelación algorítmica y análisis de capacidad docente para auxilio a la toma de decisiones."
    )
    cell_leyenda.font = Font(italic=True, size=9, color="555555")
    cell_leyenda.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")

    for r in range(4, 18):
        ws_caratula.cell(row=r, column=2).font = Font(bold=True, color="333333")

    _autoajustar_columnas(ws_caratula, min_col=2, max_col=7)

    # ==========================================
    # PESTAÑA 2: Resumen Directivo
    # ==========================================
    headers_resumen = [
        "Semestre",
        "Carrera",
        "Turno",
        "Clave",
        "Asignatura",
        "Grupos Actuales",
        "Grupos Propuestos",
        "Delta",
        "Demanda Observada",
        "Horas Docentes Requeridas",
        "Estado",
    ]

    for c_idx, h in enumerate(headers_resumen, start=1):
        cell = ws_resumen.cell(row=2, column=c_idx, value=h)
        cell.font = Font(name="Calibri", bold=True, color=HEADER_FG)
        cell.fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws_resumen.row_dimensions[2].height = 28

    # Construir índice de grupos por (materia, turno) para metadatos (semestre, carrera, clave)
    meta_materia: Dict[Tuple[str, Turno], Dict[str, Any]] = {}
    for g in grupos_input:
        key = (g.materia, g.turno)
        if key not in meta_materia:
            sem_val = g.semestre if g.semestre is not None else (int(g.grupo[0]) if g.grupo and g.grupo[0].isdigit() else "N/D")
            carrera_val = g.carrera if g.carrera is not None else "N/D"
            clave_val = g.materia_id if g.materia_id is not None else "N/D"
            meta_materia[key] = {
                "semestre": sem_val,
                "carrera": carrera_val,
                "clave": clave_val,
            }

    row_curr = 3
    for opt in optimizaciones:
        key = (opt.materia, opt.turno)
        info = meta_materia.get(key, {"semestre": "N/D", "carrera": "N/D", "clave": "N/D"})
        horas_calc = opt.grupos_propuestos * horas_materia

        if opt.delta_grupos > 0:
            estado = "SOBRECUPO (ABRIR)"
        elif opt.delta_grupos < 0:
            estado = "SUBUTILIZADO (CONSOLIDAR)"
        else:
            estado = "EQUILIBRADO"

        vals = [
            info["semestre"],
            info["carrera"],
            opt.turno.value,
            info["clave"],
            opt.materia,
            opt.grupos_actuales,
            opt.grupos_propuestos,
            opt.delta_grupos,
            opt.demanda_total,
            horas_calc,
            estado,
        ]

        for c_idx, val in enumerate(vals, start=1):
            cell = ws_resumen.cell(row=row_curr, column=c_idx, value=val)
            if c_idx in [1, 2, 3, 4, 6, 7, 8, 9, 10, 11]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            # Colorear estado
            if c_idx == 11:
                if estado == "SOBRECUPO (ABRIR)":
                    cell.fill = PatternFill(start_color=FILL_ABRIR, end_color=FILL_ABRIR, fill_type="solid")
                    cell.font = Font(bold=True, color=FONT_ABRIR)
                elif estado == "SUBUTILIZADO (CONSOLIDAR)":
                    cell.fill = PatternFill(start_color=FILL_CERRAR, end_color=FILL_CERRAR, fill_type="solid")
                    cell.font = Font(bold=True, color=FONT_CERRAR)
                else:
                    cell.fill = PatternFill(start_color=FILL_CONSERVAR, end_color=FILL_CONSERVAR, fill_type="solid")
                    cell.font = Font(bold=True, color=FONT_CONSERVAR)

        row_curr += 1

    # Fila de totales
    if row_curr > 3:
        ws_resumen.cell(row=row_curr, column=5, value="TOTAL GENERAL:").font = Font(bold=True)
        ws_resumen.cell(row=row_curr, column=6, value=f"=SUM(F3:F{row_curr - 1})").font = Font(bold=True)
        ws_resumen.cell(row=row_curr, column=7, value=f"=SUM(G3:G{row_curr - 1})").font = Font(bold=True)
        ws_resumen.cell(row=row_curr, column=8, value=f"=SUM(H3:H{row_curr - 1})").font = Font(bold=True)
        ws_resumen.cell(row=row_curr, column=9, value=f"=SUM(I3:I{row_curr - 1})").font = Font(bold=True)
        ws_resumen.cell(row=row_curr, column=10, value=f"=SUM(J3:J{row_curr - 1})").font = Font(bold=True)
        for col_t in [5, 6, 7, 8, 9, 10]:
            ws_resumen.cell(row=row_curr, column=col_t).border = Border(
                top=Side(style="thin", color=BORDER_COLOR), bottom=Side(style="double", color=BORDER_COLOR)
            )

    _aplicar_estilo_tabla(ws_resumen, 3, row_curr - 1 if row_curr > 3 else 3, 1, 11)
    _autoajustar_columnas(ws_resumen, 1, 11)

    # ==========================================
    # PESTAÑA 3: Detalle por Grupo
    # ==========================================
    headers_detalle = [
        "Grupo ID",
        "Materia",
        "Turno",
        "Acción",
        "Cupo Asignado",
        "Inscritos Estimados",
        "Atípico / Lab",
        "Justificación",
    ]

    for c_idx, h in enumerate(headers_detalle, start=1):
        cell = ws_detalle.cell(row=2, column=c_idx, value=h)
        cell.font = Font(name="Calibri", bold=True, color=HEADER_FG)
        cell.fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws_detalle.row_dimensions[2].height = 28

    row_d = 3
    for opt in optimizaciones:
        for g in opt.grupos:
            vals = [
                g.grupo_id,
                g.materia,
                g.turno.value,
                g.accion.value,
                g.cupo_asignado,
                g.inscritos_estimados,
                "Sí (Lab)" if g.es_atipico else "No",
                g.justificacion,
            ]
            for c_idx, val in enumerate(vals, start=1):
                cell = ws_detalle.cell(row=row_d, column=c_idx, value=val)
                if c_idx in [1, 3, 4, 5, 6, 7]:
                    cell.alignment = Alignment(horizontal="center", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")

                # Formato condicional de la acción
                if c_idx == 4:
                    if g.accion.value == "CONSERVAR":
                        cell.fill = PatternFill(start_color=FILL_CONSERVAR, end_color=FILL_CONSERVAR, fill_type="solid")
                        cell.font = Font(bold=True, color=FONT_CONSERVAR)
                    elif g.accion.value == "ABRIR":
                        cell.fill = PatternFill(start_color=FILL_ABRIR, end_color=FILL_ABRIR, fill_type="solid")
                        cell.font = Font(bold=True, color=FONT_ABRIR)
                    elif g.accion.value == "CERRAR":
                        cell.fill = PatternFill(start_color=FILL_CERRAR, end_color=FILL_CERRAR, fill_type="solid")
                        cell.font = Font(bold=True, color=FONT_CERRAR)

            row_d += 1

    _aplicar_estilo_tabla(ws_detalle, 3, row_d - 1 if row_d > 3 else 3, 1, 8)
    _autoajustar_columnas(ws_detalle, 1, 8)

    # ==========================================
    # PESTAÑA 4: Semáforo de Tiras
    # ==========================================
    headers_tiras = [
        "Semestre",
        "Turno",
        "Total Asignaturas",
        "Materias con Cupo Agotado",
        "Lista de Asignaturas Saturadas",
        "Diagnóstico de Tira Regular",
    ]

    for c_idx, h in enumerate(headers_tiras, start=1):
        cell = ws_tiras.cell(row=2, column=c_idx, value=h)
        cell.font = Font(name="Calibri", bold=True, color=HEADER_FG)
        cell.fill = PatternFill(start_color=HEADER_BG, end_color=HEADER_BG, fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws_tiras.row_dimensions[2].height = 28

    # Agrupar ofertas por (semestre, turno)
    tiras_dict: Dict[Tuple[Any, Turno], List[Dict[str, Any]]] = {}
    for g in grupos_input:
        sem_num = g.semestre if g.semestre is not None else (int(g.grupo[0]) if g.grupo and g.grupo[0].isdigit() else "N/D")
        key = (sem_num, g.turno)
        if key not in tiras_dict:
            tiras_dict[key] = []
        disp_est = g.cupo_max - g.demanda_estimada
        tiras_dict[key].append({"materia": g.materia, "disponibles": disp_est})

    row_t = 3
    def sort_key_tiras(item):
        sem, turno = item[0]
        s_val = sem if isinstance(sem, int) else 999
        return (s_val, str(turno.value))

    for (sem, turno), items in sorted(tiras_dict.items(), key=sort_key_tiras):
        total_asig = len(items)
        saturadas = [it["materia"] for it in items if it["disponibles"] <= 0]
        num_sat = len(saturadas)

        if num_sat == 0:
            diag = "🟢 TIRA COMPLETA GARANTIZADA"
            fill_diag = FILL_CONSERVAR
            font_diag = FONT_CONSERVAR
            lista_str = "Ninguna (Cupo disponible en todas)"
        elif num_sat < total_asig:
            diag = "🟡 TIRA EN RIESGO (PARCIALMENTE AGOTADA)"
            fill_diag = "FFF3CD"
            font_diag = "664D03"
            lista_str = ", ".join(sorted(set(saturadas)))
        else:
            diag = "🔴 TIRA BLOQUEADA (SIN CUPO)"
            fill_diag = FILL_CERRAR
            font_diag = FONT_CERRAR
            lista_str = ", ".join(sorted(set(saturadas)))

        vals = [
            f"Semestre {sem}" if isinstance(sem, int) else str(sem),
            turno.value,
            total_asig,
            num_sat,
            lista_str,
            diag,
        ]

        for c_idx, val in enumerate(vals, start=1):
            cell = ws_tiras.cell(row=row_t, column=c_idx, value=val)
            if c_idx in [1, 2, 3, 4]:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

            if c_idx == 6:
                cell.fill = PatternFill(start_color=fill_diag, end_color=fill_diag, fill_type="solid")
                cell.font = Font(bold=True, color=font_diag)

        row_t += 1

    _aplicar_estilo_tabla(ws_tiras, 3, row_t - 1 if row_t > 3 else 3, 1, 6)
    _autoajustar_columnas(ws_tiras, 1, 6)

    # Retornar BytesIO con el libro generado
    output_stream = BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)
    return output_stream
