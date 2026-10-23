from io import StringIO
from pathlib import Path
import pytest

from core.models import GrupoInput, Turno
from core.parser import parse_academic_data


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

