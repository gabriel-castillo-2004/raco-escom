from datetime import datetime
import hashlib
from io import BytesIO
from zoneinfo import ZoneInfo
import openpyxl
import pytest

from core.exporter import generar_dictamen_excel
from core.models import GrupoInput, Turno
from core.rules import optimizar_materia_turno


@pytest.fixture
def sample_dataset():
    g1 = GrupoInput(materia="Cálculo", grupo="1CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=35, demanda_estimada=52)
    g2 = GrupoInput(materia="Cálculo", grupo="1CV1", turno=Turno.V, cupo_max=35, inscritos_actuales=35, demanda_estimada=44)
    g3 = GrupoInput(materia="Química", grupo="1LM1", turno=Turno.M, cupo_max=18, inscritos_actuales=18, demanda_estimada=18)
    grupos = [g1, g2, g3]

    opt1 = optimizar_materia_turno("Cálculo", Turno.M, 52, grupos, override_cupo=35, tolerancia=2)
    opt2 = optimizar_materia_turno("Cálculo", Turno.V, 44, grupos, override_cupo=35, tolerancia=2)
    opt3 = optimizar_materia_turno("Química", Turno.M, 18, grupos, override_cupo=35, tolerancia=2)
    optimizaciones = [opt1, opt2, opt3]

    raw_text = "1CM1\tA101\tCALCULO\t35\t35\t0\n1CV1\tA101\tCALCULO\t35\t35\t0"
    parametros = {
        "tolerancia_tau": 2,
        "override_cupo": 35,
        "horas_materia": 4,
        "git_commit_tag": "test-v1.2",
    }
    return raw_text, optimizaciones, grupos, parametros


def test_generar_dictamen_excel_returns_valid_bytesio(sample_dataset):
    raw_text, optimizaciones, grupos, parametros = sample_dataset
    excel_stream = generar_dictamen_excel(raw_text, optimizaciones, grupos, parametros)

    assert isinstance(excel_stream, BytesIO)
    assert excel_stream.getbuffer().nbytes > 0


def test_generar_dictamen_excel_has_exact_4_sheets(sample_dataset):
    raw_text, optimizaciones, grupos, parametros = sample_dataset
    excel_stream = generar_dictamen_excel(raw_text, optimizaciones, grupos, parametros)

    wb = openpyxl.load_workbook(excel_stream)
    sheet_names = wb.sheetnames
    assert len(sheet_names) == 4
    assert sheet_names == [
        "Carátula y Supuestos",
        "Resumen Directivo",
        "Detalle por Grupo",
        "Semáforo de Tiras",
    ]


def test_generar_dictamen_excel_sha256_hash_matches(sample_dataset):
    raw_text, optimizaciones, grupos, parametros = sample_dataset
    excel_stream = generar_dictamen_excel(raw_text, optimizaciones, grupos, parametros)

    wb = openpyxl.load_workbook(excel_stream)
    ws_caratula = wb["Carátula y Supuestos"]
    hash_en_celda = ws_caratula["C15"].value

    expected_hash = hashlib.sha256(raw_text.strip().encode("utf-8")).hexdigest().upper()
    assert hash_en_celda == expected_hash


def test_generar_dictamen_excel_totals_and_hours_match_models(sample_dataset):
    raw_text, optimizaciones, grupos, parametros = sample_dataset
    excel_stream = generar_dictamen_excel(raw_text, optimizaciones, grupos, parametros)

    wb = openpyxl.load_workbook(excel_stream, data_only=False)
    ws_resumen = wb["Resumen Directivo"]

    # Fila 3, 4 y 5 corresponden a las 3 optimizaciones
    total_propuestos_modelo = sum(o.grupos_propuestos for o in optimizaciones)
    horas_materia = parametros["horas_materia"]

    horas_calculadas = [ws_resumen.cell(row=r, column=10).value for r in range(3, 6)]
    assert sum(horas_calculadas) == total_propuestos_modelo * horas_materia

    ws_detalle = wb["Detalle por Grupo"]
    # Total de grupos optimizados en detalle debe coincidir con la suma de grupos en optimizaciones
    grupos_en_detalle = sum(len(o.grupos) for o in optimizaciones)
    # Renglones de datos van desde row=3 hasta 3 + grupos_en_detalle - 1
    max_row = ws_detalle.max_row
    assert max_row - 2 == grupos_en_detalle

