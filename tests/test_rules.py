import pytest
from core.models import AccionGrupo, GrupoInput, Turno
from core.rules import (
    aplicar_techo_global,
    calcular_cupo_modal,
    calcular_grupos_necesarios,
    distribuir_alumnos_balanceado,
    evaluar_semaforo_tiras,
    optimizar_materia_turno,
)


def test_01_demanda_cero_grupos_cero():
    assert calcular_grupos_necesarios(0, 35) == 0


def test_02_demanda_exacta_un_cupo():
    assert calcular_grupos_necesarios(35, 35) == 1


def test_03_quiebre_un_alumno_extra_abre_grupo():
    # Con tolerancia=0 quiebra en 36
    assert calcular_grupos_necesarios(36, 35, tolerancia=0) == 2


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
    res = optimizar_materia_turno("Cálculo", Turno.M, 35, [], override_cupo=35, tolerancia=0)
    assert all(g.inscritos_estimados <= g.cupo_asignado for g in res.grupos)


def test_08_slider_manda_sobre_cupo_saes():
    grupo = GrupoInput(
        materia="Redes", grupo="3CM1", turno=Turno.M, cupo_max=40, inscritos_actuales=30, demanda_estimada=30
    )
    # Con override_cupo=25, tolerancia=0 y demanda 30 -> math.ceil(30/25) = 2 grupos
    res = optimizar_materia_turno("Redes", Turno.M, 30, [grupo], override_cupo=25, tolerancia=0)
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
        calcular_grupos_necesarios(-5, 35, tolerancia=0)


def test_16_error_cupo_invalido():
    with pytest.raises(ValueError, match="mayor a cero"):
        calcular_grupos_necesarios(35, 0)


def test_17_techo_global_greedy():
    # Materia 1: 36 alumnos en 2 grupos -> saturación 18 alumnos/grupo
    # Materia 2: 70 alumnos en 2 grupos -> saturación 35 alumnos/grupo
    r1 = optimizar_materia_turno("Compiladores", Turno.M, 36, [], cupo_slider=35, tolerancia=0)  # 2 grupos
    r2 = optimizar_materia_turno("Algoritmia", Turno.M, 70, [], cupo_slider=35, tolerancia=0)    # 2 grupos
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


def test_19_cupo_blando_tolerancia_dos_absorbe_hasta_38_y_quiebra_en_39():
    # cupo 36 y tolerancia 2 -> capacidad efectiva 38
    assert calcular_grupos_necesarios(36, 36, tolerancia=2) == 1
    assert calcular_grupos_necesarios(37, 36, tolerancia=2) == 1
    assert calcular_grupos_necesarios(38, 36, tolerancia=2) == 1
    assert calcular_grupos_necesarios(39, 36, tolerancia=2) == 2


def test_20_tolerancia_cero_replica_cupo_duro():
    assert calcular_grupos_necesarios(35, 35, tolerancia=0) == 1
    assert calcular_grupos_necesarios(36, 35, tolerancia=0) == 2


def test_21_cupo_modal_por_defecto_sin_override():
    g1 = GrupoInput(materia="Física", grupo="1CM1", turno=Turno.M, cupo_max=30, inscritos_actuales=30, demanda_estimada=30)
    g2 = GrupoInput(materia="Física", grupo="1CM2", turno=Turno.M, cupo_max=30, inscritos_actuales=30, demanda_estimada=30)
    g3 = GrupoInput(materia="Física", grupo="1CM3", turno=Turno.M, cupo_max=35, inscritos_actuales=35, demanda_estimada=35)
    # Moda es 30
    assert calcular_cupo_modal([g1, g2, g3]) == 30
    res = optimizar_materia_turno("Física", Turno.M, 60, [g1, g2, g3], override_cupo=None, tolerancia=0)
    assert res.grupos_propuestos == 2


