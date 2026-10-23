import pytest
from core.models import AccionGrupo, GrupoInput, Turno
from core.rules import (
    aplicar_techo_global,
    calcular_grupos_necesarios,
    distribuir_alumnos_balanceado,
    optimizar_materia_turno,
)


def test_01_demanda_cero_grupos_cero():
    assert calcular_grupos_necesarios(0, 35) == 0


def test_02_demanda_exacta_un_cupo():
    assert calcular_grupos_necesarios(35, 35) == 1


def test_03_quiebre_un_alumno_extra_abre_grupo():
    assert calcular_grupos_necesarios(36, 35) == 2


def test_04_distribucion_equitativa_exacta():
    dist = distribuir_alumnos_balanceado(70, 2)
    assert dist == [35, 35]


def test_05_distribucion_equitativa_con_remanente():
    dist = distribuir_alumnos_balanceado(50, 2)
    assert dist == [25, 25]


def test_06_distribucion_equitativa_remanente_impar():
    dist = distribuir_alumnos_balanceado(71, 3)
    assert dist == [24, 24, 23]
    assert sum(dist) == 71


def test_07_cupo_duro_no_se_supera():
    res = optimizar_materia_turno("Cálculo", Turno.M, 35, [], cupo_slider=35)
    assert all(g.inscritos_estimados <= g.cupo_asignado for g in res.grupos)


def test_08_slider_manda_sobre_cupo_saes():
    grupo = GrupoInput(
        materia="Redes", grupo="3CM1", turno=Turno.M, cupo_max=40, inscritos_actuales=30, demanda_estimada=30
    )
    # Con cupo_slider=25 y demanda 30 -> math.ceil(30/25) = 2 grupos
    res = optimizar_materia_turno("Redes", Turno.M, 30, [grupo], cupo_slider=25)
    assert res.grupos_propuestos == 2
    assert all(g.cupo_asignado == 25 for g in res.grupos)


def test_09_sin_estatus_rebalancear():
    grupo = GrupoInput(
        materia="Algoritmia", grupo="1CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=20, demanda_estimada=20
    )
    res = optimizar_materia_turno("Algoritmia", Turno.M, 20, [grupo], cupo_slider=35)
    acciones = {g.accion for g in res.grupos}
    assert acciones.issubset({AccionGrupo.CONSERVAR, AccionGrupo.ABRIR, AccionGrupo.CERRAR})


def test_10_cerrar_grupo_excedente():
    g1 = GrupoInput(materia="Compiladores", grupo="4CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=10, demanda_estimada=10)
    g2 = GrupoInput(materia="Compiladores", grupo="4CM2", turno=Turno.M, cupo_max=35, inscritos_actuales=10, demanda_estimada=10)
    # Demanda total = 20, con slider 35 -> 1 grupo propuesto
    res = optimizar_materia_turno("Compiladores", Turno.M, 20, [g1, g2], cupo_slider=35)
    assert res.grupos_propuestos == 1
    cerrados = [g for g in res.grupos if g.accion == AccionGrupo.CERRAR]
    assert len(cerrados) == 1
    assert cerrados[0].inscritos_estimados == 0


def test_11_abrir_nuevo_grupo_por_alta_demanda():
    g1 = GrupoInput(materia="IA", grupo="5CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=35, demanda_estimada=70)
    res = optimizar_materia_turno("IA", Turno.M, 70, [g1], cupo_slider=35)
    assert res.grupos_propuestos == 2
    abiertos = [g for g in res.grupos if g.accion == AccionGrupo.ABRIR]
    assert len(abiertos) == 1


def test_12_turnos_independientes():
    g_m = GrupoInput(materia="Física", grupo="1CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=35, demanda_estimada=35)
    g_v = GrupoInput(materia="Física", grupo="1CV1", turno=Turno.V, cupo_max=35, inscritos_actuales=10, demanda_estimada=10)
    res_m = optimizar_materia_turno("Física", Turno.M, 35, [g_m, g_v], cupo_slider=35)
    res_v = optimizar_materia_turno("Física", Turno.V, 10, [g_m, g_v], cupo_slider=35)
    assert res_m.grupos_actuales == 1
    assert res_v.grupos_actuales == 1
    assert all(g.turno == Turno.M for g in res_m.grupos)
    assert all(g.turno == Turno.V for g in res_v.grupos)


def test_13_mantiene_identificador_original():
    g1 = GrupoInput(materia="SO", grupo="3CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=30, demanda_estimada=30)
    res = optimizar_materia_turno("SO", Turno.M, 30, [g1], cupo_slider=35)
    assert res.grupos[0].grupo_id == "3CM1"


def test_14_nuevo_id_formato_correcto():
    res_m = optimizar_materia_turno("Cálculo", Turno.M, 70, [], cupo_slider=35)
    assert res_m.grupos[0].grupo_id == "M-NUEVO-1"
    assert res_m.grupos[1].grupo_id == "M-NUEVO-2"

    res_v = optimizar_materia_turno("Cálculo", Turno.V, 35, [], cupo_slider=35)
    assert res_v.grupos[0].grupo_id == "V-NUEVO-1"


def test_15_error_demanda_negativa():
    with pytest.raises(ValueError, match="no puede ser negativa"):
        calcular_grupos_necesarios(-5, 35)


def test_16_error_cupo_invalido():
    with pytest.raises(ValueError, match="mayor a cero"):
        calcular_grupos_necesarios(35, 0)


def test_17_techo_global_greedy():
    # Materia 1: 36 alumnos en 2 grupos -> saturación 18 alumnos/grupo
    # Materia 2: 70 alumnos en 2 grupos -> saturación 35 alumnos/grupo
    r1 = optimizar_materia_turno("Compiladores", Turno.M, 36, [], cupo_slider=35)  # 2 grupos
    r2 = optimizar_materia_turno("Algoritmia", Turno.M, 70, [], cupo_slider=35)    # 2 grupos
    # Total inicial: 4 grupos. Techo: 3 grupos.
    ajustados = aplicar_techo_global([r1, r2], max_grupos_global=3)
    assert sum(r.grupos_propuestos for r in ajustados) == 3
    # Compiladores (menor cupo_promedio) debió ser reducida a 1 grupo
    r1_ajustado = next(r for r in ajustados if r.materia == "Compiladores")
    assert r1_ajustado.grupos_propuestos == 1


def test_18_determinismo_reglas():
    g1 = GrupoInput(materia="ED", grupo="2CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=35, demanda_estimada=55)
    res1 = optimizar_materia_turno("ED", Turno.M, 55, [g1], cupo_slider=35)
    res2 = optimizar_materia_turno("ED", Turno.M, 55, [g1], cupo_slider=35)
    assert res1.model_dump() == res2.model_dump()

