from io import StringIO
from pathlib import Path
import pytest

from core.models import GrupoInput, Turno
from core.parser import parse_academic_data, parse_saes_clipboard_text


def test_parse_synthetic_csv_file():
    csv_path = Path("data/synthetic_escom.csv")
    assert csv_path.exists(), "El dataset sintético debe existir"

    grupos, demanda = parse_academic_data(csv_path)

    assert len(grupos) == 16
    assert all(isinstance(g, GrupoInput) for g in grupos)
    assert all(g.cupo_max == 35 for g in grupos)
    assert ("Cálculo", Turno.M) in demanda
    assert ("Cálculo", Turno.V) in demanda


def test_missing_required_columns_raises_error():
    invalid_csv = StringIO("materia,grupo,turno\nCálculo,1CM1,M\n")
    with pytest.raises(ValueError, match="Columnas faltantes"):
        parse_academic_data(invalid_csv)


def test_invalid_turno_value_raises_error():
    invalid_csv = StringIO(
        "materia,grupo,turno,cupo_max,inscritos_actuales,demanda_estimada\n"
        "Cálculo,1CM1,X,35,30,40\n"
    )
    with pytest.raises(ValueError, match="Valores de turno inválidos"):
        parse_academic_data(invalid_csv)


def test_whitespace_normalization_and_lowercase_turno():
    csv_data = StringIO(
        "materia,grupo,turno,cupo_max,inscritos_actuales,demanda_estimada\n"
        "  Álgebra Lineal   ,  1CM2  , m , 35 , 30 , 35 \n"
    )
    grupos, demanda = parse_academic_data(csv_data)

    assert len(grupos) == 1
    assert grupos[0].materia == "Álgebra Lineal"
    assert grupos[0].grupo == "1CM2"
    assert grupos[0].turno == Turno.M
    assert demanda[("Álgebra Lineal", Turno.M)] == 35


def test_demand_aggregation_by_subject_and_turno():
    csv_data = StringIO(
        "materia,grupo,turno,cupo_max,inscritos_actuales,demanda_estimada\n"
        "Redes,3CM1,M,35,30,40\n"
        "Redes,3CM2,M,35,32,45\n"
        "Redes,3CV1,V,35,20,25\n"
    )
    grupos, demanda = parse_academic_data(csv_data)

    assert len(grupos) == 3
    assert demanda[("Redes", Turno.M)] == 85
    assert demanda[("Redes", Turno.V)] == 25


def test_invalid_integer_types_raises_error():
    csv_data = StringIO(
        "materia,grupo,turno,cupo_max,inscritos_actuales,demanda_estimada\n"
        "Cálculo,1CM1,M,treinta,30,40\n"
    )
    with pytest.raises(ValueError, match="contiene valores no numéricos"):
        parse_academic_data(csv_data)


def test_excel_file_support(tmp_path):
    import pandas as pd

    excel_path = tmp_path / "test_oferta.xlsx"
    df = pd.DataFrame([
        {
            "materia": "Compiladores",
            "grupo": "4CM1",
            "turno": "M",
            "cupo_max": 35,
            "inscritos_actuales": 20,
            "demanda_estimada": 25,
        }
    ])
    df.to_excel(excel_path, index=False)

    grupos, demanda = parse_academic_data(excel_path)
    assert len(grupos) == 1
    assert grupos[0].materia == "Compiladores"
    assert demanda[("Compiladores", Turno.M)] == 25


def test_saes_clipboard_parser_extracts_correct_fields():
    raw_text = (
        "1AM1\tA101\tCALCULO MULTIVARIABLE\t35\t36\t-1\n"
        "3AV2\tA204\tREDES DE COMPUTADORAS\t18\t18\t0\n"
        "5CM1\tB301\tSISTEMAS DISTRIBUIDOS\t7\t0\t7\n"
        "2CV1\tC202\tESTRUCTURAS DE DATOS\t35\t38\t-3\n"
    )
    df = parse_saes_clipboard_text(raw_text)

    assert len(df) == 4
    assert list(df["grupo"]) == ["1AM1", "3AV2", "5CM1", "2CV1"]
    assert list(df["semestre"]) == [1, 3, 5, 2]
    assert list(df["carrera"]) == ["A", "A", "C", "C"]
    assert list(df["turno"]) == [Turno.M, Turno.V, Turno.M, Turno.V]

    # Cupos especiales y disponibles negativos
    fila_calculo = df[df["grupo"] == "1AM1"].iloc[0]
    assert fila_calculo["cupo"] == 35
    assert fila_calculo["inscritos"] == 36
    assert fila_calculo["disponibles"] == -1
    assert not fila_calculo["discrepancia_saes"]

    fila_redes = df[df["grupo"] == "3AV2"].iloc[0]
    assert fila_redes["cupo"] == 18
    assert fila_redes["inscritos"] == 18
    assert fila_redes["disponibles"] == 0

    # Caso grupo zombi (7 cupos, 0 inscritos)
    fila_zombi = df[df["grupo"] == "5CM1"].iloc[0]
    assert fila_zombi["cupo"] == 7
    assert fila_zombi["inscritos"] == 0
    assert fila_zombi["disponibles"] == 7


def test_saes_clipboard_parser_detects_discrepancy():
    # Simulación de inconsistencia interna SAES (ej. cupo 35, inscritos 30 pero disponibles reporta 2)
    raw_text = "1CM1\tA102\tALGEBRA LINEAL\t35\t30\t2\n"
    df = parse_saes_clipboard_text(raw_text)

    assert len(df) == 1
    assert bool(df.iloc[0]["discrepancia_saes"]) is True


def test_saes_clipboard_parser_with_semester_column():
    raw_text = "4CM2\tA405\tCOMPILADORES\t4\t30\t30\t0\n"
    df = parse_saes_clipboard_text(raw_text)

    assert len(df) == 1
    assert df.iloc[0]["semestre"] == 4
    assert df.iloc[0]["nombre_materia"] == "COMPILADORES"


def test_saes_clipboard_parser_empty_text():
    df = parse_saes_clipboard_text("")
    assert df.empty


def test_saes_clipboard_materia_con_numero_y_formato_oficial():
    # Valida materias con números en el nombre delimitadas por espacios dobles o tabs
    raw_text = (
        "8CM1  TT801  TRABAJO TERMINAL 1  8  25  24  1\n"
        "3CV1\tING30\tINGLES 2\t30\t32\t-2\n"
    )
    df = parse_saes_clipboard_text(raw_text)

    assert len(df) == 2
    tt = df[df["grupo"] == "8CM1"].iloc[0]
    assert tt["nombre_materia"] == "TRABAJO TERMINAL 1"
    assert tt["semestre"] == 8
    assert tt["cupo"] == 25
    assert tt["inscritos"] == 24
    assert tt["disponibles"] == 1
    assert not tt["discrepancia_saes"]

    ingles = df[df["grupo"] == "3CV1"].iloc[0]
    assert ingles["nombre_materia"] == "INGLES 2"
    assert ingles["semestre"] == 3
    assert ingles["turno"] == Turno.V
    assert ingles["cupo"] == 30
    assert ingles["inscritos"] == 32
    assert ingles["disponibles"] == -2
    assert not ingles["discrepancia_saes"]
