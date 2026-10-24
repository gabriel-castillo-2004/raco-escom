from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from core.exporter import generar_dictamen_excel
from core.models import AccionGrupo, GrupoInput, ResumenMateria, Turno
from core.parser import parse_academic_data, parse_saes_clipboard_text
from core.rules import aplicar_techo_global, optimizar_materia_turno

# 1. Configuración Institucional
st.set_page_config(
    page_title="RACO | ESCOM-IPN",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🎓 RACO: Risk-Adjusted Capacity Optimizer")
st.caption("Planificación y Optimización de Capacidad Docente — Escuela Superior de Cómputo (ESCOM IPN)")
st.divider()

# Inicialización de Session State para persistencia (Fila 8)
if "saes_raw_text" not in st.session_state:
    st.session_state["saes_raw_text"] = ""
if "modo_fuente" not in st.session_state:
    st.session_state["modo_fuente"] = "clipboard"
if "es_sintetico" not in st.session_state:
    st.session_state["es_sintetico"] = False

# 2. Barra Lateral de Simulación (Sidebar)
st.sidebar.header("📥 Ingesta de Datos")

metodo_ingesta = st.sidebar.radio(
    "Método de Entrada:",
    options=["Pegar desde SAES (Portapapeles)", "Subir archivo (.csv / .xlsx)"],
    index=0 if st.session_state["modo_fuente"] == "clipboard" else 1,
)

grupos_input: List[GrupoInput] = []
demanda_agregada: Dict[Tuple[str, Turno], int] = {}
df_clipboard_raw: pd.DataFrame = pd.DataFrame()
hubo_error_ingesta = False
raw_source_content = ""
lineas_omitidas = 0

if metodo_ingesta == "Pegar desde SAES (Portapapeles)":
    st.session_state["modo_fuente"] = "clipboard"
    st.session_state["es_sintetico"] = False

    # Mover área de pegado al cuerpo principal con expander (Filas 28 y 40)
    with st.expander("📋 Ingesta de datos SAES (Copiar / Pegar)", expanded=(not bool(st.session_state["saes_raw_text"]))):
        col_txt, col_ops = st.columns([4, 1])
        with col_ops:
            st.markdown("**Acciones Rápidas**")
            if st.button("Cargar Ejemplo SAES", use_container_width=True):
                st.session_state["saes_raw_text"] = (
                    "1AM1\tA101\tFUNDAMENTOS DE PROGRAMACION\t1\t33\t33\t0\n"
                    "2AM1\tA201\tALGEBRA LINEAL\t2\t36\t37\t-1\n"
                    "2AV2\tA202\tCALCULO MULTIVARIABLE\t2\t36\t6\t30\n"
                    "3AV2\tA301\tBASES DE DATOS\t3\t18\t8\t10\n"
                    "7AV1\tA701\tADMINISTRACION DE PROYECTOS DE TI\t7\t35\t39\t-4\n"
                    "7AX1\tA703\tTRABAJO TERMINAL I\t7\t250\t0\t250\n"
                    "1LM1\tQ101\tLABORATORIO QUIMICA\t1\t18\t18\t0"
                )
                st.rerun()

            if st.button("Limpiar Entrada", use_container_width=True):
                st.session_state["saes_raw_text"] = ""
                st.rerun()

        with col_txt:
            raw_clipboard = st.text_area(
                "Pega directamente la tabla copiada del SAES (Ctrl+V):",
                value=st.session_state["saes_raw_text"],
                height=160,
                placeholder=(
                    "1AM1\tA101\tFUNDAMENTOS DE PROGRAMACION\t1\t33\t33\t0\n"
                    "2AM1\tA201\tALGEBRA LINEAL\t2\t36\t37\t-1\n"
                    "7AX1\tA703\tTRABAJO TERMINAL I\t7\t250\t0\t250"
                ),
            )
            if raw_clipboard != st.session_state["saes_raw_text"]:
                st.session_state["saes_raw_text"] = raw_clipboard

    raw_source_content = st.session_state["saes_raw_text"]

    if raw_source_content.strip():
        try:
            total_lineas_no_vacias = len([l for l in raw_source_content.splitlines() if l.strip()])
            df_clipboard_raw = parse_saes_clipboard_text(raw_source_content)
            lineas_omitidas = max(0, total_lineas_no_vacias - len(df_clipboard_raw))

            if not df_clipboard_raw.empty:
                for _, row in df_clipboard_raw.iterrows():
                    demanda_calc = int(row["cupo"]) - int(row["disponibles"])
                    demanda_final = max(int(row["inscritos"]), demanda_calc)
                    g_obj = GrupoInput(
                        materia=str(row["nombre_materia"]).strip(),
                        grupo=str(row["grupo"]).strip(),
                        turno=row["turno"],
                        cupo_max=int(row["cupo"]),
                        inscritos_actuales=int(row["inscritos"]),
                        demanda_estimada=demanda_final,
                        materia_id=str(row["materia_id"]).strip(),
                        semestre=int(row["semestre"]) if pd.notna(row["semestre"]) else None,
                        carrera=str(row["carrera"]).strip(),
                    )
                    grupos_input.append(g_obj)
                    key = (g_obj.materia, g_obj.turno)
                    demanda_agregada[key] = demanda_agregada.get(key, 0) + g_obj.demanda_estimada

                # Métrica y feedback de ingesta (Fila 28 y 40)
                col_met1, col_met2 = st.columns([2, 3])
                col_met1.success(f"✅ **{len(grupos_input)}** grupos procesados correctamente")
                if lineas_omitidas > 0:
                    col_met2.warning(f"⚠️ Se omitieron **{lineas_omitidas}** líneas no conformes con el formato SAES.")
            else:
                st.warning("⚠️ No se detectaron filas válidas en el texto pegado.")
        except Exception as e:
            st.error(f"❌ Error al procesar portapapeles: {e}")
            hubo_error_ingesta = True
else:
    st.session_state["modo_fuente"] = "file"
    uploaded_file = st.sidebar.file_uploader(
        "Cargar Oferta / Demanda (.csv, .xlsx)",
        type=["csv", "xlsx", "xls"],
        help="Archivo con columnas: materia, grupo, turno, cupo_max, inscritos_actuales, demanda_estimada",
    )
    btn_sintetico = st.sidebar.button("Cargar sintéticos de ESCOM (Demo)", use_container_width=True)

    default_csv = Path("data/synthetic_escom.csv")
    file_to_parse = None

    if uploaded_file is not None:
        file_to_parse = uploaded_file
        # Fila 43: Hashear el contenido binario/texto decodificado en utf-8, jamás el nombre del archivo
        file_bytes = uploaded_file.getvalue()
        raw_source_content = file_bytes.decode("utf-8", errors="replace")
        st.session_state["es_sintetico"] = False
    elif btn_sintetico or st.session_state["es_sintetico"]:
        st.session_state["es_sintetico"] = True
        file_to_parse = default_csv
        raw_source_content = default_csv.read_text(encoding="utf-8") if default_csv.exists() else "synthetic"

    if file_to_parse:
        try:
            grupos_input, demanda_agregada = parse_academic_data(file_to_parse)
            st.success(f"✅ **{len(grupos_input)}** grupos cargados desde archivo.")
        except Exception as e:
            st.sidebar.error(f"❌ Error al procesar archivo: {e}")
            hubo_error_ingesta = True

# Banner claro de datos sintéticos (Fila 33)
if st.session_state.get("es_sintetico", False):
    st.warning("⚠️ **MODO DEMOSTRACIÓN:** Utilizando datos sintéticos de prueba. No representan registros de matrícula real del SAES.")

st.sidebar.header("⚙️ Parámetros de Optimización")

# Slider de Tolerancia de Sobrecupo (tau)
tolerancia_tau = st.sidebar.slider(
    "Tolerancia de Sobrecupo (τ)",
    min_value=0,
    max_value=5,
    value=2,
    step=1,
    help="Cupo blando (ADR-0002): margen de alumnos absorbibles antes de abrir un nuevo grupo (capacidad efectiva = cupo + τ).",
)

# Forzar cupo uniforme global (override)
forzar_cupo = st.sidebar.checkbox(
    "Forzar cupo uniforme global",
    value=False,
    help="Si está desactivado, el motor utiliza automáticamente el cupo modal de cada materia. Si se activa, manda el slider siguiente.",
)

override_cupo_val = None
if forzar_cupo:
    override_cupo_val = st.sidebar.slider(
        "Cupo Uniforme Global Objetivo",
        min_value=20,
        max_value=45,
        value=35,
        step=1,
    )

# Selector numérico editable de horas semanales frente a grupo
horas_por_materia = st.sidebar.number_input(
    "Horas semanales frente a grupo por materia",
    min_value=1,
    max_value=10,
    value=4,
    step=1,
    help="Horas docentes asignadas por cada grupo activo frente a grupo.",
)

# Filtro de turno con soporte Turno.X
filtro_turno = st.sidebar.selectbox(
    "Filtro de Turno",
    options=["Todos", "Matutino (M)", "Vespertino (V)", "Mixto / Admin (X)"],
    index=0,
)

# Expander de Glosario e Interpretación (Fila 4)
with st.expander("📖 ¿Cómo interpretar este informe?", expanded=False):
    st.markdown("""
    - **Matrícula Observada:** Alumnos registrados o con cupo agotado en SAES (no sustituye encuestas de demanda no atendida).
    - **Tolerancia tau (τ) / Cupo Blando:** Excedente de sobrecupo admisible por grupo antes de justificar la apertura de una nueva aula.
    - **Grupos Zombi:** Grupos con matrícula nula o mínima (≤ 0.6 del cupo modal) que ameritan consolidación.
    - **Macro-grupos Administrativos (Turno X):** Grupos de Trabajo Terminal (250+ cupos) protegidos de partición física en aulas.
    - **Acciones:**
      * **CONSERVAR:** El grupo se mantiene operativo con su cupo asignado.
      * **ABRIR:** Se requiere aperturar un grupo nuevo por exceso de matrícula observada.
      * **CERRAR / CONSOLIDAR:** Grupo excedentario sugerido para reubicación docente.
    """)

# 3. Pipeline de Procesamiento
if grupos_input and not hubo_error_ingesta:
    claves_unicas = sorted(list(demanda_agregada.keys()), key=lambda x: (x[0], x[1].value))
    resumenes_iniciales: List[ResumenMateria] = []

    for materia, turno in claves_unicas:
        demanda = demanda_agregada[(materia, turno)]
        resumen = optimizar_materia_turno(
            materia=materia,
            turno=turno,
            demanda=demanda,
            grupos_existentes=grupos_input,
            override_cupo=override_cupo_val,
            tolerancia=tolerancia_tau,
        )
        resumenes_iniciales.append(resumen)

    total_grupos_actuales = sum(r.grupos_actuales for r in resumenes_iniciales)

    # Techo Presupuestal Global
    habilitar_techo = st.sidebar.checkbox(
        "Habilitar Techo Presupuestal Global",
        value=False,
        help="Limita el total máximo de grupos a ofertar aplicando algoritmo greedy por menor saturación.",
    )

    resumenes_finales = resumenes_iniciales
    if habilitar_techo:
        max_grupos_global = st.sidebar.slider(
            "Máximo de Grupos Permitidos",
            min_value=1,
            max_value=max(1, total_grupos_actuales * 2),
            value=max(1, total_grupos_actuales),
            step=1,
        )
        resumenes_finales = aplicar_techo_global(resumenes_iniciales, max_grupos_global)

    # Filtrar según selección de turno
    if filtro_turno == "Matutino (M)":
        resumenes_mostrados = [r for r in resumenes_finales if r.turno == Turno.M]
    elif filtro_turno == "Vespertino (V)":
        resumenes_mostrados = [r for r in resumenes_finales if r.turno == Turno.V]
    elif filtro_turno == "Mixto / Admin (X)":
        resumenes_mostrados = [r for r in resumenes_finales if r.turno == Turno.X]
    else:
        resumenes_mostrados = resumenes_finales

    # 4. Sección de Métricas Clave (KPIs superiores con semántica de negocio) (Filas 1 y 24)
    kpi_grupos_act = sum(r.grupos_actuales for r in resumenes_mostrados)
    kpi_grupos_prop = sum(r.grupos_propuestos for r in resumenes_mostrados)
    kpi_delta = kpi_grupos_prop - kpi_grupos_act
    kpi_demanda_total = sum(r.demanda_total for r in resumenes_mostrados)
    kpi_alumnos_atendidos = sum(
        sum(g.inscritos_estimados for g in r.grupos if g.accion != AccionGrupo.CERRAR)
        for r in resumenes_mostrados
    )
    kpi_horas_docentes = kpi_grupos_prop * int(horas_por_materia)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Grupos Actuales (SAES)", kpi_grupos_act)
    col2.metric("Grupos Propuestos", kpi_grupos_prop)
    # Fila 1: delta_color="inverse" (más grupos es costo presupuestal; menos grupos es optimización)
    col3.metric(
        "Grupos a Abrir (+) / Cerrar (−)",
        f"{kpi_delta:+d}",
        delta=kpi_delta,
        delta_color="inverse",
    )
    # Fila 24: Matrícula Observada
    col4.metric(
        "Alumnos Atendidos",
        f"{kpi_alumnos_atendidos} / {kpi_demanda_total}",
        f"{(kpi_alumnos_atendidos / kpi_demanda_total * 100):.1f}%" if kpi_demanda_total > 0 else "0%",
        help="Proporción de alumnos cubiertos respecto a la matrícula observada.",
    )
    col5.metric(
        "Horas Docentes Requeridas",
        f"{kpi_horas_docentes} hrs/sem",
        help=f"Calculado como {kpi_grupos_prop} grupos propuestos × {horas_por_materia} hrs/materia",
    )

    # Alerta de discrepancias del SAES si aplica
    alertas_saes_list = []
    if not df_clipboard_raw.empty and "discrepancia_saes" in df_clipboard_raw.columns:
        discrepancias = df_clipboard_raw[df_clipboard_raw["discrepancia_saes"] == True]
        if not discrepancias.empty:
            alertas_saes_list = discrepancias.to_dict(orient="records")
            with st.expander(f"⚠️ Alerta: Se detectaron {len(discrepancias)} inconsistencias en datos SAES (cupo - inscritos ≠ disponibles)", expanded=False):
                st.caption("Estas discrepancias suelen ocurrir por bajas no consolidadas o sobrecupos no autorizados en el SAES.")
                st.dataframe(
                    discrepancias[["grupo", "materia_id", "nombre_materia", "cupo", "inscritos", "disponibles"]],
                    use_container_width=True,
                    hide_index=True,
                )

    # 4.1 Generación y Botón de Descarga del Informe Técnico Oficial en Excel (Fila 49)
    tz_cdmx = ZoneInfo("America/Mexico_City")
    timestamp_dt = datetime.now(tz_cdmx)
    timestamp_str = timestamp_dt.strftime("%Y%m%d_%H%M%S")

    parametros_dictamen = {
        "tolerancia_tau": tolerancia_tau,
        "override_cupo": override_cupo_val,
        "horas_materia": horas_por_materia,
        "timestamp": timestamp_str,
        "git_commit_tag": "v1.2.1-hardened",
    }

    excel_bytes = generar_dictamen_excel(
        raw_input_text=raw_source_content,
        optimizaciones=resumenes_finales,
        grupos_input=grupos_input,
        parametros=parametros_dictamen,
        alertas_saes=alertas_saes_list,
    )

    st.sidebar.divider()
    st.sidebar.subheader("📄 Exportación Oficial")
    st.sidebar.download_button(
        label="📥 Descargar Informe Técnico de Apoyo (.xlsx)",
        data=excel_bytes,
        file_name=f"Informe_Tecnico_RACO_ESCOM_{timestamp_str}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    st.write("")

    # 5. Pestañas de Visualización (Fila 24: Semántica de Matrícula Observada)
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Resumen Directivo",
        "📋 Detalle Operativo por Grupo",
        "⚠️ Diagnóstico de Sobrecupo y Cierres",
        "🚦 Semáforo de Tiras",
    ])

    # Pestaña 1: Resumen Directivo
    with tab1:
        st.subheader("Consolidado por Materia y Turno")
        filas_resumen = []
        for r in resumenes_mostrados:
            filas_resumen.append({
                "Materia": r.materia,
                "Turno": r.turno.value,
                "Matrícula Observada": r.demanda_total,
                "Grupos Act.": r.grupos_actuales,
                "Grupos Prop.": r.grupos_propuestos,
                "Delta": r.delta_grupos,
                "Cupo Promedio": f"{r.cupo_promedio:.1f}",
            })
        df_resumen = pd.DataFrame(filas_resumen)
        st.dataframe(df_resumen, use_container_width=True, hide_index=True)

        st.subheader("Comparativa de Grupos: Actuales vs Propuestos")
        if not df_resumen.empty:
            chart_data = df_resumen.copy()
            chart_data["Materia-Turno"] = chart_data["Materia"] + " (" + chart_data["Turno"] + ")"
            chart_df = chart_data.set_index("Materia-Turno")[["Grupos Act.", "Grupos Prop."]]
            st.bar_chart(chart_df, height=350)

    # Pestaña 2: Detalle Operativo por Grupo
    with tab2:
        st.subheader("Oferta Detallada por Grupo")
        filas_detalle = []
        for r in resumenes_mostrados:
            for g in r.grupos:
                filas_detalle.append({
                    "Materia": g.materia,
                    "Turno": g.turno.value,
                    "Grupo ID": g.grupo_id,
                    "Acción": g.accion.value,
                    "Inscritos Estimados": g.inscritos_estimados,
                    "Cupo Asignado": g.cupo_asignado,
                    "Atípico / Protegido": "Sí" if g.es_atipico else "No",
                    "Justificación": g.justificacion,
                })
        df_detalle = pd.DataFrame(filas_detalle)

        def highlight_accion(val):
            if val == "CONSERVAR":
                return "background-color: #d1e7dd; color: #0f5132; font-weight: bold;"
            elif val == "ABRIR":
                return "background-color: #cfe2ff; color: #084298; font-weight: bold;"
            elif val == "CERRAR":
                return "background-color: #f8d7da; color: #842029; font-weight: bold;"
            return ""

        if not df_detalle.empty:
            styled_df = df_detalle.style.map(highlight_accion, subset=["Acción"])
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.info("No hay grupos para mostrar con el filtro seleccionado.")

    # Pestaña 3: Diagnóstico de Sobrecupo y Cierres
    with tab3:
        st.subheader("Diagnóstico de Capacidad y Quiebre")
        col_izq, col_der = st.columns(2)

        with col_izq:
            st.markdown("#### 🚨 Materias con Sobrecupo (Requieren Nuevos Grupos)")
            sobresaturadas = [r for r in resumenes_mostrados if r.delta_grupos > 0]
            if sobresaturadas:
                for s in sobresaturadas:
                    st.warning(
                        f"**{s.materia} [{s.turno.value}]**: Matrícula de **{s.demanda_total}** alumnos "
                        f"excede la capacidad absorbible de los {s.grupos_actuales} grupos actuales. "
                        f"Se sugiere abrir **{s.delta_grupos}** nuevo(s) grupo(s)."
                    )
            else:
                st.success("No hay materias que requieran apertura de nuevos grupos con la configuración actual.")

        with col_der:
            st.markdown("#### 📉 Materias Subutilizadas (Candidatas a Consolidación / Cierre)")
            subutilizadas = [r for r in resumenes_mostrados if r.delta_grupos < 0]
            if subutilizadas:
                for u in subutilizadas:
                    st.info(
                        f"**{u.materia} [{u.turno.value}]**: Matrícula de **{u.demanda_total}** alumnos. "
                        f"Se sugiere consolidar **{abs(u.delta_grupos)}** grupo(s) "
                        f"para optimizar la asignación docente."
                    )
            else:
                st.success("No hay grupos sobrantes para cierre en la selección actual.")

    # Pestaña 4: Semáforo de Tiras
    with tab4:
        st.subheader("🚦 Diagnóstico de Paquetes Curriculares por Semestre y Turno")
        st.caption(
            "Identifica si los alumnos que inscriben un semestre completo en un mismo turno encuentran materias "
            "agotadas o saturadas (disponibles ≤ 0), lo que rompe la tira reglamentaria."
        )

        if not df_clipboard_raw.empty and "semestre" in df_clipboard_raw.columns:
            df_tiras = df_clipboard_raw.copy()
            if filtro_turno == "Matutino (M)":
                df_tiras = df_tiras[df_tiras["turno"] == Turno.M]
            elif filtro_turno == "Vespertino (V)":
                df_tiras = df_tiras[df_tiras["turno"] == Turno.V]
            elif filtro_turno == "Mixto / Admin (X)":
                df_tiras = df_tiras[df_tiras["turno"] == Turno.X]

            semestres_disponibles = sorted(df_tiras["semestre"].unique())

            if semestres_disponibles:
                for sem in semestres_disponibles:
                    df_sem = df_tiras[df_tiras["semestre"] == sem]
                    materias_saturadas = df_sem[df_sem["disponibles"] <= 0]
                    total_materias = len(df_sem)
                    num_bloqueadas = len(materias_saturadas)

                    if num_bloqueadas == 0:
                        status_color = "🟢"
                        mensaje = f"Semestre {sem} completo: Todas las materias tienen cupo disponible."
                        st.success(f"{status_color} **Semestre {sem}**: {mensaje} ({total_materias} grupos evaluados)")
                    elif num_bloqueadas < total_materias:
                        status_color = "🟡"
                        st.warning(
                            f"{status_color} **Semestre {sem} [Tira en Riesgo]**: {num_bloqueadas} de {total_materias} "
                            f"materias tienen cupo agotado (disponibles ≤ 0): {', '.join(materias_saturadas['nombre_materia'].unique())}"
                        )
                    else:
                        status_color = "🔴"
                        st.error(
                            f"{status_color} **Semestre {sem} [Tira Bloqueada]**: Todas las materias ({num_bloqueadas}) "
                            f"están saturadas o con sobrecupo negativo."
                        )
            else:
                st.info("No hay datos de semestre para mostrar con el filtro actual.")
        else:
            filas_tira = []
            for g in grupos_input:
                semestre = g.semestre if g.semestre is not None else (int(g.grupo[0]) if g.grupo and g.grupo[0].isdigit() else 1)
                disponibles_est = g.cupo_max - g.demanda_estimada
                filas_tira.append({
                    "semestre": semestre,
                    "turno": g.turno,
                    "materia": g.materia,
                    "grupo": g.grupo,
                    "disponibles": disponibles_est,
                })
            df_fallback = pd.DataFrame(filas_tira)
            if filtro_turno == "Matutino (M)":
                df_fallback = df_fallback[df_fallback["turno"] == Turno.M]
            elif filtro_turno == "Vespertino (V)":
                df_fallback = df_fallback[df_fallback["turno"] == Turno.V]
            elif filtro_turno == "Mixto / Admin (X)":
                df_fallback = df_fallback[df_fallback["turno"] == Turno.X]

            for sem in sorted(df_fallback["semestre"].unique()):
                df_sem = df_fallback[df_fallback["semestre"] == sem]
                saturadas = df_sem[df_sem["disponibles"] <= 0]
                if len(saturadas) == 0:
                    st.success(f"🟢 **Semestre {sem}**: Tira completa sin quiebre de cupo.")
                else:
                    st.warning(
                        f"🟡 **Semestre {sem} [Tira Comprometida]**: Materias con sobrecupo estimado: "
                        f"{', '.join(saturadas['materia'].unique())}"
                    )
else:
    st.info("Por favor ingresa datos pegados del SAES o carga un archivo para iniciar la optimización.")
