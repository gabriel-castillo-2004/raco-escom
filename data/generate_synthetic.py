import csv
from pathlib import Path


def generate_synthetic_data(output_path: Path) -> list[dict]:
    """
    Genera datos sintéticos de oferta y demanda académica simulando el SAES (ESCOM-IPN).
    Incluye escenarios intencionales:
    - Sobrecupo (demanda_estimada > cupo_max)
    - Subutilización (baja demanda / baja inscripción para consolidación de grupos)
    - Equilibrados (demanda e inscripción cercanas al cupo máximo)
    """
    default_cupo = 35

    rows = [
        # 1. Cálculo - Caso: Sobrecupo alto en ambos turnos
        {"materia": "Cálculo", "grupo": "1CM1", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 52},
        {"materia": "Cálculo", "grupo": "1CV1", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 44},

        # 2. Álgebra Lineal - Caso: Equilibrado en matutino, subutilizado en vespertino
        {"materia": "Álgebra Lineal", "grupo": "1CM2", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 33, "demanda_estimada": 35},
        {"materia": "Álgebra Lineal", "grupo": "1CV2", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 12, "demanda_estimada": 14},

        # 3. Algoritmia - Caso: Sobrecupo en matutino, equilibrado en vespertino
        {"materia": "Algoritmia", "grupo": "1CM3", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 48},
        {"materia": "Algoritmia", "grupo": "1CV3", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 32, "demanda_estimada": 34},

        # 4. Estructuras de Datos - Caso: Sobrecupo severo en ambos turnos
        {"materia": "Estructuras de Datos", "grupo": "2CM1", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 55},
        {"materia": "Estructuras de Datos", "grupo": "2CV1", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 46},

        # 5. Redes - Caso: Equilibrado en ambos turnos
        {"materia": "Redes", "grupo": "3CM1", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 34, "demanda_estimada": 35},
        {"materia": "Redes", "grupo": "3CV1", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 31, "demanda_estimada": 33},

        # 6. Sistemas Operativos - Caso: Subutilizado en dos grupos del mismo turno y vespertino (candidatos a consolidación)
        {"materia": "Sistemas Operativos", "grupo": "3CM2", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 14, "demanda_estimada": 15},
        {"materia": "Sistemas Operativos", "grupo": "3CV2", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 11, "demanda_estimada": 13},

        # 7. Compiladores - Caso: Subutilizado (baja demanda general, consolidable en un solo grupo)
        {"materia": "Compiladores", "grupo": "4CM1", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 15, "demanda_estimada": 16},
        {"materia": "Compiladores", "grupo": "4CV1", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 10, "demanda_estimada": 11},

        # 8. Inteligencia Artificial - Caso: Sobrecupo alto en ambos turnos
        {"materia": "Inteligencia Artificial", "grupo": "5CM1", "turno": "M", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 60},
        {"materia": "Inteligencia Artificial", "grupo": "5CV1", "turno": "V", "cupo_max": default_cupo, "inscritos_actuales": 35, "demanda_estimada": 49},
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["materia", "grupo", "turno", "cupo_max", "inscritos_actuales", "demanda_estimada"]

    with output_path.open(mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return rows


def main() -> None:
    output_csv = Path(__file__).resolve().parent / "synthetic_escom.csv"
    rows = generate_synthetic_data(output_csv)
    print(f"Dataset generado exitosamente en: {output_csv} ({len(rows)} registros)\n")
    print("Resumen de los primeros 5 registros generados:")
    print(f"{'MATERIA':<20} | {'GRUPO':<6} | {'TURNO':<5} | {'CUPO':<4} | {'INSCRITOS':<9} | {'DEMANDA':<7}")
    print("-" * 65)
    for row in rows[:5]:
        print(
            f"{row['materia']:<20} | {row['grupo']:<6} | {row['turno']:<5} | "
            f"{row['cupo_max']:<4} | {row['inscritos_actuales']:<9} | {row['demanda_estimada']:<7}"
        )


if __name__ == "__main__":
    main()

