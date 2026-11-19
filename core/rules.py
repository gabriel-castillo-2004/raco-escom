from collections import Counter
import math
from typing import Any, Dict, List, Optional, Tuple

from core.models import AccionGrupo, GrupoInput, OptimizacionGrupo, ResumenMateria, Turno


def calcular_grupos_necesarios(demanda: int, cupo_max: int, tolerancia: int = 2) -> int:
    """
    Calcula el número mínimo de grupos necesarios con cupo blando (ADR-0002).
    k_propuestos = ceil(demanda / (cupo_max + tolerancia)) si demanda > 0 else 0.

    Raises:
        ValueError: Si cupo_max <= 0 o demanda < 0.
    """
    if cupo_max <= 0:
        raise ValueError(f"El cupo máximo debe ser mayor a cero, recibido: {cupo_max}")
    if demanda < 0:
        raise ValueError(f"La demanda no puede ser negativa, recibido: {demanda}")
    if demanda == 0:
        return 0
    capacidad_efectiva = cupo_max + max(0, tolerancia)
    return math.ceil(demanda / capacidad_efectiva)


def calcular_cupo_modal(grupos: List[GrupoInput], fallback: int = 35) -> int:
    """
    Calcula la moda del cupo_max entre los grupos existentes de una materia.
    Si no hay grupos, retorna fallback.
    """
    if not grupos:
        return fallback
    conteos = Counter(g.cupo_max for g in grupos)
    return sorted(conteos.items(), key=lambda x: (x[1], x[0]), reverse=True)[0][0]


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
    cupo_slider: Optional[int] = None,
    override_cupo: Optional[int] = None,
    tolerancia: int = 2,
) -> ResumenMateria:
    """
    Optimiza la oferta de grupos para una materia y turno específicos (ADR-0002).
    - Si override_cupo (o cupo_slider) es provisto, manda dicho valor.
    - De lo contrario, calcula el cupo modal entre los grupos de la materia.
    - Soporta aislamiento y protección de grupos con cupo atípico:
      * Laboratorios: cupo <= 0.6 * modal
      * Macro-grupos administrativos / Trabajo Terminal: cupo >= 100 o turno == Turno.X
    - Garantiza que los alumnos asignados al atípico no excedan la demanda total disponible.
    """
    if demanda < 0:
        raise ValueError(f"La demanda no puede ser negativa, recibido: {demanda}")

    # Determinar cupo base
    cupo_elegido = override_cupo if override_cupo is not None else cupo_slider
    grupos_materia = [g for g in grupos_existentes if g.materia == materia]
    cupo_modal = calcular_cupo_modal(grupos_materia, fallback=35)

    cupo_base = cupo_elegido if cupo_elegido is not None else cupo_modal
    if cupo_base <= 0:
        raise ValueError(f"El cupo objetivo debe ser mayor a cero, recibido: {cupo_base}")

    existentes_turno = [g for g in grupos_materia if g.turno == turno]
    num_actuales = len(existentes_turno)

    # Identificar grupos con cupo atípico protegidos
    umbral_laboratorio = 0.6 * cupo_modal
    grupos_atipicos: List[GrupoInput] = []
    grupos_regulares: List[GrupoInput] = []

    for g in existentes_turno:
        es_macro = (g.cupo_max >= 100 or g.turno == Turno.X)
        es_lab = (g.cupo_max <= umbral_laboratorio)
        if es_macro or es_lab:
            grupos_atipicos.append(g)
        else:
            grupos_regulares.append(g)

    grupos_optimizados: List[OptimizacionGrupo] = []
    alumnos_atendidos_atipicos = 0
    demanda_restante = demanda

    # 1. Proteger y aislar grupos atípicos (CONSERVAR)
    for g in grupos_atipicos:
        es_macro = (g.cupo_max >= 100 or g.turno == Turno.X)
        capacidad_atipica = g.cupo_max
        inscritos_previos = g.inscritos_actuales if g.inscritos_actuales > 0 else capacidad_atipica
        alumnos_asig = min(demanda_restante, capacidad_atipica, inscritos_previos)
        demanda_restante -= alumnos_asig
        alumnos_atendidos_atipicos += alumnos_asig

        if es_macro:
            justificacion_str = "Macro-grupo administrativo / Trabajo Terminal (sin partición de aula regular)."
        else:
            justificacion_str = "Grupo con cupo atípico protegido (laboratorio / espacio especializado)."

        grupos_optimizados.append(
            OptimizacionGrupo(
                grupo_id=g.grupo,
                materia=materia,
                turno=turno,
                inscritos_estimados=alumnos_asig,
                cupo_asignado=g.cupo_max,
                accion=AccionGrupo.CONSERVAR,
                justificacion=justificacion_str,
                es_atipico=True,
            )
        )

    # Demanda residual a cubrir por grupos estándar
    demanda_residual = max(0, demanda - alumnos_atendidos_atipicos)
    k_regulares_propuestos = calcular_grupos_necesarios(demanda_residual, cupo_base, tolerancia=tolerancia)
    distribucion_regular = distribuir_alumnos_balanceado(demanda_residual, k_regulares_propuestos)

    # 2. Asignar grupos regulares existentes
    for idx, g in enumerate(grupos_regulares):
        if idx < k_regulares_propuestos:
            alumnos = distribucion_regular[idx]
            grupos_optimizados.append(
                OptimizacionGrupo(
                    grupo_id=g.grupo,
                    materia=materia,
                    turno=turno,
                    inscritos_estimados=alumnos,
                    cupo_asignado=cupo_base,
                    accion=AccionGrupo.CONSERVAR,
                    justificacion=f"Grupo conservado con demanda estimada de {alumnos} alumnos.",
                    es_atipico=False,
                )
            )
        else:
            grupos_optimizados.append(
                OptimizacionGrupo(
                    grupo_id=g.grupo,
                    materia=materia,
                    turno=turno,
                    inscritos_estimados=0,
                    cupo_asignado=cupo_base,
                    accion=AccionGrupo.CERRAR,
                    justificacion="Grupo cerrado por baja demanda acumulada para este turno.",
                    es_atipico=False,
                )
            )

    # 3. Abrir nuevos grupos regulares si la demanda lo exige
    num_regulares_act = len(grupos_regulares)
    if k_regulares_propuestos > num_regulares_act:
        for j in range(num_regulares_act, k_regulares_propuestos):
            alumnos = distribucion_regular[j]
            nuevo_id = f"{turno.value}-NUEVO-{j + 1}"
            grupos_optimizados.append(
                OptimizacionGrupo(
                    grupo_id=nuevo_id,
                    materia=materia,
                    turno=turno,
                    inscritos_estimados=alumnos,
                    cupo_asignado=cupo_base,
                    accion=AccionGrupo.ABRIR,
                    justificacion=f"Nuevo grupo sugerido para absorber alta demanda ({alumnos} alumnos).",
                    es_atipico=False,
                )
            )

    k_total_propuestos = len(grupos_atipicos) + k_regulares_propuestos
    cupo_prom = (demanda / k_total_propuestos) if k_total_propuestos > 0 else 0.0

    return ResumenMateria(
        materia=materia,
        turno=turno,
        demanda_total=demanda,
        grupos_actuales=num_actuales,
        grupos_propuestos=k_total_propuestos,
        delta_grupos=k_total_propuestos - num_actuales,
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
                    g.model_copy(
                        update={
                            "inscritos_estimados": 0,
                            "accion": AccionGrupo.CERRAR,
                            "justificacion": "Ajustado a CERRAR por restricción de techo global presupuestal.",
                        }
                    )
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


def evaluar_semaforo_tiras(
    grupos_input: List[GrupoInput],
    filtro_turno: Optional[Turno] = None,
) -> List[Dict[str, Any]]:
    """
    Evalúa la salud de los paquetes curriculares (tiras) agrupando por (semestre, turno).
    Descarta grupos sin semestre válido (None o <= 0).

    Estados evaluados por bloque (semestre, turno):
      - ROJO (🔴 Tira Bloqueada): Todas las materias/grupos del bloque están saturados (disponibles <= 0).
      - AMARILLO (🟡 Tira Comprometida): Al menos 1 grupo está saturado, pero existen otros con disponibilidad.
      - VERDE (🟢 Tira Fluida / Libre): Todos los grupos evaluados del bloque tienen plazas disponibles (> 0).
    """
    bloques: Dict[Tuple[int, Turno], List[Dict[str, Any]]] = {}

    for g in grupos_input:
        if filtro_turno is not None and g.turno != filtro_turno:
            continue

        sem_val: Optional[int] = g.semestre
        if sem_val is None and g.grupo and g.grupo[0].isdigit():
            sem_val = int(g.grupo[0])

        if sem_val is None or sem_val <= 0:
            continue

        demanda_efectiva = max(g.inscritos_actuales, g.demanda_estimada)
        disponibles_reales = g.cupo_max - demanda_efectiva

        key = (sem_val, g.turno)
        if key not in bloques:
            bloques[key] = []
        bloques[key].append(
            {
                "materia": g.materia,
                "grupo": g.grupo,
                "disponibles": disponibles_reales,
            }
        )

    resultados: List[Dict[str, Any]] = []
    for (sem, turno), items in sorted(bloques.items(), key=lambda item: (item[0][0], item[0][1].value)):
        total_grupos = len(items)
        saturados = [it["materia"] for it in items if it["disponibles"] <= 0]
        num_saturados = len(saturados)
        materias_saturadas = sorted(set(saturados))

        if num_saturados == 0:
            estado = "VERDE"
            icono = "🟢"
            etiqueta = "Tira Fluida / Libre"
            diag_excel = "🟢 TIRA COMPLETA GARANTIZADA"
        elif num_saturados < total_grupos:
            estado = "AMARILLO"
            icono = "🟡"
            etiqueta = "Tira Comprometida"
            diag_excel = "🟡 TIRA EN RIESGO (PARCIALMENTE AGOTADA)"
        else:
            estado = "ROJO"
            icono = "🔴"
            etiqueta = "Tira Bloqueada"
            diag_excel = "🔴 TIRA BLOQUEADA (SIN CUPO)"

        resultados.append(
            {
                "semestre": sem,
                "turno": turno,
                "total_grupos": total_grupos,
                "grupos_saturados": num_saturados,
                "materias_saturadas": materias_saturadas,
                "estado": estado,
                "icono": icono,
                "etiqueta": etiqueta,
                "diagnostico_excel": diag_excel,
            }
        )

    return resultados