def test_22_grupos_atipicos_laboratorio_protegidos():
    # Modal es 35. Un laboratorio tiene cupo 18 (<= 0.6 * 35 = 21)
    g_teoria = GrupoInput(materia="Química", grupo="1CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=35, demanda_estimada=35)
    g_lab = GrupoInput(materia="Química", grupo="1LM1", turno=Turno.M, cupo_max=18, inscritos_actuales=18, demanda_estimada=18)
    res = optimizar_materia_turno("Química", Turno.M, 35, [g_teoria, g_lab], override_cupo=35, tolerancia=2)
    lab_res = next(g for g in res.grupos if g.grupo_id == "1LM1")
    assert lab_res.accion == AccionGrupo.CONSERVAR
    assert lab_res.es_atipico is True


def test_macro_grupo_trabajo_terminal_no_se_subdivide():
    # Grupo administrativo con cupo 250 en Turno.X
    g_tt = GrupoInput(
        materia="Trabajo Terminal I",
        grupo="7AX1",
        turno=Turno.X,
        cupo_max=250,
        inscritos_actuales=180,
        demanda_estimada=180,
    )
    res = optimizar_materia_turno(
        materia="Trabajo Terminal I",
        turno=Turno.X,
        demanda=180,
        grupos_existentes=[g_tt],
        override_cupo=35,
        tolerancia=2,
    )

    assert res.grupos_propuestos == 1
    assert len(res.grupos) == 1
    grupo_opt = res.grupos[0]
    assert grupo_opt.grupo_id == "7AX1"
    assert grupo_opt.turno == Turno.X
    assert grupo_opt.cupo_asignado == 250
    assert grupo_opt.inscritos_estimados == 180
    assert grupo_opt.accion == AccionGrupo.CONSERVAR
    assert grupo_opt.es_atipico is True
    assert "Macro-grupo administrativo" in grupo_opt.justificacion


def test_23_evaluar_semaforo_tiras_tres_estados_verde_amarillo_rojo():
    grupos = [
        # Semestre 1 Matutino: 2 de 2 saturados -> ROJO (🔴)
        GrupoInput(materia="Cálculo", grupo="1AM1", turno=Turno.M, semestre=1, cupo_max=35, inscritos_actuales=35, demanda_estimada=35),
        GrupoInput(materia="Programación", grupo="1AM2", turno=Turno.M, semestre=1, cupo_max=35, inscritos_actuales=37, demanda_estimada=37),
        # Semestre 2 Matutino: 1 de 2 saturado -> AMARILLO (🟡)
        GrupoInput(materia="Álgebra Lineal", grupo="2AM1", turno=Turno.M, semestre=2, cupo_max=36, inscritos_actuales=37, demanda_estimada=37),
        GrupoInput(materia="Cálculo Multivariable", grupo="2AM2", turno=Turno.M, semestre=2, cupo_max=36, inscritos_actuales=20, demanda_estimada=20),
        # Semestre 3 Vespertino: 0 de 2 saturados -> VERDE (🟢)
        GrupoInput(materia="Bases de Datos", grupo="3AV1", turno=Turno.V, semestre=3, cupo_max=30, inscritos_actuales=18, demanda_estimada=18),
        GrupoInput(materia="Redes", grupo="3AV2", turno=Turno.V, semestre=3, cupo_max=30, inscritos_actuales=22, demanda_estimada=22),
    ]

    diagnosticos = evaluar_semaforo_tiras(grupos)
    assert len(diagnosticos) == 3

    # Semestre 1 M -> ROJO
    d_sem1 = diagnosticos[0]
    assert (d_sem1["semestre"], d_sem1["turno"]) == (1, Turno.M)
    assert d_sem1["estado"] == "ROJO"
    assert d_sem1["icono"] == "🔴"
    assert d_sem1["grupos_saturados"] == 2
    assert d_sem1["materias_saturadas"] == ["Cálculo", "Programación"]

    # Semestre 2 M -> AMARILLO
    d_sem2 = diagnosticos[1]
    assert (d_sem2["semestre"], d_sem2["turno"]) == (2, Turno.M)
    assert d_sem2["estado"] == "AMARILLO"
    assert d_sem2["icono"] == "🟡"
    assert d_sem2["grupos_saturados"] == 1
    assert d_sem2["materias_saturadas"] == ["Álgebra Lineal"]

    # Semestre 3 V -> VERDE
    d_sem3 = diagnosticos[2]
    assert (d_sem3["semestre"], d_sem3["turno"]) == (3, Turno.V)
    assert d_sem3["estado"] == "VERDE"
    assert d_sem3["icono"] == "🟢"
    assert d_sem3["grupos_saturados"] == 0
    assert d_sem3["materias_saturadas"] == []


def test_24_evaluar_semaforo_tiras_separa_matutino_y_vespertino_mismo_semestre():
    grupos = [
        # Semestre 2 Matutino: saturado (ROJO)
        GrupoInput(materia="Álgebra Lineal", grupo="2CM1", turno=Turno.M, cupo_max=35, inscritos_actuales=36, demanda_estimada=36),
        # Semestre 2 Vespertino: libre (VERDE)
        GrupoInput(materia="Álgebra Lineal", grupo="2CV1", turno=Turno.V, cupo_max=35, inscritos_actuales=12, demanda_estimada=12),
    ]

    todos = evaluar_semaforo_tiras(grupos)
    assert len(todos) == 2

    bloque_m = next(b for b in todos if b["turno"] == Turno.M)
    bloque_v = next(b for b in todos if b["turno"] == Turno.V)

    assert bloque_m["semestre"] == 2
    assert bloque_m["estado"] == "ROJO"
    assert bloque_m["icono"] == "🔴"

    assert bloque_v["semestre"] == 2
    assert bloque_v["estado"] == "VERDE"
    assert bloque_v["icono"] == "🟢"

    # Validar filtro por turno opcional
    solo_v = evaluar_semaforo_tiras(grupos, filtro_turno=Turno.V)
    assert len(solo_v) == 1
    assert solo_v[0]["turno"] == Turno.V
    assert solo_v[0]["estado"] == "VERDE"
