import math
from typing import List

from core.models import AccionGrupo, GrupoInput, OptimizacionGrupo, ResumenMateria, Turno


def calcular_grupos_necesarios(demanda: int, cupo_max: int) -> int:
    """
    Calcula el número mínimo de grupos necesarios para cubrir la demanda dada.

    Raises:
        ValueError: Si cupo_max <= 0 o demanda < 0.
    """
    if cupo_max <= 0:
        raise ValueError(f"El cupo máximo debe ser mayor a cero, recibido: {cupo_max}")
    if demanda < 0:
        raise ValueError(f"La demanda no puede ser negativa, recibido: {demanda}")
    if demanda == 0:
        return 0
    return math.ceil(demanda / cupo_max)


def distribuir_alumnos_balanceado(demanda: int, num_grupos: int) -> List[int]:
    """
    Distribuye la demanda de forma balanceada entre el número de grupos especificado.
    La diferencia máxima entre cualquier par de grupos no excede 1 alumno.
    """
    if num_grupos <= 0:
        return []
    if demanda <= 0:
        return [0] * num_grupos

    base = demanda // num_grupos
    remanente = demanda % num_grupos

    # Los primeros 'remanente' grupos reciben base + 1, los demás 'base'
    return [base + 1 if i < remanente else base for i in range(num_grupos)]


def optimizar_materia_turno(
    materia: str,
    turno: Turno,
    demanda: int,
    grupos_existentes: List[GrupoInput],
    cupo_slider: int = 35,
) -> ResumenMateria:
    """
    Optimiza la oferta de grupos para una materia y turno específicos.
    Los turnos M y V se optimizan de forma estrictamente independiente.
    El cupo_slider manda sobre el cupo histórico/SAES.
    """
    if cupo_slider <= 0:
        raise ValueError(f"cupo_slider debe ser mayor a cero, recibido: {cupo_slider}")
    if demanda < 0:
        raise ValueError(f"La demanda no puede ser negativa, recibido: {demanda}")

    # Filtrar solo grupos correspondientes a la materia y turno
    existentes = [g for g in grupos_existentes if g.materia == materia and g.turno == turno]
    num_actuales = len(existentes)
    k_propuestos = calcular_grupos_necesarios(demanda, cupo_slider)

    distribucion = distribuir_alumnos_balanceado(demanda, k_propuestos)
    grupos_optimizados: List[OptimizacionGrupo] = []

    # 1. Procesar grupos existentes
    for idx, g in enumerate(existentes):
        if idx < k_propuestos:
            alumnos = distribucion[idx]
            grupos_optimizados.append(
                OptimizacionGrupo(
                    grupo_id=g.grupo,
                    materia=materia,
                    turno=turno,
                    inscritos_estimados=alumnos,
                    cupo_asignado=cupo_slider,
                    accion=AccionGrupo.CONSERVAR,
                    justificacion=f"Grupo conservado con demanda estimada de {alumnos} alumnos.",
                )
            )
        else:
            grupos_optimizados.append(
                OptimizacionGrupo(
                    grupo_id=g.grupo,
                    materia=materia,
                    turno=turno,
                    inscritos_estimados=0,
                    cupo_asignado=cupo_slider,
                    accion=AccionGrupo.CERRAR,
                    justificacion="Grupo cerrado por baja demanda acumulada para este turno.",
                )
            )

    # 2. Si k_propuestos > existentes, generar grupos adicionales con acción ABRIR
    if k_propuestos > num_actuales:
        for j in range(num_actuales, k_propuestos):
            alumnos = distribucion[j]
            nuevo_id = f"{turno.value}-NUEVO-{j + 1}"
            grupos_optimizados.append(
                OptimizacionGrupo(
                    grupo_id=nuevo_id,
                    materia=materia,
                    turno=turno,
                    inscritos_estimados=alumnos,
                    cupo_asignado=cupo_slider,
                    accion=AccionGrupo.ABRIR,
                    justificacion=f"Nuevo grupo sugerido para absorber alta demanda ({alumnos} alumnos).",
                )
            )

    cupo_prom = (demanda / k_propuestos) if k_propuestos > 0 else 0.0

    return ResumenMateria(
        materia=materia,
        turno=turno,
        demanda_total=demanda,
        grupos_actuales=num_actuales,
        grupos_propuestos=k_propuestos,
        delta_grupos=k_propuestos - num_actuales,
        cupo_promedio=round(cupo_prom, 2),
        grupos=grupos_optimizados,
    )


def _reconstruir_resumen_con_grupos(resumen: ResumenMateria, nuevos_k: int) -> ResumenMateria:
    """Reconstruye un ResumenMateria asignando exactamente nuevos_k grupos activos."""
    demanda = resumen.demanda_total
    distribucion = distribuir_alumnos_balanceado(demanda, nuevos_k)

    nuevos_grupos: List[OptimizacionGrupo] = []
    grupos_activos_creados = 0

    for g in resumen.grupos:
        if g.accion in (AccionGrupo.CONSERVAR, AccionGrupo.ABRIR):
            if grupos_activos_creados < nuevos_k:
                alumnos = distribucion[grupos_activos_creados]
                nuevos_grupos.append(
                    g.model_copy(update={"inscritos_estimados": alumnos})
                )
                grupos_activos_creados += 1
            else:
                nuevos_grupos.append(
                    g.model_copy(update={"inscritos_estimados": 0, "accion": AccionGrupo.CERRAR, "justificacion": "Ajustado a CERRAR por restricción de techo global presupuestal."})
                )
        else:
            nuevos_grupos.append(g)

    cupo_prom = (demanda / nuevos_k) if nuevos_k > 0 else 0.0
    return ResumenMateria(
        materia=resumen.materia,
        turno=resumen.turno,
        demanda_total=demanda,
        grupos_actuales=resumen.grupos_actuales,
        grupos_propuestos=nuevos_k,
        delta_grupos=nuevos_k - resumen.grupos_actuales,
        cupo_promedio=round(cupo_prom, 2),
        grupos=nuevos_grupos,
    )


def aplicar_techo_global(resumenes: List[ResumenMateria], max_grupos_global: int) -> List[ResumenMateria]:
    """
    Aplica restricción presupuestal global (max_grupos_global) usando algoritmo greedy:
    si la suma total de grupos propuestos supera max_grupos_global, reduce grupos
    empezando por las materias con menor saturación (menor cupo_promedio).
    """
    if max_grupos_global < 0:
        raise ValueError("max_grupos_global debe ser mayor o igual a cero")

    resultado = list(resumenes)
    total_propuestos = sum(r.grupos_propuestos for r in resultado)

    while total_propuestos > max_grupos_global:
        candidatos = [r for r in resultado if r.grupos_propuestos > 1]
        if not candidatos:
            break
        menos_saturada = min(candidatos, key=lambda r: (r.cupo_promedio, r.materia, r.turno.value))
        idx = resultado.index(menos_saturada)
        resultado[idx] = _reconstruir_resumen_con_grupos(menos_saturada, menos_saturada.grupos_propuestos - 1)
        total_propuestos = sum(r.grupos_propuestos for r in resultado)

    return resultado

